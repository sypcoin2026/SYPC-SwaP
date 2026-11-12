"""Offline preview for the exact TWO-output single-input refund contracts.

The synthetic policy mirrors Atomic{Buy,Sell}RefundGuard.sc:
order input only; OUTPUTS(0) exact owner refund; OUTPUTS(1) miner fee.
Not an on-chain validity, signature or UTXO proof. Wallets must verify every
real input/output and chain rule independently before signing.
"""

from __future__ import annotations

from dataclasses import dataclass

from sypc_swap.atomic_reference import AtomicOrder, MAX_I64, SyntheticOutput


class CancelPreflightRejected(ValueError):
    """Fail closed when the proposed cancellation does not match the contract."""


@dataclass(frozen=True)
class CancellationPlan:
    """Research-only plan; input IDs and outputs are not chain authenticated."""

    input_ids: tuple[bytes, ...]
    outputs: tuple[SyntheticOutput, ...]


@dataclass(frozen=True)
class CancellationReview:
    owner_native_returned: int
    miner_native_fee: int
    returned_token_types: int
    owner_output_count: int


def _integer(value: object, label: str, minimum: int = 0) -> None:
    if type(value) is not int or not minimum <= value <= MAX_I64:
        raise CancelPreflightRejected(f"{label}: invalid signed-int64 amount")


def _id32(value: object, label: str) -> None:
    if type(value) is not bytes or len(value) != 32:
        raise CancelPreflightRejected(f"{label}: invalid 32-byte identifier")


def _canonical_locked_tokens(tokens: object) -> tuple[tuple[bytes, int], ...]:
    """Shared validation for both refund preflights; preserve token order."""
    if type(tokens) is not tuple:
        raise CancelPreflightRejected("locked tokens must be an immutable tuple")
    seen: set[bytes] = set()
    for item in tokens:
        if type(item) is not tuple or len(item) != 2:
            raise CancelPreflightRejected("malformed locked token tuple")
        token_id, amount = item
        _id32(token_id, "locked token ID")
        _integer(amount, "locked token amount", 1)
        if token_id in seen:
            raise CancelPreflightRejected("duplicate locked token ID")
        seen.add(token_id)
    return tokens


def preflight_single_input_cancel(
    order: AtomicOrder,
    plan: CancellationPlan,
    *,
    locked_native: int,
    locked_tokens: tuple[tuple[bytes, int], ...],
    miner_fee_proposition: bytes,
    max_miner_fee: int,
) -> CancellationReview:
    """Verify that a synthetic plan matches the strict one-input refund shape.

    Inputs must be verified elsewhere. The original legacy atomic contract
    still permits an unrestricted owner-signature spend; this helper alone
    cannot prevent a malicious UI from presenting unsafe bytes for signing.
    """
    if type(order) is not AtomicOrder or type(plan) is not CancellationPlan:
        raise CancelPreflightRejected("invalid order or plan")
    _integer(locked_native, "locked_native", 1)
    _integer(max_miner_fee, "max_miner_fee", 1)
    if max_miner_fee >= locked_native:
        raise CancelPreflightRejected("fee budget would consume locked balance")
    if (type(miner_fee_proposition) is not bytes
            or not 1 <= len(miner_fee_proposition) <= 4096
            or miner_fee_proposition == order.owner_proposition):
        raise CancelPreflightRejected("miner fee script must be trusted and distinct")
    if (type(plan.input_ids) is not tuple or len(plan.input_ids) != 1
            or type(plan.input_ids[0]) is not bytes
            or plan.input_ids[0] != order.box_id):
        raise CancelPreflightRejected("cancellation must spend exactly the intended order input")
    if (type(plan.outputs) is not tuple or len(plan.outputs) != 2
            or any(type(out) is not SyntheticOutput for out in plan.outputs)):
        raise CancelPreflightRejected(
            "expected exactly one owner refund and exactly one fee output"
        )

    expected_tokens = _canonical_locked_tokens(locked_tokens)
    refund, fee = plan.outputs

    if refund.r4_order_id is not None or fee.r4_order_id is not None:
        raise CancelPreflightRejected("unexpected output registers")
    if refund.value == 0 or fee.value == 0:
        raise CancelPreflightRejected("zero-valued output is forbidden")
    if refund.proposition != order.owner_proposition:
        raise CancelPreflightRejected("third-party refund not allowed")
    if fee.proposition != miner_fee_proposition:
        raise CancelPreflightRejected("unexpected miner fee script")
    if fee.tokens:
        raise CancelPreflightRejected("miner fee output must not receive tokens")
    if refund.tokens != expected_tokens:
        # Reject duplicate tokens explicitly, then report substitution or loss.
        _canonical_locked_tokens(refund.tokens)
        allowed = {asset_id for asset_id, _ in expected_tokens}
        if any(asset_id not in allowed for asset_id, _ in refund.tokens):
            raise CancelPreflightRejected("unknown token in refund")
        raise CancelPreflightRejected("token conservation failed")
    if fee.value > max_miner_fee:
        raise CancelPreflightRejected("miner fee exceeds local maximum")
    if refund.value + fee.value != locked_native:
        raise CancelPreflightRejected("native value conservation failed")

    return CancellationReview(
        owner_native_returned=refund.value,
        miner_native_fee=fee.value,
        returned_token_types=len(expected_tokens),
        owner_output_count=1,
    )
