---
name: generalized-paper-principle
description: >
  Make an LLM agent reliable at the computations tokenization breaks — first and
  foremost MATH (multi-step arithmetic, percentages, powers, roots, factorials,
  word problems: a model predicts digits instead of computing them, so it is
  confidently wrong), and equally CHARACTER work (counting, indexing, reversing,
  spelling letters in a word). Use when building, reviewing, or debugging any
  agent that does arithmetic that must be exact, or answers "how many X's in
  <word>" / "the Nth character of <word>" / "reverse <word>", and gets them
  wrong. Provides deterministic tools (guaranteed-correct calculator and string
  ops), a decompose-then-compute method for word problems, a visualize-and-count
  method for letters, a verify-then-re-derive backstop, and a "challenge re-runs
  the check" reflex. Trigger on: LLM math reliability, "my model miscounts /
  gets math wrong", multi-step calculation, word problems, percentages, exact
  arithmetic, character counting, string indexing/reversal, letter frequency,
  spelling, or any precise computation an LLM must not guess.
---

# The Generalized Paper Principle

*Most people pull out a piece of paper for anything beyond basic math. An LLM
should too — for math and for characters. This skill is that principle,
generalized and made mechanical.*

## The problem this solves

An LLM **predicts** tokens; it does not **compute**. So it is confidently wrong
on two whole classes of task, and cannot feel that it erred:

- **Math.** Asked `17×23−4³` it produces `329`, not `327` — it is generating the
  most-likely-looking digits, not calculating. This holds for anything past
  trivial: multi-step arithmetic, percentages, powers, roots, factorials, word
  problems. It is the canonical case — everyone already knows to reach for a
  calculator for real math; the same is true for the model, only it doesn't know
  to.
- **Characters.** A model sees **tokens** (sub-word chunks), not letters —
  "Accessories" arrives as a blur, not `A-c-c-e-s-s-o-r-i-e-s`. Asked to count
  the c's it counts something it cannot see, says "one c", and doubles down when
  challenged.

This bites hardest wherever there is **no guaranteed code interpreter**: local
models, hosted small/non-frontier endpoints, and — for character work — frontier
models too. The two classes decay differently with scale: **arithmetic degrades
as models grow; character work doesn't.** A frontier model mostly gets
`17×23−4³` right, yet still miscounts the r's in strawberry — tokenization does
not care about parameter count, and a model that *has* a tool often doesn't
reach for it on a question that looks trivial. One thesis, two decay curves.
The fix is the same for both: don't compute it in the model's head,
externalize it (see the principle below).

## The principle

**For anything past basic, don't compute it "in the model's head" — externalize
it, exactly as a person pulls out paper.** Reaching for a tool is not a weakness
to hide; it is what every competent reasoner does. Concretely:

| Task | Externalize to |
|---|---|
| Arithmetic (multi-step, powers, %, roots, factorials) | a deterministic **calculator** |
| Count / index / reverse letters in a KNOWN word | **deterministic string ops**, or **render + look + mark** with a vision model |
| Multi-step word problems | **decompose** into expressions, compute each deterministically, then synthesize |
| Non-arithmetic correctness (logic/factual) | a **bigger local model** — or an explicitly opt-in remote one — for a second opinion |

Behind all of it: a **deterministic backstop** that recomputes the answer and,
on a mismatch, hands it back for re-derivation — so the model *feels* the miss
instead of shipping it.

## The two layers (and their reliability)

1. **Deterministic components** — `reference/calc.py`, `reference/char_ops.py`,
   `reference/verify.py`. Pure functions, no model in the loop for the actual
   computation. **Guaranteed correct.** Drop them into any agent as tools.
2. **Reflex / vision / judgment components** — the model *choosing* to reach for
   a tool, the visualize-and-mark reading, a stronger model's verdict.
   **High-probability, not certain.** They recover gracefully (re-derive on a
   caught miss) but are not a guarantee.

Design the system so the deterministic layer is the guarantee and the reflex
layer is the ergonomics — never the reverse.

## Method for math (compute → don't predict; decompose word problems)

- **Direct arithmetic** — pass the expression to `reference/calc.py::calc`. It
  takes raw notation (`17 × 23 − 4³`, `6! ÷ (14+22) × 3`, `15/100*340`,
  `2401**0.5`) and returns the exact value. Never let the model emit the number
  from its head.
- **Word problems** — the failure there is usually *decomposition*, not
  arithmetic (the model forgets a rate, mixes up the operation). Use
  decompose-then-ground (`PATTERNS.md` §3): the model outputs the ordered
  arithmetic as complete expressions, `calc` computes each, the model
  synthesizes with correct numbers in hand. The planning step may run on a
  bigger local model; a remote planner is an explicit opt-in fenced by the
  fail-closed rule — send only the bare problem. Constrain the planner's output
  format with a grammar (GBNF / structured outputs) where the backend supports
  it — see `PATTERNS.md` §3.
- **Backstop** — `verify_answer` (below) recomputes the arithmetic in a prompt
  and flags a mismatch, exactly as it does for character ops.

## Requirements: nothing but Python for the guarantee

**No model of any kind is required for the guaranteed path.** The whole
correctness core is pure Python:

| Component | Needs | Model? |
|---|---|---|
| `calc` — all arithmetic | pure Python | none |
| `count_letter` / `char_at` / `reverse_word` | pure Python | none — deterministic |
| `verify_answer` — the backstop | pure Python | none |
| decompose-then-ground — word problems | any text LLM | text only (no vision) |
| perception of image-sourced text | a pluggable **reader** | only if the word is an IMAGE |

## Perception is pluggable; counting is deterministic

The character method separates two concerns, and only the first is uncertain:

1. **Perception** — turning pixels into letters. Needed *only* when the word is
   not already clean text (it came from a camera, screenshot, or photo). This is
   a swappable backend: a `reader(png_bytes) -> str`. **Bring whatever you have** —
   an OpenAI-compatible vision model, Tesseract (no GPU, no service), a
   Coral / Edge-TPU OCR model, or a cloud OCR API.
2. **Counting / indexing / reversing** — deterministic, exact, runs on whatever
   text perception produced. This is the guarantee.

If the word is already text, **skip perception entirely** — `count_letter` is
exact and needs nothing. This is the common case.

```python
from reference.char_ops import count_letter, count_letter_in_image, vlm_reader, tesseract_reader

count_letter("Accessories", "c")                 # 2  — word is text, no perception
count_letter_in_image(png, "c", tesseract_reader())   # OCR the photo, then count exactly
count_letter_in_image(png, "c", vlm_reader())         # or a vision model, same interface
count_letter_in_image(png, "c", my_coral_reader)      # or Coral: any png->str callable
```

### Choosing a perception backend

| Backend | Good for | Caveats |
|---|---|---|
| **none (deterministic)** | the word is already text | — (use this whenever you can) |
| **Vision-enabled main model** | your agent's model is already multimodal | spends large-model inference on OCR |
| **Dedicated small VLM** (env `VLM_URL`/`VLM_MODEL`) | text-only main model; best flexibility | needs a small always-on GPU service |
| **Tesseract** | local, model-free, CPU-only OCR | weaker on stylized fonts |
| **Coral / Edge TPU** | local, low-power OCR of clean, fronto-parallel text | needs an edgetpu-compiled recognizer; weaker on angled/stylized real-world text |
| **Cloud OCR** | zero local infra | per-call cost, sends the image out |

The key move that makes it universal: perception is the imperfect, swappable
layer; **the count is always deterministic**, so accuracy is bounded only by the
reader, and a word you already have as text needs no reader at all.

Historical note on the "make the model do the counting itself" variant: a VLM
asked "how many c's" *holistically* hallucinates (a real VLM said "Accessories"
had three), but reading letter-by-letter and marking each is reliable. That
trick is unnecessary here — transcribe (easy for a VLM) then count in code
(exact) — but it is why perception and counting are split.

## Harness patterns (adapt to your framework)

See `PATTERNS.md` for framework-agnostic pseudocode:
- **Verify-then-re-derive** — after a final answer, run the deterministic check;
  on a mismatch, log it and hand the model a correction turn to re-derive. It
  fixes the answer AND gives the model a signal it was wrong.
- **Challenge re-runs the check** — treat "are you sure?", "really?", a bare "?"
  as a trigger to RE-DERIVE from scratch, never to restate. Doubling-down
  (reaffirming a wrong answer more confidently) is the failure this prevents.
- **Decompose-then-ground** — for word problems, get a plan of complete
  arithmetic expressions from the model, compute each deterministically, then
  let the model synthesize with correct numbers in hand.

## Design rules learned the hard way

- **Validators, not crutches.** The deterministic tool should *catch* errors and
  hand them back for re-derivation — it should name the operation, not the
  answer, so the model still reasons. Don't let it become the thing the model
  leans on instead of thinking.
- **A miss is acceptable; a false accusation is not.** A backstop that flags a
  *correct* answer is worse than one with a hole — it teaches the model it erred
  when it didn't. When extraction is ambiguous (e.g. a pronoun-referenced word),
  stay silent rather than guess-and-false-flag.
- **Fail closed on privacy** for any external second-opinion call — send only the
  bare question+answer, never memory/context, and skip on any private marker.

## Effectiveness (measured, honest)

On a comprehensive battery through a live agent loop (character counting incl.
zero-counts, doubles, long words; indexing; reversal; multi-step arithmetic;
percent/root/power; word problems; embedded-in-conversation; doubling-down both
directions): **~98% across ~60 trials, 100% on the final broad run.** The
deterministic components are effectively 100%; the reflex/vision components are
high-probability with graceful self-recovery; one residual case (a word named
only by a pronoun that the model also truncates) sits outside the deterministic
net by design.

## Quick start

```python
from reference.calc import calc            # exact arithmetic
from reference.char_ops import count_letter, char_at, reverse_word  # deterministic
from reference.verify import verify_answer # backstop: returns findings to hand back
```
Run `python reference/calc.py`, `python reference/char_ops.py`,
`python reference/verify.py` — each has an assert-based self-check.
