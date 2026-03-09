from __future__ import annotations


class McfindError(Exception):
    def __init__(self, message: str, hint: str | None = None, exit_code: int = 2) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.exit_code = exit_code


class EmptyResultError(McfindError):
    def __init__(self, message: str = "No results found.", hint: str | None = None) -> None:
        super().__init__(message, hint=hint, exit_code=3)
