# token-robust-cognition

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
  - `char_ops.py` — `count_letter`, `char_at`, `reverse_word`, plus `visual_spell`
    (render → vision-model marks each letter → count; needs a VLM endpoint + Pillow).
  - `verify.py` — `verify_answer(prompt, answer)` recomputes and returns findings
    to hand back for re-derivation. Conservative: never false-flags a correct answer.
- **Harness patterns** (`PATTERNS.md`) — framework-agnostic pseudocode you adapt
  to your agent loop, plus a drop-in operating-principle paragraph.

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

See [`SKILL.md`](SKILL.md) for the full principle, method, design rules, and
measured effectiveness, and [`PATTERNS.md`](PATTERNS.md) for wiring it into an
agent.

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
