"""Tests for per-bit probability, entropy, and likelihood-ordered enumeration."""

import itertools
import random
import time
import unittest

from BinaryPossibility import (
    BinaryPossibility,
    BinaryRegister,
    BinaryRegisterGroup,
    _binary_entropy,
)


def register_from(pattern, probabilities=None):
    """Build a register from '1?0?' plus optional per-index probabilities."""
    register = BinaryRegister(len(pattern))
    for index, char in enumerate(pattern):
        register.set_bit(index, None if char == "?" else int(char))
    for index, p in (probabilities or {}).items():
        register.set_bit_probability(index, p)
    return register


class TestBinaryEntropyHelper(unittest.TestCase):
    def test_fair_coin_is_exactly_one_bit(self):
        self.assertEqual(_binary_entropy(0.5), 1.0)

    def test_certainty_is_zero_bits(self):
        self.assertEqual(_binary_entropy(0.0), 0.0)
        self.assertEqual(_binary_entropy(1.0), 0.0)

    def test_symmetric_about_a_half(self):
        for p in (0.1, 0.25, 0.4):
            self.assertAlmostEqual(_binary_entropy(p), _binary_entropy(1 - p))

    def test_bias_always_lowers_entropy(self):
        values = [_binary_entropy(p) for p in (0.5, 0.4, 0.3, 0.2, 0.1)]
        self.assertEqual(values, sorted(values, reverse=True))


class TestPossibilityProbability(unittest.TestCase):
    def test_defaults_to_fair(self):
        self.assertEqual(BinaryPossibility().p, 0.5)
        self.assertTrue(BinaryPossibility().is_fair())

    def test_rejects_out_of_range(self):
        for bad in (-0.1, 1.1, 2):
            with self.assertRaises(ValueError):
                BinaryPossibility(None, bad)
        with self.assertRaises(ValueError):
            BinaryPossibility().set_probability("half")

    def test_probability_survives_collapse_and_resuperposition(self):
        possibility = BinaryPossibility(None, 0.8)
        possibility.set_state(1)
        self.assertEqual(possibility.p, 0.8)
        possibility.set_state(None)
        self.assertEqual(possibility.p, 0.8)

    def test_probability_of_value(self):
        possibility = BinaryPossibility(None, 0.7)
        self.assertAlmostEqual(possibility.probability_of(1), 0.7)
        self.assertAlmostEqual(possibility.probability_of(0), 0.3)
        possibility.set_state(0)
        self.assertEqual(possibility.probability_of(0), 1.0)
        self.assertEqual(possibility.probability_of(1), 0.0)
        with self.assertRaises(ValueError):
            possibility.probability_of(2)

    def test_entropy_of_a_single_bit(self):
        self.assertEqual(BinaryPossibility().entropy(), 1.0)
        self.assertEqual(BinaryPossibility(1).entropy(), 0.0)
        self.assertLess(BinaryPossibility(None, 0.9).entropy(), 1.0)

    def test_str_stays_quiet_when_fair(self):
        # Backwards compatibility: the old strings must not change.
        self.assertEqual(str(BinaryPossibility(None)), "Possibility: (0 & 1)")
        self.assertEqual(str(BinaryPossibility(0)), "Possibility: 0")

    def test_str_mentions_odds_when_biased(self):
        self.assertIn("p=0.80", str(BinaryPossibility(None, 0.8)))

    def test_collapse_honours_the_odds(self):
        possibility = BinaryPossibility(None, 0.25)
        rng = random.Random(1)
        hits = sum(possibility.collapse(rng) for _ in range(4000))
        self.assertAlmostEqual(hits / 4000, 0.25, delta=0.03)

    def test_collapse_of_a_decided_bit_is_certain(self):
        self.assertEqual(BinaryPossibility(1).collapse(random.Random(0)), 1)
        self.assertEqual(BinaryPossibility(0).collapse(random.Random(0)), 0)

    def test_extremes_are_allowed_and_certain(self):
        never = BinaryPossibility(None, 0.0)
        always = BinaryPossibility(None, 1.0)
        rng = random.Random(3)
        self.assertEqual({never.collapse(rng) for _ in range(200)}, {0})
        self.assertEqual({always.collapse(rng) for _ in range(200)}, {1})
        self.assertEqual(never.entropy(), 0.0)


class TestRegisterEntropy(unittest.TestCase):
    def test_the_pinning_identity(self):
        # The whole point: for fair bits, entropy and the possibility count
        # are the same statement in different currencies.
        for pattern in ("????", "1?0?", "1", "??????????", "1010"):
            register = register_from(pattern)
            self.assertEqual(
                2 ** register.entropy(),
                register.calculate_possibility_count(),
                msg=pattern,
            )

    def test_entropy_equals_superposed_count_when_fair(self):
        register = register_from("1??0?")
        self.assertEqual(register.entropy(), 3.0)

    def test_bias_lowers_entropy_but_not_the_count(self):
        register = register_from("???")
        before_count = register.calculate_possibility_count()
        before_entropy = register.entropy()
        register.set_bit_probability(0, 0.95)
        self.assertEqual(register.calculate_possibility_count(), before_count)
        self.assertLess(register.entropy(), before_entropy)

    def test_pinned_bit_has_no_entropy_but_still_counts(self):
        register = register_from("??")
        register.set_bit_probability(0, 1.0)
        self.assertEqual(register.calculate_possibility_count(), 4)
        self.assertEqual(register.entropy(), 1.0)

    def test_collapsed_register_has_zero_entropy(self):
        self.assertEqual(register_from("1010").entropy(), 0.0)

    def test_group_entropy_adds(self):
        group = BinaryRegisterGroup(register_from("??"), register_from("???"))
        self.assertEqual(group.entropy(), 5.0)
        self.assertEqual(2 ** group.entropy(), group.calculate_possibility_count())

    def test_is_fair(self):
        register = register_from("??")
        self.assertTrue(register.is_fair())
        register.set_bit_probability(1, 0.6)
        self.assertFalse(register.is_fair())

    def test_set_all_probabilities(self):
        register = register_from("???")
        register.set_all_probabilities(0.25)
        self.assertEqual([register.get_bit_probability(i) for i in range(3)],
                         [0.25] * 3)

    def test_probability_index_guards(self):
        register = register_from("??")
        with self.assertRaises(IndexError):
            register.set_bit_probability(5, 0.5)
        with self.assertRaises(IndexError):
            register.get_bit_probability(-1)


class TestProbabilityOfState(unittest.TestCase):
    def test_fair_register_is_uniform(self):
        register = register_from("???")
        for state in register.enumerate_states():
            self.assertAlmostEqual(register.probability_of_state(state), 0.125)

    def test_weighted_register(self):
        register = register_from("??", {0: 0.9, 1: 0.5})
        self.assertAlmostEqual(register.probability_of_state("10"), 0.45)
        self.assertAlmostEqual(register.probability_of_state("00"), 0.05)

    def test_impossible_state_under_a_decided_bit(self):
        # Bit 0 is pinned to 1, so any state starting 0 has probability 0.
        self.assertEqual(register_from("1?").probability_of_state("00"), 0.0)

    def test_rejects_bad_states(self):
        register = register_from("??")
        with self.assertRaises(ValueError):
            register.probability_of_state("000")
        with self.assertRaises(ValueError):
            register.probability_of_state("0x")


class TestLikelihoodOrdering(unittest.TestCase):
    def test_probabilities_come_out_non_increasing(self):
        register = register_from("?????", {0: 0.9, 2: 0.2, 4: 0.65})
        probabilities = [p for _, p in register.iter_states_by_likelihood()]
        self.assertEqual(probabilities, sorted(probabilities, reverse=True))

    def test_covers_exactly_the_same_states(self):
        register = register_from("1??0?", {1: 0.3})
        ordered = {state for state, _ in register.iter_states_by_likelihood()}
        self.assertEqual(ordered, set(register.enumerate_states()))

    def test_probabilities_sum_to_one(self):
        register = register_from("????", {0: 0.7, 3: 0.1})
        total = sum(p for _, p in register.iter_states_by_likelihood())
        self.assertAlmostEqual(total, 1.0)

    def test_agrees_with_probability_of_state(self):
        register = register_from("???", {1: 0.8})
        for state, probability in register.iter_states_by_likelihood():
            self.assertAlmostEqual(probability,
                                   register.probability_of_state(state))

    def test_likeliest_state_is_the_argmax(self):
        register = register_from("???", {0: 0.9, 1: 0.2, 2: 0.6})
        best = next(register.iter_states_by_likelihood())
        self.assertEqual(best[0], "101")

    def test_is_lazy_on_an_enormous_space(self):
        # 2**80 states; taking the top few must not enumerate them.
        register = BinaryRegister(80)
        register.set_all_probabilities(0.75)
        top = list(itertools.islice(register.iter_states_by_likelihood(), 4))
        self.assertEqual(len(top), 4)
        self.assertEqual(top[0][0], "1" * 80)
        self.assertGreater(top[0][1], top[-1][1])

    def test_impossible_states_come_last_at_zero(self):
        register = register_from("??", {0: 0.0})
        results = list(register.iter_states_by_likelihood())
        self.assertEqual([p for _, p in results][-2:], [0.0, 0.0])
        self.assertTrue(all(s.startswith("1") for s, p in results if p == 0.0))

    def test_fully_collapsed_yields_one_certain_state(self):
        self.assertEqual(
            list(register_from("101").iter_states_by_likelihood()), [("101", 1.0)]
        )

    def test_empty_register_yields_nothing(self):
        register = BinaryRegister(1)
        register.remove_bit()
        self.assertEqual(list(register.iter_states_by_likelihood()), [])

    def test_matches_brute_force_on_randomised_registers(self):
        """The strongest guarantee available: agree with the obvious method.

        Small enough to enumerate and sort directly, random enough to hit
        collapsed bits, pinned bits, ties and extremes.
        """
        rng = random.Random(0)
        for trial in range(200):
            width = rng.randint(1, 6)
            register = BinaryRegister(width)
            for index in range(width):
                if rng.random() < 0.3:
                    register.set_bit(index, rng.choice([0, 1]))
                else:
                    register.set_bit_probability(
                        index, rng.choice([0.0, 0.1, 0.5, 0.77, 1.0])
                    )
            produced = list(register.iter_states_by_likelihood())
            expected = sorted(
                ((state, register.probability_of_state(state))
                 for state in register.enumerate_states()),
                key=lambda pair: -pair[1],
            )
            self.assertEqual({s for s, _ in produced}, {s for s, _ in expected},
                             msg=f"coverage, trial {trial}")
            for (_, got), (_, want) in zip(produced, expected):
                self.assertAlmostEqual(got, want, places=12,
                                       msg=f"probability, trial {trial}")

    def test_stays_fast_on_a_huge_space(self):
        """Regression guard for the A* heuristic.

        Ranking on cost-so-far alone is admissible but explores the tree
        exponentially; without the best-completion estimate this test hangs
        rather than failing, which is exactly how the bug was found.
        """
        register = BinaryRegister(200)
        register.set_all_probabilities(0.6)
        start = time.perf_counter()
        top = list(itertools.islice(register.iter_states_by_likelihood(), 5))
        elapsed = time.perf_counter() - start
        self.assertEqual(len(top), 5)
        self.assertLess(elapsed, 5.0, "likelihood ordering lost its heuristic")


class TestWeightedCollapse(unittest.TestCase):
    def test_collapse_is_seeded_and_reproducible(self):
        register = register_from("?????")
        self.assertEqual(register.collapse(seed=5), register.collapse(seed=5))

    def test_collapse_respects_decided_bits(self):
        register = register_from("1?0")
        for seed in range(20):
            state = register.collapse(seed=seed)
            self.assertEqual(state[0], "1")
            self.assertEqual(state[2], "0")

    def test_collapse_does_not_mutate(self):
        register = register_from("1??")
        register.collapse(seed=1)
        self.assertIsNone(register.get_bit(1))

    def test_collapse_converges_to_the_odds(self):
        register = register_from("?", {0: 0.2})
        hits = sum(int(register.collapse(seed=s)) for s in range(3000))
        self.assertAlmostEqual(hits / 3000, 0.2, delta=0.03)

    def test_fair_collapse_is_balanced(self):
        register = register_from("?")
        hits = sum(int(register.collapse(seed=s)) for s in range(3000))
        self.assertAlmostEqual(hits / 3000, 0.5, delta=0.03)

    def test_group_collapse_returns_one_string_per_register(self):
        group = BinaryRegisterGroup(register_from("??"), register_from("???"))
        result = group.collapse(seed=2)
        self.assertEqual([len(s) for s in result], [2, 3])
        self.assertTrue(all(set(s) <= {"0", "1"} for s in result))


class TestBackwardsCompatibility(unittest.TestCase):
    """The whole point of defaulting p to 0.5: nothing old should notice."""

    def test_default_registers_are_entirely_fair(self):
        self.assertTrue(BinaryRegister(8).is_fair())

    def test_counts_are_untouched_by_the_new_machinery(self):
        register = BinaryRegister(5)
        register.set_bit(0, 1)
        self.assertEqual(register.calculate_possibility_count(), 16)
        self.assertEqual(len(register.enumerate_states()), 16)

    def test_numeric_iteration_order_is_unchanged(self):
        register = register_from("1??")
        self.assertEqual(register.enumerate_states(), ["100", "101", "110", "111"])

    def test_entropy_of_a_default_register_is_its_width(self):
        self.assertEqual(BinaryRegister(7).entropy(), 7.0)


if __name__ == "__main__":
    unittest.main()
