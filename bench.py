"""The Possibility Bench -- a GUI for playing with superposition.

Run it with::

    python bench.py

Three benches, one idea.  Everywhere you see a cell you can click it, and
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

Standard library only: Tkinter for the windows, and the project's own
modules for all the actual thinking.  This GUI holds no possibility logic
of its own -- it drives the real classes, so what you see here is exactly
what your scripts will do.
"""

import os
import tkinter as tk
from tkinter import filedialog, font, messagebox, ttk
from itertools import islice

from BinaryGlitch import BinaryGlitch
from BinaryPossibility import BinaryRegister
from binarypossibilitytrees import BinaryPossibilityTree
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


def _style_cell(button: tk.Button, state) -> None:
    """Paint a bit/step button to match its state."""
    if state is None:
        button.configure(text="?", bg=SUPER_BG, fg=SUPER_FG,
                         activebackground=SUPER_BG)
    elif state == 1:
        button.configure(text="1", bg=ONE_BG, fg=ONE_FG,
                         activebackground=ONE_BG)
    else:
        button.configure(text="0", bg=ZERO_BG, fg=ZERO_FG,
                         activebackground=ZERO_BG)


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
            text="Click a bit to cycle it:  0  →  1  →  ?  →  0",
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

        state_box = ttk.LabelFrame(panes, text=" reachable states ", padding=8)
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
            button.pack(side="left", padx=2)
            self.cells.append(button)
        self.refresh()

    def cycle(self, index: int) -> None:
        self.register.set_bit(index, NEXT_STATE[self.register.get_bit(index)])
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
            _style_cell(cell, self.register.get_bit(index))

        count = self.register.calculate_possibility_count()
        superposed = sum(
            1 for p in self.register.get_individual_states() if p.is_superposition()
        )
        self.count_label.configure(
            text=f"{_pretty_count(count)} possible states"
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

        self.state_text.delete("1.0", "end")
        shown = list(islice(self.register.iter_states(), STATE_PREVIEW_LIMIT))
        body = "\n".join(shown)
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
                 "Every ? doubles the number of songs this pattern holds.",
            style="Hint.TLabel",
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
                # A wider gap every four steps, so the beat is readable.
                pad = (1, 7) if step_index % 4 == 3 else (1, 1)
                button.grid(row=track_index, column=step_index + 1, padx=pad,
                            pady=2)
                row.append(button)
            self.cells.append(row)

    def cycle(self, track_index: int, step_index: int) -> None:
        self.rack.tracks[track_index].cycle_step(step_index)
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
                _style_cell(cell, track.get_step(step_index))
        count = self.rack.possibility_count()
        self.count_label.configure(
            text=f"{_pretty_count(count)} possible songs"
            f"   ·   {self.rack.superposed_step_count()} steps undecided"
        )

    def render(self) -> None:
        self.rack.bpm = float(self.bpm_var.get())
        patterns = self.rack.collapse(seed=self.seed_var.get())
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


class Bench(tk.Tk):
    """The main window: three benches in a notebook."""

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
        style.configure("TScrollbar", background=PANEL, troughcolor=BG,
                        bordercolor=BG, arrowcolor=MUTED)


def main() -> None:
    """Open the bench."""
    Bench().mainloop()


if __name__ == "__main__":
    main()
