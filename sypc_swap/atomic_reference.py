"""Executable OFFLINE specification of Ergo's 2021 atomic-exchange spend branches.

Based on AssetsAtomicExchange.scala @ 17ed58b39460e5520de56f615936d918603a3b9e
(CC0-1.0, source preserved in third_party/ergo-contracts/).

IMPORTANT:
- This is a synthetic logic model, NOT ErgoScript, cryptographic verification,
  wallet authorization, UTXO validation or a smart contract.
- The boolean owner_approved represents a *verified signature outcome* only
  for the purpose of the model. It MUST NEVER be accepted from a remote API
  as an authorization for actual spending.
- Global transaction conservation and fees are validated by a blockchain,
  not by the original spending script. This module does neither.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

MAX_I64 = (1 << 63) - 1


def _id(value: object, label: str) -> None:
    if type(value) is not bytes or len(value) != 32:
        raise ValueError(f"{label} must be exactly 32 bytes")


def _prop(value: object, label: str) -> None:
    if type(value) is not bytes or not 1 <= len(value) <= 4096:
        raise ValueError(f"{label} must be non-empty proposition bytes")


def _amount(value: object, label: str, minimum: int = 0) -> None:
    if type(value) is not int or not minimum <= value <= MAX_I64:
        raise ValueError(f"{label} must be int in [{minimum}, {MAX_I64}]")


class Side(Enum):
    BUY_TOKEN = "buy-token"
    SELL_TOKEN = "sell-token"


@dataclass(frozen=True)
class SyntheticOutput:
    """In-memory representation of the fields used by original scripts."""

    proposition: bytes
    value: int
    tokens: tuple[tuple[bytes, int], ...] = ()
    r4_order_id: bytes | None = None

    def __post_init__(self) -> None:
        _prop(self.proposition, "output proposition")
        _amount(self.value, "output native value")
        if type(self.tokens) is not tuple:
            raise ValueError("output tokens must be immutable tuple")
        for token in self.tokens:
            if type(token) is not tuple or len(token) != 2:
                raise ValueError("each token must be pair (id, amount)")
            _id(token[0], "output token id")
            _amount(token[1], "output token amount", 1)
        if self.r4_order_id is not None:
            _id(self.r4_order_id, "R4 order id")


@dataclass(frozen=True)
class AtomicOrder:
    """A BUY checks OUTPUTS(0); a SELL checks OUTPUTS(1).

    The original order-spend scripts have fixed output positions, so the
    model deliberately does NOT search for an equivalent output elsewhere.
    """

    side: Side
    box_id: bytes
    owner_proposition: bytes
    token_id: bytes | None = None
    minimum_token_amount: int = 0
    minimum_native_value: int = 0

    def __post_init__(self) -> None:
        if type(self.side) is not Side:
            raise ValueError("invalid order side")
        _id(self.box_id, "order box id")
        _prop(self.owner_proposition, "order owner proposition")
        if self.side is Side.BUY_TOKEN:
            _id(self.token_id, "requested token id")
            _amount(self.minimum_token_amount, "minimum token amount", 1)
            if self.minimum_native_value != 0:
                raise ValueError("buy order must not specify seller native price")
        else:
            if self.token_id is not None or self.minimum_token_amount != 0:
                raise ValueError("sell order has no token-id parameter in this source contract")
            _amount(self.minimum_native_value, "seller native amount", 1)


def original_atomic_predicate(
    order: AtomicOrder, outputs: tuple[SyntheticOutput, ...], owner_approved: bool
) -> bool:
    """Faithful synthetic equivalent of the TWO source contract branches.

    Owner signature in the source bypasses matched-output constraints.
    That is intentional for cancellation, but means the client must verify
    actual refund/change outputs before asking the user to sign.
    """
    if type(order) is not AtomicOrder:
        raise TypeError("order must be AtomicOrder")
    if type(outputs) is not tuple or any(type(out) is not SyntheticOutput for out in outputs):
        raise TypeError("outputs must be tuple[SyntheticOutput, ...]")
    if type(owner_approved) is not bool:
        raise TypeError("owner_approved must be a synthetic bool (not a signature)")
    if owner_approved:
        return True
    if order.side is Side.BUY_TOKEN:
        if not outputs:
            return False
        paid = outputs[0]
        return (
            paid.r4_order_id == order.box_id
            and paid.proposition == order.owner_proposition
            and len(paid.tokens) >= 1
            and paid.tokens[0][0] == order.token_id
            and paid.tokens[0][1] >= order.minimum_token_amount
        )
    if len(outputs) <= 1:
        return False
    paid = outputs[1]
    return (
        paid.r4_order_id == order.box_id
        and paid.proposition == order.owner_proposition
        and paid.value >= order.minimum_native_value
    )
