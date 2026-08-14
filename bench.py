"""The Possibility Bench -- a GUI for playing with superposition.

Run it with::

    python bench.py

Four benches, one idea.  Everywhere you see a cell you can click it, and
every click cycles the same three states::

    0  ->  1  ->  ?  ->  0

``0`` and ``1`` are decided; ``?`` is superposed -- undecided, both at
once, and worth a doubling of the possibility space.

* **Register** -- a row of bits. Watch the count, the tree, and the list of
  every reachable state react as you click.
* **Glitch** -- type some text, superpose a few bits of it, and read every
  string it could now decode to.
* **Rack** -- a step sequencer where undecided steps mean undecided music.
  Collapse it and render the result to a .wav file.
* **Random** -- the coin-vs-bag race. A free coin and a balanced generator
  fill twin histograms from the same seed; watch the coin's spread wander
  while the bag's stays pinned, and watch what the evenness costs.

Standard library only: Tkinter for the windows, and the project's own
modules for all the actual thinking.  This GUI holds no possibility logic
of its own -- it drives the real classes, so what you see here is exactly
what your scripts will do.
"""

import math
import os
import random
import tkinter as tk
from tkinter import filedialog, font, messagebox, simpledialog, ttk
from itertools import islice

from BinaryGlitch import BinaryGlitch
from BinaryPossibility import BinaryRegister
from binarypossibilitytrees import BinaryPossibilityTree
from BinaryRandom import RandomGeneratorPerfect
from PsynthRack import PsynthRack

# --- Palette -------------------------------------------------------------
BG = "#16161f"          # window background
PANEL = "#1e1e2a"       # panel background
INK = "#e9e9f2"         # primary text
MUTED = "#8b8ba7"       # secondary text
ZERO_BG = "#2a2a38"     # a step/bit that is off
ZERO_FG = "#6a6a85"
ONE_BG = "#3ddc97"      # decided: on
ONE_FG = "#0d2b20"
SUPER_BG = "#a06ce0"    # superposed: the interesting one
SUPER_FG = "#1a0f26"
ACCENT = "#7fd4ff"

#: Clicking a cell walks this cycle.
NEXT_STATE = {0: 1, 1: None, None: 0}

#: How many states the list views will show before they stop and say so.
STATE_PREVIEW_LIMIT = 512

#: Above this many leaves, drawing the tree is more noise than insight.
TREE_LEAF_LIMIT = 64


def _mix(colour_a: str, colour_b: str, amount: float) -> str:
    """Blend two #rrggbb colours; ``amount`` 0.0 gives a, 1.0 gives b."""
    a = [int(colour_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(colour_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(
        f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b)
    )


def _superposed_colour(p: float) -> str:
    """Shade a superposed cell towards whatever it will probably become.

    Fair bits stay the neutral violet.  A bit that leans towards 1 drifts
    towards the 'on' green, one that leans towards 0 drifts towards the
    'off' grey -- but only part of the way, so a `?` still reads as a `?`.
    """
    # How far towards the destination colour a near-certainty gets. High
    # enough that a ghost note is spottable at a glance across a 16-step
    # grid, short of 1.0 so a `?` never masquerades as a decided cell.
    lean = 0.85
    if p >= 0.5:
        return _mix(SUPER_BG, ONE_BG, (p - 0.5) * 2 * lean)
    return _mix(SUPER_BG, ZERO_BG, (0.5 - p) * 2 * lean)


def _style_cell(button: tk.Button, state, p: float = 0.5) -> None:
    """Paint a bit/step button to match its state and its odds."""
    if state is None:
        colour = _superposed_colour(p)
        button.configure(text="?", bg=colour, fg=SUPER_FG,
                         activebackground=colour)
    elif state == 1:
        button.configure(text="1", bg=ONE_BG, fg=ONE_FG,
                         activebackground=ONE_BG)
    else:
        button.configure(text="0", bg=ZERO_BG, fg=ZERO_FG,
                         activebackground=ZERO_BG)


def _ask_probability(parent, current: float, what: str) -> "float | None":
    """Prompt for a 0..1 probability. Returns None if cancelled."""
    return simpledialog.askfloat(
        "Odds",
        f"How often should this {what} come out as 1?\n"
        f"0.0 never  ·  0.5 fair coin  ·  1.0 always",
        initialvalue=current, minvalue=0.0, maxvalue=1.0, parent=parent,
    )


def _pretty_count(count: int) -> str:
    """Render a possibility count readably, however silly it gets."""
    text = f"{count:,}"
    if len(text) > 30:
        digits = len(str(count))
        return f"~10^{digits - 1}  ({digits} digits)"
    return text


class RegisterBench(ttk.Frame):
    """A row of bits, its possibility count, its tree, and its states."""

    def __init__(self, parent):
        super().__init__(parent, padding=14)
        self.register = BinaryRegister(4)
        self.register.set_bit(0, 1)
        self.cells = []

        header = ttk.Label(
            self,
            text="Click a bit to cycle it:  0  →  1  →  ?  →  0"
                 "        Right-click a ? to set its odds.",
            style="Hint.TLabel",
        )
        header.pack(anchor="w")

        self.cell_row = tk.Frame(self, bg=BG)
        self.cell_row.pack(anchor="w", pady=(10, 6))

        controls = ttk.Frame(self)
        controls.pack(anchor="w", pady=(0, 10))
        ttk.Button(controls, text="+ bit", width=8,
                   command=self.add_bit).pack(side="left")
        ttk.Button(controls, text="− bit", width=8,
                   command=self.remove_bit).pack(side="left", padx=(6, 14))
        ttk.Button(controls, text="All ?", width=8,
                   command=lambda: self.set_all(None)).pack(side="left")
        ttk.Button(controls, text="All 0", width=8,
                   command=lambda: self.set_all(0)).pack(side="left", padx=6)

        self.count_label = ttk.Label(self, text="", style="Count.TLabel")
        self.count_label.pack(anchor="w", pady=(0, 10))

        panes = ttk.Frame(self)
        panes.pack(fill="both", expand=True)

        tree_box = ttk.LabelFrame(panes, text=" possibility tree ", padding=8)
        tree_box.pack(side="left", fill="both", expand=True)
        self.tree_text = self._make_text(tree_box)

        state_box = ttk.LabelFrame(panes, text=" states, likeliest first ", padding=8)
        state_box.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.state_text = self._make_text(state_box)

        self.rebuild_cells()

    def _make_text(self, parent) -> tk.Text:
        wrapper = tk.Frame(parent, bg=PANEL)
        wrapper.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(wrapper, orient="vertical")
        scroll.pack(side="right", fill="y")
        widget = tk.Text(
            wrapper, height=14, width=34, bg=PANEL, fg=INK, bd=0,
            insertbackground=INK, font=self.mono, wrap="none",
            yscrollcommand=scroll.set, padx=6, pady=4,
        )
        widget.pack(side="left", fill="both", expand=True)
        scroll.configure(command=widget.yview)
        return widget

    @property
    def mono(self):
        return self.master.master.mono_font

    # --- Editing ---

    def rebuild_cells(self) -> None:
        for cell in self.cells:
            cell.destroy()
        self.cells = []
        for index in range(len(self.register)):
            button = tk.Button(
                self.cell_row, width=3, bd=0, relief="flat",
                font=self.mono, cursor="hand2",
                command=lambda i=index: self.cycle(i),
            )
            button.bind("<Button-3>", lambda _event, i=index: self.set_odds(i))
            button.pack(side="left", padx=2)
            self.cells.append(button)
        self.refresh()

    def cycle(self, index: int) -> None:
        self.register.set_bit(index, NEXT_STATE[self.register.get_bit(index)])
        self.refresh()

    def set_odds(self, index: int) -> None:
        """Right-click handler: weight a superposed bit."""
        if self.register.get_bit(index) is not None:
            return  # a decided bit has no odds to set
        p = _ask_probability(self, self.register.get_bit_probability(index), "bit")
        if p is None:
            return
        self.register.set_bit_probability(index, p)
        self.refresh()

    def set_all(self, state) -> None:
        for index in range(len(self.register)):
            self.register.set_bit(index, state)
        self.refresh()

    def add_bit(self) -> None:
        if len(self.register) >= 24:
            return
        self.register.add_bit()
        self.rebuild_cells()

    def remove_bit(self) -> None:
        if len(self.register) <= 1:
            return
        self.register.remove_bit()
        self.rebuild_cells()

    # --- Display ---

    def refresh(self) -> None:
        for index, cell in enumerate(self.cells):
            _style_cell(cell, self.register.get_bit(index),
                        self.register.get_bit_probability(index))

        count = self.register.calculate_possibility_count()
        entropy = self.register.entropy()
        superposed = sum(
            1 for p in self.register.get_individual_states() if p.is_superposition()
        )
        self.count_label.configure(
            text=f"{_pretty_count(count)} possible states"
            f"   ·   {entropy:.2f} bits of uncertainty"
            f"   ·   {superposed} of {len(self.register)} bits superposed"
        )

        self.tree_text.delete("1.0", "end")
        if count > TREE_LEAF_LIMIT:
            self.tree_text.insert(
                "1.0",
                f"{count:,} leaves is too many to draw.\n\n"
                f"Collapse some bits to below {TREE_LEAF_LIMIT}\nand the tree "
                f"comes back.",
            )
        else:
            self.tree_text.insert("1.0", BinaryPossibilityTree(self.register).render())

        # Most-likely-first, so weighting a bit visibly reorders the list.
        self.state_text.delete("1.0", "end")
        shown = list(islice(self.register.iter_states_by_likelihood(),
                            STATE_PREVIEW_LIMIT))
        fair = self.register.is_fair()
        body = "\n".join(
            state if fair else f"{state}  {probability:.4f}"
            for state, probability in shown
        )
        if count > len(shown):
            body += f"\n\n… and {count - len(shown):,} more.\n(Streamed lazily "
            body += "— nothing built the full list.)"
        self.state_text.insert("1.0", body)


class GlitchBench(ttk.Frame):
    """Type text, superpose some of its bits, read every variant."""

    def __init__(self, parent):
        super().__init__(parent, padding=14)

        ttk.Label(
            self,
            text="Load text into a register, knock a few bits into "
                 "superposition, and read back everything it could be.",
            style="Hint.TLabel",
        ).pack(anchor="w")

        form = ttk.Frame(self)
        form.pack(anchor="w", pady=12)

        ttk.Label(form, text="Text").grid(row=0, column=0, sticky="w")
        self.text_var = tk.StringVar(value="Hi")
        entry = ttk.Entry(form, textvariable=self.text_var, width=30,
                          font=self.mono)
        entry.grid(row=0, column=1, padx=(8, 20), sticky="w")

        ttk.Label(form, text="Superposed bits").grid(row=0, column=2, sticky="w")
        self.bits_var = tk.IntVar(value=2)
        ttk.Spinbox(form, from_=0, to=12, textvariable=self.bits_var,
                    width=5).grid(row=0, column=3, padx=(8, 20))

        ttk.Label(form, text="Seed").grid(row=0, column=4, sticky="w")
        self.seed_var = tk.IntVar(value=1)
        ttk.Spinbox(form, from_=0, to=9999, textvariable=self.seed_var,
                    width=6).grid(row=0, column=5, padx=(8, 20))

        ttk.Button(form, text="Glitch it", command=self.glitch).grid(
            row=0, column=6)

        self.count_label = ttk.Label(self, text="", style="Count.TLabel")
        self.count_label.pack(anchor="w", pady=(0, 10))

        box = ttk.LabelFrame(self, text=" variants ", padding=8)
        box.pack(fill="both", expand=True)
        wrapper = tk.Frame(box, bg=PANEL)
        wrapper.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(wrapper, orient="vertical")
        scroll.pack(side="right", fill="y")
        self.output = tk.Text(wrapper, bg=PANEL, fg=INK, bd=0, font=self.mono,
                              wrap="none", yscrollcommand=scroll.set,
                              padx=8, pady=6)
        self.output.pack(side="left", fill="both", expand=True)
        scroll.configure(command=self.output.yview)
        self.output.tag_configure("original", foreground=ONE_BG)

        self.glitch()

    @property
    def mono(self):
        return self.master.master.mono_font

    def glitch(self) -> None:
        text = self.text_var.get()
        if not text:
            self.count_label.configure(text="Type something first.")
            self.output.delete("1.0", "end")
            return

        register = BinaryGlitch.register_from_text(text)
        available = len(register)
        wanted = max(0, min(self.bits_var.get(), available, 12))
        self.bits_var.set(wanted)
        BinaryGlitch.superpose_random(register, wanted, seed=self.seed_var.get())

        count = BinaryGlitch.variant_count(register)
        self.count_label.configure(
            text=f"{count:,} variants   ·   {wanted} of {available} bits "
                 f"superposed"
        )

        self.output.delete("1.0", "end")
        for variant in BinaryGlitch.iter_variant_texts(register):
            tag = "original" if variant == text else ""
            self.output.insert("end", f"{variant!r}\n", tag)


class RackBench(ttk.Frame):
    """A step sequencer where undecided steps mean undecided music."""

    def __init__(self, parent):
        super().__init__(parent, padding=14)
        self.rack = PsynthRack.demo_rack()
        self.cells = []

        ttk.Label(
            self,
            text="Each step is a bit: 0 silent, 1 hit, ? undecided. "
                 "Every ? doubles the number of songs this pattern holds.\n"
                 "Right-click a ? to set how often it fires — 0.2 makes a "
                 "ghost note that turns up in a fifth of takes. Tick "
                 "'balanced' to deal the fair ?s evenly instead of "
                 "coin-flipping them.",
            style="Hint.TLabel",
            wraplength=930,
        ).pack(anchor="w")

        self.grid_frame = tk.Frame(self, bg=BG)
        self.grid_frame.pack(anchor="w", pady=12)
        self._build_grid()

        controls = ttk.Frame(self)
        controls.pack(anchor="w")
        ttk.Button(controls, text="Superpose", width=11,
                   command=self.superpose).pack(side="left")
        self.spread_var = tk.IntVar(value=6)
        ttk.Spinbox(controls, from_=0, to=32, textvariable=self.spread_var,
                    width=4).pack(side="left", padx=(6, 4))
        ttk.Label(controls, text="random steps").pack(side="left", padx=(0, 18))

        ttk.Label(controls, text="Seed").pack(side="left")
        self.seed_var = tk.IntVar(value=1)
        ttk.Spinbox(controls, from_=0, to=9999, textvariable=self.seed_var,
                    width=6).pack(side="left", padx=(6, 18))

        ttk.Label(controls, text="BPM").pack(side="left")
        self.bpm_var = tk.IntVar(value=int(self.rack.bpm))
        ttk.Spinbox(controls, from_=40, to=220, textvariable=self.bpm_var,
                    width=5).pack(side="left", padx=(6, 18))

        self.balanced_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="balanced",
                        variable=self.balanced_var).pack(side="left",
                                                         padx=(0, 8))

        ttk.Button(controls, text="Collapse → .wav",
                   command=self.render).pack(side="left")

        self.count_label = ttk.Label(self, text="", style="Count.TLabel")
        self.count_label.pack(anchor="w", pady=(12, 6))

        self.status = ttk.Label(self, text="", style="Hint.TLabel", wraplength=760)
        self.status.pack(anchor="w")

        self.refresh()

    @property
    def mono(self):
        return self.master.master.mono_font

    def _build_grid(self) -> None:
        for track_index, track in enumerate(self.rack.tracks):
            tk.Label(
                self.grid_frame, text=track.voice.name, width=7, anchor="e",
                bg=BG, fg=MUTED, font=self.mono,
            ).grid(row=track_index, column=0, padx=(0, 8), pady=2)
            row = []
            for step_index in range(len(track)):
                button = tk.Button(
                    self.grid_frame, width=2, bd=0, relief="flat",
                    font=self.mono, cursor="hand2",
                    command=lambda t=track_index, s=step_index: self.cycle(t, s),
                )
                button.bind(
                    "<Button-3>",
                    lambda _e, t=track_index, s=step_index: self.set_odds(t, s),
                )
                # A wider gap every four steps, so the beat is readable.
                pad = (1, 7) if step_index % 4 == 3 else (1, 1)
                button.grid(row=track_index, column=step_index + 1, padx=pad,
                            pady=2)
                row.append(button)
            self.cells.append(row)

    def cycle(self, track_index: int, step_index: int) -> None:
        self.rack.tracks[track_index].cycle_step(step_index)
        self.refresh()

    def set_odds(self, track_index: int, step_index: int) -> None:
        """Right-click handler: weight a superposed step."""
        track = self.rack.tracks[track_index]
        if track.get_step(step_index) is not None:
            return  # a decided step has no odds to set
        p = _ask_probability(self, track.get_step_probability(step_index), "step")
        if p is None:
            return
        track.set_step_probability(step_index, p)
        self.refresh()

    def superpose(self) -> None:
        try:
            self.rack.superpose_random(self.spread_var.get(),
                                       seed=self.seed_var.get())
        except ValueError as error:
            messagebox.showerror("Too many steps", str(error))
            return
        self.refresh()

    def refresh(self) -> None:
        for track_index, track in enumerate(self.rack.tracks):
            for step_index, cell in enumerate(self.cells[track_index]):
                _style_cell(cell, track.get_step(step_index),
                            track.get_step_probability(step_index))
        count = self.rack.possibility_count()
        weighted = sum(
            1
            for track in self.rack.tracks
            for bit in track.register.get_individual_states()
            if bit.is_superposition() and not bit.is_fair()
        )
        text = (
            f"{_pretty_count(count)} possible songs"
            f"   ·   {self.rack.entropy():.2f} bits of uncertainty"
            f"   ·   {self.rack.superposed_step_count()} steps undecided"
        )
        if weighted:
            text += f" ({weighted} weighted)"
        self.count_label.configure(text=text)

    def _collapse(self):
        """One collapse at the bench's current seed and deal setting."""
        return self.rack.collapse(seed=self.seed_var.get(),
                                  balanced=self.balanced_var.get())

    def render(self) -> None:
        self.rack.bpm = float(self.bpm_var.get())
        patterns = self._collapse()
        path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("WAV audio", "*.wav")],
            initialfile="psynthrack.wav",
        )
        if not path:
            return
        try:
            self.rack.write_wav(path, patterns)
        except OSError as error:
            messagebox.showerror("Could not write file", str(error))
            return
        collapsed = "  ".join(patterns)
        self.status.configure(
            text=f"Wrote {os.path.basename(path)} — one of "
                 f"{self.rack.possibility_count():,} songs.  Collapsed to: "
                 f"{collapsed}"
        )


class RandomBench(ttk.Frame):
    """The coin-vs-bag race: spending randomness to buy evenness.

    Two histograms fill from the same seed -- a free coin on the left, a
    `RandomGeneratorPerfect` on the right.  The GUI holds no balance logic:
    the bag draws itself, `profile()` writes the verdicts, and the spent
    meter is nothing but log2 of the eligible-set size the library reports
    before each draw.
    """

    DRAW_SIZES = (1, 16, 256, 4096)
    CANVAS_W = 400
    CANVAS_H = 168

    def __init__(self, parent):
        super().__init__(parent, padding=14)

        ttk.Label(
            self,
            text="A free coin clumps; the bag deals. Same seed, same number "
                 "of draws — watch the spread. The bag does not make "
                 "randomness: it SPENDS randomness to buy evenness, and the "
                 "meter shows the exchange rate. Changing a dial restarts "
                 "the race.",
            style="Hint.TLabel",
            wraplength=930,
        ).pack(anchor="w")

        controls = ttk.Frame(self)
        controls.pack(anchor="w", pady=12)

        ttk.Label(controls, text="Width").pack(side="left")
        self.width_var = tk.IntVar(value=4)
        ttk.Spinbox(controls, from_=1, to=6, textvariable=self.width_var,
                    width=4, command=self.reconfigure).pack(side="left",
                                                            padx=(6, 14))
        ttk.Label(controls, text="Order").pack(side="left")
        self.order_var = tk.IntVar(value=1)
        ttk.Spinbox(controls, from_=1, to=256, textvariable=self.order_var,
                    width=5, command=self.reconfigure).pack(side="left",
                                                            padx=(6, 14))
        ttk.Label(controls, text="Seed").pack(side="left")
        self.seed_var = tk.IntVar(value=1)
        ttk.Spinbox(controls, from_=0, to=9999, textvariable=self.seed_var,
                    width=6, command=self.reconfigure).pack(side="left",
                                                            padx=(6, 18))
        for count in self.DRAW_SIZES:
            ttk.Button(
                controls, text=f"Draw ×{count}", width=10,
                command=lambda c=count: self.draw(c),
            ).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Reset", width=8,
                   command=self.reconfigure).pack(side="left", padx=(8, 0))

        panes = ttk.Frame(self)
        panes.pack(fill="both", expand=True)
        self.free_side = self._build_side(panes, " free coin ", left=True)
        self.bag_side = self._build_side(panes, " the bag ", left=False)

        self.reconfigure()

    @property
    def mono(self):
        return self.master.master.mono_font

    def _build_side(self, parent, title: str, left: bool) -> dict:
        box = ttk.LabelFrame(parent, text=title, padding=8)
        box.pack(side="left", fill="both", expand=True,
                 padx=(0, 12) if left else 0)
        canvas = tk.Canvas(box, width=self.CANVAS_W, height=self.CANVAS_H,
                           bg=PANEL, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        stats = ttk.Label(box, text="", style="Hint.TLabel", wraplength=440)
        stats.pack(anchor="w", pady=(6, 0))
        spent = ttk.Label(box, text="", style="Count.TLabel", wraplength=440)
        spent.pack(anchor="w")
        return {"box": box, "canvas": canvas, "stats": stats, "spent": spent}

    # --- The race ---

    def reconfigure(self) -> None:
        """(Re)start the race at the dialled width, order and seed."""
        width = max(1, min(6, self.width_var.get()))
        self.width_var.set(width)
        order = max(1, min(256, self.order_var.get()))
        self.order_var.set(order)
        seed = self.seed_var.get()
        self.free_gen = RandomGeneratorPerfect(
            width, None, rng=random.Random(seed))
        self.bag_gen = RandomGeneratorPerfect(
            width, order, rng=random.Random(seed))
        self.spent = {"free": 0.0, "bag": 0.0}
        self.draws = 0
        self.bag_side["box"].configure(text=f" the bag · order={order} ")
        self.refresh()

    def draw(self, count: int) -> None:
        """Advance both sides by ``count`` draws and refresh the picture."""
        for _ in range(count):
            for key, generator in (("free", self.free_gen),
                                   ("bag", self.bag_gen)):
                self.spent[key] += math.log2(generator.eligible_size())
                generator.next()
        self.draws += count
        self.refresh()

    # --- Display ---

    def _redraw(self, side: dict, generator: RandomGeneratorPerfect,
                peak: int, colour: str) -> None:
        canvas = side["canvas"]
        canvas.delete("all")
        width = max(canvas.winfo_width(), self.CANVAS_W)
        height = max(canvas.winfo_height(), self.CANVAS_H)
        pad = 10
        floor = height - pad
        canvas.create_line(pad, floor, width - pad, floor, fill=ZERO_BG)
        slot = (width - 2 * pad) / generator.A
        bar = max(1.0, slot * 0.72)
        scale = (height - 2 * pad) / max(peak, 1)
        for value, count in enumerate(generator.counts):
            x = pad + value * slot + (slot - bar) / 2
            if count:
                canvas.create_rectangle(
                    x, floor - count * scale, x + bar, floor,
                    fill=colour, outline="")
            else:
                # An unseen value still gets a tick, so gaps are visible.
                canvas.create_rectangle(
                    x, floor - 1, x + bar, floor, fill=ZERO_BG, outline="")

    def refresh(self) -> None:
        peak = max(max(self.free_gen.counts), max(self.bag_gen.counts), 1)
        self._redraw(self.free_side, self.free_gen, peak, ACCENT)
        self._redraw(self.bag_side, self.bag_gen, peak, ONE_BG)
        for key, side, generator in (
            ("free", self.free_side, self.free_gen),
            ("bag", self.bag_side, self.bag_gen),
        ):
            report = generator.profile()
            side["stats"].configure(
                text=f"n={report['n']:,}  ·  spread {report['spread']}"
                     f"  ·  free RNG ~{report['expected']:.1f}"
                     f"  ·  {report['verdict']}"
            )
            if self.draws:
                rate = self.spent[key] / self.draws
                side["spent"].configure(
                    text=f"spent {self.spent[key]:,.1f} bits"
                         f"  ·  {rate:.4f} /draw"
                )
            else:
                side["spent"].configure(text="spent 0.0 bits")


class Bench(tk.Tk):
    """The main window: four benches in a notebook."""

    def __init__(self):
        super().__init__()
        self.title("The Possibility Bench")
        self.configure(bg=BG)
        # Wide enough that a 16-step rack row fits without scrolling.
        self.geometry("1000x660")
        self.minsize(940, 580)

        self.mono_font = font.nametofont("TkFixedFont").copy()
        self.mono_font.configure(size=11)

        self._configure_style()

        heading = tk.Label(
            self, text="The Possibility Bench", bg=BG, fg=INK,
            font=("", 16, "bold"),
        )
        heading.pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(
            self,
            text="0 and 1 are decided.  ?  is both.",
            bg=BG, fg=MUTED,
        ).pack(anchor="w", padx=16, pady=(2, 10))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        notebook.add(RegisterBench(notebook), text="  Register  ")
        notebook.add(GlitchBench(notebook), text="  Glitch  ")
        notebook.add(RackBench(notebook), text="  Rack  ")
        notebook.add(RandomBench(notebook), text="  Random  ")

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        # 'clam' honours colour settings on every platform; the native
        # Windows theme ignores most of them.
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", background=BG, foreground=INK)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("Hint.TLabel", background=BG, foreground=MUTED)
        style.configure("Count.TLabel", background=BG, foreground=ACCENT,
                        font=("", 12, "bold"))
        style.configure("TLabelframe", background=BG, foreground=MUTED,
                        bordercolor=ZERO_BG)
        style.configure("TLabelframe.Label", background=BG, foreground=MUTED)
        style.configure("TButton", background=PANEL, foreground=INK,
                        bordercolor=ZERO_BG, focuscolor=BG, padding=5)
        style.map("TButton",
                  background=[("active", ZERO_BG), ("pressed", ZERO_BG)])
        style.configure("TNotebook", background=BG, bordercolor=ZERO_BG)
        style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED,
                        padding=(14, 7))
        style.map("TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])
        style.configure("TEntry", fieldbackground=PANEL, foreground=INK,
                        bordercolor=ZERO_BG, insertcolor=INK)
        style.configure("TSpinbox", fieldbackground=PANEL, foreground=INK,
                        bordercolor=ZERO_BG, arrowcolor=INK)
        style.configure("TCheckbutton", background=BG, foreground=INK,
                        focuscolor=BG)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TScrollbar", background=PANEL, troughcolor=BG,
                        bordercolor=BG, arrowcolor=MUTED)


def main() -> None:
    """Open the bench."""
    Bench().mainloop()


if __name__ == "__main__":
    main()
