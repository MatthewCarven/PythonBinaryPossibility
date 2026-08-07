"""The limits, as runnable code rather than claims.

    python randomness_demo.py

This project is about possibility spaces, and possibility spaces invite a
particular kind of overselling -- that marking bits `?` is somehow a way
to get data for free.  It isn't, and the honest thing is to be able to
show why rather than say why.

Four demonstrations, each of which prints numbers you can check:

1. **A trit costs more than a bit.** Describing a possibility space is
   larger than describing a state in it. The `?` is never the saving.
2. **The counting bound.** Almost no string can be compressed at all, and
   the fraction shrinks by half for every bit you hope to save.
3. **The PRNG paradox.** Data that defeats every general compressor, from
   a seed you can write on a napkin. "Incompressible" and "random" are
   not the same claim.
4. **Order is the whole story.** The same bytes, in two arrangements, land
   at opposite ends of what any compressor can do.

Standard library only.
"""

import gzip
import lzma
import math
import random
import struct

RULE = "─" * 68


def heading(number: int, title: str) -> None:
    print()
    print(RULE)
    print(f" {number}. {title}")
    print(RULE)


def demo_trit_cost() -> None:
    """A position that can be 0, 1 or ? costs log2(3) bits, not 1."""
    heading(1, "A possibility space is BIGGER than the thing it describes")
    trit = math.log2(3)
    print(f"  one bit  (0 or 1)      {1.0:.4f} bits")
    print(f"  one trit (0, 1 or ?)   {trit:.4f} bits")
    print(f"  overhead               {trit - 1:.1%}")
    print()
    for width in (8, 16, 64):
        print(f"  a {width:>2}-bit register costs {width * trit:>7.1f} bits "
              f"to write down, vs {width:>3} for a plain value")
    print()
    print("  So the ?s never save anything by themselves. Every win in")
    print("  compression comes from a model both ends already agree on,")
    print("  and the bits simply move into that model.")


def demo_counting_bound() -> None:
    """Pigeonhole: shorter descriptions than strings, so most strings have none."""
    heading(2, "Almost nothing can be compressed, and provably so")
    print("  There are 2^n strings of length n but far fewer shorter ones,")
    print("  so a lossless coder that shrinks some inputs must grow others.")
    print("  To save k bits you must land in a set of density 2^(1-k):")
    print()
    print(f"  {'save':>6}   {'at most this fraction of inputs can manage it':<46}")
    for k in (1, 4, 10, 21, 50):
        share = 2 ** (k - 1)
        print(f"  {k:>4} b   1 in {share:>44,}")
    print()
    print("  This is why 'compress anything to 32 bits' can never work --")
    print("  and why compressors target the structured minority instead.")


def demo_prng_paradox() -> None:
    """Data no compressor can touch, reproduced exactly from a tiny seed."""
    heading(3, "Incompressible is not the same as random")
    seed = 1
    count = 60000
    random.seed(seed)
    noise = [random.randint(-32000, 32000) for _ in range(count)]
    raw = b"".join(struct.pack("<h", v) for v in noise)

    gz = len(gzip.compress(raw, 9))
    xz = len(lzma.compress(raw, preset=9))
    recipe = f"random.seed({seed}); [random.randint(-32000,32000) for _ in range({count})]"

    print(f"  {count:,} samples of white noise")
    print()
    print(f"  raw                    {len(raw):>9,} bytes")
    print(f"  gzip -9                {gz:>9,} bytes   ({len(raw) / gz:.3f}x)")
    print(f"  lzma -9                {xz:>9,} bytes   ({len(raw) / xz:.3f}x)")
    print(f"  the line that made it  {len(recipe):>9,} bytes   "
          f"({len(raw) / len(recipe):,.0f}x)")
    print()
    print(f"      {recipe}")
    print()

    random.seed(seed)
    again = [random.randint(-32000, 32000) for _ in range(count)]
    print(f"  exact round-trip from the seed: "
          f"{'verified' if again == noise else 'FAILED'}")
    print()
    print("  Two of the best compressors ever written made this data")
    print("  BIGGER. Its actual description is one line. Unpredictable to")
    print("  a given method is a statement about the method, not the data.")


def demo_order_is_everything(bits: int = 16) -> None:
    """The same values, in two orders, at opposite extremes."""
    heading(4, "The same bytes, twice, at opposite extremes")
    values = list(range(2 ** bits))
    ordered = b"".join(struct.pack(">H", v) for v in values)
    shuffled_values = list(values)
    random.Random(42).shuffle(shuffled_values)
    shuffled = b"".join(struct.pack(">H", v) for v in shuffled_values)

    print(f"  Every {bits}-bit value exactly once: {len(ordered):,} bytes.")
    print("  Identical multiset both times. Identical histogram. No repeated")
    print("  value in either. Only the ORDER differs.")
    print()
    print(f"  {'':<12}{'gzip':>10}{'lzma':>10}")
    for label, blob in (("in order", ordered), ("shuffled", shuffled)):
        g = len(ordered) / len(gzip.compress(blob, 9))
        x = len(ordered) / len(lzma.compress(blob, preset=9))
        print(f"  {label:<12}{g:>9.2f}x{x:>9.2f}x")
    print()

    # The information-theoretic floor for any permutation, via Stirling.
    for width in (16, 32):
        n = 2 ** width
        stored = n * width
        content = stored - n * math.log2(math.e)
        print(f"  a permutation of all {width}-bit values: best possible "
              f"{stored / content:.4f}x  ({100 * (1 - content / stored):.1f}% removable)")
    print()
    print("  And seeded, that same 16 GiB shuffle is about fifty bytes.")
    print("  Same data, three answers -- decided entirely by what the")
    print("  decoder is already assumed to know. That IS compression.")


def main() -> None:
    print()
    print("  THE LIMITS")
    print("  What superposition, seeds and possibility spaces cannot do,")
    print("  demonstrated rather than asserted.")
    demo_trit_cost()
    demo_counting_bound()
    demo_prng_paradox()
    demo_order_is_everything()
    print()


if __name__ == "__main__":
    main()
