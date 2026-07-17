"""Put reference/ on sys.path so tests can `from calc import calc` — the same
import style the reference modules use among themselves. Imported by each test
file; also makes `python tests/test_*.py` work without pytest."""
import os
import sys

_REF = os.path.join(os.path.dirname(__file__), "..", "reference")
if _REF not in sys.path:
    sys.path.insert(0, _REF)


def run_module(namespace, filename):
    """Standalone runner: call every test_* function in a module's namespace."""
    fns = [(n, f) for n, f in sorted(namespace.items())
           if n.startswith("test_") and callable(f)]
    for _, f in fns:
        f()
    print(f"{os.path.basename(filename)}: {len(fns)} tests passed")
