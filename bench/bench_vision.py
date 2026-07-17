"""Benchmark the VISION path: render a word -> a VLM transcribes it -> count
deterministically on the transcription.

The counting is guaranteed correct given the transcription, so what this bench
actually measures is the PERCEPTION layer — how faithfully the vision model
reads clean rendered text back. Two numbers:

  transcription-exact : read_back == word (the reader got every character)
  count-correct       : count_letter(read_back, letter) == true count
                        (the answer the user cares about; can survive a
                         transcription slip that doesn't touch the target letter)

count-correct >= transcription-exact always: a misread that doesn't change the
count still yields the right answer, because the count runs on whatever the
reader produced.

It also times each read so you can weigh the vision path against the text path
(count_letter is ~microseconds; a local VLM is ~100 ms/word). The first call
includes model warmup — reported separately from the steady-state median.

Usage:
  python bench/bench_vision.py                     # defaults to env VLM_URL/VLM_MODEL
  VLM_URL=http://10.0.10.10:1241/v1 VLM_MODEL=Cosmos-Reason2-8B.Q5_K_M.gguf \
      python bench/bench_vision.py

Needs Pillow (render) + httpx (vlm_reader). A vision-capable endpoint only.
"""
from __future__ import annotations

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "reference"))
from char_ops import _render, count_letter, vlm_reader  # noqa: E402

URL = os.environ.get("VLM_URL", "http://localhost:1241/v1")
MODEL = os.environ.get("VLM_MODEL", "")

# Same character battery as the text bench, so the two are comparable.
WORDS = [("strawberry", "r"), ("Accessories", "c"), ("Mississippi", "s"),
         ("parallel", "l"), ("bookkeeper", "e"), ("banana", "a"),
         ("committee", "t"), ("rhythm", "y"), ("queue", "u"),
         ("fuchsia", "z"), ("entrepreneurship", "e"), ("onomatopoeia", "o")]


def main():
    reader = vlm_reader(url=URL, model=MODEL)
    n = len(WORDS)
    exact = correct = 0
    read_ms = []                                     # per-word inference latency
    print(f"vision endpoint {URL}  model {MODEL or '(endpoint default)'}")
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

    # First call carries model warmup — report it apart from steady state.
    warmup = read_ms[0] if read_ms else 0.0
    steady = read_ms[1:] or read_ms
    med = statistics.median(steady) if steady else 0.0
    print(f"\ntranscription-exact {exact}/{n}   count-correct {correct}/{n}")
    print(f"inference: warmup {warmup:.0f} ms, steady-state median {med:.0f} ms/word "
          f"(text path count_letter is ~1 us/word)")
    print(f"\n| vision reader | transcription-exact | count-correct | steady-state latency |")
    print(f"| --- | --- | --- | --- |")
    print(f"| `{MODEL or URL}` | {exact}/{n} | {correct}/{n} | ~{med:.0f} ms/word |")


if __name__ == "__main__":
    main()
