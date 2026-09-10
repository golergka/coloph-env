"""Schemas and explicit source resolution."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Generic, Self, TypeVar, cast, overload

from dotenv.parser import parse_stream

T = TypeVar("T")
E = TypeVar("E", bound="Env")


@dataclass(frozen=True)
class Problem:
    """One invalid field. Contains names and a reason, never input values."""

    field: str
    names: tuple[str, ...]
    reason: str

    def __str__(self) -> str:
        return f"{self.field} ({', '.join(self.names)}): {self.reason}"


class ValidationError(ValueError):
    """All field errors from one schema validation."""

    def __init__(self, problems: Iterable[Problem]) -> None:
        self.problems = tuple(problems)
        super().__init__("Invalid environment configuration:\n" + "\n".join(f"  {p}" for p in self.problems))


class Var(Generic[T]):
    """A required field with one or more mutually exclusive environment names."""

    @overload
    def __init__(self: Var[str], *names: str) -> None: ...

    @overload
    def __init__(self, *names: str, parse: Callable[[str], T]) -> None: ...

    def __init__(self, *names: str, parse: Callable[[str], T] = cast(Callable[[str], T], str)) -> None:
        if not names or len(set(names)) != len(names):
            raise ValueError("Supply one or more distinct environment names")
        if any(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None for name in names):
            raise ValueError("Environment names must be valid identifiers")
        self.names = names
        self.parse = parse
        self.field: str | None = None

    def __set_name__(self, owner: type[Env], name: str) -> None:
        if self.field is not None:
            raise TypeError("Create a separate Var for each field")
        self.field = name

    @overload
    def __get__(self, instance: None, owner: type[Env] | None = None) -> Self: ...

    @overload
    def __get__(self, instance: Env, owner: type[Env] | None = None) -> T: ...

    def __get__(self, instance: Env | None, owner: type[Env] | None = None) -> T | Self:
        if instance is None:
            return self
        return cast(T, instance._values[self.field])

    def __set__(self, instance: Env, value: T) -> None:
        raise AttributeError("Environment configuration is read-only")


class Env:
    """Base class for application-owned schemas."""

    _values: Mapping[str | None, object]

    def __init__(self) -> None:
        raise TypeError("Use load(Schema) or Schema.from_mapping(values)")

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        for name, value in vars(cls).items():
            if isinstance(value, Var) and (name.startswith("_") or hasattr(Env, name)):
                raise TypeError("Field names must be public and must not replace Env methods")
        used: set[str] = set()
        for field in cls._fields().values():
            if used.intersection(field.names):
                raise TypeError("Environment names must belong to only one field")
            used.update(field.names)

    @classmethod
    def _fields(cls) -> dict[str, Var[Any]]:
        attributes: dict[str, object] = {}
        for base in reversed(cls.__mro__):
            attributes.update(vars(base))
        return {name: value for name, value in attributes.items() if isinstance(value, Var)}

    @classmethod
    def from_mapping(cls, source: Mapping[str, str | None]) -> Self:
        """Validate a mapping without reading or changing the process environment."""
        values: dict[str | None, object] = {}
        problems: list[Problem] = []
        for name, field in cls._fields().items():
            present = [(key, source[key]) for key in field.names if source.get(key) is not None]
            present = [(key, value.strip()) for key, value in present if value is not None and value.strip()]
            if not present:
                problems.append(Problem(name, field.names, "required value is missing or empty"))
            elif len(present) > 1:
                problems.append(Problem(name, field.names, "multiple aliases are set"))
            else:
                try:
                    values[name] = field.parse(cast(str, present[0][1]))
                except ValueError:
                    # Parser messages can contain secrets. Keep only the field identity.
                    problems.append(Problem(name, field.names, "value is invalid"))
        if problems:
            raise ValidationError(problems)
        instance = object.__new__(cls)
        object.__setattr__(instance, "_values", MappingProxyType(values))
        return instance

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Environment configuration is read-only")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Environment configuration is read-only")

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>)"


def _read_files(files: Iterable[str | Path]) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for filename in files:
        path = Path(filename)
        with path.open(encoding="utf-8") as stream:
            # The tokenizer preserves literal values and exposes malformed lines.
            # dotenv_values() can skip malformed lines and expand ambient secrets.
            for binding in parse_stream(stream):
                if binding.error:
                    raise ValueError(f"Invalid dotenv syntax in {path} at line {binding.original.line}")
                if binding.key is not None:
                    values[binding.key] = binding.value
    return values


def load(schema: type[E], *, files: Iterable[str | Path] = (), environ: Mapping[str, str | None] | None = None) -> E:
    """Load explicit files, overlay the environment, then validate the schema.

    Later files win. Process values win over files. An explicit environ mapping
    replaces the process source, including an empty mapping for file-only validation.
    No source is mutated. Variable interpolation is disabled.
    """
    values = _read_files(files)
    values.update(os.environ if environ is None else environ)
    return schema.from_mapping(values)
