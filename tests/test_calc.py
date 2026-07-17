import _path  # noqa: F401  (puts reference/ on sys.path)
from calc import calc


def test_multistep_and_power():
    assert calc("17 × 23 − 4³") == (327, None)
    assert calc("6! / (14 + 22) × 3") == (60, None)
    assert calc("2**10") == (1024, None)


def test_division_and_floats():
    assert calc("840 / 1.4 / 60") == (10, None)
    assert calc("144 / 12 + 8") == (20, None)


def test_functions_and_roots():
    assert calc("sqrt(2401)") == (49, None)
    assert calc("729 ** (1/3)")[0] == 9  # 9.0 -> int when whole


def test_percent_and_commas():
    assert calc("15 / 100 * 340") == (51, None)
    assert calc("1,000 + 1") == (1001, None)


def test_human_notation():
    assert calc("100 ÷ 4")[0] == 25
    assert calc("5!")[0] == 120


def test_multiarg_functions_keep_their_commas():
    assert calc("min(1,2)") == (1, None)
    assert calc("max(3, 10)") == (10, None)
    assert calc("gcd(12, 18)") == (6, None)
    assert calc("1,234,567 + 1") == (1234568, None)      # grouping commas still stripped


def test_refuses_unsafe():
    assert calc("__import__('os')")[0] is None          # no code execution
    assert calc("9**9**9")[0] is None                    # no runaway exponent
    assert calc("open('/etc/passwd')")[0] is None        # no calls to non-whitelisted names
    assert calc("9999999!")[0] is None                   # factorial magnitude cap (no CPU burn)
    assert calc("999999**999999")[0] is None             # result-size cap (no CPU burn)
    assert calc("100!")[0] is not None                   # sane factorials still work


def test_errors():
    assert calc("1/0")[1] == "division by zero"
    assert calc("")[1] == "empty expression"
    assert calc("2 +")[0] is None                        # syntax error -> (None, msg)


if __name__ == "__main__":
    _path.run_module(globals(), __file__)
