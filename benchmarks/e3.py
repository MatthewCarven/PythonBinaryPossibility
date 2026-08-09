"""E3 — is local balance a knife-edge too?

    python -m benchmarks.e3

`ideas.md` measured that a GLOBALLY balanced 64 KB has 1,354 spare bits in it,
and that a 2% perturbation destroys three-quarters of them — a knife-edge.
`PLAN-generators.md` then measured that the same file balanced in every window
of 256 has 93,185 spare bits, 69x more, and flagged the obvious question as the
one that decides the whole thread: is the local property equally brittle?

This answers it. The models live in `balance.py`; this file only runs them, with
controls, and pays for every choice it makes.
"""

import math
import os
import random
import statistics
import struct
import sys
import wave

try:
    from benchmarks.balance import *  # noqa
except ImportError:                                    # run as a plain script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from balance import *  # noqa

N = 65536
SEEDS = (1, 2, 3)
PERFECT_BITS = log2fact(256) / 256          # 6.5781
PERFECT_SAVE = 8 - PERFECT_BITS             # 1.4219 bits/symbol


def heading(t):
    print()
    print(RULE)
    print(f" {t}")
    print(RULE)


def clean(seed):
    return PerfectGenerator(8, 1, random.Random(seed)).take(N)


def kept(bits_per_symbol):
    return (8 - bits_per_symbol) / PERFECT_SAVE


print()
print("  E3 — IS LOCAL BALANCE A KNIFE-EDGE TOO?")
print("  Globally, a 2% perturbation destroyed three-quarters of the available")
print("  bits. The local property is worth 69x more. Same question, local.")

# =======================================================================
heading("0. THE FOUR MODELS, on unperturbed order=1 output")
c = clean(1)
for name, cls, kw in (("order-0 frequencies (control)", Order0Coder, {}),
                      ("running counts, hard + escape", RunningBalance, {"order": 1}),
                      ("windowed counts (reset per 256)", WindowedBalance, {"order": 1, "window": 256}),
                      ("soft exponential tilt", TiltBalance, {"beta": 0.001, "window": 0})):
    b, m = charge(c, cls, **kw)
    print(f"  {name:<34} {N*8/b:>8.4f}x   {b/N:>7.4f} bits/sym   miss {m:>5.1%}")
print(f"  {'closed form for order=1':<34} "
      f"{8/PERFECT_BITS:>8.4f}x   {PERFECT_BITS:>7.4f} bits/sym")
print()
print("  The order-0 control is BLIND to balance, as it must be — it sees a flat")
print("  histogram and says 8 bits. Every number below is quoted against it.")

# =======================================================================
heading("1. SUBSTITUTION — a fraction of symbols replaced by uniform draws")
print("  The closest analogue of the global experiment. Median of 3 seeds.")
print("  'kept' is the fraction of the 1.4219 bits/symbol perfect saving that survives.")
print()
print(f"  {'rate':>7} {'spread':>7} | {'order-0':>9} | {'running':>9} {'kept':>7} | "
      f"{'windowed':>9} {'kept':>7} {'@o/w':>10} | {'tilt':>9} {'kept':>7}")

RATES = (0.0, 0.005, 0.01, 0.02, 0.05, 0.10, 0.25, 0.50, 1.00)
sub = {}
for rate in RATES:
    acc = {"o0": [], "run": [], "win": [], "tilt": [], "sp": [], "cfg": []}
    for s in SEEDS:
        d = perturb_substitute(clean(s), rate, random.Random(1000 + s)) if rate else clean(s)
        acc["o0"].append(charge(d, Order0Coder)[0] / N)
        acc["run"].append(best_of(d, RunningBalance, RUN_GRID)[0] / N)
        wb = best_of(d, WindowedBalance, WIN_GRID)
        acc["win"].append(wb[0] / N); acc["cfg"].append((wb[1]["order"], wb[1]["window"]))
        acc["tilt"].append(best_of(d, TiltBalance, TILT_GRID)[0] / N)
        acc["sp"].append(local_spread(d))
    m = {k: statistics.median(v) for k, v in acc.items() if k != "cfg"}
    sub[rate] = m
    cfg = statistics.mode(acc["cfg"])
    print(f"  {rate:>6.1%} {m['sp']:>7.0f} | {8/m['o0']:>8.4f}x | "
          f"{8/m['run']:>8.4f}x {kept(m['run']):>6.1%} | "
          f"{8/m['win']:>8.4f}x {kept(m['win']):>6.1%} {str(cfg):>10} | "
          f"{8/m['tilt']:>8.4f}x {kept(m['tilt']):>6.1%}")

# =======================================================================
heading("2. WHY v1 COLLAPSED — the running model is pinned by its laggards")
d = perturb_substitute(clean(1), 0.02, random.Random(1001))
for label, cls, kw in (("running", RunningBalance, {"order": 1}),
                       ("windowed", WindowedBalance, {"order": 1, "window": 256})):
    co = cls(**kw)
    sizes = []
    for v in d:
        sizes.append(co.g.eligible_size())
        co.cost(v)
    cnt = co.g.counts
    print(f"  {label:<9} median eligible set {statistics.median(sizes):>5.0f} of 256   "
          f"miss rate {co.miss_rate:>5.1%}   values at the minimum: "
          f"{sum(1 for x in cnt if x == min(cnt)):>3}")
print()
print(f"  The 2%-perturbed data still has a final count spread of "
      f"{max(cnt) - min(cnt)} out of 256 draws each —")
print("  it is STILL nearly balanced. The data was never the problem. Eligibility")
print("  anchored to min() is a max-statistic, and max-statistics are pinned by")
print("  their single worst outlier. One value that stops being drawn holds `lo`")
print("  down forever and the eligible set degenerates to that one laggard.")

# =======================================================================
heading("3. SWAP — global histogram preserved EXACTLY, only locality damaged")
print("  If balance were a global property this table would not move at all.")
print()
print(f"  {'rate':>7} {'spread':>7} {'order-0':>9} {'windowed':>9} {'kept':>7} {'lzma':>8}")
for rate in RATES:
    acc = {"o0": [], "win": [], "sp": [], "lz": []}
    for s in SEEDS:
        d = perturb_swap(clean(s), rate, random.Random(2000 + s)) if rate else clean(s)
        acc["o0"].append(charge(d, Order0Coder)[0] / N)
        acc["win"].append(best_of(d, WindowedBalance, WIN_GRID)[0] / N)
        acc["sp"].append(local_spread(d))
        acc["lz"].append(toolbox(d)["lzma"])
    m = {k: statistics.median(v) for k, v in acc.items()}
    print(f"  {rate:>6.1%} {m['sp']:>7.0f} {8/m['o0']:>8.4f}x {8/m['win']:>8.4f}x "
          f"{kept(m['win']):>6.1%} {m['lz']:>7.3f}x")

# =======================================================================
heading("4. SCALE — the global saving vanishes with file size. Does the local one?")
print(f"  {'size':>12} {'local (bits)':>16} {'global (bits)':>15} {'local/global':>13} "
      f"{'local as % of file':>19}")
for n in (4096, 65536, 1 << 20, 1 << 24):
    lo_, gl = local_saving_bits(n), global_saving_bits(n)
    print(f"  {n:>12,} {lo_:>16,.0f} {gl:>15,.0f} {lo_/gl:>12,.0f}x {lo_/(n*8):>18.2%}")
print()
print("  The global saving grows as ~(A-1)/2*log2(N) and is gone by 16 MB.")
print("  The local saving is LINEAR in N — it is a constant 17.8% of the file,")
print("  forever. That is the structural difference, not a bigger constant.")

# =======================================================================
heading("5. CONTROLS — if any of these misbehave the numbers above are fiction")
r = random.Random(77)
noise = [r.randrange(256) for _ in range(N)]
sh = clean(1)[:]
random.Random(5).shuffle(sh)                 # same multiset, locality destroyed
ctl = [
    ("uniform noise, windowed balance", 8 / (best_of(noise, WindowedBalance, WIN_GRID)[0] / N),
     "<= 1.0000x  a wrong model must cost"),
    ("uniform noise, order-0", 8 / (charge(noise, Order0Coder)[0] / N), "<= 1.0000x"),
    ("clean data SHUFFLED, windowed", 8 / (best_of(sh, WindowedBalance, WIN_GRID)[0] / N),
     "~1.0000x  same bytes, locality gone"),
    ("100% substituted (= pure noise)", 8 / sub[1.0]["win"], "~1.0000x  no fantasy at the far end"),
    ("gzip on perfect balance", toolbox(clean(1))["gzip"], "< 1.0  the toolbox cannot see exhaustion"),
    ("lzma on perfect balance", toolbox(clean(1))["lzma"], "< 1.0"),
    ("bz2 on perfect balance", toolbox(clean(1))["bz2"], "< 1.0"),
]
for name, val, note in ctl:
    print(f"  {name:<36} {val:>9.4f}x   {note}")
print()
vals = []
for s in (1, 2, 3, 4, 5):
    d = perturb_substitute(clean(s), 0.02, random.Random(3000 + s))
    vals.append(8 / (best_of(d, WindowedBalance, WIN_GRID)[0] / N))
print(f"  seed stability at 2% substitution: "
      f"{'  '.join(f'{v:.4f}x' for v in vals)}  (spread {max(vals)-min(vals):.4f})")


# =======================================================================
heading("5b. THE SHARPER CONTROL — does the WINDOW alone explain the gain?")
print("  WindowedBalance differs from Order0Coder in two ways at once: it models")
print("  balance, and it models locally. WindowedOrder0 has the locality and no")
print("  balance. Anything it matches was never about balance.")
print()
print(f"  {'stream':<24}{'order-0':>10}{'win order-0':>13}{'win balance':>13}{'balance adds':>14}")
for name, d in (("perfect order=1", clean(1)),
                ("2% substituted", perturb_substitute(clean(1), 0.02, random.Random(1001))),
                ("5% substituted", perturb_substitute(clean(1), 0.05, random.Random(1001))),
                ("counter mod 256", [i & 0xFF for i in range(N)]),
                ("Mersenne Twister", list(random.Random(5).randbytes(N)))):
    o0 = charge(d, Order0Coder)[0] / N
    w0 = best_of(d, WindowedOrder0, W0_GRID)[0] / N
    wb = best_of(d, WindowedBalance, WIN_GRID)[0] / N
    print(f"  {name:<24}{8/o0:>9.4f}x{8/w0:>12.4f}x{8/wb:>12.4f}x{w0-wb:>+13.3f}b")
print()
print("  On balance-constrained data the window alone gains NOTHING (it is worse")
print("  than the global model — resetting a frequency model on a flat histogram")
print("  just costs you the relearning). All of the gain is balance.")
print()
print("  CAVEAT, and it is why the audio row of the panel is not claimed below:")
print("  WindowedOrder0 resets to a Laplace prior of 256 pseudo-counts and then")
print("  sees only `window` real ones, so on a 64-symbol window it is badly")
print("  over-smoothed and is NOT a fair local-frequency baseline for peaked data.")
print("  It is a fair baseline here, where the histogram really is flat.")

# =======================================================================
heading("6. THE PANEL — where the randomness this project already has sits")
print("  spread = median max-min over non-overlapping 256-byte windows.")
print("  A free RNG should read ~5 at that window size; perfect balance reads 0.")
print("  'gain' is windowed-balance minus order-0: what BALANCE contributed,")
print("  once vocabulary and frequency are taken out.")
print()


def wav_bytes(path, limit=N):
    with wave.open(path, "rb") as w:
        return list(w.readframes(w.getnframes())[:limit])


def wav_residual_bytes(path, limit=N):
    with wave.open(path, "rb") as w:
        nch, nf = w.getnchannels(), w.getnframes()
        frames = w.readframes(nf)
    s = list(struct.unpack("<%dh" % (len(frames) // 2), frames))[::nch]
    out = []
    for i in range(1, len(s)):
        v = s[i] - s[i - 1]
        out.append(((v << 1) ^ (v >> 31)) & 0xFF)
    return out[:limit]


panel = [("perfect order=1", clean(1)),
         ("perfect order=16", PerfectGenerator(8, 16, random.Random(1)).take(N)),
         ("Mersenne Twister", list(random.Random(5).randbytes(N))),
         ("os.urandom", list(os.urandom(N))),
         ("counter mod 256", [i & 0xFF for i in range(N)])]
e = []
for i in range(N // 4):
    e.extend(struct.pack(">I", i))
panel.append(("enum/ordered 32-bit", e[:N]))
shl = list(range(N // 4))
random.Random(42).shuffle(shl)
e2 = []
for i in shl:
    e2.extend(struct.pack(">I", i))
panel.append(("enum/shuffled 32-bit", e2[:N]))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
wp = os.path.join(REPO, "psynthrack_take1.wav")
if os.path.exists(wp):
    panel.append(("real audio, raw bytes", wav_bytes(wp)))
    panel.append(("real audio, residuals", wav_residual_bytes(wp)))
else:
    print(f"  (no {os.path.basename(wp)} in the repo root — audio rows skipped)")
t = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "balance.py"), "rb").read()  # any text will do
while len(t) < N:
    t += t
panel.append(("source text", list(t[:N])))

print(f"  {'stream':<22} {'spread':>7} {'order-0':>9} {'windowed':>9} {'gain':>8} "
      f"{'@o/w':>10} {'miss':>6} {'lzma':>9}")
for name, data in panel:
    data = (data * (N // max(1, len(data)) + 1))[:N]
    o0 = charge(data, Order0Coder)[0] / N
    wb, cfg, miss = best_of(data, WindowedBalance, WIN_GRID)
    wb /= N
    print(f"  {name:<22} {local_spread(data):>7.0f} {8/o0:>8.4f}x {8/wb:>8.4f}x "
          f"{o0-wb:>+7.3f}b {str((cfg['order'], cfg['window'])):>10} {miss:>5.1%} "
          f"{toolbox(data)['lzma']:>8.3f}x")
print()
print("  READ THIS TABLE WITH 5b's CAVEAT. The two rows with a high miss rate and")
print("  a peaked histogram -- real audio raw and residuals -- are NOT claimed as")
print("  balance wins. At a 33-44% miss rate the escape flag has stopped being an")
print("  escape and become a hot/cold frequency split, which is the OPPOSITE of")
print("  what this model claims to be doing. Resolving that needs a properly aged")
print("  local frequency baseline, not a reset one. Open.")
print("  The rows that ARE clean: perfect balance and counter (+1.44b, 0% miss),")
print("  and the two negative rows -- text and shuffled enumeration -- where")
print("  balance honestly LOSES to a plain frequency model.")

# =======================================================================
heading("7. THE RACK — what an independent coin per step does to a 16-step bar")
print("  PsynthRack.collapse() flips one coin per undecided step.")
print()
trials = 5000
coin = random.Random(9)
cc = [sum(1 for _ in range(16) if coin.random() < 0.5) for _ in range(trials)]
bl = [sum(PerfectGenerator(1, 1, random.Random(1000 + t)).take(16)) for t in range(trials)]
for label, c_ in (("independent coin", cc), ("balanced selector", bl)):
    print(f"  {label:<20} mean {statistics.mean(c_):>5.2f}  sd {statistics.pstdev(c_):>4.2f}  "
          f"bars with <=4 hits {sum(1 for x in c_ if x <= 4)/trials:>6.2%}  "
          f">=12 hits {sum(1 for x in c_ if x >= 12)/trials:>6.2%}")
print()
print(f"  A balanced 16-step bar costs log2(16!)/16 = {log2fact(16)/16:.4f} bits/step")
print(f"  against 1.0000 for a coin — per-bit balance is the most expensive")
print(f"  setting on the whole dial. For a drum pattern that expense IS the point.")
print()
