from __future__ import annotations

import sys
import unittest
from pathlib import Path


# load-simulator 테스트 디렉터리 전체를 한 번에 수집해 실행한다.
def main() -> None:
    base_dir = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(base_dir))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
