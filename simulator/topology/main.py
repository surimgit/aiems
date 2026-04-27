from __future__ import annotations

import threading
import time
from http.server import ThreadingHTTPServer

import publisher
import repository
import subscriber
from config import PORT
from handler import Handler
from state import _topology


def main() -> None:
    _topology.update(repository.load())
    print(f"[topology] loaded: {len(_topology.get('nodes', []))} nodes, "
          f"{len(_topology.get('lines', []))} lines")

    threading.Thread(target=subscriber.connect, daemon=True).start()

    def _initial_publish():
        time.sleep(3)
        publisher.republish_all()
        print("[topology] initial state published")

    threading.Thread(target=_initial_publish, daemon=True).start()

    print(f"[topology] listening: http://0.0.0.0:{PORT}")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
