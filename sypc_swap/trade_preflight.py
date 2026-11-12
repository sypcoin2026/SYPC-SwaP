"""Strict, offline, fail-closed swap intent preflight for SYPC Swap research.

NO transactions are built, signed, broadcast, or executed by this module.
Every trust anchor MUST come from an independently verified wallet/node.
This does not check signatures, UTXO unspentness, ErgoScript, or consensus.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

MAX_I64 = (1 << 63) - 1
FEE_DENOM = 1000
BPS_DENOM = 10000
NATIVE_ASSET = "SYPC_NATIVE"  # Intent marker, NOT a consensus identifier.
_HEX256 = re.compile(r"[0-9a-f]{64}\Z")


class PreflightRejected(ValueError):
    """No transaction may proceed when the offline preflight rejects it."""


def _hash_id(value: object, name: str) -> None:
    if type(value) is not str or _HEX256.fullmatch(value) is None:
        raise PreflightRejected(f"{name}: must be a lowercase 32-byte hex identifier")


def _asset_id(value: object, name: str) -> None:
    # Exact type matters: arbitrary __eq__ must not impersonate native SYPC.
    if type(value) is not str:
        raise PreflightRejected(f"{name}: expected a plain string asset ID")
    if value != NATIVE_ASSET:
        _hash_id(value, name)


def _int_range(value: object, name: str, low: int, high: int) -> None:
    if type(value) is not int or not low <= value <= high:
        raise PreflightRejected(f"{name}: outside allowed integer range")


@dataclass(frozen=True)
class VerifiedContext:
    """Trusted input supplied by a separate, independent verification layer.

    Supplying arbitrary data here does NOT magically verify its provenance.
    The referenced chain tip must be checked against a locally verified node.
    """

    genesis_id: str
    tip_id: str
    tip_height: int
    verified_pool_box_id: str


@dataclass(frozen=True)
class TradePolicy:
    """Locally pinned allowlist (never fetched from a price/indexer endpoint)."""

    genesis_id: str
    contract_hash: str
    pool_nft_id: str
    asset_x: str
    asset_y: str
    recipient_script_hash: str
    fee_num: int
    max_miner_fee: int
    max_slippage_bps: int = 100
    max_ttl_blocks: int = 20


@dataclass(frozen=True)
class PoolSnapshot:
    """Untrusted proposal that must be authenticated against chain state."""

    genesis_id: str
    contract_hash: str
    pool_nft_id: str
    pool_box_id: str
    tip_id: str
    tip_height: int
    asset_x: str
    asset_y: str
    reserve_x: int
    reserve_y: int
    fee_num: int


@dataclass(frozen=True)
class TradeIntent:
    """An immutable offline request, not a signed or executable transaction."""

    genesis_id: str
    contract_hash: str
    pool_nft_id: str
    pool_box_id: str
    tip_id: str
    tip_height: int
    asset_in: str
    asset_out: str
    recipient_script_hash: str
    amount_in: int
    minimum_out: int
    slippage_bps: int
    max_miner_fee: int
    valid_until_height: int


@dataclass(frozen=True)
class PreflightResult:
    """Validation result for display only, never authorization to sign."""

    theoretical_amount_out: int
    minimum_out: int
    intent_sha256: str


def _quote_amount(reserve_in: int, reserve_out: int, amount_in: int, fee_num: int) -> int:
    # Python big integers for intermediate math. On-chain numeric semantics
    # MUST be checked separately before any production implementation.
    numerator = reserve_out * amount_in * fee_num
    denominator = reserve_in * FEE_DENOM + amount_in * fee_num
    return numerator // denominator


def preflight_trade(
    intent: TradeIntent,
    pool: PoolSnapshot,
    policy: TradePolicy,
    trusted: VerifiedContext,
) -> PreflightResult:
    """Reject wrong-chain, wrong-pool, stale, malformed or too-permissive intents.

    This is an offline *defense in depth* aid. It does not authenticate pool
    contents, a live UTXO, network provenance, or the contents of a tx to sign.
    The eventual wallet MUST independently verify those properties and the
    exact transaction outputs immediately before signing.
    """
    if type(intent) is not TradeIntent or type(pool) is not PoolSnapshot:
        raise PreflightRejected("invalid intent or pool type")
    if type(policy) is not TradePolicy or type(trusted) is not VerifiedContext:
        raise PreflightRejected("invalid policy or trust context")

    for name, value in (
        ("policy.genesis_id", policy.genesis_id),
        ("policy.contract_hash", policy.contract_hash),
        ("policy.pool_nft_id", policy.pool_nft_id),
        ("policy.recipient_script_hash", policy.recipient_script_hash),
        ("trusted.genesis_id", trusted.genesis_id),
        ("trusted.tip_id", trusted.tip_id),
        ("trusted.verified_pool_box_id", trusted.verified_pool_box_id),
        ("pool.genesis_id", pool.genesis_id),
        ("pool.contract_hash", pool.contract_hash),
        ("pool.pool_nft_id", pool.pool_nft_id),
        ("pool.pool_box_id", pool.pool_box_id),
        ("pool.tip_id", pool.tip_id),
        ("intent.genesis_id", intent.genesis_id),
        ("intent.contract_hash", intent.contract_hash),
        ("intent.pool_nft_id", intent.pool_nft_id),
        ("intent.pool_box_id", intent.pool_box_id),
        ("intent.tip_id", intent.tip_id),
        ("intent.recipient_script_hash", intent.recipient_script_hash),
    ):
        _hash_id(value, name)
    for name, value in (
        ("policy.asset_x", policy.asset_x), ("policy.asset_y", policy.asset_y),
        ("pool.asset_x", pool.asset_x), ("pool.asset_y", pool.asset_y),
        ("intent.asset_in", intent.asset_in), ("intent.asset_out", intent.asset_out),
    ):
        _asset_id(value, name)
    if (policy.asset_x == policy.asset_y or pool.asset_x == pool.asset_y
            or intent.asset_in == intent.asset_out):
        raise PreflightRejected("same-asset swap is prohibited")
    for name, value in (
        ("pool.reserve_x", pool.reserve_x), ("pool.reserve_y", pool.reserve_y),
        ("intent.amount_in", intent.amount_in), ("intent.minimum_out", intent.minimum_out),
        ("intent.max_miner_fee", intent.max_miner_fee), ("policy.max_miner_fee", policy.max_miner_fee),
    ):
        _int_range(value, name, 1, MAX_I64)
    for name, value in (("pool.fee_num", pool.fee_num), ("policy.fee_num", policy.fee_num)):
        _int_range(value, name, 1, FEE_DENOM)
    _int_range(policy.max_slippage_bps, "policy.max_slippage_bps", 0, 5000)
    _int_range(intent.slippage_bps, "intent.slippage_bps", 0, BPS_DENOM - 1)
    _int_range(policy.max_ttl_blocks, "policy.max_ttl_blocks", 1, 100)
    for name, value in (
        ("trusted.tip_height", trusted.tip_height),
        ("pool.tip_height", pool.tip_height),
        ("intent.tip_height", intent.tip_height),
        ("intent.valid_until_height", intent.valid_until_height),
    ):
        _int_range(value, name, 1, MAX_I64)

    if (policy.genesis_id != trusted.genesis_id
            or policy.genesis_id != pool.genesis_id
            or policy.genesis_id != intent.genesis_id):
        raise PreflightRejected("chain/genesis mismatch")
    if (pool.contract_hash != policy.contract_hash
            or intent.contract_hash != policy.contract_hash):
        raise PreflightRejected("contract script hash mismatch")
    if (pool.pool_nft_id != policy.pool_nft_id
            or intent.pool_nft_id != policy.pool_nft_id):
        raise PreflightRejected("pool NFT mismatch")
    if intent.recipient_script_hash != policy.recipient_script_hash:
        raise PreflightRejected("recipient script mismatch")
    if pool.fee_num != policy.fee_num:
        raise PreflightRejected("unexpected pool fee")
    if (pool.tip_height != trusted.tip_height
            or intent.tip_height != trusted.tip_height
            or pool.tip_id != trusted.tip_id
            or intent.tip_id != trusted.tip_id):
        raise PreflightRejected("stale/foreign tip; refresh from locally verified node")
    if (intent.pool_box_id != pool.pool_box_id
            or pool.pool_box_id != trusted.verified_pool_box_id):
        raise PreflightRejected("pool UTXO mismatch")
    if (pool.asset_x, pool.asset_y) != (policy.asset_x, policy.asset_y):
        raise PreflightRejected("pool asset allowlist mismatch")
    if not (trusted.tip_height < intent.valid_until_height
            <= trusted.tip_height + policy.max_ttl_blocks):
        raise PreflightRejected("expired or overly long transaction validity")
    if intent.max_miner_fee > policy.max_miner_fee:
        raise PreflightRejected("miner fee exceeds local policy")
    if intent.slippage_bps > policy.max_slippage_bps:
        raise PreflightRejected("slippage exceeds local policy")
    if (intent.asset_in, intent.asset_out) == (pool.asset_x, pool.asset_y):
        reserve_in, reserve_out = pool.reserve_x, pool.reserve_y
    elif (intent.asset_in, intent.asset_out) == (pool.asset_y, pool.asset_x):
        reserve_in, reserve_out = pool.reserve_y, pool.reserve_x
    else:
        raise PreflightRejected("asset pair does not match pool")
    if intent.amount_in > MAX_I64 - reserve_in:
        raise PreflightRejected("pool incoming reserve would overflow int64")
    theoretical_out = _quote_amount(reserve_in, reserve_out, intent.amount_in, pool.fee_num)
    if not (1 <= theoretical_out < reserve_out):
        raise PreflightRejected("zero or invalid theoretical output")
    lower_bound = max(1, theoretical_out * (BPS_DENOM - intent.slippage_bps) // BPS_DENOM)
    if not (lower_bound <= intent.minimum_out <= theoretical_out):
        raise PreflightRejected("minimum_out violates quote/slippage policy")

    # A stable commitment for offline review. Hashing does NOT produce a
    # signature, prove authenticity or enforce an ErgoScript spend condition.
    canonical = json.dumps(
        {"type": "SYPC_SWAP_OFFLINE_INTENT_V1", **asdict(intent)},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")
    return PreflightResult(
        theoretical_amount_out=theoretical_out,
        minimum_out=intent.minimum_out,
        intent_sha256=hashlib.sha256(canonical).hexdigest(),
    )
