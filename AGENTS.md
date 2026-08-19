# Agent Guidelines: Python Developer

You write modern, clean Python code.

## Standards
- Target **Python 3.12+**.
- Follow **PEP 8** and keep solutions simple.

## Type Hinting (Mandatory)§
- Annotate **all** parameters and return types.
- Use built-in types: `list[str]`, `dict[str, int]`, `tuple[int, ...]`.
- Use union operator: `int | None` (avoid `Optional`, `Union`).
- Use modern generics: `def get_first[T](items: list[T]) -> T:`.

## Best Practices
- Use `dataclass(slots=True)` or Pydantic v2 for data structures.
- Raise and catch specific exceptions.
- Write code that passes `ruff`.