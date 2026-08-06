"""Tests for BinaryPossibility, BinaryRegister, and BinaryRegisterGroup."""

import unittest

from BinaryPossibility import BinaryPossibility, BinaryRegister, BinaryRegisterGroup


class TestBinaryPossibility(unittest.TestCase):
    def test_default_is_superposition(self):
        self.assertTrue(BinaryPossibility().is_superposition())

    def test_valid_states(self):
        for state in (0, 1, None):
            self.assertEqual(BinaryPossibility(state).state, state)

    def test_invalid_states_raise(self):
        for bad in (2, -1, "1", "0", [0]):
            with self.assertRaises(ValueError):
                BinaryPossibility(bad)
        possibility = BinaryPossibility()
        with self.assertRaises(ValueError):
            possibility.set_state(3)

    def test_set_state_and_collapse(self):
        possibility = BinaryPossibility()
        possibility.set_state(1)
        self.assertFalse(possibility.is_superposition())
        possibility.set_state(None)
        self.assertTrue(possibility.is_superposition())

    def test_str_forms(self):
        self.assertEqual(str(BinaryPossibility(None)), "Possibility: (0 & 1)")
        self.assertEqual(str(BinaryPossibility(0)), "Possibility: 0")
        self.assertEqual(str(BinaryPossibility(1)), "Possibility: 1")


class TestBinaryRegister(unittest.TestCase):
    def test_init_requires_positive_bits(self):
        for bad in (0, -3):
            with self.assertRaises(ValueError):
                BinaryRegister(bad)

    def test_starts_fully_superposed(self):
        register = BinaryRegister(4)
        self.assertEqual(len(register), 4)
        self.assertTrue(all(p.is_superposition() for p in register.get_individual_states()))

    def test_add_and_remove_bits(self):
        register = BinaryRegister(1)
        register.add_bit()
        self.assertEqual(len(register), 2)
        register.remove_bit()
        register.remove_bit()
        self.assertEqual(len(register), 0)
        with self.assertRaises(IndexError):
            register.remove_bit()

    def test_set_and_get_bit(self):
        register = BinaryRegister(3)
        register.set_bit(1, 0)
        self.assertEqual(register.get_bit(1), 0)
        self.assertIsNone(register.get_bit(0))
        with self.assertRaises(IndexError):
            register.set_bit(3, 1)
        with self.assertRaises(IndexError):
            register.get_bit(-1)
        with self.assertRaises(ValueError):
            register.set_bit(0, 5)

    def test_enumerate_states_known_cases(self):
        register = BinaryRegister(3)
        register.set_bit(0, 1)
        self.assertEqual(register.enumerate_states(), ["100", "101", "110", "111"])
        register.set_bit(1, 1)
        self.assertEqual(register.enumerate_states(), ["110", "111"])
        register.set_bit(0, None)
        register.set_bit(1, None)
        self.assertEqual(
            register.enumerate_states(),
            ["000", "001", "010", "011", "100", "101", "110", "111"],
        )

    def test_fully_collapsed_register_has_one_state(self):
        register = BinaryRegister(4)
        for index, state in enumerate((1, 0, 1, 1)):
            register.set_bit(index, state)
        self.assertEqual(register.enumerate_states(), ["1011"])
        self.assertEqual(register.calculate_possibility_count(), 1)

    def test_count_matches_enumeration_length(self):
        register = BinaryRegister(5)
        register.set_bit(0, 1)
        register.set_bit(3, 0)
        self.assertEqual(
            register.calculate_possibility_count(), len(register.enumerate_states())
        )

    def test_empty_register_semantics(self):
        register = BinaryRegister(1)
        register.remove_bit()
        self.assertEqual(register.calculate_possibility_count(), 0)
        self.assertEqual(register.enumerate_states(), [])

    def test_iter_states_is_lazy(self):
        register = BinaryRegister(3)
        iterator = register.iter_states()
        self.assertEqual(next(iterator), "000")
        self.assertEqual(next(iterator), "001")

    def test_large_register_streams_without_recursion(self):
        # Regression guard: the old recursive enumeration hit the recursion
        # limit near 1000 bits. 2000 collapsed bits + 2 superposed = 4 states.
        register = BinaryRegister(2000)
        for index in range(2000):
            register.set_bit(index, 1)
        register.set_bit(0, None)
        register.set_bit(1999, None)
        states = list(register.iter_states())
        self.assertEqual(len(states), 4)
        self.assertEqual(register.calculate_possibility_count(), 4)
        self.assertTrue(all(len(s) == 2000 for s in states))


class TestBinaryRegisterGroup(unittest.TestCase):
    def test_count_is_product_of_registers(self):
        group = BinaryRegisterGroup(BinaryRegister(2), BinaryRegister(3))
        self.assertEqual(group.calculate_possibility_count(), 32)

    def test_collapsing_reduces_count(self):
        reg_a, reg_b = BinaryRegister(2), BinaryRegister(3)
        group = BinaryRegisterGroup(reg_a, reg_b)
        reg_a.set_bit(0, 1)
        self.assertEqual(group.calculate_possibility_count(), 16)

    def test_enumerate_is_cartesian_product(self):
        reg_a, reg_b = BinaryRegister(1), BinaryRegister(1)
        reg_a.set_bit(0, 1)
        group = BinaryRegisterGroup(reg_a, reg_b)
        self.assertEqual(group.enumerate_states(), ["10", "11"])
        self.assertEqual(
            len(group.enumerate_states()), group.calculate_possibility_count()
        )

    def test_add_register(self):
        group = BinaryRegisterGroup(BinaryRegister(1))
        group.add_register(BinaryRegister(2))
        self.assertEqual(len(group), 2)
        self.assertEqual(group.calculate_possibility_count(), 8)

    def test_empty_group_has_single_empty_state(self):
        # Documented current behaviour: a group with no registers has one
        # (empty) combined state and a count of 1.
        group = BinaryRegisterGroup()
        self.assertEqual(group.enumerate_states(), [""])
        self.assertEqual(group.calculate_possibility_count(), 1)


if __name__ == "__main__":
    unittest.main()
