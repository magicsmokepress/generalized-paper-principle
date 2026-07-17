"""Deterministic tools for the generalized paper principle.

Installed as the `paper_principle` package (pip install .); also importable
in-place as `reference` when you copy the directory into your project.
"""
from .calc import calc
from .char_ops import (char_at, count_letter, count_letter_in_image,
                       reverse_word, tesseract_reader, text_from_image,
                       visual_spell, vlm_reader)
from .verify import correction_message, verify_answer

__all__ = ["calc", "char_at", "count_letter", "count_letter_in_image",
           "reverse_word", "tesseract_reader", "text_from_image",
           "visual_spell", "vlm_reader", "correction_message", "verify_answer"]
