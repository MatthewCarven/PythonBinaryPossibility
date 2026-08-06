"""Render the possibility tree of a BinaryRegister.

Each level of the tree is one bit of the register, starting from bit 0 at
the top.  A collapsed bit contributes a single child (the tree passes
straight through it); a bit in superposition branches into 0 and 1.  Every
leaf is therefore one complete possible state of the register, and the
number of leaves always equals ``register.calculate_possibility_count()``.

Example for a 3-bit register with bit 0 collapsed to 1::

    (register: 1??)
    \\-- 1
        |-- 0
        |   |-- 0  => 100
        |   \\-- 1  => 101
        \\-- 1
            |-- 0  => 110
            \\-- 1  => 111

Output is plain ASCII on purpose, so it survives any terminal.
"""

from typing import Iterator, List, Optional

from BinaryPossibility import BinaryRegister


class _TreeNode:
    """One node of the possibility tree (internal)."""

    __slots__ = ("value", "children")

    def __init__(self, value: Optional[str]):
        self.value = value  # None for the root, "0" or "1" otherwise
        self.children: List["_TreeNode"] = []


class BinaryPossibilityTree:
    """The branching structure of a register's possibility space.

    Build it from a :class:`BinaryRegister`, then :meth:`render` it as
    ASCII art or walk its :meth:`leaves` (which match
    ``register.enumerate_states()`` exactly, in the same order).
    """

    def __init__(self, register: BinaryRegister, max_leaves: int = 64):
        """Build the tree for ``register``.

        ``max_leaves`` guards against accidentally building (and printing)
        an enormous tree: a register with k superposed bits has 2**k
        leaves.  Raise the limit deliberately if you really want a bigger
        tree.
        """
        count = register.calculate_possibility_count()
        if count > max_leaves:
            raise ValueError(
                f"This register has {count} possible states, more than "
                f"max_leaves={max_leaves}. Pass a higher max_leaves if you "
                f"really want a tree this big."
            )
        self._bits = "".join(
            "?" if p.is_superposition() else str(p.state)
            for p in register.get_individual_states()
        )
        self.root = _TreeNode(None)

        # Build level by level (no recursion, so register depth is unlimited).
        frontier = [self.root]
        for possibility in register.get_individual_states():
            if possibility.is_superposition():
                options = ("0", "1")
            else:
                options = (str(possibility.state),)
            next_frontier = []
            for node in frontier:
                for option in options:
                    child = _TreeNode(option)
                    node.children.append(child)
                    next_frontier.append(child)
            frontier = next_frontier

    def leaves(self) -> List[str]:
        """Return every complete state (one per leaf), in tree order.

        This always equals ``register.enumerate_states()`` for the register
        the tree was built from.
        """
        if not self._bits:
            return []
        results: List[str] = []
        # Iterative depth-first walk; children pushed in reverse so the
        # 0-branch is always explored before the 1-branch.
        stack = [(self.root, "")]
        while stack:
            node, path = stack.pop()
            if node.value is not None:
                path = path + node.value
            if not node.children:
                results.append(path)
                continue
            for child in reversed(node.children):
                stack.append((child, path))
        return results

    def iter_leaves(self) -> Iterator[str]:
        """Lazily yield every complete state (one per leaf), in tree order."""
        return iter(self.leaves())

    def render(self) -> str:
        """Render the tree as ASCII art and return it as a string.

        A run of nodes with single children is a collapsed (fixed) bit; a
        fork is a bit in superposition.  Leaves are annotated with the full
        state they represent.
        """
        lines = [f"(register: {self._bits or 'empty'})"]
        if not self._bits:
            return "\n".join(lines)

        # Iterative depth-first render carrying the drawing prefix.
        stack = []
        for index, child in enumerate(reversed(self.root.children)):
            is_last = index == 0  # reversed: first pushed is the last sibling
            stack.append((child, "", is_last, ""))
        while stack:
            node, prefix, is_last, path = stack.pop()
            path = path + (node.value or "")
            connector = "\\-- " if is_last else "|-- "
            annotation = f"  => {path}" if not node.children else ""
            lines.append(f"{prefix}{connector}{node.value}{annotation}")
            child_prefix = prefix + ("    " if is_last else "|   ")
            for index, child in enumerate(reversed(node.children)):
                child_is_last = index == 0
                stack.append((child, child_prefix, child_is_last, path))
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.render()


def render_possibility_tree(register: BinaryRegister, max_leaves: int = 64) -> str:
    """Convenience one-liner: build the tree for ``register`` and render it."""
    return BinaryPossibilityTree(register, max_leaves=max_leaves).render()
