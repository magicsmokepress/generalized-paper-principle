"""Benchmark: does the harness lift THIS model, on which column?

Runs an arithmetic battery and a character-counting battery against any
OpenAI-compatible endpoint, twice each:
  bare      — the model's one-pass answer
  harnessed — verify-then-re-derive (stage 1: name the op, one retry;
              stage 2: substitute the deterministic result)

and reports, per column, the numbers that decide tool-vs-demo:
  bare accuracy / harnessed accuracy — the lift
  catch rate   — wrong drafts that verify_answer flagged (coverage)
  false flags  — correct drafts that verify_answer flagged (must be 0)

Usage:
  OPENAI_BASE_URL=http://host:1234/v1 python bench/bench.py
  BENCH_MODEL=<name>       # default: first model the endpoint lists
  OPENAI_API_KEY=<key>     # default: "none" (local endpoints ignore it)
  BENCH_SUFFIX=" /no_think"  # optional, appended to every prompt

Stdlib only. Temperature 0. One row of the README matrix per run.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "reference"))
from calc import calc                                    # noqa: E402
from char_ops import count_letter                        # noqa: E402
from verify import _answer_has, _claimed_number, correction_message, verify_answer  # noqa: E402

BASE = (os.environ.get("OPENAI_BASE_URL") or os.environ.get("BENCH_URL")
        or "http://localhost:1234/v1").rstrip("/")
KEY = os.environ.get("OPENAI_API_KEY", "none")
SUFFIX = os.environ.get("BENCH_SUFFIX", "")
# Reasoning models spend tokens thinking before the visible answer; a low cap
# truncates to empty content and silently zeroes the whole bench.
MAX_TOKENS = int(os.environ.get("BENCH_MAX_TOKENS", "3000"))


def _http(path, payload=None):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(payload).encode() if payload else None,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


MODEL = os.environ.get("BENCH_MODEL") or _http("/models")["data"][0]["id"]


def llm(prompt):
    out = _http("/chat/completions", {
        "model": MODEL, "temperature": 0, "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt + SUFFIX}]})
    choice = out["choices"][0]
    text = (choice["message"]["content"] or "").strip()
    if not text and choice.get("finish_reason") == "length":
        print("    WARNING: empty answer, reasoning truncated — raise BENCH_MAX_TOKENS", flush=True)
    return text


# ── batteries ──────────────────────────────────────────────────────────────
ARITH_EXPRS = ["17 × 23 − 4^3", "6! ÷ (14+22) × 3", "1200 × 12", "89 × 76",
               "2401^0.5 + 13^2", "(847 − 269) × 34", "58 × 47 − 1963",
               "312 ÷ 8 + 19 × 7", "7! ÷ 5!", "13^3 − 999", "456 × 789",
               "9876 − 4321 + 55 × 8"]
ARITH = [(f"What is {e}?", calc(e)[0]) for e in ARITH_EXPRS]
assert all(v is not None for _, v in ARITH)

CHAR_WORDS = [("strawberry", "r"), ("Accessories", "c"), ("Mississippi", "s"),
              ("parallel", "l"), ("bookkeeper", "e"), ("banana", "a"),
              ("committee", "t"), ("rhythm", "y"), ("queue", "u"),
              ("fuchsia", "z"), ("entrepreneurship", "e"), ("onomatopoeia", "o")]
CHAR = [(f'How many "{c}" are in "{w}"?', count_letter(w, c)) for w, c in CHAR_WORDS]


def check_arith(expected, answer):
    return _answer_has(expected, answer)


def check_char(expected, answer):
    return _claimed_number(answer) == expected


def run(items, checker, label):
    n = len(items)
    bare = harness = caught = wrong = false_flag = correct = 0
    for q, expected in items:
        draft = llm(q)
        ok = checker(expected, draft)
        findings = verify_answer(q, draft)
        bare += ok
        if ok:
            correct += 1
            false_flag += bool(findings)
        else:
            wrong += 1
            caught += bool(findings)
        final = draft
        if findings:                                   # stage 1: re-derive
            final = llm(f"{q}\n\n{correction_message(findings)}")
            if verify_answer(q, final):                # stage 2: substitute
                final = " ".join(str(f["expected"]) for f in findings)
        harness += checker(expected, final)
        print(f"  [{label}] {'ok ' if ok else 'MISS'} "
              f"{'flagged' if findings else '-      '} {q[:58]}", flush=True)
    print(f"{label}: bare {bare}/{n}  harnessed {harness}/{n}  "
          f"caught {caught}/{wrong} wrong  false-flags {false_flag}/{correct} correct")
    return bare, harness, caught, wrong, false_flag, n


if __name__ == "__main__":
    print(f"endpoint {BASE}  model {MODEL}")
    a = run(ARITH, check_arith, "arith")
    c = run(CHAR, check_char, "chars")
    fmt = lambda r: f"{r[0]}/{r[5]} → {r[1]}/{r[5]} (caught {r[2]}/{r[3]}, false-flags {r[4]})"
    print(f"\n| model | arithmetic (bare → harnessed) | char counting (bare → harnessed) |")
    print(f"| --- | --- | --- |")
    print(f"| `{MODEL}` | {fmt(a)} | {fmt(c)} |")
