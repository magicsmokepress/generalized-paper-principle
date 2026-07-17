# generalized-paper-principle

![CI](https://github.com/magicsmokepress/generalized-paper-principle/actions/workflows/ci.yml/badge.svg)

> *Most people pull out a piece of paper for anything beyond basic math. An LLM
> should too.* This repo generalizes that principle — for math **and**
> characters — and makes it mechanical.

**For LLMs without a guaranteed code interpreter** — local models, hosted
small/non-frontier endpoints, and frontier models on character tasks. If your
model always runs code for every computation, you don't need this. Everyone
else's model *predicts* tokens where it should *compute*: `17×23−4³` comes out
`329` not `327`, "Accessories" gets "one c" instead of two — with no internal
signal that it erred, and it doubles down when challenged. The fix is the one
people already use: **externalize it — reach for the calculator, spell it out
on paper.** This repo packages that as deterministic tools plus harness
patterns, framework-agnostic.

## One thesis, two decay curves

**Arithmetic degrades with scale; character work decays slower.** Tokenization
doesn't care about parameter count, so character work was long the failure that
survived scale — though the famous cases (strawberry's r's) are now trained
around at the frontier, and our own measurements below show it. Expected lifts,
before measuring:

| | arithmetic | char counting |
|---|---|---|
| local small (7B–30B) | big lift | big lift |
| hosted mid-tier | moderate lift | big lift |
| frontier | ~none | unproven — measure it |

Measure your own cell — that table is the repo's claim, and `bench/bench.py`
produces your row against any OpenAI-compatible endpoint:

```bash
OPENAI_BASE_URL=http://localhost:1234/v1 python bench/bench.py
```

It reports bare accuracy, harnessed accuracy, catch rate, and false-flag rate —
the four numbers that decide whether this is a tool or a demo. Measured rows so
far (temperature 0, 12 items per column):

| model | arithmetic (bare → harnessed) | char counting (bare → harnessed) |
| --- | --- | --- |
| `gemma-4-26B-A4B-it-Q5_K_M` (local KoboldCpp, reasoning on, unbounded thinking) | 12/12 → 12/12, 0 false flags | 12/12 → 12/12, 0 false flags |
| `gemma-4-26B-A4B-it-Q5_K_M` (same model, thinking truncated at 400 tokens) | 3/12 bare | 11/12 bare |
| `anthropic/claude-opus-4.8` (OpenRouter) | 12/12 → 12/12, 0 false flags | 12/12 → 12/12, 0 false flags |
| `openai/gpt-5.5` (OpenRouter) | 12/12 → 12/12, 0 false flags | 12/12 → 12/12, 0 false flags |
| `x-ai/grok-4.5` (OpenRouter) | 12/12 → 12/12, 0 false flags | **11/12 → 12/12** (1 caught, re-derived correct), 0 false flags |

Honest findings from the measured rows:

- **The frontier char-counting cell is model-dependent.** Opus 4.8 and GPT-5.5
  saturate this battery — the famous character failures are trained around
  there, at least for short common words at temperature 0. Grok 4.5 aced the
  arithmetic and still miscounted the e's in "bookkeeper"; the backstop flagged
  it, the model re-derived, and the final answer was correct — the full
  verify-then-re-derive loop closing on a frontier model. Where the cell is
  empty, we don't claim a lift; harder character work (long rare strings,
  adversarial spacing, non-Latin scripts) remains unmeasured.
- **The lift concentrates down-spectrum and under constrained thinking.** A
  local 26B reasoning model saturates the battery with unbounded thinking, then
  loses most of its arithmetic (12/12 → 3/12) when its reasoning is truncated —
  exactly the regime batch/latency-limited and non-reasoning deployments run in.
- **On a saturating model the harness costs nothing:** 0 false flags across
  every row means the backstop never takes away a correct answer.

Measured rows for hosted mid-tier and non-reasoning small models welcome.

## Two layers

- **Deterministic tools** (`reference/`) — pure functions, no model in the loop
  for the actual computation. **Guaranteed correct. Drop-in.**
  - `calc.py` — AST-safe calculator (`calc("17 × 23 − 4³") → 327`).
  - `char_ops.py` — deterministic `count_letter` / `char_at` / `reverse_word`
    (NFC-normalized, combining-mark-safe), plus `count_letter_in_image` /
    `visual_spell` with a **pluggable perception reader** (VLM, Tesseract,
    Coral, cloud — any `png->str`); counting stays deterministic.
  - `verify.py` — `verify_answer(prompt, answer)` recomputes and returns findings
    to hand back for re-derivation. Conservative: never false-flags a correct answer.
- **Harness patterns** (`PATTERNS.md`) — framework-agnostic pseudocode you adapt
  to your agent loop, plus a drop-in operating-principle paragraph.

**No model of any kind is needed for the guaranteed path** — it is pure Python.
Perception (a `reader(png_bytes) -> str`) is needed only when the word comes
from an *image*; see [`SKILL.md`](SKILL.md) § *Perception is pluggable;
counting is deterministic*.

## Quick start

```bash
pip install .        # or just copy reference/ — it has no dependencies
python reference/calc.py && python reference/char_ops.py && python reference/verify.py  # self-checks
```

```python
from reference.calc import calc
from reference.char_ops import count_letter, char_at, reverse_word
from reference.verify import verify_answer, correction_message

calc("17 × 23 − 4³")                     # (327, None)  -- not 329
count_letter("Accessories", "c")         # 2            -- not "one"
char_at("kompressor", 4, from_end=True)  # "s"
reverse_word("semaphore")                # "erohpames"
verify_answer('How many c in "Accessories"?', "one")
# [{'op': 'the number of "c" in "Accessories"', 'expected': 2}]
```

## Integration

Guard any agent turn with the backstop: draft → deterministic check → hand back
to re-derive → substitute the deterministic result if the re-derivation is
still wrong (two-stage; see `PATTERNS.md` §1):

```python
from reference.verify import verify_answer, correction_message

def answer_reliably(user_prompt, llm):
    draft = llm(user_prompt)
    findings = verify_answer(user_prompt, draft)     # deterministic re-computation
    if not findings:
        return draft                                 # nothing checkable, or correct
    retry = llm(f"{user_prompt}\n\n{correction_message(findings)}")   # names the op, not the answer
    if not verify_answer(user_prompt, retry):
        return retry                                 # model re-derived correctly
    return "; ".join(f"{f['op']} = {f['expected']}" for f in findings)  # floor: known-right beats known-wrong
```

`llm(prompt) -> str` is any model call. Concretely:

```python
# Ollama
import ollama
llm = lambda p: ollama.chat(model="qwen2.5:7b", messages=[{"role": "user", "content": p}])["message"]["content"]

# llama.cpp / KoboldCpp / LM Studio / any OpenAI-compatible endpoint (local or hosted)
from openai import OpenAI
client = OpenAI(base_url="http://localhost:1234/v1", api_key="none")
llm = lambda p: client.chat.completions.create(model="local", messages=[{"role": "user", "content": p}]).choices[0].message.content
```

Reading a word off an image (camera/photo) — plug in any perception backend;
the count is still deterministic:

```python
from reference.char_ops import count_letter_in_image, tesseract_reader  # or vlm_reader / a Coral reader
count_letter_in_image(photo_png, "c", tesseract_reader())
```

For the harness patterns (verify-then-re-derive with the two-stage fallback,
"are you sure?" re-runs the check, decompose-then-ground for word problems with
grammar-constrained planning), see [`PATTERNS.md`](PATTERNS.md). For the full
principle and method, see [`SKILL.md`](SKILL.md).

## Tests

```bash
python -m pytest tests/         # or run any tests/test_*.py directly, no framework needed
```

## Design rules worth keeping

- **Validators, not crutches.** The backstop names the *operation*, not the
  answer — the model re-derives first. Substituting the deterministic result is
  the floor (stage 2), not the policy.
- **A miss is acceptable; a false accusation is not.** A check that flags a
  correct answer is worse than one with a hole. When extraction is ambiguous,
  stay silent.
- **Fail closed on privacy** for any external second-opinion call — send only
  the bare question and answer.

## License

MIT — see [`LICENSE`](LICENSE).
