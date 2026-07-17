"""Deterministic backstop — recompute a checkable answer and report a mismatch.

Given the task text and the model's answer, this catches wrong arithmetic and
wrong character ops (count / index / reverse) that slipped through. It returns
findings you hand back to the model to RE-DERIVE — it names the operation, not
the answer, so the model still reasons (validator, not crutch).

Two rules baked in:
  - It stays CONSERVATIVE: a false positive (flagging a correct answer) is worse
    than a miss, so it only fires when the target and the claim are unambiguous.
  - It resolves the target word by structure (quoted / "the word X" / "in|of X"
    / "reverse X" / "X backwards") but does NOT guess a pronoun target — guessing
    there false-flags correct answers.
"""
from __future__ import annotations

import re

from calc import calc

_NUM_IN_ANSWER = re.compile(r"-?\d+(?:\.\d+)?")

# ── arithmetic ─────────────────────────────────────────────────────────────
_SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_OPS = rf"+\-*/×÷−–—^!{_SUP}"
_ECHARS = rf"[0-9.,()\s{_OPS}]"
_TERM = rf"[0-9!{_SUP}]"
_EXPR_RE = re.compile(rf"\d{_ECHARS}*[{_OPS}]{_ECHARS}*{_TERM}|\d\s*!")
_BINOP_RE = re.compile(rf"[{_OPS}]")


def _answer_has(value, answer):
    for n in (float(x) for x in _NUM_IN_ANSWER.findall(answer or "")):
        if abs(n - value) < 1e-6 or round(n, 2) == round(float(value), 2):
            return True
    return False


def _arith_findings(prompt, answer):
    if not answer or not _NUM_IN_ANSWER.search(answer):
        return []
    out = []
    for m in _EXPR_RE.finditer(prompt or ""):
        expr = m.group(0).strip().rstrip(".,")
        if not _BINOP_RE.search(expr):
            continue
        if len(re.findall(r"\d", expr)) < 2 and "!" not in expr:
            continue
        val, err = calc(expr)
        if err is None and not _answer_has(val, answer):
            out.append({"op": expr, "expected": val})
    return out


# ── character ops ──────────────────────────────────────────────────────────
_NTH_END = re.compile(r'(\d+)\s*(?:st|nd|rd|th)?\s+(?:character|letter|char)\b(?:(?!from the start).)*?\bfrom\s+the\s+end', re.I | re.S)
_NTH_START = re.compile(r'(\d+)\s*(?:st|nd|rd|th)?\s+(?:character|letter|char)\b(?:(?!from the end).)*?\bfrom\s+the\s+(?:start|beginning)', re.I | re.S)
_REV = re.compile(r"\brevers", re.I)
_COUNT_Q = re.compile(r"\b(how many|number of|count)\b", re.I)
_QUOTED_WORD = re.compile(r'["“‘’”\']([A-Za-z]{2,40})["“‘’”\']')
_QUOTED_LETTER = re.compile(r'["“‘’”\']([A-Za-z])["“‘’”\']')
_AFTER = re.compile(r'\b(?:in|of|within|inside)\s+(?:the\s+word\s+|the\s+string\s+)?([A-Za-z]{3,40})\b', re.I)
_THEWORD = re.compile(r'\bthe\s+(?:word|string)\s+([A-Za-z]{3,40})', re.I)
_BEFORE_REV = re.compile(r'\b([A-Za-z]{3,40})\s+(?:backwards?|reversed)', re.I)
_AFTER_VERB = re.compile(r'\b(?:reverse|reversed|spell)\s+(?:the\s+(?:word|string)\s+)?([A-Za-z]{3,40})', re.I)
_STOP = {"the", "word", "string", "letter", "this", "that", "reverse", "which"}
_SINGLE = re.compile(r"(?<![A-Za-z])([A-Za-z])(?![A-Za-z])")
_NUMWORDS = {"zero": 0, "no": 0, "none": 0, "one": 1, "two": 2, "three": 3, "four": 4,
             "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def _word_target(prompt):
    p = prompt or ""
    for rx in (_QUOTED_WORD, _THEWORD, _BEFORE_REV):
        m = rx.search(p)
        if m and m.group(1).lower() not in _STOP:
            return m.group(1)
    cands = [w for w in _AFTER.findall(p) if w.lower() not in _STOP]
    if cands:
        return cands[-1]
    m = _AFTER_VERB.search(p)
    return m.group(1) if m and m.group(1).lower() not in _STOP else None


def _claimed_number(answer):
    m = re.search(r"-?\d+", answer or "")
    if m:
        return int(m.group(0))
    for w, n in _NUMWORDS.items():
        if re.search(rf"\b{w}\b", answer or "", re.I):
            return n
    return None


def _string_findings(prompt, answer):
    s = _word_target(prompt)
    out = []
    if s and answer:
        for rx, idx in ((_NTH_END, "end"), (_NTH_START, "start")):
            m = rx.search(prompt)
            if m and 1 <= int(m.group(1)) <= len(s):
                correct = s[-int(m.group(1))] if idx == "end" else s[int(m.group(1)) - 1]
                cands = {c.lower() for c in _SINGLE.findall(answer)}
                if cands and correct.lower() not in cands:
                    out.append({"op": f'the {m.group(1)}th char from the {idx} of "{s}"', "expected": correct})
        if _REV.search(prompt) and s[::-1].lower() not in answer.lower():
            out.append({"op": f'the reverse of "{s}"', "expected": s[::-1]})
    if _COUNT_Q.search(prompt or "") and answer:
        word = _word_target(prompt)
        ql = _QUOTED_LETTER.findall(prompt or "")
        letter = ql[0] if ql else None
        if not letter:
            m = re.search(r"(?<![A-Za-z])([A-Za-z])'?s\b", prompt or "")
            letter = m.group(1) if m else None
        if not letter:
            singles = [c for c in _SINGLE.findall(prompt or "") if c.lower() != "i"]
            letter = singles[0] if len(singles) == 1 else None
        claimed = _claimed_number(answer)
        if word and letter and claimed is not None:
            correct = word.lower().count(letter.lower())
            if claimed != correct:
                out.append({"op": f'the number of "{letter}" in "{word}"', "expected": correct})
    return out


def verify_answer(prompt: str, answer: str) -> list[dict]:
    """Return [{op, expected}] for computations the answer got wrong (empty =
    nothing checkable, or correct). Hand `op` back to the model to re-derive —
    do NOT hand it `expected` (that would answer for it)."""
    return _arith_findings(prompt, answer) + _string_findings(prompt, answer)


def correction_message(findings: list[dict]) -> str:
    ops = "; ".join(f["op"] for f in findings)
    return (f"Your answer for {ops} does not check out. Work it out again with a "
            f"tool (calculate it / spell it out character by character), then "
            f"correct your answer. Do not restate the old one.")


if __name__ == "__main__":
    assert verify_answer("What is 17 × 23 − 4³?", "329")          # arith wrong
    assert not verify_answer("What is 17 × 23 − 4³?", "327")       # arith right
    assert verify_answer("How many 'c' in \"Accessories\"?", "one")  # count wrong
    assert not verify_answer("How many 'c' in \"Accessories\"?", "two")
    assert verify_answer("How many r's in strawberry?", "two")     # unquoted count
    assert not verify_answer("How many r's in strawberry?", "three")
    assert verify_answer("4th char from the end of \"kompressor\"?", "e")  # index wrong
    assert not verify_answer("4th char from the end of \"kompressor\"?", "s")
    assert not verify_answer("What is the capital of France?", "Paris")    # no target
    assert not verify_answer("I picked strawberry; how many r's in it?", "strawberry has 3 r's")  # pronoun -> no false flag
    print("verify self-check ok (flags wrongs, no false positives, no pronoun false-flag)")
