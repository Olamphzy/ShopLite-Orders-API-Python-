import threading
from typing import Callable

TTL_SECONDS = 60


class ProductCache:
    def __init__(self, clock: Callable[[], float]):
        self._clock = clock
        self._entries: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> dict | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry[0] <= self._clock():
                return None
            return entry[1]

    def set(self, key: str, value: dict) -> None:
        with self._lock:
            self._entries[key] = (self._clock() + TTL_SECONDS, value)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
