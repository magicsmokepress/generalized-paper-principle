import _path  # noqa: F401
from char_ops import count_letter, char_at, reverse_word, visual_spell, count_letter_in_image


def test_count_letter():
    assert count_letter("Accessories", "c") == 2
    assert count_letter("Mississippi", "s") == 4
    assert count_letter("parallel", "l") == 3
    assert count_letter("beekeeper", "e") == 5
    assert count_letter("Mississippi", "t") == 0        # zero-count
    assert count_letter("Accessories", "C") == 2        # case-insensitive


def test_char_at():
    assert char_at("kompressor", 4, from_end=True) == "s"
    assert char_at("python", 2) == "y"
    assert char_at("elephant", 3, from_end=True) == "a"
    assert char_at("hi", 5) is None                     # out of range


def test_reverse():
    assert reverse_word("semaphore") == "erohpames"
    assert reverse_word("orange") == "egnaro"


def test_unicode_nfc_and_combining_marks():
    assert count_letter("caf\u00e9", "\u00e9") == 1   # composed
    assert count_letter("cafe\u0301", "\u00e9") == 1  # decomposed input, composed letter
    assert count_letter("caf\u00e9", "e\u0301") == 1  # composed input, decomposed letter
    assert reverse_word("cafe\u0301") == "\u00e9fac"  # accent stays on the e
    assert char_at("caf\u00e9", 1, from_end=True) == "\u00e9"


def test_pluggable_reader_counts_on_its_output():
    # Perception is swappable; counting is deterministic on whatever it returns.
    fake_reader = lambda png: "Accessories"
    assert visual_spell("Accessories", "c", reader=fake_reader)["count"] == 2
    assert count_letter_in_image(b"", "s", reader=lambda p: "Mississippi") == 4


def test_visual_spell_consistency_flag():
    good = visual_spell("banana", "a", reader=lambda p: "banana")
    assert good["read_matches"] is True and good["count"] == 3
    bad = visual_spell("banana", "a", reader=lambda p: "banan")   # reader dropped a letter
    assert bad["read_matches"] is False                          # caught by the round-trip


if __name__ == "__main__":
    _path.run_module(globals(), __file__)
