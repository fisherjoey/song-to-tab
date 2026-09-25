"""Basic Pitch MIDI -> capo-relative, range-filtered MIDI -> tuttut ASCII tab.

Usage: uv run python song_to_tab.py <in.mid> <out_dir> [--capo 3] [--bpm 90]
           [--beats-from stem.wav --div 4 | --offset 8.7] [--playable --chords Bb,Eb,Gm,F]
"""
import argparse
from pathlib import Path

import pretty_midi
from tuttut.logic.tab import Tab
from tuttut.logic.theory import Tuning

from playability import make_playable, parse_chords, report_text, shape_chords
from quantize import detect_beats, quantize

E2, E6 = 40, 88  # open low E .. ~fret 20 on high E, in shape space


def clean(pm: pretty_midi.PrettyMIDI, capo: int, min_dur: float, bpm: float | None, offset: float = 0.0) -> pretty_midi.PrettyMIDI:
    out = pretty_midi.PrettyMIDI(initial_tempo=bpm or pm.estimate_tempo())
    inst = pretty_midi.Instrument(program=25, name="guitar")  # steel acoustic
    kept = dropped_range = dropped_short = 0
    for src in pm.instruments:
        for n in src.notes:
            p = n.pitch - capo
            if n.end - n.start < min_dur:
                dropped_short += 1
                continue
            if not (E2 <= p <= E6):
                dropped_range += 1
                continue
            if n.start < offset:
                continue
            inst.notes.append(pretty_midi.Note(velocity=n.velocity, pitch=p, start=n.start - offset, end=n.end - offset))
            kept += 1
    inst.notes.sort(key=lambda n: (n.start, n.pitch))
    out.instruments.append(inst)
    print(f"kept {kept}, dropped {dropped_range} out of range, {dropped_short} shorter than {min_dur}s")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("midi", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--capo", type=int, default=3)
    ap.add_argument("--min-dur", type=float, default=0.05)
    ap.add_argument("--bpm", type=float, default=None)
    ap.add_argument("--offset", type=float, default=0.0, help="time of first downbeat; earlier notes dropped")
    ap.add_argument("--beats-from", type=Path, default=None, help="wav to beat-track; enables quantisation")
    ap.add_argument("--div", type=int, default=4, help="grid steps per beat (4 = 16ths)")
    ap.add_argument("--beat-shift", type=int, default=0, help="beats to skip so bar 1 starts on a downbeat")
    ap.add_argument("--playable", action="store_true", help="prune notes one fingerpicker could not play")
    ap.add_argument("--velocity-floor", type=int, default=45)
    ap.add_argument("--strum-onsets", type=int, default=4)
    ap.add_argument("--max-span", type=int, default=4)
    ap.add_argument("--max-voices", type=int, default=3)
    ap.add_argument("--chords", default=None,
                    help="comma-separated sounding chords for the chord prior, e.g. Bb,Eb,Gm,F (major/m/7/m7/maj7)")
    a = ap.parse_args()
    if a.playable and not (a.bpm or a.beats_from):
        ap.error("--playable needs --bpm or --beats-from")

    a.out_dir.mkdir(parents=True, exist_ok=True)
    pm = pretty_midi.PrettyMIDI(str(a.midi))
    if a.beats_from:
        bpm, beats = detect_beats(str(a.beats_from), a.bpm or 90)
        beats = beats[a.beat_shift:]
        print(f"beat-tracked {len(beats)} beats, first at {beats[0]:.2f}s, ~{60/float((beats[1:]-beats[:-1]).mean()):.1f} bpm")
        a.bpm = a.bpm or round(bpm)
        pm = quantize(pm, beats, a.bpm, a.div)
        a.offset = 0.0
    pm = clean(pm, a.capo, a.min_dur, a.bpm, a.offset)
    if a.playable:
        pm, rep = make_playable(pm, a.bpm, a.div, chords=shape_chords(parse_chords(a.chords), a.capo) if a.chords else None,
                                velocity_floor=a.velocity_floor, strum_onsets=a.strum_onsets,
                                max_span=a.max_span, max_voices=a.max_voices)
        report = a.out_dir / f"{a.midi.stem}.removed.txt"
        report.write_text(report_text(rep, a.div, 4, a.capo))
        print("playability:", ", ".join(f"{k}={v}" for k, v in sorted(rep.by_rule().items())), f"-> {report}")
    cleaned = a.out_dir / f"{a.midi.stem}.capo{a.capo}.mid"
    pm.write(str(cleaned))

    tab = Tab(cleaned.stem, Tuning(), pm, output_dir=str(a.out_dir))
    tab.to_ascii()
    print(f"wrote {a.out_dir / (Path(cleaned.stem).stem + '.txt')}")  # tuttut drops the .capoN suffix


if __name__ == "__main__":
    main()
