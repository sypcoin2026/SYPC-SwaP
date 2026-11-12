"""Adversarial offline cancellation preflight tests; not real transactions."""

from dataclasses import replace
import unittest

from sypc_swap.atomic_reference import AtomicOrder, Side, SyntheticOutput, wallet_cancel_refund_preflight
from sypc_swap.cancel_preflight import (
    CancellationPlan, CancelPreflightRejected, preflight_single_input_cancel,
)

ID = b"a" * 32
OTHER_ID = b"b" * 32
TOKEN = b"c" * 32
EXTRA_TOKEN = b"d" * 32
OWNER = b"owner-script"
FEE = b"miner-fee-script"
ATTACKER = b"attacker-script"


def order():
    return AtomicOrder(Side.SELL_TOKEN, ID, OWNER, minimum_native_value=300)


def good_plan():
    return CancellationPlan(
        (ID,),
        (
            SyntheticOutput(OWNER, 975, ((TOKEN, 20),)),
            SyntheticOutput(FEE, 25),
        ),
    )


def check(plan=None, *, locked_native=1000, locked_tokens=((TOKEN, 20),),
          max_miner_fee=30, fee_script=FEE):
    return preflight_single_input_cancel(
        order(), good_plan() if plan is None else plan,
        locked_native=locked_native, locked_tokens=locked_tokens,
        miner_fee_proposition=fee_script, max_miner_fee=max_miner_fee,
    )


class StrictCancellationTests(unittest.TestCase):
    def test_normal_refund_and_fee(self):
        result = check()
        self.assertEqual(result.owner_native_returned, 975)
        self.assertEqual(result.miner_native_fee, 25)
        self.assertEqual(result.returned_token_types, 1)

    def test_split_owner_outputs_preserve_assets(self):
        plan = CancellationPlan(
            (ID,),
            (
                SyntheticOutput(OWNER, 400, ((TOKEN, 12),)),
                SyntheticOutput(OWNER, 575, ((TOKEN, 8),)),
                SyntheticOutput(FEE, 25),
            ),
        )
        self.assertEqual(check(plan).owner_output_count, 2)

    def test_reject_multiple_inputs_even_if_owner_receives_enough(self):
        # The older output-only helper cannot observe extra funding inputs.
        deceptive = CancellationPlan((ID, OTHER_ID), good_plan().outputs)
        self.assertTrue(wallet_cancel_refund_preflight(
            order(), deceptive.outputs,
            locked_native=1000, locked_tokens=((TOKEN, 20),), max_native_fee=30
        ))
        with self.assertRaisesRegex(CancelPreflightRejected, "exactly"):
            check(deceptive)

    def test_reject_different_order_input(self):
        with self.assertRaisesRegex(CancelPreflightRejected, "intended order"):
            check(replace(good_plan(), input_ids=(OTHER_ID,)))

    def test_reject_invalid_input_collection(self):
        with self.assertRaises(CancelPreflightRejected):
            check(replace(good_plan(), input_ids=[ID]))

    def test_reject_wrong_recipient_with_correct_total(self):
        forged = CancellationPlan(
            (ID,),
            (SyntheticOutput(ATTACKER, 400), SyntheticOutput(OWNER, 575, ((TOKEN, 20),)),
             SyntheticOutput(FEE, 25)),
        )
        with self.assertRaisesRegex(CancelPreflightRejected, "third-party"):
            check(forged)

    def test_reject_missing_native_balance(self):
        altered = replace(good_plan(), outputs=(
            SyntheticOutput(OWNER, 974, ((TOKEN, 20),)), SyntheticOutput(FEE, 25)
        ))
        with self.assertRaisesRegex(CancelPreflightRejected, "native"):
            check(altered)

    def test_reject_miner_fee_too_high(self):
        altered = replace(good_plan(), outputs=(
            SyntheticOutput(OWNER, 960, ((TOKEN, 20),)), SyntheticOutput(FEE, 40)
        ))
        with self.assertRaisesRegex(CancelPreflightRejected, "fee"):
            check(altered)

    def test_reject_ambiguous_multiple_fee_outputs(self):
        altered = replace(good_plan(), outputs=(
            SyntheticOutput(OWNER, 975, ((TOKEN, 20),)),
            SyntheticOutput(FEE, 10), SyntheticOutput(FEE, 15)
        ))
        with self.assertRaisesRegex(CancelPreflightRejected, "exactly one fee"):
            check(altered)

    def test_reject_fee_recipient_holding_tokens(self):
        altered = replace(good_plan(), outputs=(
            SyntheticOutput(OWNER, 975, ((TOKEN, 19),)),
            SyntheticOutput(FEE, 25, ((TOKEN, 1),)),
        ))
        with self.assertRaisesRegex(CancelPreflightRejected, "must not receive tokens"):
            check(altered)

    def test_reject_token_theft(self):
        altered = replace(good_plan(), outputs=(
            SyntheticOutput(OWNER, 975, ((TOKEN, 19),)),
            SyntheticOutput(FEE, 25),
        ))
        with self.assertRaisesRegex(CancelPreflightRejected, "token conservation"):
            check(altered)

    def test_reject_unexpected_token(self):
        altered = replace(good_plan(), outputs=(
            SyntheticOutput(OWNER, 975, ((TOKEN, 20), (EXTRA_TOKEN, 1))),
            SyntheticOutput(FEE, 25),
        ))
        with self.assertRaisesRegex(CancelPreflightRejected, "unknown"):
            check(altered)

    def test_reject_fee_script_equal_to_owner_script(self):
        with self.assertRaisesRegex(CancelPreflightRejected, "distinct"):
            check(fee_script=OWNER)

    def test_reject_duplicate_locked_token_id(self):
        with self.assertRaisesRegex(CancelPreflightRejected, "duplicate"):
            check(locked_tokens=((TOKEN, 10), (TOKEN, 10)))

    def test_reject_empty_outputs(self):
        with self.assertRaises(CancelPreflightRejected):
            check(CancellationPlan((ID,), ()))

    def test_reject_owner_zero_output(self):
        bad = CancellationPlan((ID,), (
            SyntheticOutput(OWNER, 0, ((TOKEN, 20),)),
            SyntheticOutput(FEE, 25),
        ))
        with self.assertRaisesRegex(CancelPreflightRejected, "zero"):
            check(bad)

    def test_reject_unexpected_register(self):
        bad = CancellationPlan((ID,), (
            SyntheticOutput(OWNER, 975, ((TOKEN, 20),), ID),
            SyntheticOutput(FEE, 25),
        ))
        with self.assertRaisesRegex(CancelPreflightRejected, "registers"):
            check(bad)

    def test_reject_no_fee(self):
        bad = CancellationPlan((ID,), (SyntheticOutput(OWNER, 1000, ((TOKEN, 20),)),))
        with self.assertRaisesRegex(CancelPreflightRejected, "fee"):
            check(bad)

    def test_reject_fee_budget_that_could_consume_all_locked_funds(self):
        with self.assertRaisesRegex(CancelPreflightRejected, "consume"):
            check(max_miner_fee=1000)

    def test_reject_boolean_and_float_monetary_inputs(self):
        for amount in (True, 1000.0, -1, 0):
            with self.subTest(amount=amount), self.assertRaises(CancelPreflightRejected):
                check(locked_native=amount)

    def test_reject_untrusted_fee_id(self):
        for fee in (b"", b"f" * 4097, "miner", True):
            with self.subTest(fee=fee), self.assertRaises(CancelPreflightRejected):
                check(fee_script=fee)

    def test_reject_unknown_locked_token_format(self):
        with self.assertRaises(CancelPreflightRejected):
            check(locked_tokens=((b"short", 20),))
        with self.assertRaises(CancelPreflightRejected):
            check(locked_tokens=[(TOKEN, 20)])

    def test_reject_owner_output_exceeding_locked_value(self):
        bad = CancellationPlan((ID,), (
            SyntheticOutput(OWNER, 985, ((TOKEN, 20),)),
            SyntheticOutput(FEE, 25),
        ))
        with self.assertRaisesRegex(CancelPreflightRejected, "native"):
            check(bad)

    def test_reject_fee_output_with_extra_register(self):
        bad = CancellationPlan((ID,), (
            SyntheticOutput(OWNER, 975, ((TOKEN, 20),)),
            SyntheticOutput(FEE, 25, r4_order_id=ID),
        ))
        with self.assertRaisesRegex(CancelPreflightRejected, "register"):
            check(bad)

    def test_reject_no_owner_refund(self):
        bad = CancellationPlan((ID,), (SyntheticOutput(FEE, 25),))
        with self.assertRaisesRegex(CancelPreflightRejected, "owner"):
            check(bad)


if __name__ == "__main__":
    unittest.main()
