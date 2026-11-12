"""Conservative offline constant-product quote model inspired by Spectrum CFMM.

This is NOT an ErgoScript interpreter or an adapted smart contract. It has
no ability to read a chain, sign a transaction, execute a trade, or move funds.
Every value is an unscaled integer in a hypothetical pair of asset units.

Reference: spectrum-finance/ergo-dex, pinned in upstreams.lock.json,
contracts/amm/cfmm/v1/n2t/Pool.sc (fee denominator 1000).
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_I64 = (1 << 63) - 1
FEE_DENOM = 1000
BPS_DENOM = 10000


def _positive_i64(value: int, label: str) -> None:
    if type(value) is not int or not 1 <= value <= MAX_I64:
        raise ValueError(f"{label} must be an integer between 1 and {MAX_I64}")


@dataclass(frozen=True)
class PoolState:
    """Two strictly positive reserves, plus a fee multiplier / 1000.

    fee_num is NOT a selected protocol fee for SYPC Swap. E.g. 997 represents
    a hypothetical 0.3% fee; real fees remain an open governance decision.
    """

    reserve_x: int
    reserve_y: int
    fee_num: int

    def __post_init__(self) -> None:
        _positive_i64(self.reserve_x, "reserve_x")
        _positive_i64(self.reserve_y, "reserve_y")
        if type(self.fee_num) is not int or not 1 <= self.fee_num <= FEE_DENOM:
            raise ValueError("fee_num must be an integer in [1, 1000]")


@dataclass(frozen=True)
class Quote:
    """Pure arithmetic projection; NOT a real or guaranteed market quote."""

    asset_in: str
    amount_in: int
    amount_out: int
    minimum_out: int
    slippage_bps: int
    next_state: PoolState


def quote_exact_in(pool: PoolState, asset_in: str, amount_in: int, *, slippage_bps: int = 0) -> Quote:
    """Return an integer quote consistent with the reference CFMM inequality.

    If x is the incoming asset, maximum outgoing y is:
        floor(y * dx * fee_num / (x * 1000 + dx * fee_num)).
    Round DOWN to avoid granting the taker more than the reserve inequality
    permits. Reject zero/dust quotes rather than silently reporting success.
    """
    if not isinstance(pool, PoolState):
        raise TypeError("pool must be PoolState")
    if asset_in not in ("x", "y"):
        raise ValueError("asset_in must be 'x' or 'y'")
    _positive_i64(amount_in, "amount_in")
    if type(slippage_bps) is not int or not 0 <= slippage_bps < BPS_DENOM:
        raise ValueError("slippage_bps must be an integer in [0, 9999]")

    reserve_in, reserve_out = ((pool.reserve_x, pool.reserve_y) if asset_in == "x"
                               else (pool.reserve_y, pool.reserve_x))
    if amount_in > MAX_I64 - reserve_in:
        raise ValueError("incoming reserve would exceed signed int64")

    numerator = reserve_out * amount_in * pool.fee_num
    denominator = reserve_in * FEE_DENOM + amount_in * pool.fee_num
    amount_out = numerator // denominator
    if not 1 <= amount_out < reserve_out:
        raise ValueError("trade yields zero or invalid output")

    minimum_out = max(1, amount_out * (BPS_DENOM - slippage_bps) // BPS_DENOM)
    new_in, new_out = reserve_in + amount_in, reserve_out - amount_out
    if asset_in == "x":
        next_state = PoolState(new_in, new_out, pool.fee_num)
    else:
        next_state = PoolState(new_out, new_in, pool.fee_num)
    if next_state.reserve_x * next_state.reserve_y < pool.reserve_x * pool.reserve_y:
        raise ArithmeticError("constant-product invariant unexpectedly decreased")
    return Quote(asset_in, amount_in, amount_out, minimum_out, slippage_bps, next_state)
