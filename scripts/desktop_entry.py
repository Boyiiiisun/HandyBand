"""Entry point for the portable Windows bundle."""

import os
import sys
from pathlib import Path

from handyband.app import main

if __name__ == "__main__":
    os.chdir(Path(sys.executable).parent)
    if "--self-test" in sys.argv:
        from handyband.bundle_check import check_bundle

        raise SystemExit(check_bundle())
    raise SystemExit(main())
