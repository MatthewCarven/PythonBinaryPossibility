"""Tests for BinaryGlitch: loading real data, superposing bits, enumerating variants."""

import unittest

from BinaryGlitch import BinaryGlitch


class TestLoading(unittest.TestCase):
    def test_register_from_bytes_bit_pattern(self):
        register = BinaryGlitch.register_from_bytes(b"\x48")  # 'H' = 01001000
        bits = [register.get_bit(i) for i in range(8)]
        self.assertEqual(bits, [0, 1, 0, 0, 1, 0, 0, 0])

    def test_register_from_text_length(self):
        register = BinaryGlitch.register_from_text("Hi")
        self.assertEqual(len(register.get_individual_states()), 16)

    def test_unglitched_register_has_single_variant(self):
        register = BinaryGlitch.register_from_bytes(b"Hi")
        self.assertEqual(BinaryGlitch.variant_count(register), 1)
        self.assertEqual(list(BinaryGlitch.iter_variant_bytes(register)), [b"Hi"])

    def test_empty_bytes_raise(self):
        with self.assertRaises(ValueError):
            BinaryGlitch.register_from_bytes(b"")


class TestSuperposing(unittest.TestCase):
    def test_superpose_specific_bits(self):
        register = BinaryGlitch.register_from_text("Hi")
        BinaryGlitch.superpose(register, 6, 7)
        self.assertEqual(BinaryGlitch.variant_count(register), 4)

    def test_hi_becomes_hijk(self):
        register = BinaryGlitch.register_from_text("Hi")
        BinaryGlitch.superpose(register, 6, 7)  # low two bits of 'H'
        variants = list(BinaryGlitch.iter_variant_texts(register))
        self.assertEqual(variants, ["Hi", "Ii", "Ji", "Ki"])

    def test_original_is_always_among_variants(self):
        register = BinaryGlitch.register_from_bytes(b"data")
        BinaryGlitch.superpose(register, 0, 9, 17)
        self.assertIn(b"data", list(BinaryGlitch.iter_variant_bytes(register)))

    def test_superpose_random_is_reproducible(self):
        reg_a = BinaryGlitch.register_from_bytes(b"seeded")
        reg_b = BinaryGlitch.register_from_bytes(b"seeded")
        BinaryGlitch.superpose_random(reg_a, 4, seed=42)
        BinaryGlitch.superpose_random(reg_b, 4, seed=42)
        self.assertEqual(
            list(BinaryGlitch.iter_variant_bytes(reg_a)),
            list(BinaryGlitch.iter_variant_bytes(reg_b)),
        )

    def test_superpose_random_count_bounds(self):
        register = BinaryGlitch.register_from_bytes(b"x")  # 8 bits
        with self.assertRaises(ValueError):
            BinaryGlitch.superpose_random(register, 9)
        with self.assertRaises(ValueError):
            BinaryGlitch.superpose_random(register, -1)


class TestVariants(unittest.TestCase):
    def test_variant_count_matches_stream_length(self):
        register = BinaryGlitch.register_from_bytes(b"ab")
        BinaryGlitch.superpose(register, 3, 5, 12)
        self.assertEqual(
            len(list(BinaryGlitch.iter_variant_bytes(register))),
            BinaryGlitch.variant_count(register),
        )

    def test_partial_byte_register_raises(self):
        register = BinaryGlitch.register_from_bytes(b"Hi")
        register.remove_bit()  # 15 bits: no longer whole bytes
        with self.assertRaises(ValueError):
            next(BinaryGlitch.iter_variant_bytes(register))

    def test_invalid_utf8_variants_are_replaced(self):
        # 0xFF glitched at bit 0 yields 0x7F (valid) and 0xFF (invalid UTF-8).
        register = BinaryGlitch.register_from_bytes(b"\xff")
        BinaryGlitch.superpose(register, 0)
        variants = list(BinaryGlitch.iter_variant_texts(register))
        self.assertEqual(variants, ["\x7f", "�"])

    def test_strict_errors_raise_on_invalid_utf8(self):
        register = BinaryGlitch.register_from_bytes(b"\xff")
        with self.assertRaises(UnicodeDecodeError):
            list(BinaryGlitch.iter_variant_texts(register, errors="strict"))


class TestOneShots(unittest.TestCase):
    def test_glitch_text_streams_expected_count(self):
        variants = list(BinaryGlitch.glitch_text("Hello", 3, seed=7))
        self.assertEqual(len(variants), 8)
        self.assertIn("Hello", variants)

    def test_glitch_bytes_streams_expected_count(self):
        variants = list(BinaryGlitch.glitch_bytes(b"Hello", 2, seed=7))
        self.assertEqual(len(variants), 4)
        self.assertIn(b"Hello", variants)


if __name__ == "__main__":
    unittest.main()
