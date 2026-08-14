"""E4 — the generator as predictor: the admission test.

    python -m benchmarks.e4

`ideas.md` sets one admission bar for every generator: *it earns a packet
type only if it lowers the residual against the predictor already there.*
The predictor already there is predict-and-cancel plus a describer (rice /
register / bit-tree, `benchmarks/coders.py`), and the corpus already holds
the class the balance model claims: `enum/ordered` and `enum/shuffled`, a
full 16-bit alphabet each value exactly once — which IS one complete round
of `RandomGeneratorPerfect` at width 16.

`PLAN-generators.md` predicted this would be "the best case measured all
project, and if it isn't, something in the framing is wrong."

Three questions, answered with controls:

1. Does the balance packet lower the total on the enumeration class,
   against every incumbent at once?  (§1 — the admission table.)
2. What does imperfection do at word width — does E3's window story
   replay?  (§2, §3 — and the answer sharpened E3's own finding.)
3. What happens when the packet is pointed at data it has no business
   with?  (§4 — the row that refused to lose, and why that is a warning
   rather than a win.)

The models are the shipped library (`BinaryRandom.RandomGeneratorPerfect`,
charging exactly as a decoder would) and `benchmarks/balance.py`'s
instrumented equivalents; §0 confirms the two agree to floating point.
Every choice of parameter grid is paid for at log2(len(grid)) bits, once.
Standard library only.
"""

import math
import os
import random
import struct
import sys

try:
    from benchmarks.balance import (
        Order0Coder, RunningBalance, charge as model_charge, log2fact, toolbox,
    )
    from benchmarks.coders import predict_then_bits, residuals, to_signed, zigzag
    from benchmarks.corpus import enumeration_items
except ImportError:                                    # run as a plain script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.dirname(sys.path[0]))
    from balance import (
        Order0Coder, RunningBalance, charge as model_charge, log2fact, toolbox,
    )
    from coders import predict_then_bits, residuals, to_signed, zigzag
    from corpus import enumeration_items

from BinaryRandom import RandomGeneratorPerfect

RULE = "-" * 78
BITS = 16
A = 1 << BITS
RAW = A * BITS


def heading(t):
    print()
    print(RULE)
    print(f" {t}")
    print(RULE)


def ratio(bits):
    return RAW / bits


print("E4 — the generator as predictor. The admission bar, from ideas.md:")
print("a generator earns a packet type only if it lowers the residual against")
print("the predictor already there. The claimed class: enumerations.")

# =======================================================================
heading("0. THE IDENTITY AT CORPUS SCALE — the packet's price is a theorem")

items = {i.name: i for i in enumeration_items(BITS)}
ordered = items["enum/ordered"].records
shuffled = items["enum/shuffled"].records

ideal = RandomGeneratorPerfect.ideal_bits(BITS, 1, A)
model = RandomGeneratorPerfect(BITS, 1)          # order=1, window=0
charge_shuffled = model.charge(shuffled)
charge_ordered = model.charge(ordered)
with_escape = model.charge(shuffled, escape=True)
instrumented, miss = model_charge(shuffled, RunningBalance, width=BITS, order=1)

print(f"  log2(A!) closed form        {ideal:>13,.1f} bits   ceiling {ratio(ideal):.4f}x")
print(f"  charge(enum/shuffled)       {charge_shuffled:>13,.1f} bits   delta {charge_shuffled - ideal:+.1e}")
print(f"  charge(enum/ordered)        {charge_ordered:>13,.1f} bits   identical: order-blind")
print(f"  escape overhead when clean  {with_escape - charge_shuffled:>13.2f} bits   (= log2(A+1) = {math.log2(A + 1):.2f})")
print(f"  library vs instrumented     agree to {abs(with_escape - instrumented):.1e} bits, miss rate {miss:.1%}")
print()
print("  A full-alphabet permutation IS one round of the bag, so its charge is")
print("  log2(A!) exactly, for ANY order of the values — the coder is the")
print("  process, now at corpus scale rather than in a unit test.")

# =======================================================================
heading("1. THE ADMISSION TABLE — every incumbent, both enumerations")

print(f"  {'model':<26}{'enum/ordered':>14}{'enum/shuffled':>15}")
rows = []
for name, fn in (
    ("gzip -9", lambda item: len(__import__('gzip').compress(item.raw_bytes, 9)) * 8),
    ("lzma -9", lambda item: len(__import__('lzma').compress(item.raw_bytes, preset=9)) * 8),
    ("bz2 -9", lambda item: len(__import__('bz2').compress(item.raw_bytes, 9)) * 8),
    ("predict+rice", lambda item: predict_then_bits(item, "rice")),
    ("predict+reg-persist", lambda item: predict_then_bits(item, "register-persist")),
    ("predict+bittree", lambda item: predict_then_bits(item, "bittree")),
    ("word order-0 (control)", lambda item: model_charge(item.records, Order0Coder, width=BITS)[0]),
    ("balance packet (ours)", lambda item: RandomGeneratorPerfect(BITS, 1).charge(item.records, escape=True)),
):
    row = [fn(items["enum/ordered"]), fn(items["enum/shuffled"])]
    rows.append((name, row))
    print(f"  {name:<26}{ratio(row[0]):>13.4f}x{ratio(row[1]):>14.4f}x")
print(f"  {'permutation ceiling':<26}{ratio(ideal):>13.4f}x{ratio(ideal):>14.4f}x")

best_incumbent_shuffled = min(bits for name, row in rows[:-1] for bits in [row[1]])
balance_shuffled = rows[-1][1][1]
print()
print(f"  On enum/ordered the incumbents already win (best here "
      f"{max(ratio(row[0]) for _, row in rows[:-1]):.2f}x) and the packet is redundant.")
print(f"  On enum/shuffled every incumbent reads nothing or worse "
      f"(best {ratio(best_incumbent_shuffled):.4f}x)")
print(f"  and the balance packet reads {ratio(balance_shuffled):.4f}x — the ceiling, minus 16 bits")
print(f"  of escape. It is the only model in the building that sees a shuffled")
print(f"  permutation. Saving over the best incumbent: "
      f"{(best_incumbent_shuffled - balance_shuffled) / 1024 / 8:,.1f} KB of {RAW / 1024 / 8:,.0f} KB.")
print()
print("  The packet decision costs 1 bit per stream (choice of 2, paid):")
for name in ("enum/ordered", "enum/shuffled"):
    incumbent = min(row[0 if name == "enum/ordered" else 1] for _, row in rows[:-1])
    packet = rows[-1][1][0 if name == "enum/ordered" else 1]
    chosen = min(incumbent, packet) + 1.0
    which = "incumbent" if incumbent < packet else "BALANCE"
    print(f"    {name:<15} chooses {which:<9} -> {ratio(chosen):.4f}x")

# =======================================================================
heading("2. THE NEAR-PERMUTATION — 2% substituted, one round (N = A)")

print("  Real enumeration-shaped data will not be a perfect permutation. At")
print("  byte width, E3 said imperfection demands a window. Here N = A — the")
print("  file IS one round — and the story inverts:")
print()
print(f"  {'model on 2%-substituted shuffled enum':<44}{'ratio':>9}{'miss':>7}")
rng = random.Random(2)
perturbed = [rng.randrange(A) if rng.random() < 0.02 else v for v in shuffled]
WINDOW_GRID = (0, 256, 4096)          # paid: log2(3) bits, once
for window in WINDOW_GRID:
    bits, miss = model_charge(perturbed, RunningBalance, width=BITS, order=1) \
        if window == 0 else (RandomGeneratorPerfect(BITS, 1, window).charge(perturbed, escape=True), float("nan"))
    label = f"order=1, window={window}" + ("  (running counts)" if window == 0 else "")
    miss_text = f"{miss:.1%}" if miss == miss else "—"
    print(f"  {label:<44}{ratio(bits):>8.4f}x{miss_text:>7}")
bits2, _ = model_charge(perturbed, RunningBalance, width=BITS, order=2)
print(f"  {'order=2, window=0':<44}{ratio(bits2):>8.4f}x{'—':>7}")
kept = (ratio(RandomGeneratorPerfect(BITS, 1).charge(perturbed, escape=True)) - 1) / (ratio(ideal) - 1)
print()
print(f"  Running counts keep {kept:.0%} of the available saving at 2% — almost")
print("  exactly E3's 82% — and every window DESTROYS the structure instead of")
print("  protecting it. No contradiction with E3: E3's laggard trap needs the")
print("  minimum count to advance, and in a single round it never does. The")
print("  window's job is to separate rounds; one round needs none.")

# =======================================================================
heading("3. THE ROUND IS THE WINDOW — width 12, four rounds (N = 4A)")

BITS2, ROUNDS = 12, 4
A2 = 1 << BITS2
N2 = ROUNDS * A2
RAW2 = N2 * BITS2
clean = RandomGeneratorPerfect(BITS2, 1, rng=random.Random(5)).take(N2)
exact = ROUNDS * log2fact(A2)
for window in (0, A2):
    charged = RandomGeneratorPerfect(BITS2, 1, window).charge(clean)
    print(f"  clean 4-round bag output, window={window:<6} {RAW2 / charged:.4f}x   "
          f"exact vs 4*log2(A!): {abs(charged - exact) < 1e-6}")
print()
print(f"  {'2%-substituted, seeds 3/4/5':<40}{'ratio (median of 3)':>20}")
WINDOW_GRID2 = (0, A2 // 2, A2, 2 * A2)   # paid: 2 bits, once
results = {}
for window in WINDOW_GRID2:
    ratios = []
    for seed in (3, 4, 5):
        rng = random.Random(seed)
        pert = [rng.randrange(A2) if rng.random() < 0.02 else v for v in clean]
        ratios.append(RAW2 / RandomGeneratorPerfect(BITS2, 1, window).charge(pert, escape=True))
    ratios.sort()
    results[window] = ratios[1]
    label = {0: "window=0  (running counts — E3's v1)",
             A2 // 2: f"window=A/2 ({A2 // 2})",
             A2: f"window=A   ({A2})  — ONE ROUND",
             2 * A2: f"window=2A  ({2 * A2})"}[window]
    print(f"  {label:<40}{ratios[1]:>19.4f}x")
rng = random.Random(3)
pert = [rng.randrange(A2) if rng.random() < 0.02 else v for v in clean]
o2bits, _ = model_charge(pert, RunningBalance, width=BITS2, order=2)
o0bits, _ = model_charge(pert, Order0Coder, width=BITS2)
print(f"  {'order=2, window=0 (softening, not the fix)':<40}{RAW2 / o2bits:>19.4f}x")
print(f"  {'word order-0 (blind control)':<40}{RAW2 / o0bits:>19.4f}x")
print()
print("  Multi-round imperfect data replays E3's collapse exactly — running")
print("  counts fall BELOW 1.0 once the minimum starts advancing — and the fix")
print("  is not 'a window' but a specific one: ONE ALPHABET'S WORTH. Half a")
print("  round forfeits the exhaustion; two rounds re-admit the trap inside")
print("  each window. Which reprices E3's own result: its winning window=256")
print("  at width 8 was never an arbitrary grid point. 256 WAS the alphabet.")
print("  One rule covers both experiments: the model lives at round scale,")
print("  window = A per round of data, 0 when the file is a single round.")

# =======================================================================
heading("4. THE ROW THAT REFUSED TO LOSE — balance pointed at residuals")

values = to_signed(ordered, BITS)
resid = [zigzag(v) for v in residuals(values, 1)]
n = len(resid)
width = max(v.bit_length() for v in resid)
raw_resid = n * width
bal_bits, bal_miss = model_charge(resid, RunningBalance, width=width, order=1)
o0_bits, _ = model_charge(resid, Order0Coder, width=width)
lzma_blob = b"".join(struct.pack("<I", v) for v in resid)
lzma_bits = len(__import__("lzma").compress(lzma_blob, preset=9)) * 8

print("  Ordered-enum residuals after predict-and-cancel: constant 2s with one")
print(f"  spike at the sign wraparound — width {width}, as peaked as data gets.")
print("  Balance should have no business here. And yet:")
print()
print(f"    balance packet     {raw_resid / bal_bits:>9.1f}x   at a {bal_miss:.1%} miss rate")
print(f"    word order-0       {raw_resid / o0_bits:>9.1f}x   (Laplace prior 2^{width} — over-smoothed)")
print(f"    lzma on the bytes  {raw_resid / lzma_bits:>9.1f}x   the actual incumbent")
print()
print("  DO NOT BANK THE 13x. At a 100% miss rate the model never once used its")
print("  eligible set: every symbol went through the escape, whose miss cost")
print("  log2(A - |eligible|) is ~0 bits when exactly one value is over quota.")
print("  The escape has degenerated into a repeat-the-hot-value coder — the")
print("  E3 audio footnote's hot/cold split, reproduced on demand — and the")
print("  fair frequency baseline it embarrasses is over-smoothed at this width.")
print("  Against the real incumbent it is 58x short. Rule, restated from E3 and")
print("  now with a clean example: a balance CODER can post a ratio while the")
print("  balance MODEL is dead. Quote the miss rate or quote nothing. The aged")
print("  local frequency baseline stays the open item that settles audio.")

# =======================================================================
heading("5. CONTROLS — if these misbehave, everything above is fiction")

rng = random.Random(9)
uniform = [rng.randrange(A) for _ in range(A)]
uni = RandomGeneratorPerfect(BITS, 1).charge(uniform, escape=True)
print(f"  uniform 16-bit noise through the packet   {ratio(uni):.4f}x   (must be ~<= 1)")
seeds = []
for seed in (7, 8, 9):
    rng = random.Random(seed)
    p = [rng.randrange(A) if rng.random() < 0.02 else v for v in shuffled]
    seeds.append(ratio(RandomGeneratorPerfect(BITS, 1).charge(p, escape=True)))
print(f"  seed stability, 2% x 3 seeds              {min(seeds):.4f}–{max(seeds):.4f}x  spread {max(seeds) - min(seeds):.4f}")
tb = toolbox(items["enum/shuffled"].raw_bytes)
print(f"  toolbox on enum/shuffled                  gzip {tb['gzip']:.4f}x  lzma {tb['lzma']:.4f}x  bz2 {tb['bz2']:.4f}x")
print(f"  ideal_bits vs randomness_demo ceiling     "
      f"{RAW / ideal:.4f}x vs {BITS / (BITS - math.log2(math.e)):.4f}x")

# =======================================================================
heading("VERDICT")

print("  The plan predicted E4 would be the best case measured all project.")
print("  It is — precisely bounded:")
print()
print("  * ADMITTED, for the enumeration class. On a shuffled full-alphabet")
print(f"    permutation the packet reads {ratio(balance_shuffled):.4f}x where every incumbent —")
print("    gzip, lzma, bz2, rice, register, bit-tree — reads 0.93–1.00x. It is")
print("    the first corpus item where the balance model beats ALL incumbents,")
print("    it does so at the theoretical ceiling exactly, and the win survives")
print("    2% dirt at 80% strength. Structured near-permutation data (dealt")
print("    records, round-robin logs, id sweeps) is the packet's home ground.")
print("  * The window law unifies: window = one round (A symbols), 0 for")
print("    single-round files. E3's 256 was the alphabet all along.")
print("  * NOT a residual describer. The 13x in §4 is the escape degenerating")
print("    into a frequency split at 100% miss — a warning shot for the audio")
print("    row, not a result. The narrow §7 claim of the plan stands verbatim.")
print()
print("  Kill criteria, assessed:")
print("  * 'Balance model fails to lower the residual on the enumeration")
print("    class' — NOT triggered: lowered by ~9% where nothing else moves.")
print("  * 'An incumbent already captures it' — NOT triggered: best incumbent")
print("    on enum/shuffled is 1.0007x (bz2, noise).")
print("  * 'Only wins on its own output' — NOT triggered: enum/shuffled is a")
print("    corpus item that predates the generator by two design threads.")
