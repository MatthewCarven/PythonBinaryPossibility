"""Tests for the Phase 1 benchmark machinery.

Fast checks on small inputs -- the benchmark itself takes minutes, but its
building blocks should be verifiable in milliseconds. What matters here is
that the *measurements* are trustworthy, since conclusions were drawn from
them.
"""

import math
import unittest

from benchmarks import coders, corpus


class TestHelpers(unittest.TestCase):
    def test_zigzag_keeps_small_magnitudes_small(self):
        self.assertEqual(coders.zigzag(0), 0)
        self.assertEqual(coders.zigzag(-1), 1)
        self.assertEqual(coders.zigzag(1), 2)
        for value in (-500, -1, 0, 1, 500):
            self.assertGreaterEqual(coders.zigzag(value), 0)

    def test_zigzag_is_injective(self):
        seen = {coders.zigzag(v) for v in range(-200, 201)}
        self.assertEqual(len(seen), 401)

    def test_to_signed_round_trips(self):
        self.assertEqual(coders.to_signed([0, 1, 32767, 32768, 65535], 16),
                         [0, 1, 32767, -32768, -1])

    def test_residual_order_zero_is_the_value(self):
        values = [5, 9, 2]
        self.assertEqual(coders.residuals(values, 0), values)

    def test_residual_order_one_is_the_delta(self):
        self.assertEqual(coders.residuals([5, 9, 2], 1), [5, 4, -7])

    def test_a_counter_cancels_to_a_constant(self):
        # The heart of why ordered enumeration compresses: order-1 residuals
        # of a counter are all 1.
        values = list(range(100))
        self.assertEqual(set(coders.residuals(values, 1)[1:]), {1})

    def test_adaptive_bit_costs_less_as_it_learns(self):
        model = coders.AdaptiveBit()
        first = model.cost(1)
        for _ in range(50):
            model.cost(1)
        self.assertLess(model.cost(1), first)

    def test_adaptive_bit_is_a_valid_code_length(self):
        model = coders.AdaptiveBit()
        # A fair first guess costs exactly one bit.
        self.assertAlmostEqual(model.cost(0), 1.0)


class TestModelState(unittest.TestCase):
    """The numbers the component conclusion rests on."""

    def make_item(self, records, width):
        return corpus.Item("t/test", "records", records, width)

    def wide_item(self):
        """Data whose residuals stay wide, so model state is really exercised.

        A counter would NOT do here: prediction cancels it to residuals two
        bits wide, which is the whole mechanism working and would hide the
        difference this test exists to show.
        """
        import random
        rng = random.Random(3)
        return self.make_item([rng.getrandbits(16) for _ in range(500)], 16)

    def test_prediction_shrinks_state_on_predictable_data(self):
        counter = self.make_item(list(range(500)), 16)
        self.assertLessEqual(coders.model_state(counter, "register"), 4)

    def test_register_state_is_linear_in_width(self):
        self.assertLessEqual(coders.model_state(self.wide_item(), "register"), 18)

    def test_bittree_state_is_exponential_in_width(self):
        item = self.wide_item()
        register = coders.model_state(item, "register")
        bittree = coders.model_state(item, "bittree")
        self.assertEqual(bittree, 2 ** register)
        self.assertGreater(bittree, register * 1000)

    def test_bittree_is_unbuildable_at_32_bit_widths(self):
        # The finding that decides the component question: at 32 bits a
        # bit-tree wants ~4.3 billion contexts and cannot exist, while the
        # register wants 32 numbers.
        packets, _ = corpus.record_items(500)
        self.assertGreater(coders.model_state(packets, "bittree"), 10 ** 9)
        self.assertLessEqual(coders.model_state(packets, "register"), 34)

    def test_rice_holds_a_single_parameter(self):
        self.assertEqual(coders.model_state(self.wide_item(), "rice"), 1)


class TestCoderSanity(unittest.TestCase):
    def make_item(self, records, width):
        return corpus.Item("t/test", "records", records, width)

    def test_every_describer_produces_positive_bits(self):
        item = self.make_item([i % 251 for i in range(600)], 16)
        for describe in ("rice", "register", "register-static", "bittree"):
            bits = coders.predict_then_bits(item, describe)
            self.assertGreater(bits, 0, msg=describe)

    def test_unknown_describer_is_rejected(self):
        item = self.make_item([1, 2, 3, 4] * 50, 8)
        with self.assertRaises(ValueError):
            coders.predict_then_bits(item, "telepathy")

    def test_a_counter_compresses_hard(self):
        item = self.make_item(list(range(4096)), 16)
        ratio = item.raw_bits / coders.predict_then_bits(item, "register")
        self.assertGreater(ratio, 5.0)

    def test_random_data_does_not_compress(self):
        import random
        rng = random.Random(1)
        item = self.make_item([rng.getrandbits(16) for _ in range(4096)], 16)
        for describe in ("rice", "register", "bittree"):
            ratio = item.raw_bits / coders.predict_then_bits(item, describe)
            self.assertLess(ratio, 1.05, msg=f"{describe} beat the ceiling")

    def test_constant_stream_compresses_enormously(self):
        item = self.make_item([1234] * 4096, 16)
        ratio = item.raw_bits / coders.predict_then_bits(item, "register")
        self.assertGreater(ratio, 20.0)

    def test_rice_beats_nothing_on_noise_but_stays_finite(self):
        import random
        rng = random.Random(2)
        item = self.make_item([rng.getrandbits(12) for _ in range(2048)], 16)
        self.assertTrue(math.isfinite(coders.predict_then_bits(item, "rice")))


class TestCorpus(unittest.TestCase):
    def test_enumeration_pair_holds_identical_values(self):
        ordered, shuffled, seeded = corpus.enumeration_items(10)
        self.assertEqual(sorted(ordered.records), sorted(shuffled.records))
        self.assertEqual(shuffled.records, seeded.records)
        self.assertNotEqual(ordered.records, shuffled.records)

    def test_shuffled_control_is_incompressible(self):
        _, shuffled, _ = corpus.enumeration_items(12)
        for describe in ("rice", "register", "bittree"):
            ratio = shuffled.raw_bits / coders.predict_then_bits(shuffled, describe)
            self.assertLess(ratio, 1.06, msg=f"{describe} broke the control")

    def test_effective_depth_spots_reduced_audio(self):
        # 8-bit audio in a 16-bit box: few distinct values, low byte zero.
        reduced = [(v << 8) for v in range(256)] * 20
        full = [(v * 7919) & 0xFFFF for v in range(5000)]
        self.assertFalse(corpus.effective_depth(reduced)[0])
        self.assertTrue(corpus.effective_depth(full)[0])

    def test_effective_depth_handles_empty(self):
        self.assertEqual(corpus.effective_depth([])[0], True)

    def test_item_raw_bytes_width_dependent(self):
        self.assertEqual(len(corpus.Item("a", "t", [1, 2], 8).raw_bytes), 2)
        self.assertEqual(len(corpus.Item("a", "t", [1, 2], 16).raw_bytes), 4)
        self.assertEqual(len(corpus.Item("a", "t", [1, 2], 32).raw_bytes), 8)

    def test_raw_bits_matches_records_times_width(self):
        item = corpus.Item("a", "t", list(range(50)), 16)
        self.assertEqual(item.raw_bits, 800)

    def test_record_items_are_shaped_as_described(self):
        packets, sensor = corpus.record_items(200)
        self.assertEqual(packets.width, 32)
        self.assertEqual(sensor.width, 16)
        self.assertEqual(len(packets.records), 200)


class TestBaselines(unittest.TestCase):
    def test_general_purpose_baselines_run(self):
        item = corpus.Item("a", "t", [i % 200 for i in range(3000)], 8)
        for function in (coders.gzip_bits, coders.lzma_bits, coders.bz2_bits):
            self.assertGreater(function(item), 0)

    def test_flac_declines_non_audio(self):
        item = corpus.Item("a", "records", [1, 2, 3], 16)
        self.assertIsNone(coders.flac_bits(item))


if __name__ == "__main__":
    unittest.main()


class TestDepthHeuristic(unittest.TestCase):
    """The classifier that decides which audio is fit to judge on.

    It was originally distinct-values-per-sample, which is wrong: that ratio
    falls as a stream gets longer regardless of quality. A three-minute
    full-depth recording has 41,000 distinct values across 9 million samples
    -- 0.4%, which looks damning until you notice it is 63% of the 16-bit
    range. The low-byte test does not have that flaw.
    """

    def test_long_full_depth_stream_is_not_misjudged(self):
        records = [(i * 7919) & 0xFFFF for i in range(900000)]
        full, distinct_ratio, _ = corpus.effective_depth(records)
        self.assertTrue(full)
        self.assertLess(distinct_ratio, 0.10)   # would fail the old test

    def test_eight_bit_in_a_sixteen_bit_box_is_caught(self):
        records = [(v << 8) for v in range(256)] * 500
        full, _, zero_low = corpus.effective_depth(records)
        self.assertFalse(full)
        self.assertGreater(zero_low, 0.9)

    def test_heavily_quantised_material_is_caught(self):
        records = [(i % 40) * 3 + 1 for i in range(50000)]
        self.assertFalse(corpus.effective_depth(records)[0])

    def test_empty_stream_does_not_crash(self):
        self.assertTrue(corpus.effective_depth([])[0])


class TestWavLoading(unittest.TestCase):
    def write_wav(self, path, frames, channels=1, rate=44100):
        import struct as _struct
        import wave as _wave
        with _wave.open(path, "wb") as writer:
            writer.setnchannels(channels)
            writer.setsampwidth(2)
            writer.setframerate(rate)
            writer.writeframes(b"".join(_struct.pack("<h", v) for v in frames))

    def test_stereo_is_reduced_to_the_left_channel(self):
        import tempfile
        import os as _os
        with tempfile.TemporaryDirectory() as tmp:
            path = _os.path.join(tmp, "s.wav")
            frames = []
            for i in range(5000):
                frames += [i % 3000, -1]     # left ramps, right constant
            self.write_wav(path, frames, channels=2)
            item = corpus.load_wav(path)
            self.assertIsNotNone(item)
            self.assertEqual(len(item.records), 5000)
            self.assertNotIn(0xFFFF, item.records[:10])
            self.assertIn("left channel", item.note)

    def test_offset_skips_leading_frames(self):
        import tempfile
        import os as _os
        with tempfile.TemporaryDirectory() as tmp:
            path = _os.path.join(tmp, "m.wav")
            self.write_wav(path, list(range(9000)))
            self.assertEqual(len(corpus.load_wav(path).records), 9000)
            skipped = corpus.load_wav(path, offset=4000)
            self.assertEqual(len(skipped.records), 5000)
            self.assertEqual(skipped.records[0], 4000)

    def test_limit_caps_length(self):
        import tempfile
        import os as _os
        with tempfile.TemporaryDirectory() as tmp:
            path = _os.path.join(tmp, "m.wav")
            self.write_wav(path, list(range(9000)))
            self.assertEqual(len(corpus.load_wav(path, limit=3000).records), 3000)

    def test_too_short_is_declined(self):
        import tempfile
        import os as _os
        with tempfile.TemporaryDirectory() as tmp:
            path = _os.path.join(tmp, "tiny.wav")
            self.write_wav(path, list(range(100)))
            self.assertIsNone(corpus.load_wav(path))

    def test_missing_file_is_declined(self):
        self.assertIsNone(corpus.load_wav("/nonexistent/nope.wav"))
