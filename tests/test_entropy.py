"""Tests for BinaryEntropy — measuring what a real stream actually does."""

import math
import random
import unittest

from BinaryEntropy import BinaryEntropy
from BinaryPossibility import BinaryRegister


class TestRegisterFromStream(unittest.TestCase):
    def test_recovers_known_structure(self):
        # Top two bits pinned to 1, bottom two free and even.
        records = [0b1100 | (i & 0b0011) for i in range(1000)]
        register = BinaryEntropy.register_from_stream(records, 4)
        self.assertEqual(repr(register), "BinaryRegister('11??')")
        self.assertEqual(register.get_bit(0), 1)
        self.assertEqual(register.get_bit(1), 1)
        self.assertAlmostEqual(register.get_bit_probability(2), 0.5, delta=0.01)
        self.assertAlmostEqual(register.get_bit_probability(3), 0.5, delta=0.01)

    def test_recovers_a_known_bias(self):
        rng = random.Random(4)
        records = [1 if rng.random() < 0.8 else 0 for _ in range(5000)]
        register = BinaryEntropy.register_from_stream(records, 1)
        self.assertAlmostEqual(register.get_bit_probability(0), 0.8, delta=0.02)

    def test_constant_columns_collapse(self):
        register = BinaryEntropy.register_from_stream([0b1010] * 50, 4)
        self.assertEqual(repr(register), "BinaryRegister('1010')")
        self.assertEqual(register.entropy(), 0.0)
        self.assertEqual(register.calculate_possibility_count(), 1)

    def test_bit_order_is_most_significant_first(self):
        # Matches BinaryConverter/BinaryGlitch: index 0 is the high bit.
        register = BinaryEntropy.register_from_stream([0b1000, 0b1001], 4)
        self.assertEqual(register.get_bit(0), 1)
        self.assertEqual(register.get_bit(1), 0)
        self.assertIsNone(register.get_bit(3))

    def test_register_from_bytes(self):
        register = BinaryEntropy.register_from_bytes(b"AAAA")
        self.assertEqual(register.entropy(), 0.0)

    def test_ascii_high_bit_is_detected_as_constant(self):
        register = BinaryEntropy.register_from_bytes(b"plain ascii text here")
        self.assertEqual(register.get_bit(0), 0)  # bit 7 of every byte

    def test_rejects_empty_or_bad_width(self):
        with self.assertRaises(ValueError):
            BinaryEntropy.register_from_stream([], 8)
        with self.assertRaises(ValueError):
            BinaryEntropy.register_from_stream([1], 0)


class TestEntropyMeasures(unittest.TestCase):
    def test_uniform_random_stream_is_nearly_full_entropy(self):
        rng = random.Random(1)
        records = [rng.getrandbits(8) for _ in range(4000)]
        register = BinaryEntropy.register_from_stream(records, 8)
        self.assertGreater(register.entropy(), 7.9)

    def test_constant_stream_has_no_entropy(self):
        self.assertEqual(BinaryEntropy.stream_entropy([7] * 100, 8), 0.0)

    def test_stream_entropy_scales_with_length(self):
        rng = random.Random(2)
        records = [rng.getrandbits(4) for _ in range(500)]
        register = BinaryEntropy.register_from_stream(records, 4)
        self.assertAlmostEqual(
            BinaryEntropy.stream_entropy(records, 4),
            register.entropy() * len(records),
        )

    def test_column_probabilities_match_the_register(self):
        rng = random.Random(3)
        records = [rng.getrandbits(6) for _ in range(800)]
        probabilities = BinaryEntropy.column_probabilities(records, 6)
        register = BinaryEntropy.register_from_stream(records, 6)
        for index, p in enumerate(probabilities):
            self.assertAlmostEqual(register.get_bit_probability(index), p)

    def test_register_cost_is_log2_three_per_position(self):
        self.assertAlmostEqual(
            BinaryEntropy.register_cost(16), 16 * math.log2(3)
        )
        # And that is bigger than storing a plain value of the same width.
        self.assertGreater(BinaryEntropy.register_cost(16), 16)


class TestBlocked(unittest.TestCase):
    def test_one_register_per_block(self):
        records = list(range(100))
        registers = BinaryEntropy.blocked_registers(records, 8, block_size=16)
        self.assertEqual(len(registers), 7)  # 6 full blocks + a short tail
        self.assertTrue(all(isinstance(r, BinaryRegister) for r in registers))

    def test_local_measurement_beats_whole_stream_on_a_counter(self):
        # The finding this module exists to make reproducible: over the whole
        # stream every column varies, but inside a window most hold still.
        records = list(range(4096))
        whole = BinaryEntropy.stream_entropy(records, 16)
        blocked = BinaryEntropy.blocked_entropy(records, 16, block_size=16)
        self.assertLess(blocked, whole / 2)

    def test_blocked_entropy_of_a_constant_stream_is_zero(self):
        self.assertEqual(
            BinaryEntropy.blocked_entropy([3] * 64, 8, block_size=16), 0.0
        )

    def test_rejects_bad_block_size(self):
        with self.assertRaises(ValueError):
            BinaryEntropy.blocked_registers([1, 2], 8, block_size=0)


class TestReporting(unittest.TestCase):
    def test_report_keys_and_consistency(self):
        records = list(range(500))
        data = BinaryEntropy.report(records, 16)
        self.assertEqual(data["records"], 500)
        self.assertEqual(data["raw_bits"], 500 * 16)
        self.assertGreater(data["blocked_ratio"], data["whole_stream_ratio"])
        self.assertLessEqual(data["entropy_per_record"], 16.0)

    def test_report_counts_constant_columns(self):
        records = [0b0000_1111 & (0b1111 | (i & 0b1111)) for i in range(200)]
        data = BinaryEntropy.report(records, 8)
        self.assertGreaterEqual(data["constant_columns"], 4)

    def test_describe_is_printable_and_mentions_the_register(self):
        text = BinaryEntropy.describe(list(range(200)), 16, name="counter")
        self.assertIn("counter", text)
        self.assertIn("BinaryRegister", text)
        self.assertIn("entropy per record", text)


class TestHonestLimits(unittest.TestCase):
    """The module should not flatter itself on data it cannot see into."""

    def test_a_counter_looks_like_noise_to_this_lens(self):
        # Trivially predictable, but every low bit varies evenly, so a
        # per-position measurement finds almost nothing. Documented, not a bug.
        records = list(range(65536))
        register = BinaryEntropy.register_from_stream(records, 16)
        self.assertGreater(register.entropy(), 15.9)

    def test_but_measuring_locally_sees_straight_through_it(self):
        records = list(range(65536))
        blocked = BinaryEntropy.blocked_entropy(records, 16, block_size=16)
        self.assertLess(blocked / len(records), 5.0)


if __name__ == "__main__":
    unittest.main()
