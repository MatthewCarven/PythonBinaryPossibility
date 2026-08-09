"""Tests for BinaryEntropy — measuring what a real stream actually does."""

import math
import random
import unittest

from BinaryEntropy import BinaryEntropy
from BinaryPossibility import BinaryRegister


def sample_text(size: int = 60000) -> list:
    """Real English prose, as bytes — the stand-in for the text corpus."""
    with open("README.md", "rb") as handle:
        return list((handle.read() * 2)[:size])


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


class TestDeadBits(unittest.TestCase):
    def test_dead_positions_found(self):
        # top two bits always 0, bottom two vary
        records = [(i & 0b0011) for i in range(400)]
        self.assertEqual(BinaryEntropy.dead_positions(records, 4), [0, 1])
        self.assertEqual(BinaryEntropy.effective_width(records, 4), 2)

    def test_constant_stream_is_entirely_dead(self):
        self.assertEqual(BinaryEntropy.effective_width([5] * 50, 8), 0)

    def test_wasted_low_bits_spots_padding(self):
        # 16-bit audio exported into a 32-bit box
        records = [(v << 16) for v in range(1, 5000)]
        self.assertEqual(BinaryEntropy.wasted_low_bits(records, 32), 16)

    def test_no_wasted_bits_when_the_bottom_moves(self):
        self.assertEqual(BinaryEntropy.wasted_low_bits([1, 2, 4], 16), 0)

    def test_all_zero_stream_is_entirely_wasted(self):
        self.assertEqual(BinaryEntropy.wasted_low_bits([0, 0], 16), 16)

    def test_one_counts_are_most_significant_first(self):
        self.assertEqual(BinaryEntropy.one_counts([0b10], 2), [1, 0])


class TestLocality(unittest.TestCase):
    def test_independent_noise_has_no_locality(self):
        rng = random.Random(1)
        records = [rng.getrandbits(12) for _ in range(4000)]
        self.assertLess(BinaryEntropy.locality(records, 12), 0.10)

    def test_a_slow_signal_is_far_more_local_than_noise(self):
        """The claim worth pinning is comparative, not a magic threshold.

        Real music measures ~60% locality and a bounded random walk ~31%,
        so an absolute bar is a number picked from one sample. That a slow
        signal is dramatically more local than white noise is the property
        the module actually relies on.
        """
        rng = random.Random(2)
        value, walk = 30000, []
        for _ in range(4000):
            value = max(0, min(65535, value + rng.randint(-40, 40)))
            walk.append(value)
        noise = [rng.getrandbits(16) for _ in range(4000)]
        self.assertGreater(BinaryEntropy.locality(walk, 16),
                           BinaryEntropy.locality(noise, 16) * 3)

    def test_locality_of_a_constant_stream_is_zero(self):
        self.assertEqual(BinaryEntropy.locality([7] * 100, 8), 0.0)


class TestDrift(unittest.TestCase):
    def test_stationary_stream_barely_drifts(self):
        rng = random.Random(3)
        records = [rng.getrandbits(8) for _ in range(4000)]
        self.assertLess(BinaryEntropy.drift_cost(records, 8) / 4000, 1.0)

    def test_the_sign_correlated_trap_drifts_hard(self):
        """Locally certain, globally a coin flip -- persistence's worst case."""
        records = []
        for index in range(4000):
            sign = 0 if (index // 64) % 2 == 0 else 0xFF
            records.append(sign)
        per_record = BinaryEntropy.drift_cost(records, 8) / 4000
        self.assertGreater(per_record, 4.0)
        self.assertFalse(BinaryEntropy.prefers_persistent_model(records, 8))

    def test_drift_is_never_negative(self):
        rng = random.Random(4)
        for width in (4, 8):
            records = [rng.getrandbits(width) for _ in range(500)]
            self.assertGreaterEqual(
                BinaryEntropy.drift_cost(records, width), -1e-6)

    def test_prediction_changes_the_answer(self):
        """The usage rule, pinned: drift belongs to the stream AS CODED.

        A wandering signal drifts hard as raw values and barely at all as
        deltas, and those two readings recommend opposite designs. Measured
        on real music this is 9.599 vs 0.325 bits/record.
        """
        value, raw = 30000, []
        rng = random.Random(5)
        for _ in range(4000):
            value = max(0, min(65535, value + rng.randint(-60, 60)))
            raw.append(value)
        deltas = [raw[0]] + [raw[i] - raw[i - 1] for i in range(1, len(raw))]
        zig = [(d << 1) ^ (d >> 63) if d < 0 else (d << 1) for d in deltas]
        width = max(1, max(v.bit_length() for v in zig))
        self.assertGreater(
            BinaryEntropy.drift_cost(raw, 16) / len(raw),
            BinaryEntropy.drift_cost(zig, width) / len(zig),
        )


class TestBlockSizeSearch(unittest.TestCase):
    def test_returns_one_of_the_candidates(self):
        records = list(range(2000))
        size, bits = BinaryEntropy.best_block_size(records, 16)
        self.assertIn(size, (4, 8, 16, 32, 64, 128, 256))
        self.assertGreater(bits, 0)

    def test_large_blocks_win_on_a_stationary_stream(self):
        # nothing local to exploit, so per-block register overhead dominates
        rng = random.Random(6)
        records = [rng.getrandbits(8) for _ in range(4000)]
        size, _ = BinaryEntropy.best_block_size(records, 8)
        self.assertGreaterEqual(size, 64)

    def test_report_carries_the_new_measurements(self):
        data = BinaryEntropy.report(list(range(1000)), 16)
        for key in ("locality", "drift_cost", "prefers_persistent",
                    "best_block_size", "wasted_low_bits", "effective_width"):
            self.assertIn(key, data)

    def test_describe_mentions_locality_and_drift(self):
        text = BinaryEntropy.describe(list(range(500)), 16, name="counter")
        self.assertIn("locality", text)
        self.assertIn("drift", text)


if __name__ == "__main__":
    unittest.main()


class TestWordLens(unittest.TestCase):
    """Whole words, rather than bit positions — what a *selector* can use."""

    def test_vocabulary_orderings_are_deterministic(self):
        records = [5, 1, 5, 9, 1, 1]
        self.assertEqual(BinaryEntropy.vocabulary(records, "first"), [5, 1, 9])
        self.assertEqual(BinaryEntropy.vocabulary(records, "value"), [1, 5, 9])
        self.assertEqual(BinaryEntropy.vocabulary(records, "frequency"), [1, 5, 9])

    def test_frequency_ties_break_on_value(self):
        self.assertEqual(
            BinaryEntropy.vocabulary([9, 9, 2, 2, 7], "frequency"), [2, 9, 7])

    def test_rejects_unknown_ordering(self):
        with self.assertRaises(ValueError):
            BinaryEntropy.vocabulary([1, 2], "vibes")

    def test_word_frequencies(self):
        self.assertEqual(BinaryEntropy.word_frequencies([3, 3, 8]), {3: 2, 8: 1})

    def test_recency_distances_measure_the_gap(self):
        self.assertEqual(BinaryEntropy.recency_distances([1, 2, 1, 1]), [2, 1])

    def test_a_stream_with_no_repeats_yields_no_gaps(self):
        self.assertEqual(BinaryEntropy.recency_distances(list(range(50))), [])
        self.assertEqual(BinaryEntropy.recurrence_rate(list(range(50))), 0.0)

    def test_recency_profile_on_a_tight_alphabet(self):
        records = [i % 4 for i in range(400)]
        profile = BinaryEntropy.recency_profile(records)
        self.assertEqual(profile["vocabulary"], 4)
        self.assertEqual(profile["median_gap"], 4)
        self.assertEqual(profile["within_16"], 1.0)

    def test_profile_of_a_norepeat_stream_reports_infinite_gap(self):
        profile = BinaryEntropy.recency_profile(list(range(50)))
        self.assertEqual(profile["median_gap"], math.inf)
        self.assertEqual(profile["within_256"], 0.0)

    def test_vocabulary_growth_flattens_on_a_fixed_alphabet(self):
        growth = BinaryEntropy.vocabulary_growth([i % 10 for i in range(800)])
        self.assertEqual(growth[-1][1], 10)
        self.assertEqual(growth[0][1], growth[-1][1])   # flat from the start

    def test_vocabulary_growth_climbs_forever_on_enumeration(self):
        growth = BinaryEntropy.vocabulary_growth(list(range(800)))
        self.assertLess(growth[0][1], growth[-1][1])
        self.assertEqual(growth[-1][1], 800)

    def test_growth_handles_empty(self):
        self.assertEqual(BinaryEntropy.vocabulary_growth([]), [])


class TestSymbolStatistics(unittest.TestCase):
    """Order-0 statistics: what the counts alone say, before any ordering."""

    def test_uniform_alphabet_has_full_entropy_and_no_skew(self):
        records = list(range(256)) * 40
        self.assertAlmostEqual(BinaryEntropy.symbol_entropy(records), 8.0)
        self.assertAlmostEqual(BinaryEntropy.skew(records), 0.0)

    def test_a_constant_stream_is_wholly_skewed(self):
        self.assertEqual(BinaryEntropy.symbol_entropy([7] * 500), 0.0)
        self.assertEqual(BinaryEntropy.skew([7] * 500), 1.0)

    def test_empty_stream_is_defined(self):
        self.assertEqual(BinaryEntropy.symbol_entropy([]), 0.0)

    def test_prose_is_skewed_and_a_drifting_signal_is_not(self):
        """The measurement the advice split turns on.

        English letter frequencies are famously uneven. A signal that
        wanders across its whole range visits values almost evenly and is
        compressible for a different reason entirely — one number tells
        them apart. (Real music is *both*, and correctly gets both pieces
        of advice; it is not the counterexample here.)
        """
        text = sample_text()
        rng = random.Random(5)
        value, drifting = 30000, []
        for _ in range(20000):
            value = max(0, min(65535, value + rng.randint(-60, 60)))
            drifting.append(value)
        self.assertGreater(BinaryEntropy.skew(text), BinaryEntropy.SKEWED)
        self.assertLess(BinaryEntropy.skew(drifting), BinaryEntropy.SKEWED)

    def test_skew_converges_from_below_as_a_stream_lengthens(self):
        """Length-dependence, pinned down rather than left to bite later.

        The denominator is the alphabet *observed*, so a short excerpt has
        not met its rare values yet and reads low. The direction is the
        safe one — it understates the opportunity and grows towards the
        truth — but a previous detector in this project got exactly this
        wrong in the other direction, so it is worth a test.
        """
        rng = random.Random(8)
        # Values clustered near zero: a stand-in for sampled audio, whose
        # rare loud values only show up in a long enough excerpt.
        stream = [min(255, int(abs(rng.gauss(0, 20)))) for _ in range(60000)]
        readings = [BinaryEntropy.skew(stream[:n])
                    for n in (2000, 10000, 60000)]
        self.assertLess(readings[0], readings[-1])
        self.assertLessEqual(readings[0], readings[1])

    def test_skew_never_leaves_its_range(self):
        rng = random.Random(6)
        for records in ([1, 2], [0] * 9 + [1], [rng.getrandbits(8)
                                               for _ in range(4000)]):
            self.assertGreaterEqual(BinaryEntropy.skew(records), 0.0)
            self.assertLessEqual(BinaryEntropy.skew(records), 1.0)


class TestArrangementFloor(unittest.TestCase):
    """The combinatorial floor — and the price of the counts that set it."""

    def test_arrangement_of_a_constant_stream_is_zero(self):
        # One arrangement exists, so the ordering carries no information.
        self.assertAlmostEqual(BinaryEntropy.arrangement_bits([3] * 100), 0.0)

    def test_a_permutation_costs_log2_of_n_factorial(self):
        records = list(range(1000))
        self.assertAlmostEqual(
            BinaryEntropy.arrangement_bits(records),
            math.log2(math.factorial(1000)),
            places=6,
        )

    def test_order_does_not_change_it(self):
        # It is a function of the counts alone — which is exactly why it is
        # a floor and not a measurement of this particular sequence.
        records = [0, 0, 1, 2, 2, 2, 3]
        shuffled = list(records)
        random.Random(9).shuffle(shuffled)
        self.assertAlmostEqual(BinaryEntropy.arrangement_bits(records),
                               BinaryEntropy.arrangement_bits(shuffled))

    def test_repeats_are_cheaper_than_distinct_values(self):
        distinct = BinaryEntropy.arrangement_bits(list(range(64)))
        repeated = BinaryEntropy.arrangement_bits(list(range(8)) * 8)
        self.assertLess(repeated, distinct)

    def test_count_bits_matches_the_exact_combination(self):
        records, width = [0, 1, 1, 0, 1], 2
        self.assertAlmostEqual(
            BinaryEntropy.count_bits(records, width),
            math.log2(math.comb(len(records) + 4 - 1, 4 - 1)),
            places=9,
        )

    def test_count_bits_grows_with_the_alphabet(self):
        records = list(range(256)) * 4
        narrow = BinaryEntropy.count_bits(records, 8)
        wide = BinaryEntropy.count_bits(records, 16)
        self.assertGreater(wide, narrow)

    def test_reproduces_the_hardcoded_permutation_ceiling(self):
        """The figure randomness_demo.py estimates via Stirling, computed.

        That demo prints the best-possible ratio for a permutation of every
        16-bit value from an approximation. Doing it from real counts should
        land in the same place, which is the point of generalising it.
        """
        records = list(range(65536))
        floor = BinaryEntropy.arrangement_floor(records, 16)
        stirling = 65536 * 16 - 65536 * math.log2(math.e)
        self.assertAlmostEqual(floor["agreed_ratio"],
                               65536 * 16 / stirling, places=4)

    def test_the_agreed_floor_is_never_the_reachable_one(self):
        rng = random.Random(11)
        records = [rng.getrandbits(8) for _ in range(20000)]
        floor = BinaryEntropy.arrangement_floor(records, 8)
        self.assertGreater(floor["discovered"], floor["agreed"])
        self.assertLess(floor["discovered_ratio"], floor["agreed_ratio"])
        self.assertAlmostEqual(floor["discovered"],
                               floor["agreed"] + floor["count_bits"])

    def test_balanced_counts_promise_a_win_and_do_not_deliver_it(self):
        """The whole reason both figures are reported.

        Exactly-even counts really do constrain the ordering — the agreed
        floor sits above 1.0x and it is not a rounding error. But the
        counts that pin it down cost more to send than the constraint
        saves, so a self-contained file ends up *larger*. A constraint only
        pays when it is shared, never when it has to be transmitted.
        """
        records = []
        for value in range(256):
            records.extend([value] * 256)
        random.Random(13).shuffle(records)
        floor = BinaryEntropy.arrangement_floor(records, 8)
        self.assertGreater(floor["agreed_ratio"], 1.0)
        self.assertLess(floor["discovered_ratio"], 1.0)

    def test_empty_stream_is_defined(self):
        floor = BinaryEntropy.arrangement_floor([], 8)
        self.assertEqual(floor["raw_bits"], 0.0)
        self.assertEqual(floor["arrangement_bits"], 0.0)


class TestClassify(unittest.TestCase):
    """The decision tree, checked against the streams it was derived from."""

    def test_padding_is_caught_before_anything_else(self):
        records = [(v << 8) for v in range(1, 3000)]
        self.assertEqual(BinaryEntropy.classify(records, 16)["label"], "PADDED")

    def test_ordered_enumeration(self):
        # nothing ever recurs, but measuring locally sees straight through it
        verdict = BinaryEntropy.classify(list(range(8192)), 16)
        self.assertEqual(verdict["label"], "ENUMERATED")
        self.assertEqual(verdict["recurrence_rate"], 0.0)

    def test_shuffled_enumeration_is_told_apart_by_locality_alone(self):
        """The pair the word lens cannot separate, and locality can.

        Same vocabulary, same total absence of recurrence — identical to a
        selector. One is the best case measured all project (18x) and the
        other is provably hopeless, and only the bit lens knows which.
        """
        ordered = list(range(8192))
        shuffled = list(ordered)
        random.Random(42).shuffle(shuffled)
        first = BinaryEntropy.classify(ordered, 16)
        second = BinaryEntropy.classify(shuffled, 16)
        self.assertEqual(first["vocabulary"], second["vocabulary"])
        self.assertEqual(first["recurrence_rate"], second["recurrence_rate"])
        self.assertEqual(first["label"], "ENUMERATED")
        self.assertEqual(second["label"], "INCOMPRESSIBLE")

    def test_text_is_symbolic(self):
        verdict = BinaryEntropy.classify(sample_text(), 8)
        self.assertEqual(verdict["label"], "SYMBOLIC")
        # and the bit lens finds almost nothing here, which is the point
        self.assertLess(verdict["locality"], 0.20)

    def test_white_noise_is_incompressible(self):
        rng = random.Random(1)
        records = [rng.getrandbits(16) for _ in range(20000)]
        verdict = BinaryEntropy.classify(records, 16)
        self.assertEqual(verdict["label"], "INCOMPRESSIBLE")

    def test_a_drifting_signal_is_analog(self):
        rng = random.Random(2)
        value, records = 30000, []
        for _ in range(20000):
            value = max(0, min(65535, value + rng.randint(-60, 60)))
            records.append(value)
        self.assertEqual(BinaryEntropy.classify(records, 16)["label"], "ANALOG")

    def test_a_constant_stream_reads_as_all_padding(self):
        # Every position is dead, so PADDED fires and its advice -- strip
        # them and classify again -- correctly leaves nothing behind.
        self.assertEqual(BinaryEntropy.classify([42] * 500, 16)["label"], "PADDED")

    def test_verdict_carries_its_evidence(self):
        verdict = BinaryEntropy.classify(list(range(2000)), 16)
        for key in ("label", "suits", "vocabulary", "recurrence_rate",
                    "median_gap", "locality", "wasted_low_bits"):
            self.assertIn(key, verdict)

    def test_describe_reports_the_verdict(self):
        text = BinaryEntropy.describe(list(range(1000)), 16, name="counter")
        self.assertIn("vocabulary", text)
        self.assertIn("ENUMERATED", text)


class TestDerivedMechanisms(unittest.TestCase):
    """Advice comes from the measurements, not from the label.

    Two streams can share a label and want opposite mechanisms, which is
    why the advice is derived rather than looked up. Text and audio are the
    pair that forced it.
    """

    @staticmethod
    def _text():
        return sample_text()

    @staticmethod
    def _audio():
        rng = random.Random(4)
        value, records = 30000, []
        for _ in range(20000):
            value = max(0, min(65535, value + rng.randint(-60, 60)))
            records.append(value)
        return records

    def test_skewed_streams_are_told_to_code_by_frequency(self):
        joined = " ".join(BinaryEntropy.classify(self._text(), 8)["mechanisms"])
        self.assertIn("frequency coding", joined)

    def test_local_streams_are_told_to_predict_instead(self):
        joined = " ".join(BinaryEntropy.classify(self._audio(), 16)["mechanisms"])
        self.assertIn("predict and cancel", joined)
        self.assertNotIn("frequency coding", joined)

    def test_the_two_lenses_recommend_different_things(self):
        """The check that matters: neither stream gets the other's advice."""
        text = BinaryEntropy.classify(self._text(), 8)
        audio = BinaryEntropy.classify(self._audio(), 16)
        self.assertNotEqual(text["mechanisms"], audio["mechanisms"])
        self.assertGreater(text["skew"], audio["skew"])
        self.assertGreater(audio["locality"], text["locality"])

    def test_padding_advice_comes_first_and_alone_matters(self):
        records = [(v << 8) for v in range(1, 3000)]
        mechanisms = BinaryEntropy.classify(records, 16)["mechanisms"]
        self.assertIn("dead low bits", mechanisms[0])
        self.assertEqual(mechanisms[0],
                         BinaryEntropy.classify(records, 16)["suits"])

    def test_a_stream_with_nothing_to_offer_is_given_its_floor(self):
        rng = random.Random(1)
        records = [rng.getrandbits(16) for _ in range(20000)]
        verdict = BinaryEntropy.classify(records, 16)
        self.assertEqual(verdict["mechanisms"], [verdict["suits"]])
        self.assertIn("no mechanism above threshold", verdict["suits"])
        self.assertLess(verdict["discovered_ratio"], 1.0)

    def test_an_unreachable_floor_is_named_as_unreachable(self):
        """Wide alphabet: the counts cost more to send than they save."""
        records = []
        for value in range(256):
            records.extend([value] * 256)
        random.Random(17).shuffle(records)
        advice = BinaryEntropy.classify(records, 8)["suits"]
        self.assertIn("not reachable", advice)

    def test_a_reachable_floor_is_credited_to_an_adaptive_model(self):
        """Two symbols: stating the bias costs ~18 bits and saves thousands.

        The same sentence has to serve both cases honestly, so the branch
        that decides between them is worth pinning down.
        """
        rng = random.Random(3)
        records = [1 if rng.random() < 0.40 else 0 for _ in range(200000)]
        verdict = BinaryEntropy.classify(records, 1)
        self.assertLess(verdict["skew"], BinaryEntropy.SKEWED)
        self.assertIn("adaptive model", verdict["suits"])
        self.assertNotIn("not reachable", verdict["suits"])
        self.assertGreater(verdict["discovered_ratio"], 1.0)

    def test_every_verdict_carries_at_least_one_mechanism(self):
        rng = random.Random(23)
        streams = [
            (list(range(4096)), 16),
            ([rng.getrandbits(8) for _ in range(4096)], 8),
            (list(range(64)) * 64, 16),
            ([9] * 400, 8),
        ]
        for records, width in streams:
            verdict = BinaryEntropy.classify(records, width)
            self.assertTrue(verdict["mechanisms"])
            self.assertEqual(verdict["suits"], verdict["mechanisms"][0])
