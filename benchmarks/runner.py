"""Run every coder over every corpus item and report honestly.

    python -m benchmarks.runner
    python -m benchmarks.runner --enum-bits 18 myfile.wav other.bin

Phase 1 of PLAN-compression.md. This does not build a codec; it decides
whether one is worth building, against kill criteria that were written down
*before* the numbers existed.
"""

import argparse
import sys
import time
from typing import Dict, List

from benchmarks import coders, corpus

#: Written into PLAN-compression.md in advance. Checked, not negotiated.
KILL_CRITERIA = [
    ("loses to FLAC on every real audio item by a wide margin",
     "stop: record the finding, do not build the codec"),
    ("only ever wins on synthetic or unusually sparse signals",
     "stop: the win was an artefact, say so in the README"),
    ("wins narrowly but never beats plain Rice-coded residuals",
     "stop: the register is decoration on a conventional codec"),
    ("'compresses' shuffled enumeration by more than ~1.05x",
     "bug: that ceiling is a theorem, not an opinion"),
]

NOT_KILL_CRITERIA = [
    "losing on text -- expected, in the corpus to stay visible",
    "slight expansion of incompressible input -- every codec does this",
]


def measure(item, verbose=True) -> Dict[str, float]:
    """Every coder against one item. Returns name -> ratio (raw / coded)."""
    raw = item.raw_bits
    results = {}
    for name, function, _ in coders.BASELINES:
        try:
            bits = function(item)
        except Exception as error:            # a baseline failing is data
            if verbose:
                print(f"      {name} failed: {error}", file=sys.stderr)
            bits = None
        if bits:
            results[name] = raw / bits
    for name, function, _ in coders.MODELS:
        bits = function(item)
        results[name] = raw / bits if bits > 0 else float("inf")
    return results


def format_table(rows: List, columns: List[str]) -> str:
    """A plain fixed-width table; the winner of each row marked with *.

    Rows are (name, results, flag). The flag marks corpus items whose
    quality makes them unfit for the verdict -- they still print, so the
    limitation is visible instead of quietly dropped.
    """
    name_width = max(len(name) for name, _, _ in rows) + 3
    head = " " * name_width + "".join(f"{c:>17}" for c in columns)
    lines = [head, "-" * len(head)]
    for name, results, flag in rows:
        best = max((v for v in results.values() if v is not None), default=0)
        cells = ""
        for column in columns:
            value = results.get(column)
            if value is None:
                cells += f"{'—':>17}"
            else:
                mark = "*" if value == best else " "
                cells += f"{value:>15.2f}x{mark}"
        label = f"{name}{'  !' if flag else ''}"
        lines.append(f"{label:<{name_width}}" + cells)
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="extra files to include")
    parser.add_argument("--enum-bits", type=int, default=16,
                        help="width of the enumeration cases (16 = 128KB)")
    parser.add_argument("--root", default=".", help="where to find text")
    parser.add_argument("--quick", action="store_true",
                        help="skip the slowest items")
    args = parser.parse_args(argv)

    print()
    print("=" * 78)
    print(" PHASE 1 BENCHMARK — does the possibility register earn its place?")
    print("=" * 78)
    print()
    print(" Three ways to describe the same residual:")
    print("   predict+rice     no probabilities, geometric assumption   (FLAC)")
    print("   predict+register one probability per bit POSITION         (OURS)")
    print("   predict+bittree  one probability per tree NODE            (LZMA)")
    print()
    print(" Baselines are ACTUAL bytes, containers included.")
    print(" Models are analytic code lengths and pay no container cost,")
    print(" so they are flattered by a few hundred bytes of framing.")
    print()

    items = corpus.default_corpus(args.root, args.enum_bits)
    items += corpus.user_items(args.files)
    if args.quick:
        items = [i for i in items if len(i.records) <= 70000]

    columns = [n for n, _, _ in coders.BASELINES] + [n for n, _, _ in coders.MODELS]
    by_kind: Dict[str, List] = {}
    started = time.time()

    notes = []
    excluded = 0
    for item in items:
        print(f"  measuring {item.name} "
              f"({len(item.records):,} x {item.width}b) …", flush=True)
        flag = not item.full_depth
        excluded += flag
        by_kind.setdefault(item.kind, []).append(
            (item.name, measure(item), flag)
        )
        notes.append((item.name, item.note))

    print()
    for kind in ("audio", "records", "text", "enum", "user"):
        if kind not in by_kind:
            continue
        print()
        print(f"### {kind.upper()}")
        print(format_table(by_kind[kind], columns))

    if excluded:
        print()
        print(f"  ! {excluded} audio item(s) are 8-bit inside a 16-bit "
              f"container. Byte-oriented compressors")
        print("    exploit that for free while sample-oriented models cannot,")
        print("    so these rows are shown but EXCLUDED from the verdict:")
        for name, note in notes:
            if "REDUCED DEPTH" in note:
                print(f"      {name:<20} {note}")

    print()
    print("  Corpus notes:")
    for name, note in notes:
        if "REDUCED DEPTH" not in note:
            print(f"    {name:<20} {note}")

    measured = {}
    for rows in by_kind.values():
        for name, results, _ in rows:
            measured[name] = results

    print()
    print(f"  ({time.time() - started:.1f}s)")
    print()
    component_tradeoff(items, measured)
    verdict(by_kind)
    return 0


def component_tradeoff(items, measured=None) -> None:
    """The question that actually matters: what does the register COST?

    Ratio alone says the bit-tree wins everywhere. Ratio per unit of model
    state says something much more useful.
    """
    print("=" * 78)
    print(" COMPONENT TRADE-OFF — describing a W-bit residual")
    print("=" * 78)
    print()
    print("   rice      1 parameter    | register  W parameters"
          " | bit-tree  2**W nodes")
    print()
    print(f"  {'item':<20}{'rice':>9}{'register':>11}{'bit-tree':>11}"
          f"{'reg state':>11}{'tree state':>16}")
    print("  " + "-" * 76)

    chosen = [i for i in items
              if i.kind in ("audio", "records", "enum") and i.full_depth
              and "seeded" not in i.name]
    for item in chosen:
        raw = item.raw_bits
        # Reuse what the tables already measured; recomputing here doubled
        # the runtime of a long sweep for no new information.
        cached = (measured or {}).get(item.name, {})
        row = {}
        for describe, column in (("rice", "predict+rice"),
                                 ("register", "predict+register"),
                                 ("bittree", "predict+bittree")):
            row[describe] = cached.get(column) or (
                raw / coders.predict_then_bits(item, describe)
            )
        reg_state = coders.model_state(item, "register")
        tree_state = coders.model_state(item, "bittree")
        tree_text = f"{tree_state:,}" if tree_state < 10 ** 9 else "unbuildable"
        print(f"  {item.name:<20}{row['rice']:>8.2f}x{row['register']:>10.2f}x"
              f"{row['bittree']:>10.2f}x{reg_state:>11,}{tree_text:>16}")
    print()
    print("  The register is a BOUNDED-MEMORY approximation of the bit-tree:")
    print("  same binary tree, but odds per depth instead of per path. It")
    print("  gives up accuracy where the value genuinely depends on the route")
    print("  taken (analog signals) and gives up almost nothing where the")
    print("  structure is positional (counters, enumeration, telemetry) --")
    print("  while staying buildable at widths where a bit-tree cannot exist.")
    print()


def verdict(by_kind: Dict[str, List]) -> None:
    """Check the kill criteria that were agreed before the numbers existed."""
    print("=" * 78)
    print(" KILL CRITERIA — agreed in PLAN-compression.md before running")
    print("=" * 78)

    def usable(kind):
        """Rows fit to judge on: reduced-depth audio is excluded."""
        return [(n, r) for n, r, flag in by_kind.get(kind, []) if not flag]

    def ratios(kind, coder):
        return [r.get(coder) for _, r in usable(kind) if r.get(coder)]

    verdicts = []
    audio = usable("audio")

    # 1. loses to FLAC on every real audio item by a wide margin
    pairs = [(r["predict+register"], r["flac -8"]) for _, r in audio
             if r.get("flac -8")]
    if pairs:
        beaten_badly = all(ours < flac * 0.8 for ours, flac in pairs)
        wins = sum(1 for ours, flac in pairs if ours >= flac)
        verdicts.append((
            "loses to FLAC everywhere by a wide margin", beaten_badly,
            f"beats or matches FLAC on {wins}/{len(pairs)} full-depth audio items",
        ))

    # 2. only wins on synthetic / sparse
    real_wins = sum(
        1 for _, r in audio
        if r.get("predict+register", 0) >= max(
            r.get("gzip -9", 0), r.get("lzma -9", 0), r.get("bz2 -9", 0))
    )
    verdicts.append((
        "only ever wins on synthetic or sparse signals", real_wins == 0,
        f"beats every general-purpose baseline on {real_wins}/{len(audio)} "
        f"full-depth real signals",
    ))

    # 3. never beats plain Rice -- the component it would displace
    ours = ratios("audio", "predict+register") + ratios("records", "predict+register")
    rice = ratios("audio", "predict+rice") + ratios("records", "predict+rice")
    if ours and rice:
        beats_rice = sum(1 for a, b in zip(ours, rice) if a > b)
        verdicts.append((
            "never beats plain Rice-coded residuals", beats_rice == 0,
            f"beats Rice on {beats_rice}/{len(ours)} signal+record items",
        ))

    # 4. the control: shuffled enumeration must not compress
    shuffled = [r for n, r, _ in by_kind.get("enum", []) if "shuffled" in n]
    if shuffled:
        worst = max(v for v in shuffled[0].values() if v)
        verdicts.append((
            "'compresses' shuffled enumeration past ~1.05x", worst > 1.06,
            f"best any coder managed on the control: {worst:.3f}x",
        ))

    # Not a kill criterion, but the question that actually matters: does the
    # per-position register earn its place against the per-node bit-tree it
    # would sit beside in an LZMA-shaped codec?
    ours_all = ratios("audio", "predict+register") + ratios("records", "predict+register") \
        + ratios("enum", "predict+register")
    tree_all = ratios("audio", "predict+bittree") + ratios("records", "predict+bittree") \
        + ratios("enum", "predict+bittree")
    if ours_all and tree_all:
        beats_tree = sum(1 for a, b in zip(ours_all, tree_all) if a >= b - 1e-9)
        print()
        print("  Component question: the register (one probability per bit")
        print("  POSITION) vs the bit-tree (one per tree NODE, LZMA's model).")
        print(f"  Register matches or beats bit-tree on "
              f"{beats_tree}/{len(ours_all)} items.")
        print()

    triggered = 0
    for description, fired, evidence in verdicts:
        mark = "TRIGGERED" if fired else "not met"
        triggered += fired
        print(f"  [{mark:^9}] {description}")
        print(f"              {evidence}")

    print()
    print("  Explicitly NOT kill criteria:")
    for note in NOT_KILL_CRITERIA:
        print(f"    - {note}")
    print()
    if triggered:
        print(f"  VERDICT: {triggered} criterion/criteria triggered — "
              f"see PLAN-compression.md for what that means.")
    else:
        print("  VERDICT: no kill criteria triggered. Phase 2 is earned,")
        print("  and the tables above say which data class to aim it at.")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
