"""Run all Python contract tests against the installed package, including pytest functions."""
import argparse
from pathlib import Path
import sys

import akousma
import pytest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junitxml", required=True)
    args = parser.parse_args()
    prefix = Path(sys.prefix).resolve()
    if not Path(akousma.__file__).resolve().is_relative_to(prefix):
        raise RuntimeError("Install py-akousma with its dev extra in this interpreter first")
    print("Installed akousma:", akousma.__file__, flush=True)
    root = Path(__file__).resolve().parents[1]
    result = pytest.main(["-q", "-ra", "-p", "no:cacheprovider",
                          str(root / "packages/py-akousma/tests"), "--junitxml", args.junitxml])
    for name, module in tuple(sys.modules.items()):
        if name.startswith("akousma.") and getattr(module, "__file__", None):
            if not Path(module.__file__).resolve().is_relative_to(prefix):
                raise RuntimeError("Tests imported source instead of the installed package: " + name)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
