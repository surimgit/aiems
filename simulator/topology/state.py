from __future__ import annotations

import threading

_topology: dict = {}
_lock = threading.Lock()
