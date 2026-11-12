"""Tests of pure arithmetic only. NOT on-chain contract validation."""

import random
import unittest

from sypc_swap.offline_amm import MAX_I64, PoolState, quote_exact_in


class PoolValidationTests(unittest.TestCase):
    def test_reject_empty_negative_or_noninteger_reserves(self):
        for bad in (0, -1, 1.25, True, False, "3", None, MAX_I64 + 1):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                PoolState(bad, 20, 997)
            with self.subTest(bad=bad, asset="y"), self.assertRaises(ValueError):
                PoolState(10, bad, 997)

    def test_reject_unsupported_fees(self):
        for bad in (0, -3, 1001, True, 997.0, "997", MAX_I64):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                PoolState(10, 20, bad)

    def test_valid_edge_fees(self):
        PoolState(100, 100, 1)
        PoolState(100, 100, 1000)


class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.pool = PoolState(100000, 200000, 997)

    def test_sample_quote_using_integer_floor(self):
        q = quote_exact_in(self.pool, "x", 1000)
        expected = (200000 * 1000 * 997) // (100000 * 1000 + 1000 * 997)
        self.assertEqual(q.amount_out, expected)
        self.assertEqual(q.next_state.reserve_x, 101000)
        self.assertEqual(q.next_state.reserve_y, 200000 - expected)
        self.assertEqual(q.minimum_out, expected)

    def test_reverse_direction(self):
        q = quote_exact_in(self.pool, "y", 1000)
        self.assertEqual(q.amount_out, (100000 * 1000 * 997) // (200000 * 1000 + 1000 * 997))
        self.assertEqual(q.next_state.reserve_x, 100000 - q.amount_out)
        self.assertEqual(q.next_state.reserve_y, 201000)

    def test_same_swap_on_reversed_pool(self):
        a = quote_exact_in(self.pool, "x", 1200)
        b = quote_exact_in(PoolState(self.pool.reserve_y, self.pool.reserve_x, 997), "y", 1200)
        self.assertEqual(a.amount_out, b.amount_out)
        self.assertEqual(a.next_state.reserve_x, b.next_state.reserve_y)
        self.assertEqual(a.next_state.reserve_y, b.next_state.reserve_x)

    def test_minimum_out_slippage_floor(self):
        q = quote_exact_in(self.pool, "x", 1000, slippage_bps=100)
        self.assertEqual(q.minimum_out, q.amount_out * 9900 // 10000)
        self.assertLessEqual(q.minimum_out, q.amount_out)
        self.assertGreaterEqual(q.minimum_out, 1)

    def test_slippage_does_not_change_price(self):
        a = quote_exact_in(self.pool, "x", 2000, slippage_bps=0)
        b = quote_exact_in(self.pool, "x", 2000, slippage_bps=9999)
        self.assertEqual(a.amount_out, b.amount_out)
        self.assertEqual(a.next_state, b.next_state)
        self.assertEqual(b.minimum_out, 1)

    def test_bad_slippage(self):
        for bad in (-1, 10000, True, 2.5, "100"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                quote_exact_in(self.pool, "x", 100, slippage_bps=bad)

    def test_bad_input_amount(self):
        for bad in (0, -1, True, 2.5, "100", MAX_I64 + 1):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                quote_exact_in(self.pool, "x", bad)

    def test_invalid_asset_direction(self):
        for bad in (None, "X", "z", "", 0):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                quote_exact_in(self.pool, bad, 20)

    def test_pool_type(self):
        with self.assertRaises(TypeError):
            quote_exact_in("pool", "x", 20)

    def test_reject_zero_output(self):
        with self.assertRaisesRegex(ValueError, "zero"):
            quote_exact_in(PoolState(10 ** 14, 1, 997), "x", 1)

    def test_reject_integer_reserve_overflow(self):
        with self.assertRaisesRegex(ValueError, "int64"):
            quote_exact_in(PoolState(MAX_I64, 99, 997), "x", 1)

    def test_constant_product_never_decreases_with_fee(self):
        rng = random.Random(20261112)
        successes = 0
        for _ in range(4000):
            pool = PoolState(rng.randrange(2, 1_000_000), rng.randrange(2, 1_000_000), rng.randrange(1, 1001))
            asset = rng.choice(("x", "y"))
            try:
                q = quote_exact_in(pool, asset, rng.randrange(1, 100_000))
            except ValueError as err:
                self.assertIn("zero", str(err))
                continue
            successes += 1
            self.assertGreaterEqual(q.next_state.reserve_x * q.next_state.reserve_y,
                                    pool.reserve_x * pool.reserve_y)
            self.assertGreater(q.amount_out, 0)
            self.assertGreaterEqual(q.minimum_out, 1)
        self.assertGreater(successes, 3000)

    def test_price_output_decreases_when_fee_increases(self):
        no_fee = quote_exact_in(PoolState(100_000, 200_000, 1000), "x", 10_000)
        fee = quote_exact_in(PoolState(100_000, 200_000, 997), "x", 10_000)
        self.assertLessEqual(fee.amount_out, no_fee.amount_out)

    def test_larger_input_yields_no_smaller_output(self):
        amounts = [5, 50, 500, 5000]
        out = [quote_exact_in(self.pool, "x", value).amount_out for value in amounts]
        self.assertEqual(out, sorted(out))

    def test_does_not_mutate_input_pool(self):
        before = (self.pool.reserve_x, self.pool.reserve_y, self.pool.fee_num)
        quote_exact_in(self.pool, "x", 100)
        self.assertEqual(before, (self.pool.reserve_x, self.pool.reserve_y, self.pool.fee_num))


if __name__ == "__main__":
    unittest.main()
