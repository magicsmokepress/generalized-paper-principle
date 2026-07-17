import _path  # noqa: F401
from verify import verify_answer, correction_message


def test_arithmetic_flags_wrong_passes_right():
    assert verify_answer("What is 17 × 23 − 4³?", "329")            # wrong
    assert not verify_answer("What is 17 × 23 − 4³?", "327")         # right
    assert verify_answer("What is 6! / (14+22) × 3?", "62")          # wrong
    assert not verify_answer("What is 6! / (14+22) × 3?", "60")      # right


def test_arithmetic_restated_correct_not_flagged():
    assert not verify_answer("What is 17 × 23 − 4³?",
                             "17×23 is 391, minus 64 gives 327.")


def test_currency_and_comma_grouping():
    assert not verify_answer("What is 1200 × 12?", "$14,400")   # right, formatted
    assert verify_answer("What is 1200 × 12?", "$14,600")       # wrong


def test_leading_paren_expression():
    assert verify_answer("What is (847 − 269) × 34?", "19000")  # wrong
    assert not verify_answer("What is (847 − 269) × 34?", "19652")


def test_hyphen_chains_are_not_subtraction():
    assert not verify_answer("How many days from 2024-12-25 to 2025-01-01?", "7 days")
    assert not verify_answer("What changed in Python 3.12-3.13?", "The REPL. 2 big things.")
    assert not verify_answer("Call 555-1234; how many 'a' in banana?", "3")
    assert not verify_answer("Read pages 10-15. How long?", "about 20 minutes")
    assert not verify_answer("The score was 21-14; who won?", "The home team.")
    assert verify_answer("What is 100 - 37?", "53")             # spaced minus is real math


def test_compound_answer_not_false_flagged():
    assert not verify_answer("How many 'a' are in 'banana'? And what is 2+2?",
                             "2+2 is 4, and there are 3 a's in banana.")
    assert verify_answer("How many 'a' are in 'banana'? And what is 2+2?",
                         "2+2 is 4, and there are 2 a's in banana.")


def test_factorial_extraction_and_huge_values():
    assert verify_answer("What is 6!?", "719")                  # wrong -> flag
    assert not verify_answer("What is 6!?", "720")
    f = verify_answer("What is 12!?", "a big number, maybe 479001601")
    assert f and f[0]["op"] == "12!"                            # whole literal, not last digit
    assert not verify_answer("What is 500!?", "That is a 1135-digit number.")  # huge -> silent, no crash


def test_count_quoted():
    assert verify_answer('How many "c" in "Accessories"?', "one")    # wrong (2)
    assert not verify_answer('How many "c" in "Accessories"?', "two")


def test_count_unquoted():
    assert verify_answer("How many r's are in strawberry?", "two")   # wrong (3)
    assert not verify_answer("How many r's are in strawberry?", "three")
    assert verify_answer("Count how many times a appears in banana.", "four")  # wrong (3)


def test_index_and_reverse():
    assert verify_answer('4th char from the end of "kompressor"?', "e")   # wrong (s)
    assert not verify_answer('4th char from the end of "kompressor"?', "s")
    assert verify_answer("Reverse orange.", "egnoar")                 # wrong
    assert not verify_answer("Reverse orange backwards.", "egnaro")   # right


def test_embedded_question():
    # Char question buried in a larger turn; a stray quote in the answer must
    # not hijack the target.
    assert verify_answer(
        'I like the word Accessories for my brand — how many c\'s does it have?',
        "It has one c, and 'groceries' rhymes.")


def test_no_false_positives():
    assert not verify_answer("What is the capital of France?", "Paris")   # no target
    assert not verify_answer("I picked strawberry today.", "nice")        # not a count Q
    # pronoun target is deliberately NOT guessed -> never false-flags a correct answer
    assert not verify_answer("I picked strawberry; how many r's in it?",
                             "strawberry has 3 r's")


def test_correction_names_op_not_answer():
    f = verify_answer('How many "c" in "Accessories"?', "one")
    msg = correction_message(f)
    assert "Accessories" in msg and "two" not in msg.lower() and "2" not in msg


if __name__ == "__main__":
    _path.run_module(globals(), __file__)
