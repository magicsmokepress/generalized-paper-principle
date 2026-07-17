"""Benchmark the PERCEPTION path: render a word -> a reader transcribes it ->
count deterministically on the transcription.

The counting is guaranteed correct given the transcription, so what this bench
actually measures is the reader — how faithfully it turns rendered text back
into characters. Two numbers per reader:

  transcription-exact : read_back == word (the reader got every character)
  count-correct       : count_letter(read_back, letter) == true count
                        (the answer the user cares about; can survive a
                         transcription slip that doesn't touch the target letter)

count-correct >= transcription-exact always: a misread that doesn't change the
count still yields the right answer, because the count runs on whatever the
reader produced.

It also times each read so you can weigh the perception path against the text
path (count_letter is ~microseconds). The first call includes model/process
warmup — reported separately from the steady-state median.

Two readers, benched if available:
  - Tesseract  — local, CPU-only, model-free OCR (needs `pytesseract` + the
    `tesseract` binary). Always attempted.
  - VLM        — an OpenAI-compatible vision endpoint (needs `httpx`), enabled
    when VLM_URL/VLM_MODEL are set. Prompted to transcribe, not count.

Usage:
  python bench/bench_vision.py                     # Tesseract only, if installed
  VLM_URL=http://10.0.10.10:1241/v1 VLM_MODEL=Cosmos-Reason2-8B.Q5_K_M.gguf \
      python bench/bench_vision.py                 # Tesseract + that VLM

Needs Pillow to render. Each reader has its own optional dependency; a reader
whose deps or endpoint are missing is skipped with a note, not a crash.
"""
from __future__ import annotations

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "reference"))
from char_ops import _render, count_letter, tesseract_reader, vlm_reader  # noqa: E402

URL = os.environ.get("VLM_URL", "")
MODEL = os.environ.get("VLM_MODEL", "")

# Same character battery as the text bench, so the two are comparable.
WORDS = [("strawberry", "r"), ("Accessories", "c"), ("Mississippi", "s"),
         ("parallel", "l"), ("bookkeeper", "e"), ("banana", "a"),
         ("committee", "t"), ("rhythm", "y"), ("queue", "u"),
         ("fuchsia", "z"), ("entrepreneurship", "e"), ("onomatopoeia", "o")]


def _readers():
    """(label, reader) for each backend whose deps are actually present."""
    out = []
    try:                                             # Tesseract: local, model-free
        import pytesseract
        pytesseract.get_tesseract_version()          # raises if the binary is absent
        out.append(("Tesseract (CPU OCR)", tesseract_reader()))
    except Exception as e:
        print(f"  skip Tesseract: {type(e).__name__} {e}")
    if URL or MODEL:                                 # VLM: only when configured
        out.append((f"VLM {MODEL or URL}", vlm_reader(url=URL or None, model=MODEL or None)))
    else:
        print("  skip VLM: set VLM_URL / VLM_MODEL to bench a vision endpoint")
    return out


def _bench(label, reader):
    n = len(WORDS)
    exact = correct = 0
    read_ms = []
    print(f"\n== {label} ==")
    for word, letter in WORDS:
        true_count = count_letter(word, letter)
        png = _render(word)
        t = time.perf_counter()
        try:
            read = reader(png)
        except Exception as e:                       # perception is the fallible layer
            print(f"  ERR  {word!r}: {type(e).__name__} {e}")
            continue
        dt = (time.perf_counter() - t) * 1000
        read_ms.append(dt)
        is_exact = read.strip().lower() == word.lower()
        got = count_letter(read, letter)
        is_correct = got == true_count
        exact += is_exact
        correct += is_correct
        flag = "ok  " if is_correct else "MISS"
        note = "" if is_exact else f"  (read {read.strip()!r})"
        print(f"  [{flag}] {word!r:>18} '{letter}': count {got} vs {true_count}"
              f"  {dt:6.0f} ms{note}", flush=True)
    warmup = read_ms[0] if read_ms else 0.0
    steady = read_ms[1:] or read_ms
    med = statistics.median(steady) if steady else 0.0
    print(f"  -> transcription-exact {exact}/{n}   count-correct {correct}/{n}   "
          f"warmup {warmup:.0f} ms, steady median {med:.0f} ms/word")
    return {"label": label, "exact": exact, "correct": correct, "n": n, "med": med}


def main():
    rows = [_bench(label, reader) for label, reader in _readers()]
    if not rows:
        print("\nno readers available"); return
    print(f"\n| perception reader | transcription-exact | count-correct | steady-state latency |")
    print(f"| --- | --- | --- | --- |")
    for r in rows:
        print(f"| {r['label']} | {r['exact']}/{r['n']} | {r['correct']}/{r['n']} "
              f"| ~{r['med']:.0f} ms/word |")
    print("\n(text path `count_letter` is ~1 us/word and always exact — perception "
          "is the ceiling, not the count.)")


if __name__ == "__main__":
    main()
