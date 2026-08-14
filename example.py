"""Tour of PythonBinaryPossibility: registers, groups, trees, glitching,
sound, and balanced randomness.

Run it with ``python example.py``. For the clickable version, ``python bench.py``.
"""

import random

from BinaryPossibility import BinaryRegister, BinaryRegisterGroup
from binarypossibilitytrees import render_possibility_tree
from BinaryGlitch import BinaryGlitch
from BinaryRandom import RandomGeneratorPerfect
from PsynthRack import PsynthRack, Track, Voice
from BinaryEntropy import BinaryEntropy

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

# ---------------------------------------------------------------
# 5. Weighted possibilities: what's likely, not just what's possible
# ---------------------------------------------------------------
print()
print("A ? is a fair coin until you weight it.")
weighted = BinaryRegister(3)
print(f"  fair:   {weighted.calculate_possibility_count()} states, "
      f"{weighted.entropy():.2f} bits of uncertainty  "
      f"(2**{weighted.entropy():.0f} = {2 ** weighted.entropy():.0f}, they agree)")
weighted.set_bit_probability(0, 0.95)
weighted.set_bit_probability(1, 0.90)
print(f"  weighted: {weighted.calculate_possibility_count()} states still possible, "
      f"but only {weighted.entropy():.2f} bits of uncertainty")
print()
print("  Most likely first -- the states, and their odds:")
for state, probability in weighted.iter_states_by_likelihood():
    print(f"    {state}   {probability:.4f}")
print()
print("  Counting says what could happen; entropy says what probably will.")

# Measuring, rather than choosing, where the ?s go.
print()
print("Measured from data instead of chosen -- a stream of 11?? records:")
observed = [0b1100 | (index & 0b0011) for index in range(1000)]
print("  " + BinaryEntropy.describe(observed, 4, name="stream").replace("\n", "\n  "))

# ---------------------------------------------------------------
# 6. Psynthrack: superposition you can hear
# ---------------------------------------------------------------
print()
print("A step sequencer whose undecided steps make undecided music:")
rack = PsynthRack.demo_rack()
rack.superpose_random(5, seed=11)
for track in rack.tracks:
    print(f"  {track.voice.name:<6} {track.pattern()}")
print(f"  -> {rack.superposed_step_count()} steps undecided, "
      f"{rack.possibility_count():,} possible songs")

print()
print("Collapsing the same rack three ways (only the hats and bass move):")
for take, seed in enumerate((1, 2, 3), start=1):
    patterns = rack.collapse(seed=seed)
    filename = rack.write_wav(f"psynthrack_take{take}.wav", patterns)
    print(f"  take {take}: {patterns[2]}  ->  {filename}")
print("Play those three files -- same pattern, three different songs.")

# ---------------------------------------------------------------
# 7. Balanced randomness: spending bits to buy evenness
# ---------------------------------------------------------------
print()
print("A free coin clumps; RandomGeneratorPerfect deals from a bag instead:")
bag = RandomGeneratorPerfect(width=2, order=1, rng=random.Random(6))
stream = bag.take(12)
print(f"  order=1 at width 2: {stream}")
print(f"  every 4 draws is a permutation of 0..3, spread stays <= 1")
bits = bag.charge(stream)
print(f"  and describing those 12 draws costs exactly {bits:.4f} bits")
print(f"  (3 rounds x log2(4!) -- the charge IS the process)")
print()
print("The same bag makes drum bars land evenly -- collapse(balanced=True):")
bar = PsynthRack(Track(Voice("hat", frequency=8000.0, waveform="noise",
                             decay=0.06), "?" * 16))
coin_hits = [bar.collapse(seed=s)[0].count("1") for s in range(5)]
bag_hits = [bar.collapse(seed=s, balanced=True)[0].count("1") for s in range(5)]
print(f"  a 16-step bar, every step a fair ?:")
print(f"  five coin collapses hit {coin_hits} times -- they wander")
print(f"  five bag  collapses hit {bag_hits} times -- every bar, its share")
