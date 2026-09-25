"""Snap MIDI note times to a detected beat grid and quantise to a subdivision.

Notes are mapped into beat space by linear interpolation between detected beat
times (so tempo drift is absorbed), rounded to the nearest 1/`div` beat, then
written back on a fixed-tempo grid so downstream bar lines are exact.
"""
from __future__ import annotations

import numpy as np
import pretty_midi


def to_beat_space(times: np.ndarray, beats: np.ndarray) -> np.ndarray:
    """Seconds -> fractional beat index, extrapolating with the edge beat interval."""
    idx = np.arange(len(beats), dtype=float)
    lo, hi = beats[1] - beats[0], beats[-1] - beats[-2]
    out = np.interp(times, beats, idx)
    before = times < beats[0]
    after = times > beats[-1]
    out[before] = (times[before] - beats[0]) / lo
    out[after] = idx[-1] + (times[after] - beats[-1]) / hi
    return out


def quantize(pm: pretty_midi.PrettyMIDI, beats: np.ndarray, bpm: float, div: int = 4) -> pretty_midi.PrettyMIDI:
    """Return a new PrettyMIDI with notes snapped to 1/div beats on a fixed `bpm` grid.

    Notes on the same grid step with the same pitch are merged. Minimum length is one step.
    """
    beats = np.asarray(beats, dtype=float)
    spb = 60.0 / bpm
    out = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    for src in pm.instruments:
        inst = pretty_midi.Instrument(program=src.program, name=src.name)
        if not src.notes:
            out.instruments.append(inst)
            continue
        starts = to_beat_space(np.array([n.start for n in src.notes]), beats)
        ends = to_beat_space(np.array([n.end for n in src.notes]), beats)
        qs = np.round(starts * div) / div
        qe = np.maximum(np.round(ends * div) / div, qs + 1.0 / div)
        seen: dict[tuple[float, int], pretty_midi.Note] = {}
        for n, s, e in zip(src.notes, qs, qe):
            if s < 0:
                continue
            key = (float(s), n.pitch)
            if key in seen:
                seen[key].end = max(seen[key].end, e * spb)
                seen[key].velocity = max(seen[key].velocity, n.velocity)
                continue
            seen[key] = pretty_midi.Note(velocity=n.velocity, pitch=n.pitch, start=s * spb, end=e * spb)
        inst.notes = sorted(seen.values(), key=lambda n: (n.start, n.pitch))
        out.instruments.append(inst)
    return out


def detect_beats(wav_path: str, bpm_hint: float) -> tuple[float, np.ndarray]:
    import librosa

    y, sr = librosa.load(wav_path, sr=22050, mono=True)
    oenv = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=sr, bpm=bpm_hint, units="time")
    return float(np.atleast_1d(tempo)[0]), np.asarray(beats)
