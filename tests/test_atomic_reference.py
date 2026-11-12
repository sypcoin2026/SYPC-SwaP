"""Adversarial tests of the 2021 Ergo atomic-exchange OFFLINE reference.

No Scala/ErgoScript bytecode, network, wallet, signature or money is involved.
"""

from dataclasses import FrozenInstanceError, replace
import itertools
import random
import unittest

from sypc_swap.atomic_reference import (
    MAX_I64, AtomicOrder, Side, SyntheticOutput, original_atomic_predicate,
)

ORDER_ID = b"\xa1" * 32
OTHER_ID = b"\xa2" * 32
TOKEN_ID = b"\xb1" * 32
WRONG_TOKEN = b"\xb2" * 32
OWNER = b"\x08owner-proposition"
ATTACKER = b"\x08attacker-proposition"


def buying() -> AtomicOrder:
    return AtomicOrder(Side.BUY_TOKEN, ORDER_ID, OWNER, TOKEN_ID, minimum_token_amount=10)


def selling() -> AtomicOrder:
    return AtomicOrder(Side.SELL_TOKEN, ORDER_ID, OWNER, minimum_native_value=900)


def token_out(*, recipient=OWNER, reference=ORDER_ID, token=TOKEN_ID, amount=10):
    return SyntheticOutput(recipient, 1000000, ((token, amount),), reference)


def native_out(*, recipient=OWNER, reference=ORDER_ID, amount=900):
    return SyntheticOutput(recipient, amount, (), reference)


class DataModelTests(unittest.TestCase):
    def test_reject_invalid_box_id(self):
        for value in (b"", b"a" * 31, b"a" * 33, True, "not-bytes"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(buying(), box_id=value)

    def test_reject_invalid_token_id(self):
        with self.assertRaises(ValueError):
            replace(buying(), token_id=b"x")

    def test_reject_invalid_owner(self):
        for value in (b"", b"x" * 4097, 3, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(buying(), owner_proposition=value)

    def test_reject_invalid_order_side(self):
        with self.assertRaises(ValueError):
            replace(buying(), side="buy-token")

    def test_reject_wrong_order_parameters(self):
        for invalid in (
            lambda: replace(buying(), minimum_token_amount=0),
            lambda: replace(buying(), minimum_token_amount=True),
            lambda: replace(buying(), minimum_native_value=1),
            lambda: replace(selling(), token_id=TOKEN_ID),
            lambda: replace(selling(), minimum_native_value=0),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                invalid()

    def test_reject_negative_or_boolean_output(self):
        for value in (-1, MAX_I64 + 1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(native_out(), value=value)

    def test_reject_malformed_tokens(self):
        for invalid in ([(TOKEN_ID, 1)], ((b"short", 1),), ((TOKEN_ID, 0),), ((TOKEN_ID, True),), ((TOKEN_ID,),)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                SyntheticOutput(OWNER, 100, invalid, ORDER_ID)

    def test_reject_malformed_r4(self):
        with self.assertRaises(ValueError):
            replace(token_out(), r4_order_id=b"short")

    def test_frozen_structures(self):
        with self.assertRaises(FrozenInstanceError):
            buying().box_id = OTHER_ID
        with self.assertRaises(FrozenInstanceError):
            native_out().value = 1


class BuyOrderTests(unittest.TestCase):
    def test_exact_fill(self):
        self.assertTrue(original_atomic_predicate(buying(), (token_out(),), False))

    def test_overfill(self):
        self.assertTrue(original_atomic_predicate(buying(), (token_out(amount=12),), False))

    def test_wrong_receiver(self):
        self.assertFalse(original_atomic_predicate(buying(), (token_out(recipient=ATTACKER),), False))

    def test_wrong_token(self):
        self.assertFalse(original_atomic_predicate(buying(), (token_out(token=WRONG_TOKEN),), False))

    def test_underfill(self):
        self.assertFalse(original_atomic_predicate(buying(), (token_out(amount=9),), False))

    def test_wrong_reference(self):
        self.assertFalse(original_atomic_predicate(buying(), (token_out(reference=OTHER_ID),), False))

    def test_missing_reference(self):
        self.assertFalse(original_atomic_predicate(buying(), (token_out(reference=None),), False))

    def test_wrong_output_index(self):
        self.assertFalse(original_atomic_predicate(buying(), (native_out(), token_out()), False))

    def test_first_token_slot_matters(self):
        wrong_first = SyntheticOutput(OWNER, 10, ((WRONG_TOKEN, 1), (TOKEN_ID, 10)), ORDER_ID)
        self.assertFalse(original_atomic_predicate(buying(), (wrong_first,), False))

    def test_empty_tokens_and_outputs(self):
        self.assertFalse(original_atomic_predicate(buying(), (), False))
        self.assertFalse(original_atomic_predicate(buying(), (native_out(),), False))

    def test_signed_owner_branch_has_no_refund_guarantee(self):
        # Source contract: buyerPk || (...). A valid owner signature bypasses
        # payout checks, so frontend MUST analyze whole tx before signing.
        self.assertTrue(original_atomic_predicate(buying(), (token_out(recipient=ATTACKER),), True))


class SellOrderTests(unittest.TestCase):
    def test_exact_fill(self):
        self.assertTrue(original_atomic_predicate(selling(), (token_out(), native_out()), False))

    def test_overfill(self):
        self.assertTrue(original_atomic_predicate(selling(), (token_out(), native_out(amount=1000)), False))

    def test_insufficient_native_amount(self):
        self.assertFalse(original_atomic_predicate(selling(), (token_out(), native_out(amount=899)), False))

    def test_wrong_receiver(self):
        self.assertFalse(original_atomic_predicate(selling(), (token_out(), native_out(recipient=ATTACKER)), False))

    def test_wrong_order_reference(self):
        self.assertFalse(original_atomic_predicate(selling(), (token_out(), native_out(reference=OTHER_ID)), False))

    def test_wrong_output_position(self):
        # The second output is evaluated: force it below the native payout,
        # otherwise the source script correctly permits it even with tokens.
        out1 = SyntheticOutput(OWNER, 0, ((TOKEN_ID, 10),), ORDER_ID)
        self.assertFalse(original_atomic_predicate(selling(), (native_out(), out1), False))

    def test_seller_allows_extra_tokens_in_payout(self):
        # Explicitly document the original's actual predicate: a valid
        # native payout may include tokens. Do not silently add constraints.
        self.assertTrue(original_atomic_predicate(selling(), (native_out(), token_out()), False))

    def test_requires_second_output(self):
        self.assertFalse(original_atomic_predicate(selling(), (native_out(),), False))
        self.assertFalse(original_atomic_predicate(selling(), (), False))

    def test_owner_signature_can_cancel(self):
        self.assertTrue(original_atomic_predicate(selling(), (), True))

    def test_sale_contract_does_not_filter_token_id_itself(self):
        # The source sell() branch demands a native payout, not token ID.
        # Input assets are checked by chain rules, NOT this local predicate.
        self.assertTrue(original_atomic_predicate(selling(), (token_out(token=WRONG_TOKEN), native_out()), False))


class OriginalPredicateBoundaryTests(unittest.TestCase):
    def test_bad_argument_types_fail_closed(self):
        with self.assertRaises(TypeError):
            original_atomic_predicate(buying(), [token_out()], False)
        with self.assertRaises(TypeError):
            original_atomic_predicate(buying(), (token_out(),), 1)

    def test_exhaustive_buy_match_outcome(self):
        total = 0
        for reference, receiver, token, amount in itertools.product(
            (ORDER_ID, OTHER_ID, None),
            (OWNER, ATTACKER),
            (TOKEN_ID, WRONG_TOKEN),
            (9, 10, 11),
        ):
            o = token_out(reference=reference, recipient=receiver, token=token, amount=amount)
            should_accept = (reference == ORDER_ID and receiver == OWNER
                             and token == TOKEN_ID and amount >= 10)
            self.assertEqual(original_atomic_predicate(buying(), (o,), False), should_accept)
            total += 1
        self.assertEqual(total, 36)

    def test_randomized_sell_and_owner_policy(self):
        rng = random.Random(20261112)
        for _ in range(1500):
            ref = rng.choice([ORDER_ID, OTHER_ID])
            receiver = rng.choice([OWNER, ATTACKER])
            payout = rng.randrange(0, 2000)
            authentic = (ref == ORDER_ID and receiver == OWNER and payout >= 900)
            out = native_out(reference=ref, recipient=receiver, amount=payout)
            self.assertEqual(original_atomic_predicate(selling(), (token_out(), out), False), authentic)


if __name__ == "__main__":
    unittest.main()
