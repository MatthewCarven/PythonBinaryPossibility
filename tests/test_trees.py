"""Tests for the possibility-tree renderer."""

import unittest

from BinaryPossibility import BinaryRegister
from binarypossibilitytrees import BinaryPossibilityTree, render_possibility_tree


def _register(pattern):
    """Build a register from a pattern string like '1??0' (? = superposition)."""
    register = BinaryRegister(len(pattern))
    for index, char in enumerate(pattern):
        register.set_bit(index, None if char == "?" else int(char))
    return register


class TestLeavesMatchEnumeration(unittest.TestCase):
    def test_leaves_equal_enumerate_states(self):
        for pattern in ("???", "1??", "10", "1", "?0?1?", "0000"):
            register = _register(pattern)
            tree = BinaryPossibilityTree(register)
            self.assertEqual(
                tree.leaves(),
                register.enumerate_states(),
                msg=f"pattern {pattern!r}",
            )

    def test_leaf_count_equals_possibility_count(self):
        register = _register("??1?")
        tree = BinaryPossibilityTree(register)
        self.assertEqual(len(tree.leaves()), register.calculate_possibility_count())

    def test_iter_leaves_matches_leaves(self):
        register = _register("1??")
        tree = BinaryPossibilityTree(register)
        self.assertEqual(list(tree.iter_leaves()), tree.leaves())


class TestRender(unittest.TestCase):
    def test_render_docstring_example_exactly(self):
        expected = (
            "(register: 1??)\n"
            "\\-- 1\n"
            "    |-- 0\n"
            "    |   |-- 0  => 100\n"
            "    |   \\-- 1  => 101\n"
            "    \\-- 1\n"
            "        |-- 0  => 110\n"
            "        \\-- 1  => 111"
        )
        self.assertEqual(render_possibility_tree(_register("1??")), expected)

    def test_str_is_render(self):
        tree = BinaryPossibilityTree(_register("?1"))
        self.assertEqual(str(tree), tree.render())

    def test_every_leaf_state_appears_in_render(self):
        register = _register("??")
        rendered = render_possibility_tree(register)
        for state in register.enumerate_states():
            self.assertIn(f"=> {state}", rendered)


class TestGuards(unittest.TestCase):
    def test_max_leaves_guard(self):
        register = BinaryRegister(7)  # 128 states > default max_leaves of 64
        with self.assertRaises(ValueError):
            BinaryPossibilityTree(register)
        tree = BinaryPossibilityTree(register, max_leaves=128)
        self.assertEqual(len(tree.leaves()), 128)

    def test_deep_collapsed_register_builds_and_renders(self):
        # 1500 collapsed bits: only one leaf, but 1500 levels deep. The
        # iterative build/render must not hit the recursion limit.
        register = BinaryRegister(1500)
        for index in range(1500):
            register.set_bit(index, index % 2)
        tree = BinaryPossibilityTree(register)
        self.assertEqual(len(tree.leaves()), 1)
        rendered = tree.render()
        self.assertEqual(len(rendered.splitlines()), 1501)  # header + one per bit


if __name__ == "__main__":
    unittest.main()
