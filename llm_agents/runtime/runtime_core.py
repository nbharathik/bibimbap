"""Framework-agnostic runtime helpers for LLM agents."""


def is_recursion_error(exc: BaseException) -> bool:
    if isinstance(exc, RecursionError):
        return True
    exc_name = type(exc).__name__.lower()
    if "recursion" in exc_name:
        return True
    return "recursion" in str(exc).lower()
