"""Domain errors surfaced as structured HTTP responses."""
from __future__ import annotations


class ServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)
