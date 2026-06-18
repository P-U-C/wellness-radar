from __future__ import annotations

import time


def main() -> None:
    print("jobs scheduler idle; APScheduler wiring is deferred until the next milestone")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
