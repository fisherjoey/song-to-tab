import numpy as np
import pretty_midi

from quantize import quantize, to_beat_space


def _pm(notes):
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=25)
    inst.notes = [pretty_midi.Note(velocity=80, pitch=p, start=s, end=e) for p, s, e in notes]
    pm.instruments.append(inst)
    return pm


def test_beat_space_interpolates_and_extrapolates():
    beats = np.array([1.0, 2.0, 3.0])
    got = to_beat_space(np.array([0.5, 1.0, 1.5, 3.0, 3.5]), beats)
    assert np.allclose(got, [-0.5, 0.0, 0.5, 2.0, 2.5])


def test_snaps_to_16ths_on_fixed_grid():
    beats = np.array([0.0, 0.5, 1.0, 1.5])  # 120 bpm
    pm = _pm([(60, 0.13, 0.30), (62, 0.49, 0.70)])  # ~1/4 beat and ~1 beat
    q = quantize(pm, beats, bpm=120, div=4)
    n = q.instruments[0].notes
    assert [(x.pitch, round(x.start, 3), round(x.end, 3)) for x in n] == [(60, 0.125, 0.25), (62, 0.5, 0.75)]


def test_tempo_drift_is_absorbed():
    beats = np.array([0.0, 0.6, 1.3, 2.1])  # slowing down
    pm = _pm([(60, 1.3, 1.7)])  # exactly on beat 2, held half a beat
    q = quantize(pm, beats, bpm=100, div=4)
    n = q.instruments[0].notes[0]
    assert round(n.start, 3) == round(2 * 0.6, 3)
    assert round(n.end, 3) == round(2.5 * 0.6, 3)


def test_merges_duplicates_and_enforces_min_length():
    beats = np.array([0.0, 1.0, 2.0])
    pm = _pm([(60, 0.0, 0.01), (60, 0.02, 0.6), (64, -0.5, 0.0)])
    q = quantize(pm, beats, bpm=60, div=4)
    n = q.instruments[0].notes
    assert len(n) == 1
    assert n[0].pitch == 60 and n[0].start == 0.0 and round(n[0].end, 3) == 0.5
