"""Offline negative tests for domain binding; no signing or blockchain."""

from dataclasses import FrozenInstanceError, replace
import random
import unittest

from sypc_swap.trade_preflight import (
    MAX_I64, NATIVE_ASSET, PoolSnapshot, PreflightRejected,
    TradeIntent, TradePolicy, VerifiedContext, preflight_trade,
)

G = "a" * 64
C = "b" * 64
N = "c" * 64
BOX = "d" * 64
TIP = "e" * 64
RECIPIENT = "f" * 64
TOKEN = "1" * 64


def fixture():
    policy = TradePolicy(G, C, N, NATIVE_ASSET, TOKEN, RECIPIENT, 997, max_miner_fee=2000, max_slippage_bps=100)
    trusted = VerifiedContext(G, TIP, 1000, BOX)
    pool = PoolSnapshot(G, C, N, BOX, TIP, 1000, NATIVE_ASSET, TOKEN, 100000, 200000, 997)
    intent = TradeIntent(G, C, N, BOX, TIP, 1000, NATIVE_ASSET, TOKEN, RECIPIENT,
                         1000, 1955, 100, 1800, 1010)
    return intent, pool, policy, trusted


class PreflightSecurityTests(unittest.TestCase):
    def setUp(self):
        self.intent, self.pool, self.policy, self.trusted = fixture()

    def validate(self, intent=None, pool=None, policy=None, trusted=None):
        return preflight_trade(
            self.intent if intent is None else intent,
            self.pool if pool is None else pool,
            self.policy if policy is None else policy,
            self.trusted if trusted is None else trusted,
        )

    def test_valid_intent_returns_stable_review_hash(self):
        result = self.validate()
        self.assertEqual(len(result.intent_sha256), 64)
        self.assertEqual(result, self.validate())
        self.assertGreaterEqual(result.theoretical_amount_out, 1955)

    def test_changes_to_intent_change_commitment(self):
        original = self.validate()
        tighter = self.validate(intent=replace(self.intent, minimum_out=1956))
        self.assertNotEqual(original.intent_sha256, tighter.intent_sha256)

    def test_immutable_intent(self):
        with self.assertRaises(FrozenInstanceError):
            self.intent.amount_in = 2

    def test_wrong_chain_rejected_even_with_consistent_attacker_snapshot(self):
        attack_id = "2" * 64
        with self.assertRaisesRegex(PreflightRejected, "chain"):
            self.validate(intent=replace(self.intent, genesis_id=attack_id),
                          pool=replace(self.pool, genesis_id=attack_id),
                          trusted=replace(self.trusted, genesis_id=attack_id))

    def test_wrong_script_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "script"):
            self.validate(pool=replace(self.pool, contract_hash="2" * 64))
        with self.assertRaisesRegex(PreflightRejected, "script"):
            self.validate(intent=replace(self.intent, contract_hash="2" * 64))

    def test_wrong_pool_nft_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "NFT"):
            self.validate(intent=replace(self.intent, pool_nft_id="2" * 64))

    def test_synthetic_pool_box_not_verified_by_local_context(self):
        attack_id = "2" * 64
        with self.assertRaisesRegex(PreflightRejected, "UTXO"):
            self.validate(intent=replace(self.intent, pool_box_id=attack_id),
                          pool=replace(self.pool, pool_box_id=attack_id))

    def test_asset_substitution_with_consistent_intent_rejected(self):
        fake = "2" * 64
        with self.assertRaisesRegex(PreflightRejected, "allowlist"):
            self.validate(intent=replace(self.intent, asset_out=fake),
                          pool=replace(self.pool, asset_y=fake))

    def test_pool_box_replay_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "UTXO"):
            self.validate(intent=replace(self.intent, pool_box_id="2" * 64))

    def test_wrong_tip_id_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "stale"):
            self.validate(pool=replace(self.pool, tip_id="2" * 64))

    def test_stale_height_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "stale"):
            self.validate(trusted=replace(self.trusted, tip_height=1001))
        with self.assertRaisesRegex(PreflightRejected, "stale"):
            self.validate(intent=replace(self.intent, tip_height=999))

    def test_recipient_substitution_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "recipient"):
            self.validate(intent=replace(self.intent, recipient_script_hash="2" * 64))

    def test_fee_or_unexpected_pool_fee_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "miner fee"):
            self.validate(intent=replace(self.intent, max_miner_fee=2001))
        with self.assertRaisesRegex(PreflightRejected, "pool fee"):
            self.validate(pool=replace(self.pool, fee_num=999))

    def test_slippage_too_high_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "slippage"):
            self.validate(intent=replace(self.intent, slippage_bps=101))

    def test_minimum_output_too_low_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "minimum_out"):
            self.validate(intent=replace(self.intent, minimum_out=1))

    def test_minimum_output_above_quote_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "minimum_out"):
            self.validate(intent=replace(self.intent, minimum_out=200000))

    def test_expired_and_long_lived_rejected(self):
        for height in (999, 1000, 1021, MAX_I64):
            with self.subTest(height=height), self.assertRaisesRegex(PreflightRejected, "validity"):
                self.validate(intent=replace(self.intent, valid_until_height=height))

    def test_wrong_assets_or_same_pair_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "asset pair"):
            self.validate(intent=replace(self.intent, asset_out="2" * 64))
        with self.assertRaisesRegex(PreflightRejected, "same-asset"):
            self.validate(intent=replace(self.intent, asset_out=NATIVE_ASSET))

    def test_overflow_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "overflow"):
            self.validate(pool=replace(self.pool, reserve_x=MAX_I64))

    def test_bad_boolean_and_float_amounts_rejected(self):
        for bad in (True, False, 1000.0, -1, 0, "1000"):
            with self.subTest(bad=bad), self.assertRaises(PreflightRejected):
                self.validate(intent=replace(self.intent, amount_in=bad))

    def test_bad_hex_format_rejected(self):
        for bad in ("A" * 64, "g" * 64, "a" * 63, "a" * 65, None, True, "0x" + "a" * 64):
            with self.subTest(bad=bad), self.assertRaisesRegex(PreflightRejected, "hex"):
                self.validate(intent=replace(self.intent, genesis_id=bad))

    def test_bad_context_type_rejected(self):
        with self.assertRaises(PreflightRejected):
            self.validate(trusted={"genesis_id": G})

    def test_output_zero_rejected(self):
        with self.assertRaisesRegex(PreflightRejected, "zero"):
            self.validate(pool=replace(self.pool, reserve_x=10 ** 14, reserve_y=1))

    def test_reverse_direction(self):
        reverse = replace(self.intent, asset_in=TOKEN, asset_out=NATIVE_ASSET, amount_in=2000, minimum_out=980)
        result = self.validate(intent=reverse)
        self.assertGreaterEqual(result.theoretical_amount_out, 980)

    def test_random_amounts_do_not_exceed_reserves(self):
        rng = random.Random(20261112)
        successes = 0
        for _ in range(3000):
            amount = rng.randint(1, 40000)
            intent = replace(self.intent, amount_in=amount, minimum_out=1, slippage_bps=100)
            try:
                # Start with a quote with the same fee, then set actual min-out.
                from sypc_swap.trade_preflight import _quote_amount
                quote = _quote_amount(self.pool.reserve_x, self.pool.reserve_y, amount, self.pool.fee_num)
                minimum = max(1, quote * 9900 // 10000)
                result = self.validate(intent=replace(intent, minimum_out=minimum))
                self.assertLess(result.theoretical_amount_out, self.pool.reserve_y)
                self.assertGreaterEqual(result.theoretical_amount_out, minimum)
                successes += 1
            except PreflightRejected:
                self.fail("valid bounded random quote rejected")
        self.assertEqual(successes, 3000)


if __name__ == "__main__":
    unittest.main()
