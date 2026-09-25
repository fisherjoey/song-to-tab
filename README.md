# song-to-tab

A hobby experiment: how close can off-the-shelf, open models get to turning a recorded song
into a guitar tab you could actually play?

It chains existing tools (source separation, audio-to-MIDI transcription, beat tracking and a
fingering model) with a little glue code for capo handling, quantisation and playability
pruning. It is not a finished app. Expect to hand-fix the output.

I built it against a commercially released, fingerpicked acoustic song (capo 3, four chords,
around 90 bpm, vocals in the mix). That song's audio, stems, MIDI and tabs are not in this
repository. Bring your own audio, and only use recordings you have the rights to use (your
own playing, something you licensed, or public-domain material).

## Pipeline

| Stage | Tool / model | Output |
|---|---|---|
| 1. Guitar stem | [Mel-Band RoFormer guitar checkpoint by becruily](https://huggingface.co/becruily/mel-band-roformer-guitar), run through [ZFTurbo's Music-Source-Separation-Training](https://github.com/ZFTurbo/Music-Source-Separation-Training) (MSST) | `stems/roformer/<song>/Guitar.wav` |
| 1b. Alternative stem | [Demucs](https://github.com/facebookresearch/demucs) `htdemucs_6s` (has a guitar stem; noisier, more bass bleed) | `stems/htdemucs_6s/<song>/guitar.wav` |
| 2. Audio to MIDI | [Spotify Basic Pitch](https://github.com/spotify/basic-pitch) | `midi/roformer/Guitar_basic_pitch.mid` |
| 3. Beat grid + quantise | [librosa](https://librosa.org) beat tracking on the stem, then `quantize.py` snaps notes to 16ths | in memory |
| 4. Clean up | `song_to_tab.py`: shift into capo-relative "shape space", drop notes outside guitar range or too short | `<out>/<name>.capoN.mid` |
| 5. Playability (optional) | `playability.py`: velocity floor, strum collapse, 4-fret hand span, voice cap, chord prior | `<out>/<name>.removed.txt` report |
| 6. Fingering | [tuttut](https://github.com/natecdr/tuttut) (HMM that tries to minimise hand movement) | `<out>/<name>.txt` ASCII tab |
| 7. Layout | `render_tab.py` wraps the tab into lines of N bars | stdout |

## Requirements

- Linux or macOS, Python 3.11, [uv](https://docs.astral.sh/uv/).
- A GPU is optional. With an NVIDIA card, separating a 3 to 4 minute song takes under 10
  seconds. On a CPU it works but takes minutes. Everything after separation runs fine on a CPU.
- About 8 GB of disk for the Python environment. PyTorch with CUDA and TensorFlow (pulled in by
  Basic Pitch) are both large.
- Versions pinned in `uv.lock`: torch 2.14, Basic Pitch 0.4.0, Demucs 4.1.0, tuttut 0.0.6,
  librosa 0.11, numpy 1.x.

## Setup

```sh
git clone https://github.com/fisherjoey/song-to-tab.git
cd song-to-tab
uv sync

# MSST (separation code). Not vendored here; clone it next to the project.
git clone --depth 1 https://github.com/ZFTurbo/Music-Source-Separation-Training vendor/msst

# becruily guitar checkpoint and its config (~45 MB)
mkdir -p models
curl -L -o models/becruily_guitar.ckpt \
  https://huggingface.co/becruily/mel-band-roformer-guitar/resolve/main/becruily_guitar.ckpt
curl -L -o models/config_guitar_becruily.yaml \
  https://huggingface.co/becruily/mel-band-roformer-guitar/resolve/main/config_guitar_becruily.yaml
```

`vendor/`, `models/`, audio, stems, MIDI and tabs are all gitignored.

## Usage

Put a WAV file in `audio/` (for example `audio/my-song.wav`), then:

```sh
# 1. Separate the guitar
uv run python vendor/msst/inference.py --model_type mel_band_roformer \
  --config_path models/config_guitar_becruily.yaml \
  --start_check_point models/becruily_guitar.ckpt \
  --input_folder audio --store_dir stems/roformer

#    or, with Demucs:
uv run demucs -n htdemucs_6s -o stems audio/my-song.wav

# 2. Transcribe the stem to MIDI
uv run basic-pitch midi/roformer stems/roformer/my-song/Guitar.wav --save-midi

# 3-6. Beat-snap, clean up, prune and finger
uv run python song_to_tab.py midi/roformer/Guitar_basic_pitch.mid tabs/my-song \
  --capo 3 --bpm 90 \
  --beats-from stems/roformer/my-song/Guitar.wav --div 4 \
  --playable --chords Bb,Eb,Gm,F

# 7. Lay it out 4 bars per line
uv run python render_tab.py tabs/my-song/Guitar_basic_pitch.txt 4 > tabs/my-song.txt
```

Useful options for `song_to_tab.py`:

- `--capo N`: the tab comes out relative to the capo, so a `3` means three frets above it.
- `--bpm`: a tempo hint for the beat tracker. Without `--beats-from` it sets a fixed grid.
- `--beats-from stem.wav --div 4`: beat-track the stem and quantise to 1/div of a beat.
- `--beat-shift N`: skip N detected beats so bar 1 starts on a downbeat. The first detected
  beat is often not beat 1.
- `--offset SECONDS`: when not beat-tracking, drop everything before the first downbeat.
- `--playable` and its knobs `--velocity-floor`, `--strum-onsets`, `--max-span`, `--max-voices`.
- `--chords`: the song's sounding chords (major, `m`, `7`, `m7`, `maj7`). Turns on the chord
  prior, which drops isolated off-beat notes that are not in the bar's best-fitting chord.

Run `uv run python song_to_tab.py --help` for the full list.

## Results so far

Everything below comes from one fingerpicked acoustic song with vocals.

### What works reasonably well

- Separation. The RoFormer guitar stem was clearly cleaner than Demucs `htdemucs_6s`: about
  2% of transcribed notes fell below the playable range, against about 8% for Demucs, mostly
  bass bleed.
- Pitch content. Basic Pitch got the harmony right. A pitch-class histogram gave exactly the
  song's four chords, and a windowed chord fit followed the song's form.
- Fingering. tuttut picked sensible open-position shapes, and the alternating-bass
  fingerpicking pattern was recognisable.
- Beat-snapping. After quantising to the librosa beat grid, bar lines line up and the picking
  pattern shows up as regular 16th positions.

### Weak or unfinished

- Downbeats. Beat tracking finds beats but not bar 1. `--beat-shift` is a manual guess.
- Rhythm and note lengths still need hand-fixing. Quantisation to 16ths helps but does not know
  about swing, triplets or held notes.
- Bleed. Some high notes are clearly vocals or harmonics leaking into the stem.
- Fingering does not know which chord is being held, so some notes land on the wrong string.
- The playability rules are hand-tuned on one song. The strum rule was good at removing a
  second guitar's strummed chords. The other thresholds are guesses and have not been checked
  against a reference tab.
- Output is plain ASCII only. No Guitar Pro or MusicXML export yet.

### Next steps

- Better downbeat detection (for example madmom), so bar 1 no longer has to be set by hand.
- Tuning the quantiser and Basic Pitch thresholds (onset threshold, minimum frequency) to cut
  bleed.
- Writing `.gp5` via PyGuitarPro so the result opens in TuxGuitar or Guitar Pro for editing.

`docs/tool-survey.md` has the notes on which tools were considered and why these were picked.

## Tests

The unit tests cover quantisation and the playability rules. They need no models or audio:

```sh
uv run pytest
```

CI installs only the light dependencies these tests need (`numpy`, `pretty-midi`, `pytest`) and
runs them on a CPU.

## License

The code in this repository is MIT licensed. See [LICENSE](LICENSE).

The models and tools it calls have their own licenses, and you must follow them. At the time
of writing, MSST, Demucs and tuttut are MIT, Basic Pitch is Apache-2.0 and librosa is ISC.
The becruily guitar checkpoint does not state a license on its model page, so ask its author
before using it for anything beyond personal experiments. You are responsible for the audio you
run through the pipeline.
