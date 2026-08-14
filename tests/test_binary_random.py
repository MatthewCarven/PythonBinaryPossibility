"""Tests for BinaryRandom -- the twelve from PLAN-generators.md section 6,
plus the E3 regressions that must not be relearned.

Test 3 is the crown jewel, modelled on the existing
``2**entropy() == calculate_possibility_count()`` identity: at order=1 the
charge equals R * log2(A!) exactly, because the coder IS the process.
"""

import math
import random
import time
import unittest

from BinaryEntropy import BinaryEntropy
from BinaryRandom import RandomGeneratorPerfect


def log2fact(n: int) -> float:
    return math.lgamma(n + 1) / math.log(2)


class TestConstruction(unittest.TestCase):
    def test_rejects_order_below_one(self):
        with self.assertRaises(ValueError):
            RandomGeneratorPerfect(8, order=0)
        with self.assertRaises(ValueError):
            RandomGeneratorPerfect(8, order=-3)

    def test_rejects_fractional_and_bool_order(self):
        with self.assertRaises(ValueError):
            RandomGeneratorPerfect(8, order=1.5)
        with self.assertRaises(ValueError):
            RandomGeneratorPerfect(8, order=True)

    def test_rejects_negative_width_and_window(self):
        with self.assertRaises(ValueError):
            RandomGeneratorPerfect(-1)
        with self.assertRaises(ValueError):
            RandomGeneratorPerfect(8, window=-1)

    def test_none_and_inf_both_mean_free(self):
        for free in (None, math.inf):
            g = RandomGeneratorPerfect(3, order=free, rng=random.Random(0))
            self.assertEqual(g.order, math.inf)
            self.assertEqual(g.eligible_size(), 8)


class TestBalanceInvariant(unittest.TestCase):
    """Test 1: after any number of draws, spread never exceeds order."""

    def test_spread_bounded_at_every_step(self):
        for width in (1, 3, 8):
            for order in (1, 2, 4, 16):
                g = RandomGeneratorPerfect(width, order, rng=random.Random(7))
                for _ in range(300):
                    g.next()
                    self.assertLessEqual(g.spread, order)

    def test_observe_shares_the_same_counts(self):
        g = RandomGeneratorPerfect(2, order=math.inf, rng=random.Random(0))
        g.observe_all([0, 0, 0, 1])
        self.assertEqual(g.spread, 3)
        self.assertEqual(g.counts, [3, 1, 0, 0])

    def test_observe_rejects_out_of_alphabet_values(self):
        g = RandomGeneratorPerfect(2)
        with self.assertRaises(ValueError):
            g.observe(4)
        with self.assertRaises(ValueError):
            g.observe(-1)


class TestExhaustion(unittest.TestCase):
    """Test 2: at order=1, every A consecutive draws is a permutation."""

    def test_each_round_is_a_permutation(self):
        A = 16
        for seed in range(5):
            g = RandomGeneratorPerfect(4, 1, rng=random.Random(seed))
            stream = g.take(A * 8)
            for start in range(0, len(stream), A):
                chunk = stream[start:start + A]
                self.assertEqual(sorted(chunk), list(range(A)))


class TestTheIdentity(unittest.TestCase):
    """Test 3: at order=1, charge(stream) == R * log2(A!) EXACTLY, for every
    stream the generator can emit.  The coder is the process."""

    def test_full_rounds_charge_exactly(self):
        for width in (2, 3, 4):
            A = 1 << width
            expected = 5 * log2fact(A)
            for seed in range(25):
                g = RandomGeneratorPerfect(width, 1, rng=random.Random(seed))
                stream = g.take(5 * A)
                charged = g.charge(stream)
                self.assertLess(abs(charged - expected), 1e-9)

    def test_partial_rounds_charge_exactly(self):
        width, A, r = 3, 8, 3
        expected = 2 * log2fact(A) + (log2fact(A) - log2fact(A - r))
        for seed in range(10):
            g = RandomGeneratorPerfect(width, 1, rng=random.Random(seed))
            charged = g.charge(g.take(2 * A + r))
            self.assertLess(abs(charged - expected), 1e-9)
            self.assertLess(
                abs(charged - RandomGeneratorPerfect.ideal_bits(width, 1, 2 * A + r)),
                1e-9,
            )

    def test_charge_composes_from_cost_of_and_observe(self):
        g = RandomGeneratorPerfect(3, 1, rng=random.Random(11))
        stream = g.take(40)
        model = RandomGeneratorPerfect(3, 1)
        manual = 0.0
        for v in stream:
            manual += model.cost_of(v)
            model.observe(v)
        self.assertLess(abs(manual - g.charge(stream)), 1e-9)

    def test_window_segments_charge_exactly(self):
        # A window that is NOT a multiple of A restarts the deal mid-round;
        # each window prices independently and the total is still exact.
        width, A, window, n = 3, 8, 10, 35
        g = RandomGeneratorPerfect(width, 1, window, rng=random.Random(4))
        stream = g.take(n)
        per_window = RandomGeneratorPerfect.ideal_bits(width, 1, window)
        tail = RandomGeneratorPerfect.ideal_bits(width, 1, n % window)
        expected = (n // window) * per_window + tail
        self.assertLess(abs(g.charge(stream) - expected), 1e-9)


class TestDeterminismGuard(unittest.TestCase):
    """Test 4: the dial's far end is a counter, and this guard fails loudly
    if the generator ever stops spending randomness."""

    def test_entropy_rate_matches_closed_form(self):
        g = RandomGeneratorPerfect(4, 1)
        target = log2fact(16) / 16
        self.assertLess(abs(g.entropy_rate(4096, seed=3) - target), 1e-9)

    def test_two_seeds_differ_in_stream_but_not_counts(self):
        a = RandomGeneratorPerfect(4, 1, rng=random.Random(1))
        b = RandomGeneratorPerfect(4, 1, rng=random.Random(2))
        sa, sb = a.take(64), b.take(64)
        self.assertNotEqual(sa, sb)
        self.assertEqual(a.counts, b.counts)  # 4 full rounds: all exactly 4


class TestNoClosedFormBeyondOrderOne(unittest.TestCase):
    """Test 5: at 1 < order < inf the closed form genuinely dies -- streams
    have unequal probabilities.  State it, don't fudge it."""

    def test_charges_disagree_across_seeds(self):
        charges = set()
        for seed in range(60):
            g = RandomGeneratorPerfect(3, 3, rng=random.Random(seed))
            c = g.charge(g.take(24))
            self.assertTrue(math.isfinite(c))
            charges.add(round(c, 9))
        self.assertGreater(len(charges), 10)
        self.assertGreater(max(charges) - min(charges), 1.0)

    def test_eligible_probabilities_sum_to_one_at_every_step(self):
        g = RandomGeneratorPerfect(3, 3, rng=random.Random(9))
        for _ in range(60):
            total = sum(2 ** -g.cost_of(v) for v in g.eligible())
            self.assertLess(abs(total - 1.0), 1e-9)
            g.next()

    def test_ideal_bits_refuses_the_middle(self):
        with self.assertRaises(ValueError):
            RandomGeneratorPerfect.ideal_bits(8, 3, 100)


class TestFreeDegeneracy(unittest.TestCase):
    """Test 6: order=inf charges exactly log2(A) per symbol and its output
    is as uniform as the stdlib's."""

    def test_free_charge_is_flat(self):
        g = RandomGeneratorPerfect(4, None, rng=random.Random(0))
        stream = g.take(512)
        self.assertLess(abs(g.charge(stream) - 512 * 4), 1e-9)

    def test_chi_squared_matches_randrange(self):
        n, A = 25600, 256

        def chi2(values):
            counts = [0] * A
            for v in values:
                counts[v] += 1
            expected = n / A
            return sum((c - expected) ** 2 / expected for c in counts)

        g = RandomGeneratorPerfect(8, None, rng=random.Random(13))
        ours = chi2(g.take(n))
        rng = random.Random(13)
        stdlib = chi2([rng.randrange(A) for _ in range(n)])
        # df = 255, sd ~ 22.6; 400 is ~6 sigma above the mean.  Seeded.
        self.assertLess(ours, 400)
        self.assertLess(stdlib, 400)


class TestRunAndGapBounds(unittest.TestCase):
    """Test 7: at order=1 max run is 2 and max recency distance is 2A-1 --
    tight bounds, measured through BinaryEntropy so the modules agree."""

    def test_bounds_hold_and_are_hit(self):
        A = 8
        longest_run = 0
        longest_gap = 0
        for seed in range(60):
            g = RandomGeneratorPerfect(3, 1, rng=random.Random(seed))
            stream = g.take(240)
            run = best = 1
            for previous, current in zip(stream, stream[1:]):
                run = run + 1 if current == previous else 1
                best = max(best, run)
            self.assertLessEqual(best, 2)
            longest_run = max(longest_run, best)
            gaps = BinaryEntropy.recency_distances(stream)
            self.assertLessEqual(max(gaps), 2 * A - 1)
            longest_gap = max(longest_gap, max(gaps))
        # Tight bounds get HIT, not just respected -- an off-by-one in the
        # eligibility logic moves them.
        self.assertEqual(longest_run, 2)
        self.assertEqual(longest_gap, 2 * A - 1)


class TestSpreadCurve(unittest.TestCase):
    """Test 8: free spread grows as sqrt(N); order=1 stays pinned."""

    def test_free_grows_and_perfect_does_not(self):
        at_1k = []
        at_16k = []
        for seed in range(9):
            g = RandomGeneratorPerfect(8, None, rng=random.Random(seed))
            curve = dict(g.discrepancy_curve(g.take(16384), 8))
            at_1k.append(curve[1024])
            at_16k.append(curve[16384])
        at_1k.sort()
        at_16k.sort()
        ratio = at_16k[4] / at_1k[4]  # medians; sqrt(16) = 4
        self.assertGreater(ratio, 2.2)
        self.assertLess(ratio, 7.0)

        g = RandomGeneratorPerfect(8, 1, rng=random.Random(0))
        for _, spread in g.discrepancy_curve(g.take(16384), 8):
            self.assertLessEqual(spread, 1)

    def test_expected_spread_scales_as_sqrt(self):
        one = RandomGeneratorPerfect.expected_spread(8, 4096)
        four = RandomGeneratorPerfect.expected_spread(8, 16384)
        self.assertLess(abs(four / one - 2.0), 1e-9)


class TestCrossCheckAgainstShippedDemo(unittest.TestCase):
    """Test 9: ideal_bits agrees with the permutation ceiling
    randomness_demo.py has printed all along -- the class arrives already
    cross-checked against something shipped."""

    def test_width_32_ceiling(self):
        n = 2 ** 32
        stored = n * 32
        ratio = stored / RandomGeneratorPerfect.ideal_bits(32, 1, n)
        demo = stored / (stored - n * math.log2(math.e))
        self.assertLess(abs(ratio - demo), 1e-6)
        self.assertLess(abs(ratio - 1.0472), 1e-3)

    def test_width_16_ceiling(self):
        n = 2 ** 16
        stored = n * 16
        ratio = stored / RandomGeneratorPerfect.ideal_bits(16, 1, n)
        demo = stored / (stored - n * math.log2(math.e))
        self.assertLess(abs(ratio - demo), 2e-4)  # the Stirling remainder


class TestTimeBound(unittest.TestCase):
    """Test 10: fails by BEING SLOW, not by erroring.  The plan measured the
    naive scan at 507 s for 100k draws at width 16; the bucket structure
    must keep both configurations quick, because width 32 is exactly where
    balance is cheapest and the naive version could never reach it."""

    def test_width_8_hundred_thousand_draws(self):
        g = RandomGeneratorPerfect(8, 1, rng=random.Random(0))
        started = time.monotonic()
        g.take(100_000)
        self.assertLess(time.monotonic() - started, 10.0)

    def test_width_16_thirty_thousand_draws(self):
        g = RandomGeneratorPerfect(16, 1, rng=random.Random(0))
        started = time.monotonic()
        g.take(30_000)
        self.assertLess(time.monotonic() - started, 10.0)


class TestTinyAlphabets(unittest.TestCase):
    """Test 11: width=0 and width=1, decided deliberately, in the spirit of
    the empty-register decision."""

    def test_width_zero_is_the_one_symbol_alphabet(self):
        g = RandomGeneratorPerfect(0, 1, rng=random.Random(0))
        self.assertEqual(g.take(5), [0, 0, 0, 0, 0])
        self.assertEqual(g.spread, 0)
        self.assertEqual(g.cost_of(0), 0.0)
        self.assertEqual(g.charge([0, 0, 0]), 0.0)
        self.assertEqual(g.entropy_rate(64), 0.0)

    def test_width_one_alternates_in_pairs(self):
        g = RandomGeneratorPerfect(1, 1, rng=random.Random(3))
        stream = g.take(40)
        for start in range(0, 40, 2):
            self.assertEqual(sorted(stream[start:start + 2]), [0, 1])
        # Each pair costs log2(2) + log2(1) = exactly one bit.
        self.assertLess(abs(g.charge(stream) - 20.0), 1e-9)


class TestRoundTrip(unittest.TestCase):
    """Test 12: same seed, same parameters, same stream."""

    def test_same_configuration_reproduces(self):
        for order in (1, 4, None):
            for window in (0, 96):
                a = RandomGeneratorPerfect(5, order, window, random.Random(21))
                b = RandomGeneratorPerfect(5, order, window, random.Random(21))
                self.assertEqual(a.take(200), b.take(200))

    def test_different_seeds_do_not(self):
        a = RandomGeneratorPerfect(5, 1, rng=random.Random(1))
        b = RandomGeneratorPerfect(5, 1, rng=random.Random(2))
        self.assertNotEqual(a.take(200), b.take(200))


class TestE3Regressions(unittest.TestCase):
    """The findings E3 paid for, pinned so they cannot be relearned.

    ``min()`` is a max-statistic: a running-count model anchors eligibility
    to the worst-off value and collapses on data that is still nearly
    balanced.  The windowed model is the difference between 0% and 82%.
    """

    N = 8192

    def _ratio(self, model: RandomGeneratorPerfect, records) -> float:
        return (len(records) * 8) / model.charge(records, escape=True)

    def test_window_survives_substitution_and_running_counts_do_not(self):
        clean = RandomGeneratorPerfect(8, 1, rng=random.Random(1)).take(self.N)
        rng = random.Random(2)
        perturbed = [
            rng.randrange(256) if rng.random() < 0.02 else v for v in clean
        ]
        windowed = RandomGeneratorPerfect(8, 1, window=256)
        running = RandomGeneratorPerfect(8, 1, window=0)

        self.assertGreater(self._ratio(windowed, clean), 1.20)      # E1: 1.2161x
        ratio_windowed = self._ratio(windowed, perturbed)           # E3: 1.1709x
        ratio_running = self._ratio(running, perturbed)             # E3: collapse
        self.assertGreater(ratio_windowed, 1.10)
        self.assertLess(ratio_running, 1.02)
        self.assertGreater(ratio_windowed, ratio_running + 0.08)

    def test_prng_reads_as_nothing(self):
        # Mersenne Twister has no local balance structure: the model must
        # yield ~1.0000x, not a fantasy ratio.
        rng = random.Random(5)
        stream = [rng.randrange(256) for _ in range(self.N)]
        ratio = self._ratio(RandomGeneratorPerfect(8, 1, window=256), stream)
        self.assertGreater(ratio, 0.97)
        self.assertLess(ratio, 1.005)

    def test_escape_is_nearly_free_when_it_never_fires(self):
        # The always-0 adaptive flag costs ~log2(N+1) bits total -- E3's
        # "15.99 bits over a whole 64 KB file" is log2(65537).
        clean = RandomGeneratorPerfect(8, 1, rng=random.Random(8)).take(self.N)
        model = RandomGeneratorPerfect(8, 1)
        overhead = model.charge(clean, escape=True) - model.charge(clean)
        self.assertGreater(overhead, 0.0)
        self.assertLess(abs(overhead - math.log2(self.N + 1)), 1.5)


class TestProfile(unittest.TestCase):
    def test_profile_verdicts(self):
        g = RandomGeneratorPerfect(8, 1, rng=random.Random(0))
        self.assertEqual(g.profile()["verdict"], "empty")
        g.take(4096)
        report = g.profile()
        self.assertEqual(report["n"], 4096)
        self.assertEqual(report["verdict"], "balance-constrained")

        free = RandomGeneratorPerfect(8, None, rng=random.Random(0))
        free.take(4096)
        self.assertEqual(free.profile()["verdict"], "free")

        lopsided = RandomGeneratorPerfect(8)
        lopsided.observe_all([7] * 4096)
        self.assertEqual(lopsided.profile()["verdict"], "structured")


class TestConveniences(unittest.TestCase):
    def test_to_bytes_at_width_8(self):
        g = RandomGeneratorPerfect(8, 1, rng=random.Random(0))
        data = g.to_bytes(256)
        self.assertIsInstance(data, bytes)
        self.assertEqual(sorted(data), list(range(256)))  # one full round

    def test_to_bytes_refuses_wide_symbols(self):
        with self.assertRaises(ValueError):
            RandomGeneratorPerfect(16).to_bytes(4)

    def test_reset_zeroes_counts_and_window_phase(self):
        g = RandomGeneratorPerfect(3, 1, window=5, rng=random.Random(0))
        g.take(13)
        g.reset()
        self.assertEqual(g.spread, 0)
        self.assertEqual(sum(g.counts), 0)

    def test_charge_never_touches_the_live_counts(self):
        g = RandomGeneratorPerfect(3, 1, rng=random.Random(0))
        g.take(5)
        before = list(g.counts)
        g.charge([0, 1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(g.counts, before)

    def test_cost_of_inf_on_ineligible_symbol(self):
        g = RandomGeneratorPerfect(2, 1)
        g.observe(3)
        self.assertEqual(g.cost_of(3), math.inf)     # 3 is ahead of the deal
        self.assertEqual(g.charge([3, 3]), math.inf)  # documented v1 honesty


if __name__ == "__main__":
    unittest.main()
