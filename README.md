# generalized-paper-principle

> *Most people pull out a piece of paper for anything beyond basic math. An LLM
> should too.* This repo generalizes that principle — for math **and**
> characters — and makes it mechanical.

Make an LLM agent reliable at the computations tokenization breaks — **math**
first (multi-step arithmetic, percentages, powers, roots, factorials, word
problems) and **character work** (counting, indexing, reversing, spelling
letters in a word).

An LLM **predicts** tokens; it does not **compute**. So it is confidently wrong
on both — `17×23−4³` comes out `329` not `327`, and "Accessories" gets "one c"
instead of two — with no internal signal that it erred, and it doubles down when
challenged. A bigger model lowers the rate; it does not remove it. The fix is
the same one people already use: **don't do it in your head — externalize it,
like reaching for a calculator or writing it out on paper.**

This repo packages that as an agent skill: deterministic tools that are
guaranteed correct, a decompose-then-compute method for word problems, a
visualize-and-mark method for letters, and framework-agnostic harness patterns
(verify-then-re-derive, and "are you sure?" re-runs the check instead of
restating).

## Two layers

- **Deterministic tools** (`reference/`) — pure functions, no model in the loop
  for the actual computation. **Guaranteed correct. Drop-in.**
  - `calc.py` — AST-safe calculator (`calc("17 × 23 − 4³") → 327`).
  - `char_ops.py` — deterministic `count_letter` / `char_at` / `reverse_word`,
    plus `count_letter_in_image` / `visual_spell` with a **pluggable perception
    reader** (VLM, Tesseract, Coral, cloud — any `png->str`); counting stays
    deterministic.
  - `verify.py` — `verify_answer(prompt, answer)` recomputes and returns findings
    to hand back for re-derivation. Conservative: never false-flags a correct answer.
- **Harness patterns** (`PATTERNS.md`) — framework-agnostic pseudocode you adapt
  to your agent loop, plus a drop-in operating-principle paragraph.

## Requirements

**No model of any kind is needed for the guaranteed path.** `calc`,
`count_letter`, `char_at`, `reverse_word`, and `verify_answer` are pure Python.
Word-problem decomposition needs any text LLM (no vision).

The character method splits into **pluggable perception** and **deterministic
counting** — and perception is only needed when the word comes from an *image*
(camera/photo), not when it is already text. The perception step is a swappable
`reader(png_bytes) -> str`: use a vision-enabled model, a dedicated small VLM
(env `VLM_URL`/`VLM_MODEL`), **Tesseract** (CPU, no service), a **Coral/Edge-TPU**
OCR model, or a cloud OCR — whatever hardware you have. The count is always
deterministic, so accuracy is bounded only by the reader, and a word you already
have as text needs no reader at all. See [`SKILL.md`](SKILL.md) § *Perception is
pluggable; counting is deterministic*.

## Quick start

```bash
python reference/calc.py       # self-check
python reference/char_ops.py   # self-check (deterministic part)
python reference/verify.py     # self-check
```

```python
from reference.calc import calc
from reference.char_ops import count_letter, char_at, reverse_word
from reference.verify import verify_answer, correction_message

calc("6! ÷ (14+22) × 3")            # (60, None)
count_letter("Mississippi", "s")    # 4
char_at("kompressor", 4, from_end=True)  # "s"
verify_answer("How many c in \"Accessories\"?", "one")  # [{'op': 'the number of "c" in "Accessories"', 'expected': 2}]
```

## Usage example

**Simplest — when you already have the word/expression as text, skip the model
entirely.** This is exact and needs nothing:

```python
from reference.calc import calc
from reference.char_ops import count_letter, char_at, reverse_word

calc("17 × 23 − 4³")                        # (327, None)   -- not 329
count_letter("Accessories", "c")            # 2             -- not "one"
char_at("kompressor", 4, from_end=True)     # "s"
reverse_word("semaphore")                   # "erohpames"
```

**Integration — guard any agent turn with the backstop.** Let your model draft
an answer, deterministically check it, and hand it back to re-derive if it's
wrong. Works with any provider — `llm(prompt) -> str` is your model call:

```python
from reference.verify import verify_answer, correction_message

def answer_reliably(user_prompt, llm):
    draft = llm(user_prompt)                       # your model's first pass
    findings = verify_answer(user_prompt, draft)   # deterministic re-computation
    if not findings:
        return draft                               # nothing checkable, or correct
    # a check caught an error -> hand it back to re-derive (names the op, not the answer)
    return llm(f"{user_prompt}\n\n{correction_message(findings)}\n"
               "Compute it exactly (calculator / spell it out), then give the corrected answer.")

# If the model first says "There is one 'c' in Accessories", verify_answer flags it
# and the retry re-derives to "two". Same for 17×23−4³ -> 329 caught -> 327.
answer_reliably('How many "c" are in "Accessories"?', my_llm)
```

**Reading a word off an image** (camera/photo) — plug in any perception backend;
the count is still deterministic:

```python
from reference.char_ops import count_letter_in_image, tesseract_reader  # or vlm_reader / a Coral reader

count_letter_in_image(photo_png, "c", tesseract_reader())   # OCR the picture, then count exactly
```

For the harness patterns (verify-then-re-derive, "are you sure?" re-runs the
check, decompose-then-ground for word problems) and a drop-in operating-principle
paragraph, see [`PATTERNS.md`](PATTERNS.md). For the full principle, method, and
measured effectiveness, see [`SKILL.md`](SKILL.md).

## Design rules worth keeping

- **Validators, not crutches.** The backstop names the *operation*, not the
  answer — the model still re-derives.
- **A miss is acceptable; a false accusation is not.** A check that flags a
  correct answer is worse than one with a hole. When extraction is ambiguous,
  stay silent.
- **Fail closed on privacy** for any external second-opinion call — send only
  the bare question and answer.

## License

MIT — see [`LICENSE`](LICENSE).
