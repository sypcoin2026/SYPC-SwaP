"""Strict single-input cancellation preview for the SYPC Swap research lab.

NOT a wallet, signature verifier, node client, UTXO proof, or authorization
to spend funds. This is a deliberately restrictive offline model.

The original Ergo atomic owner-signature branch permits arbitrary outputs.
Therefore the eventual wallet must independently check the ENTIRE proposed
transaction before signing a cancellation. This helper illustrates a safe
minimal transaction shape, rather than changing original contract semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

from sypc_swap.atomic_reference import AtomicOrder, MAX_I64, SyntheticOutput


class CancelPreflightRejected(ValueError):
    """Fail closed when the candidate cancellation is not an exact refund."""


@dataclass(frozen=True)
class CancellationPlan:
    """Synthetic plan only; input_ids are NOT on-chain authenticated here."""

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


def preflight_single_input_cancel(
    order: AtomicOrder,
    plan: CancellationPlan,
    *,
    locked_native: int,
    locked_tokens: tuple[tuple[bytes, int], ...],
    miner_fee_proposition: bytes,
    max_miner_fee: int,
) -> CancellationReview:
    """Accept only a transparent refund from exactly one locked order box.

    All native value and tokens must be accounted for, and every output must
    be either an exact owner-script output or ONE fee-script output.
    Unrelated inputs, external recipients, unknown assets, duplicate token
    identifiers, empty refunds, and fee manipulation are refused.

    Source chain information (including the real UTXO balance and accepted
    miner fee script) still needs independent validation by a real wallet.
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
    if (type(plan.input_ids) is not tuple
            or len(plan.input_ids) != 1
            or type(plan.input_ids[0]) is not bytes
            or plan.input_ids[0] != order.box_id):
        raise CancelPreflightRejected("cancellation must spend exactly the intended order input")
    if (type(plan.outputs) is not tuple
            or not plan.outputs
            or any(type(out) is not SyntheticOutput for out in plan.outputs)):
        raise CancelPreflightRejected("invalid cancellation outputs")
    if type(locked_tokens) is not tuple:
        raise CancelPreflightRejected("locked_tokens must be an immutable tuple")
    expected: dict[bytes, int] = {}
    for token in locked_tokens:
        if type(token) is not tuple or len(token) != 2:
            raise CancelPreflightRejected("malformed locked token tuple")
        token_id, count = token
        if type(token_id) is not bytes or len(token_id) != 32:
            raise CancelPreflightRejected("invalid locked token id")
        _integer(count, "locked token amount", 1)
        if token_id in expected:
            raise CancelPreflightRejected("duplicate locked token id")
        expected[token_id] = count

    paid_native = 0
    fee_native = 0
    fee_count = 0
    owner_count = 0
    returned_tokens: dict[bytes, int] = {}
    for output in plan.outputs:
        # Strict template: no embedded registers, zero outputs or token fee.
        if output.r4_order_id is not None or output.value == 0:
            raise CancelPreflightRejected("unexpected output registers or zero-valued output")
        if output.proposition == order.owner_proposition:
            owner_count += 1
            paid_native += output.value
            tokens_in_box: set[bytes] = set()
            for token_id, amount in output.tokens:
                if token_id in tokens_in_box:
                    raise CancelPreflightRejected("duplicate token id in refund output")
                tokens_in_box.add(token_id)
                if token_id not in expected:
                    raise CancelPreflightRejected("unknown token in refund")
                returned_tokens[token_id] = returned_tokens.get(token_id, 0) + amount
        elif output.proposition == miner_fee_proposition:
            fee_count += 1
            fee_native += output.value
            if output.tokens:
                raise CancelPreflightRejected("miner fee output must not receive tokens")
        else:
            raise CancelPreflightRejected("third-party output not allowed in cancellation")

    if owner_count == 0 or fee_count != 1:
        raise CancelPreflightRejected("one owner refund and exactly one fee output required")
    if fee_native > max_miner_fee:
        raise CancelPreflightRejected("miner fee exceeds local maximum")
    if returned_tokens != expected:
        raise CancelPreflightRejected("token conservation failed")
    if paid_native + fee_native != locked_native:
        raise CancelPreflightRejected("native value conservation failed")
    if paid_native < 1:
        raise CancelPreflightRejected("no native owner refund")

    return CancellationReview(
        owner_native_returned=paid_native,
        miner_native_fee=fee_native,
        returned_token_types=len(returned_tokens),
        owner_output_count=owner_count,
    )
