"""Tour of PythonBinaryPossibility: registers, groups, trees, and glitching."""

from BinaryPossibility import BinaryRegister, BinaryRegisterGroup
from binarypossibilitytrees import render_possibility_tree
from BinaryGlitch import BinaryGlitch

# ---------------------------------------------------------------
# 1. A single register: collapse bits, watch the possibility space
# ---------------------------------------------------------------
br = BinaryRegister(3)
print("1,None,None")
br.set_bit(0, 1)
for state in br.enumerate_states():
    print(state)

print("1,1,None")
br.set_bit(1, 1)
for state in br.enumerate_states():
    print(state)

print("None,None,None")
br.set_bit(0, None)
br.set_bit(1, None)
for state in br.enumerate_states():
    print(state)

# ---------------------------------------------------------------
# 2. Register groups: possibility spaces multiply
# ---------------------------------------------------------------
reg_a = BinaryRegister(2)  # 2 bits
reg_b = BinaryRegister(3)  # 3 bits

group = BinaryRegisterGroup(reg_a, reg_b)

# Mathematical count -- immediate, no iteration.
# Initially: 2 bits (4 states) * 3 bits (8 states) = 32 possibilities
print(f"Total Possibilities: {group.calculate_possibility_count()}")

# Collapse a bit in one register to halve the space.
reg_a.set_bit(0, 1)
print(f"New Total: {group.calculate_possibility_count()}")

print(str(group.enumerate_states()))

# ---------------------------------------------------------------
# 3. Possibility trees: see the space branch
# ---------------------------------------------------------------
print()
print("The possibility tree of a register '1??':")
tree_register = BinaryRegister(3)
tree_register.set_bit(0, 1)
print(render_possibility_tree(tree_register))

# ---------------------------------------------------------------
# 4. Glitching: superpose bits of real data
# ---------------------------------------------------------------
print()
print("Glitching the text 'Hi' by superposing the low two bits of 'H':")
glitched = BinaryGlitch.register_from_text("Hi")
BinaryGlitch.superpose(glitched, 6, 7)
print(f"  {BinaryGlitch.variant_count(glitched)} variants:", end=" ")
print(", ".join(repr(v) for v in BinaryGlitch.iter_variant_texts(glitched)))

print("A seeded random glitch of 'Hello' (3 bits of superposition):")
for variant in BinaryGlitch.glitch_text("Hello", 3, seed=42):
    print(f"  {variant!r}")
