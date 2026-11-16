"""Shared caller-visible errors for manual data processing."""


class ProcessingError(ValueError):
    """A caller-visible failure; details can be serialized by the owning API."""

    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict:
        return {"code": self.code, "message": str(self), "details": self.details}
