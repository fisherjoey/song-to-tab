import pretty_midi

import pytest

from playability import make_playable, min_span, parse_chords, rule_span, rule_strum, rule_voices, shape_chords


def N(p, v=80, s=0.0, e=0.1):
    return pretty_midi.Note(velocity=v, pitch=p, start=s, end=e)


def test_min_span_open_chord_is_zero_and_wide_is_none_or_big():
    assert min_span([43, 47, 50, 55, 59, 67]) == 1   # open G shape: frets 3,2,0,0,0,3
    assert min_span([41, 88]) is None or min_span([41, 88]) > 4  # F on low E + top-fret e


def test_strum_keeps_thumb():
    keep, gone = rule_strum([N(43), N(47), N(50), N(55)], 4)
    assert [n.pitch for n in keep] == [43] and len(gone) == 3
    keep, gone = rule_strum([N(43), N(47), N(50)], 4)
    assert len(keep) == 3 and gone == []


def test_span_drops_outlier():
    keep, gone = rule_span([N(41), N(45), N(64 + 12)], 4)  # F2, A2 open, e at fret 12
    assert [n.pitch for n in gone] == [76]


def test_voices_keeps_bass_top_and_loudest_middle():
    keep, gone = rule_voices([N(40, 50), N(47, 90), N(52, 60), N(59, 70)], 3)
    assert sorted(n.pitch for n in keep) == [40, 47, 59]


def test_pipeline_velocity_and_chord_prior():
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=25)
    step = 60 / 120 / 4
    # bar of G-shape (Bb sounding at capo 3): B2 D3 G3 on beats, then a quiet off-beat C# and an off-beat chord tone
    inst.notes = [N(47, 80, 0, 0.5), N(50, 80, 0, 0.5), N(55, 80, 0, 0.5),
                  N(61, 30, step, step * 2),              # quiet -> velocity
                  N(61, 80, step * 3, step * 4),          # C#, off-beat, not a G-chord tone -> chord
                  N(59, 80, step * 5, step * 6)]          # B, off-beat chord tone -> kept
    pm.instruments.append(inst)
    chords = shape_chords({"Bb": {10, 2, 5}, "Eb": {3, 7, 10}}, capo=3)  # -> G, C shapes
    out, rep = make_playable(pm, bpm=120, div=4, chords=chords, velocity_floor=45)
    assert rep.by_rule() == {"velocity": 1, "chord": 1}
    assert rep.chords[0] == "Bb"
    assert sorted(n.pitch for n in out.instruments[0].notes) == [47, 50, 55, 59]


def test_parse_chords():
    assert parse_chords("Bb, Eb,Gm,F") == {"Bb": {10, 2, 5}, "Eb": {3, 7, 10}, "Gm": {7, 10, 2}, "F": {5, 9, 0}}
    assert parse_chords("C#m7,Dmaj7") == {"C#m7": {1, 4, 8, 11}, "Dmaj7": {2, 6, 9, 1}}
    with pytest.raises(ValueError):
        parse_chords("Hsus4")
