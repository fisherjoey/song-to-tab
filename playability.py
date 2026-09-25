"""Prune transcribed notes a single fingerpicking guitarist could not (or would not) play.

Operates on capo-shifted, quantised MIDI (shape space). Rules run in order and each
records what it removed so the result can be reviewed bar by bar.
"""
from __future__ import annotations

import itertools
import re
from collections import defaultdict
from dataclasses import dataclass, field

import pretty_midi

NAMES = "C C# D D# E F F# G G# A A# B".split()
OPEN = [40, 45, 50, 55, 59, 64]  # E A D G B e
MAX_FRET = 20


def name(p: int) -> str:
    return f"{NAMES[p % 12]}{p // 12 - 1}"


@dataclass
class Removed:
    step: int
    pitch: int
    rule: str


@dataclass
class Report:
    removed: list[Removed] = field(default_factory=list)
    chords: dict[int, str] = field(default_factory=dict)  # bar -> chord label

    def by_rule(self) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for r in self.removed:
            out[r.rule] += 1
        return dict(out)


def min_span(pitches: list[int]) -> int | None:
    """Smallest fret span over all string assignments; open strings ignored. None if unplayable."""
    best = None
    for strings in itertools.permutations(range(6), len(pitches)):
        frets = [p - OPEN[s] for p, s in zip(pitches, strings)]
        if any(f < 0 or f > MAX_FRET for f in frets):
            continue
        fretted = [f for f in frets if f > 0]
        span = (max(fretted) - min(fretted)) if fretted else 0
        if best is None or span < best:
            best = span
    return best


def rule_velocity(ev: list[pretty_midi.Note], floor: int) -> tuple[list, list]:
    keep = [n for n in ev if n.velocity >= floor]
    return keep, [n for n in ev if n.velocity < floor]


def rule_strum(ev: list[pretty_midi.Note], max_onsets: int) -> tuple[list, list]:
    if len(ev) < max_onsets:
        return ev, []
    thumb = min(ev, key=lambda n: n.pitch)
    return [thumb], [n for n in ev if n is not thumb]


def rule_span(ev: list[pretty_midi.Note], max_span: int) -> tuple[list, list]:
    ev = sorted(ev, key=lambda n: n.pitch)
    dropped: list = []
    while len(ev) > 1:
        s = min_span([n.pitch for n in ev])
        if s is not None and s <= max_span:
            break
        # drop whichever single note's removal gives the smallest span; on ties drop the highest
        best_i, best_s = None, None
        for i in reversed(range(len(ev))):
            s2 = min_span([n.pitch for j, n in enumerate(ev) if j != i])
            if s2 is not None and (best_s is None or s2 < best_s):
                best_i, best_s = i, s2
        if best_i is None:
            best_i = len(ev) // 2
        dropped.append(ev.pop(best_i))
    return ev, dropped


def rule_voices(ev: list[pretty_midi.Note], max_voices: int) -> tuple[list, list]:
    if len(ev) <= max_voices:
        return ev, []
    ev = sorted(ev, key=lambda n: n.pitch)
    keep = [ev[0], ev[-1]]
    middle = sorted(ev[1:-1], key=lambda n: -n.velocity)
    keep += middle[: max_voices - 2]
    return keep, [n for n in ev if n not in keep]


def fit_chords(events: dict[int, list], steps_per_bar: int, chords: dict[str, set[int]]) -> dict[int, str]:
    """Best chord per bar by note-time weight on chord tones."""
    bars: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for step, ev in events.items():
        for n in ev:
            bars[step // steps_per_bar][n.pitch % 12] += n.end - n.start
    out = {}
    for b, pcs in bars.items():
        tot = sum(pcs.values()) or 1
        out[b] = max(chords, key=lambda c: sum(pcs[p] for p in chords[c]) / tot)
    return out


def rule_chord(step: int, ev: list, chord: set[int], div: int) -> tuple[list, list]:
    if len(ev) != 1 or step % div == 0:
        return ev, []
    n = ev[0]
    return ([], [n]) if n.pitch % 12 not in chord else (ev, [])


def make_playable(
    pm: pretty_midi.PrettyMIDI,
    bpm: float,
    div: int = 4,
    beats_per_bar: int = 4,
    chords: dict[str, set[int]] | None = None,
    velocity_floor: int = 45,
    strum_onsets: int = 4,
    max_span: int = 4,
    max_voices: int = 3,
) -> tuple[pretty_midi.PrettyMIDI, Report]:
    step_len = 60.0 / bpm / div
    spb = div * beats_per_bar
    rep = Report()
    out = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    for src in pm.instruments:
        inst = pretty_midi.Instrument(program=src.program, name=src.name)
        events: dict[int, list] = defaultdict(list)
        for n in src.notes:
            events[int(round(n.start / step_len))].append(n)
        if chords:
            rep.chords = fit_chords(events, spb, chords)
        for step in sorted(events):
            ev = events[step]
            for rule, fn in (
                ("velocity", lambda e: rule_velocity(e, velocity_floor)),
                ("strum", lambda e: rule_strum(e, strum_onsets)),
                ("span", lambda e: rule_span(e, max_span)),
                ("voices", lambda e: rule_voices(e, max_voices)),
            ):
                ev, gone = fn(ev)
                rep.removed += [Removed(step, g.pitch, rule) for g in gone]
            if chords:
                ev, gone = rule_chord(step, ev, chords[rep.chords[step // spb]], div)
                rep.removed += [Removed(step, g.pitch, "chord") for g in gone]
            inst.notes += ev
        inst.notes.sort(key=lambda n: (n.start, n.pitch))
        out.instruments.append(inst)
    return out, rep


QUALITIES = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "maj7": (0, 4, 7, 11)}


def parse_chords(spec: str) -> dict[str, set[int]]:
    """'Bb,Eb,Gm,F' -> {'Bb': {10, 2, 5}, ...} as pitch classes (C = 0)."""
    out = {}
    for label in (c.strip() for c in spec.split(",")):
        if not label:
            continue
        m = re.fullmatch(r"([A-G])([#b]?)(maj7|m7|m|7)?", label)
        if not m:
            raise ValueError(f"unsupported chord name: {label!r}")
        root = (NAMES.index(m.group(1)) + {"#": 1, "b": -1, "": 0}[m.group(2)]) % 12
        out[label] = {(root + i) % 12 for i in QUALITIES[m.group(3) or ""]}
    return out


def shape_chords(sounding: dict[str, set[int]], capo: int) -> dict[str, set[int]]:
    return {k: {(p - capo) % 12 for p in v} for k, v in sounding.items()}


def report_text(rep: Report, div: int, beats_per_bar: int, capo: int = 0) -> str:
    spb = div * beats_per_bar
    lines = [f"note names are capo-relative (shape space, capo {capo}); chord labels are sounding", "removed per rule: " + ", ".join(f"{k}={v}" for k, v in sorted(rep.by_rule().items())), ""]
    by_bar: dict[int, list[Removed]] = defaultdict(list)
    for r in rep.removed:
        by_bar[r.step // spb].append(r)
    for b in sorted(by_bar):
        chord = rep.chords.get(b, "?")
        items = ", ".join(f"beat {r.step % spb / div + 1:g} {name(r.pitch)} ({r.rule})" for r in sorted(by_bar[b], key=lambda r: r.step))
        lines.append(f"bar {b:3d} [{chord}]: {items}")
    return "\n".join(lines)
