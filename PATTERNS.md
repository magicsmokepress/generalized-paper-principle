# Harness integration patterns

Framework-agnostic pseudocode. The three patterns below turn the deterministic
tools into reliable behavior. Adapt to your agent loop (LangChain, a custom
turn loop, an SDK agent — the shape is the same).

## 1. Verify-then-re-derive (the backstop)

After the model produces a final answer, run the deterministic check. On a
mismatch, hand it back once for re-derivation. This both fixes the answer and
gives the model a signal it was wrong (log it, so drives/metrics can see it).

```python
def on_final_answer(prompt, answer, messages):
    findings = verify_answer(prompt, answer)          # reference/verify.py
    if findings and not turn_flag("verified"):
        set_turn_flag("verified")                     # one re-derivation — no loops
        log_failure("self_verify", findings)          # the perception signal
        messages.append(user_turn(correction_message(findings)))
        return REGENERATE                             # stage 1: name the op, model re-derives
    if findings:                                      # stage 2: re-derivation ALSO came back wrong
        log_failure("re_derive_failed", findings)
        return COMMIT_WITH(substitute(answer, findings))  # splice in each finding's `expected`
    return COMMIT
```

Notes:
- **Two-stage, tier-aware.** Stage 1 names the operation, not the answer — right
  for models that can act on it. If the handback *still* comes back wrong (small
  models often do), stage 2 substitutes the deterministic result: committing a
  known-right value beats committing a known-wrong one. `substitute` replaces the
  claimed value with the finding's `expected` (or appends a correction line).
- **Once per turn.** Guard against re-derivation loops; the miss is already logged.
- **Run all checks, combine corrections.** If one turn has an arithmetic error
  AND a character error, catch both in one handback, not first-wins.
- **Name the operation, not the answer** (correction_message does this) — the
  model must re-derive, not parrot. Substitution is the floor, not the policy.

## 2. Challenge re-runs the check (anti-doubling-down)

Treat a short questioning turn as a signal to RE-DERIVE, never to restate. This
prevents the failure where "are you sure?" makes the model *more* confident in a
wrong answer.

```python
# English-locked and deliberately loose — extend for your users' language and
# idiom; a missed challenge just skips a re-check, it breaks nothing.
CHALLENGE = re.compile(r"\b(are you sure|really|is that (?:right|correct)|"
                       r"double.?check|you'?re wrong|that'?s (?:not right|wrong|incorrect)|"
                       r"nope|no it isn'?t|hm+|certain)\b", re.I)

def is_challenge(text):
    t = text.strip()
    return (t.strip("?") == "" and "?" in t) or bool(len(t) <= 48 and CHALLENGE.search(t))

def on_turn_start(user_input, messages):
    if is_challenge(user_input):
        prev_q, prev_a = last_qa(messages)
        findings = verify_answer(prev_q or "", prev_a or "")
        if findings:
            prepend_system(f"Your previous answer is WRONG for "
                           f"{'; '.join(f['op'] for f in findings)}. Re-derive it "
                           f"with a tool and correct it.")
        else:
            prepend_system("You are being questioned. Do NOT restate your answer. "
                           "Re-derive it from scratch with your tools, then confirm "
                           "or correct. Confidence is not evidence; the re-derivation is.")
```

## 3. Decompose-then-ground (word problems)

For a multi-step word problem, don't let the model do the whole thing in one
pass. Get a plan of complete arithmetic expressions, compute each
deterministically, then let the model synthesize with correct numbers in hand.

```python
def maybe_ground(prompt):
    if not looks_multistep_math(prompt):       # >=2 numbers + a compute cue, or %, root, power
        return None
    plan = ask_model(PLAN_SYSTEM, prompt)       # "output CALC: <complete expression> per step"
    exprs = extract("CALC:", plan)
    if not exprs:                               # format failure: small models compute anyway
        exprs = bare_expressions(plan)          # salvage: regex any inline arithmetic out of the prose
    if not exprs:
        plan = ask_model(PLAN_SYSTEM + " Output NOTHING except CALC: lines.", prompt)
        exprs = extract("CALC:", plan)          # one strict retry, then give up gracefully
    grounded = []
    for expr in exprs:
        val, err = calc(expr)                   # reference/calc.py
        if err is None:
            grounded.append(f"{expr} = {val}")
    if grounded:
        return "Verified computations (use these, do not redo in your head):\n" + "\n".join(grounded)

PLAN_SYSTEM = ("Break the problem into ordered arithmetic. For EVERY calculation "
    "output: CALC: <complete expression with literal numbers, e.g. 840/(3.5-2.1)/60>. "
    "Account for ALL quantities including opposing ones. Do not compute — only write "
    "the expressions.")
```

**Own the format instead of parsing around it.** On llama.cpp / KoboldCpp,
constrain the planner's decoding with a grammar — the model *cannot* emit
anything but CALC: lines:

```
root  ::= line+
line  ::= "CALC: " expr "\n"
expr  ::= [0-9] [0-9 ().+*/^!-]*
```

Hosted OpenAI-compatible endpoints get the same guarantee with structured
outputs: `response_format={"type": "json_schema", ...}` around
`{"steps": [{"expr": "..."}]}`. Either one deletes the format-failure path
above — prefer it whenever the backend supports it.

The planner may run on a **bigger local model** if you have one. A *remote*
planner is an explicit opt-in, fenced by the fail-closed rule: send only the
bare problem — never memory or context — and skip the call entirely on any
private marker. `calc` grounds the plan; the main model synthesizes.

## Operating-principle text (drop into a system prompt)

> **Work it out on paper — do not do it in your head.** For anything beyond basic
> mental computation — multi-step arithmetic, precise counting, character/string
> work — externalize it and work it step by step, as any capable person pulls out
> paper. This is not a weakness; it is what every competent reasoner does. Your
> one-pass in-head answer to a non-trivial computation is a *guess*: use the
> calculator for arithmetic, spell words out letter-by-letter to count or index
> them, decompose word problems. When you are questioned — "are you sure?", "?" —
> re-derive from scratch, never restate. Confidence is not evidence; the
> re-derivation is.

## Reliability contract

- Deterministic tools (calc, count_letter/char_at/reverse_word, verify_answer on
  a quoted or structurally-named target): **guaranteed correct**.
- Model-in-the-loop parts (reaching for the tool, visual_spell, a stronger
  model's verdict): **high-probability, recovers on a caught miss, not certain.**
- Ambiguous extraction (pronoun-referenced target): **stay silent** — a false
  accusation is worse than a miss.
