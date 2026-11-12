"""Fail-closed synthetic pre-signing check for a TWO-input sponsor refund.

Research-only. The script under study is Atomic{Buy,Sell}SponsorRefund.sc.
This module never reads a blockchain, verifies signatures, signs or sends txs.
Caller MUST independently authenticate order/sponsor boxes, chain identity,
min-box value and fee proposition using a trusted SYPC validating node.
A PASS here is NOT a valid on-chain transaction or a recovery guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass

from sypc_swap.atomic_reference import AtomicOrder, MAX_I64, SyntheticOutput
from sypc_swap.cancel_preflight import (
    CancellationPlan, CancellationReview, CancelPreflightRejected,
)


@dataclass(frozen=True)
class SponsorBox:
    """Claimed chain UTXO data; creating this value does not verify its origin."""

    box_id: bytes
    owner_proposition: bytes
    native_value: int
    tokens: tuple[tuple[bytes, int], ...] = ()


def _int64(value: object, label: str, minimum: int = 1) -> None:
    if type(value) is not int or not minimum <= value <= MAX_I64:
        raise CancelPreflightRejected(f"{label}: invalid native/token amount")


def _box_id(value: object, label: str) -> None:
    if type(value) is not bytes or len(value) != 32:
        raise CancelPreflightRejected(f"{label}: expected 32-byte box ID")


def _locked_tokens(tokens: object) -> tuple[tuple[bytes, int], ...]:
    if type(tokens) is not tuple:
        raise CancelPreflightRejected("locked tokens must be a tuple")
    ids: set[bytes] = set()
    for token in tokens:
        if type(token) is not tuple or len(token) != 2:
            raise CancelPreflightRejected("malformed locked token")
        token_id, amount = token
        _box_id(token_id, "locked token")
        _int64(amount, "locked token amount")
        if token_id in ids:
            raise CancelPreflightRejected("duplicated locked token ID")
        ids.add(token_id)
    return tokens


def preflight_sponsored_cancel(
    order: AtomicOrder,
    plan: CancellationPlan,
    sponsor: SponsorBox,
    *,
    locked_native: int,
    locked_tokens: tuple[tuple[bytes, int], ...],
    miner_fee_proposition: bytes,
    max_miner_fee: int,
    min_output_native: int,
) -> CancellationReview:
    """Check the exact 2-input, 2-output candidate for sponsor refund.

    This intentionally mirrors the *strict* structure of our research
    ErgoScripts, unlike the more permissive single-input preview.

    Caller-supplied inputs are NOT independently verified; this is defense
    in depth only, not a signature/UTXO/consensus authorization.
    """
    if (type(order) is not AtomicOrder or type(plan) is not CancellationPlan
            or type(sponsor) is not SponsorBox):
        raise CancelPreflightRejected("invalid review object")
    _box_id(order.box_id, "order box")
    _box_id(sponsor.box_id, "sponsor box")
    _int64(locked_native, "locked native")
    _int64(sponsor.native_value, "sponsor native")
    _int64(max_miner_fee, "max miner fee")
    _int64(min_output_native, "minimum native per output")
    _locked_tokens(locked_tokens)

    if sponsor.box_id == order.box_id:
        raise CancelPreflightRejected("sponsor cannot duplicate the order input")
    if (type(sponsor.owner_proposition) is not bytes
            or sponsor.owner_proposition != order.owner_proposition):
        raise CancelPreflightRejected("sponsor must belong to the order owner")
    if type(sponsor.tokens) is not tuple or sponsor.tokens:
        raise CancelPreflightRejected("sponsor must contain native value only")
    if (type(miner_fee_proposition) is not bytes
            or not 1 <= len(miner_fee_proposition) <= 4096
            or miner_fee_proposition == order.owner_proposition):
        raise CancelPreflightRejected("invalid or ambiguous fee proposition")

    if (type(plan.input_ids) is not tuple
            or plan.input_ids != (order.box_id, sponsor.box_id)):
        raise CancelPreflightRejected("expected exactly order then sponsor inputs")
    if (type(plan.outputs) is not tuple or len(plan.outputs) != 2
            or any(type(o) is not SyntheticOutput for o in plan.outputs)):
        raise CancelPreflightRejected("expected exactly owner refund and fee output")

    refund, fee = plan.outputs
    if refund.r4_order_id is not None or fee.r4_order_id is not None:
        raise CancelPreflightRejected("unexpected output registers")
    if refund.proposition != order.owner_proposition:
        raise CancelPreflightRejected("refund redirected away from owner")
    if fee.proposition != miner_fee_proposition or fee.tokens:
        raise CancelPreflightRejected("incorrect miner fee output")
    if refund.tokens != locked_tokens:
        raise CancelPreflightRejected("exact locked token refund required")
    _int64(refund.value, "refund native")
    _int64(fee.value, "fee native")
    if refund.value < min_output_native or fee.value < min_output_native:
        raise CancelPreflightRejected("output below trusted minimum native value")
    if fee.value > max_miner_fee:
        raise CancelPreflightRejected("miner fee exceeds local policy")
    if refund.value < locked_native:
        raise CancelPreflightRejected("sponsor did not preserve locked native value")
    if refund.value + fee.value != locked_native + sponsor.native_value:
        raise CancelPreflightRejected("native value conservation failed")

    return CancellationReview(
        owner_native_returned=refund.value,
        miner_native_fee=fee.value,
        returned_token_types=len(locked_tokens),
        owner_output_count=1,
    )
