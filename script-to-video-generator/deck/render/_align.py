"""Standalone forced-alignment helper: WAV files -> word timestamps as JSON.

Run in an ISOLATED Python 3.11 env, not the main app: whisper-timestamped's
dependency chain (torch, numba) has no wheels for the project's Python 3.14, so
`record.py` shells out to this via
`uv run --no-project --python 3.11 --with whisper-timestamped python
 deck/render/_align.py <out.json> <wav> [<wav> ...]`.
It imports nothing from `deck`, so it runs fine under a different interpreter.

Loads the model ONCE and aligns every WAV, writing JSON to <out.json>:
  {"clips": [[{"w": text, "start": s, "end": s}, ...], ...]}   # one list per WAV
The model is "tiny" — plenty for aligning clean synthetic TTS.
"""
import json
import sys

import whisper_timestamped as whisper


def align(model, wav_path):
    result = whisper.transcribe(model, wav_path, language="en", verbose=False)
    words = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            words.append({"w": w["text"], "start": w["start"], "end": w["end"]})
    return words


if __name__ == "__main__":
    out_path, wavs = sys.argv[1], sys.argv[2:]
    model = whisper.load_model("tiny")
    clips = [align(model, w) for w in wavs]
    with open(out_path, "w") as f:
        json.dump({"clips": clips}, f)
