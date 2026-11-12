"""Negative security cases for an OFFLINE sponsored-cancellation model.

These tests are NOT blockchain execution, UTXO proof, or cryptographic signing.
"""

from dataclasses import replace
import random
import unittest

from sypc_swap.atomic_reference import AtomicOrder, Side, SyntheticOutput
from sypc_swap.cancel_preflight import CancellationPlan, CancelPreflightRejected
from sypc_swap.sponsor_cancel_preflight import SponsorBox, preflight_sponsored_cancel

ORDER_ID = b"a" * 32
SPONSOR_ID = b"b" * 32
TOKEN = b"c" * 32
OTHER = b"d" * 32
OWNER = b"owner-script"
FEE_SCRIPT = b"fee-script"
STRANGER = b"stranger-script"
LOCKED_TOKENS = ((TOKEN, 7),)


def fixture(sponsor_native=500, fee=50):
    order = AtomicOrder(Side.SELL_TOKEN, ORDER_ID, OWNER, minimum_native_value=200)
    sponsor = SponsorBox(SPONSOR_ID, OWNER, sponsor_native)
    refund = SyntheticOutput(OWNER, 1000 + sponsor_native - fee, LOCKED_TOKENS)
    fee_output = SyntheticOutput(FEE_SCRIPT, fee)
    return order, sponsor, CancellationPlan(
        (ORDER_ID, SPONSOR_ID), (refund, fee_output),
    )


def check(order=None, sponsor=None, plan=None, **changes):
    a, b, c = fixture()
    kw = dict(
        locked_native=1000, locked_tokens=LOCKED_TOKENS,
        miner_fee_proposition=FEE_SCRIPT, max_miner_fee=100,
        min_output_native=20,
    )
    kw.update(changes)
    return preflight_sponsored_cancel(
        a if order is None else order,
        c if plan is None else plan,
        b if sponsor is None else sponsor,
        **kw,
    )


class SponsoredCancelPreflightTests(unittest.TestCase):
    def test_valid_two_input_cancel(self):
        result = check()
        self.assertEqual(result.owner_native_returned, 1450)
        self.assertEqual(result.miner_native_fee, 50)
        self.assertEqual(result.returned_token_types, 1)
        self.assertEqual(result.owner_output_count, 1)

    def test_absent_or_swapped_inputs_fail_closed(self):
        a, b, c = fixture()
        for bad in ((ORDER_ID,), (SPONSOR_ID, ORDER_ID),
                    (ORDER_ID, SPONSOR_ID, OTHER),
                    (ORDER_ID, ORDER_ID), [ORDER_ID, SPONSOR_ID]):
            with self.subTest(input_ids=bad), self.assertRaises(CancelPreflightRejected):
                check(plan=replace(c, input_ids=bad))

    def test_duplicate_sponsor_input_rejected(self):
        a, b, c = fixture()
        with self.assertRaisesRegex(CancelPreflightRejected, "duplicate"):
            check(sponsor=replace(b, box_id=ORDER_ID))

    def test_foreign_or_invalid_sponsor_rejected(self):
        a, b, c = fixture()
        for bad in (STRANGER, b"", "owner-script"):
            with self.subTest(owner=bad), self.assertRaises(CancelPreflightRejected):
                check(sponsor=replace(b, owner_proposition=bad))
        with self.assertRaisesRegex(CancelPreflightRejected, "native value only"):
            check(sponsor=replace(b, tokens=((TOKEN, 1),)))
        with self.assertRaises(CancelPreflightRejected):
            check(sponsor=replace(b, tokens=[]))

    def test_wrong_or_malformed_sponsor_value_rejected(self):
        a, b, c = fixture()
        for bad in (0, -1, True, 500.0, "500"):
            with self.subTest(value=bad), self.assertRaises(CancelPreflightRejected):
                check(sponsor=replace(b, native_value=bad))
        with self.assertRaises(CancelPreflightRejected):
            check(sponsor=replace(b, box_id=b"short"))

    def test_refund_cannot_be_redirected(self):
        a, b, c = fixture()
        hijacked = SyntheticOutput(STRANGER, 1450, LOCKED_TOKENS)
        with self.assertRaisesRegex(CancelPreflightRejected, "redirect"):
            check(plan=replace(c, outputs=(hijacked, c.outputs[1])))

    def test_refund_tokens_are_exact_and_in_order(self):
        a, b, c = fixture()
        for tokens in ((), ((TOKEN, 6),), ((OTHER, 7),),
                       ((TOKEN, 7), (OTHER, 1))):
            with self.subTest(tokens=tokens), self.assertRaises(CancelPreflightRejected):
                check(plan=replace(c, outputs=(
                    SyntheticOutput(OWNER, 1450, tokens), c.outputs[1],
                )))
        # The contract enforces exact (positional) equality, not just sums.
        two = ((TOKEN, 7), (OTHER, 2))
        a, b, c = fixture()
        altered = SyntheticOutput(OWNER, 1450, tuple(reversed(two)))
        with self.assertRaises(CancelPreflightRejected):
            check(plan=replace(c, outputs=(altered, c.outputs[1])),
                  locked_tokens=two)

    def test_wrong_fee_script_or_fee_tokens_rejected(self):
        a, b, c = fixture()
        for bad in (SyntheticOutput(STRANGER, 50),
                    SyntheticOutput(FEE_SCRIPT, 50, ((OTHER, 1),))):
            with self.subTest(fee=bad), self.assertRaises(CancelPreflightRejected):
                check(plan=replace(c, outputs=(c.outputs[0], bad)))
        with self.assertRaisesRegex(CancelPreflightRejected, "fee proposition"):
            check(miner_fee_proposition=OWNER)

    def test_overlong_or_spoofed_outputs_rejected(self):
        a, b, c = fixture()
        for bad in ((), (c.outputs[0],), c.outputs + (SyntheticOutput(OWNER, 10),),
                    tuple(reversed(c.outputs))):
            with self.subTest(outputs=bad), self.assertRaises(CancelPreflightRejected):
                check(plan=replace(c, outputs=bad))
        with self.assertRaisesRegex(CancelPreflightRejected, "registers"):
            check(plan=replace(c, outputs=(
                SyntheticOutput(OWNER, 1450, LOCKED_TOKENS, ORDER_ID),
                c.outputs[1],
            )))

    def test_fee_cap_and_output_floor_are_enforced(self):
        a, b, c = fixture()
        with self.assertRaisesRegex(CancelPreflightRejected, "fee exceeds"):
            check(max_miner_fee=40)
        with self.assertRaisesRegex(CancelPreflightRejected, "minimum"):
            check(min_output_native=60)
        with self.assertRaises(CancelPreflightRejected):
            check(min_output_native=0)

    def test_no_native_value_can_be_siphoned_or_created(self):
        a, b, c = fixture()
        for value in (1449, 1451):
            with self.subTest(value=value), self.assertRaisesRegex(
                CancelPreflightRejected, "conservation"):
                check(plan=replace(c, outputs=(
                    SyntheticOutput(OWNER, value, LOCKED_TOKENS), c.outputs[1]
                )))
        # The order's own 1,000 native units must not pay the sponsor's fee.
        low_sponsor = SponsorBox(SPONSOR_ID, OWNER, 10)
        low_refund = SyntheticOutput(OWNER, 960, LOCKED_TOKENS)
        with self.assertRaisesRegex(CancelPreflightRejected, "preserve"):
            check(sponsor=low_sponsor, plan=CancellationPlan(
                (ORDER_ID, SPONSOR_ID), (low_refund, c.outputs[1]),
            ))

    def test_malformed_locked_token_spec_rejected(self):
        for bad in ([(TOKEN, 7)], ((TOKEN, True),), ((TOKEN, 7), (TOKEN, 1)),
                    ((b"short", 7),)):
            with self.subTest(tokens=bad), self.assertRaises(CancelPreflightRejected):
                check(locked_tokens=bad)

    def test_reproducible_random_sponsor_fee_conservation(self):
        rng = random.Random(20261112)
        for _ in range(500):
            sponsor_native = rng.randint(50, 5000)
            fee = rng.randint(20, min(100, sponsor_native))
            a, b, c = fixture(sponsor_native, fee)
            good = check(order=a, sponsor=b, plan=c)
            self.assertGreaterEqual(good.owner_native_returned, 1000)
            tampered = replace(c, outputs=(
                SyntheticOutput(OWNER, good.owner_native_returned - 1, LOCKED_TOKENS),
                c.outputs[1],
            ))
            with self.assertRaises(CancelPreflightRejected):
                check(order=a, sponsor=b, plan=tampered)


if __name__ == "__main__":
    unittest.main()
