"""Small reusable utilities for the application layer."""

from pathlib import Path
from typing import Callable, TypeVar


T = TypeVar("T")


class RetryPolicy:
    """Describe retry behavior without coupling callers to a framework."""

    def __init__(self, attempts: int = 3, delay_seconds: float = 2):
        self.attempts = attempts
        self.delay_seconds = delay_seconds


class FileStore:
    """Provide a stable repository-relative path for persisted data."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read_or(self, reader: Callable[[], T], default: T) -> T:
        try:
            return reader()
        except (FileNotFoundError, ValueError):
            return default
