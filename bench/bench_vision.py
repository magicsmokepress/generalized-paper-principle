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

Usage:
  python bench/bench_vision.py                     # defaults to env VLM_URL/VLM_MODEL
  VLM_URL=http://10.0.10.10:1241/v1 VLM_MODEL=Cosmos-Reason2-8B.Q5_K_M.gguf \
      python bench/bench_vision.py

Needs Pillow (render) + httpx (vlm_reader). A vision-capable endpoint only.
"""
from __future__ import annotations

import os
import sys

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
    print(f"vision endpoint {URL}  model {MODEL or '(endpoint default)'}")
    for word, letter in WORDS:
        true_count = count_letter(word, letter)
        try:
            read = reader(_render(word))
        except Exception as e:                       # perception is the fallible layer
            print(f"  ERR  {word!r}: {type(e).__name__} {e}")
            continue
        is_exact = read.strip().lower() == word.lower()
        got = count_letter(read, letter)
        is_correct = got == true_count
        exact += is_exact
        correct += is_correct
        flag = "ok  " if is_correct else "MISS"
        note = "" if is_exact else f"  (read {read.strip()!r})"
        print(f"  [{flag}] {word!r:>18} '{letter}': count {got} vs {true_count}{note}", flush=True)
    print(f"\ntranscription-exact {exact}/{n}   count-correct {correct}/{n}")
    print(f"\n| vision reader | transcription-exact | count-correct |")
    print(f"| --- | --- | --- |")
    print(f"| `{MODEL or URL}` | {exact}/{n} | {correct}/{n} |")


if __name__ == "__main__":
    main()
