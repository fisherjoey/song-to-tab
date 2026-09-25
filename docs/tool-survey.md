# Song to guitar tab: tool landscape (survey, September 2026)

Written while choosing the tools for this project. The test case was a fingerpicked acoustic
song in a full mix with vocals, where only chord charts existed online and no string/fret tab.

## Separation (needed: vocals in the mix)
1. becruily Mel-Band RoFormer guitar ckpt via ZFTurbo MSST (MIT, 2026-09): best local dedicated guitar stem. Ckpt in HF Politrees/UVR_resources.
2. Demucs htdemucs_6s: has guitar stem, "so-so", repo archived 2024.
3. MVSEP hosted: best numbers (guitar SDR 9.05, Lead/Rhythm guitar model Mar 2026), weights not downloadable.

## Audio → MIDI
1. Spotify Basic Pitch (Apache-2, 5.6k): default. Raise onset threshold to suppress percussive hits.
2. trimplexx/music-transcription: GuitarSet CRNN, 2026-01, no license. Second opinion.
3. YourMT3+: multi-instrument from full mix, heavy, GPL.
Research with no released weights: Riley et al. ICASSP 2024 (fingerstyle domain adaptation), TART v2 (Sept 2026, 71.8% tab F1), Klangio Fretting-Transformer.

## MIDI → tab (fingering)
1. natecdr/tuttut (MIT, 139★, 2026-03): HMM-style, minimizes hand movement, ASCII out.
2. V2arK/midi-to-guitar-tab (MIT, 2026-04): writes .gp5 via PyGuitarPro.
3. stephenmthomas/midi2tab: Viterbi DP, pushed 2026-09-13.
TuxGuitar / MuseScore 4 MIDI import = naive first-position fingering. Guitar Pro 8 better but paid.

## Commercial
- Klangio Guitar2Tabs ($4.99/mo MuseHub): guitar-specialised, fingerpicking research behind it. Best paid bet.
- Songsterr AI ($9.90/mo): YouTube link → draft tab, "fairly accurate", good editor.
- Moises: stems + chords, no tab export. Chordify: chords only.

## End-to-end OSS (hobby grade, glue reference only)
philipposk/riffscribe (WebGPU, Basic Pitch + demucs-web + DP fingering), mgd1984/tab-gener8or, topkoa/TabGrabber.

## Realistic accuracy
Clean guitar: 70 to 90% of notes right; rhythm quantisation and fingering are the hand-fix parts. Percussive hits and harmonics misread badly by everything OSS.

## Recommended local pipeline
your audio file → MSST Mel-RoFormer guitar stem → Basic Pitch (tuned thresholds) → tuttut / .gp5 writer → TuxGuitar or MuseScore for cleanup.

## Sources
https://github.com/ZFTurbo/Music-Source-Separation-Training
https://huggingface.co/Politrees/UVR_resources
https://github.com/facebookresearch/demucs
https://mvsep.com/en/news
https://github.com/spotify/basic-pitch
https://github.com/trimplexx/music-transcription
https://github.com/mimbres/yourmt3
https://xavriley.github.io/HighResolutionGuitarTranscription/
https://arxiv.org/abs/2609.11904
https://arxiv.org/abs/2506.14223
https://github.com/natecdr/tuttut
https://github.com/V2arK/midi-to-guitar-tab
https://github.com/stephenmthomas/midi2tab
https://github.com/Perlence/PyGuitarPro
https://github.com/helge17/tuxguitar
https://www.musehub.com/app/guitar2tabs
https://www.songsterr.com/help
https://github.com/philipposk/riffscribe
