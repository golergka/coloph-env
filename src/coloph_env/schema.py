"""Schemas and explicit source resolution."""

from __future__ import annotations

import json
import os
import re
import tomllib
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
    source: str | None = None

    def __str__(self) -> str:
        source = f" in {self.source}" if self.source is not None else ""
        return f"{self.field} ({', '.join(self.names)}){source}: {self.reason}"


class ValidationError(ValueError):
    """All field errors from one schema validation."""

    def __init__(self, problems: Iterable[Problem]) -> None:
        self.problems = tuple(problems)
        super().__init__("Invalid environment configuration:\n" + "\n".join(f"  {p}" for p in self.problems))


class Var(Generic[T]):
    """A required field with one or more mutually exclusive environment names."""

    @overload
    def __init__(self: Var[str], *names: str, toml: str | None = None) -> None: ...

    @overload
    def __init__(self, *names: str, parse: Callable[[str], T], toml: str | None = None) -> None: ...

    def __init__(
        self,
        *names: str,
        parse: Callable[[str], T] = cast(Callable[[str], T], str),
        toml: str | None = None,
    ) -> None:
        if not names or len(set(names)) != len(names):
            raise ValueError("Supply one or more distinct environment names")
        if any(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None for name in names):
            raise ValueError("Environment names must be valid identifiers")
        if toml == "":
            raise ValueError("TOML keys must not be empty")
        self.names = names
        self.parse = parse
        self.toml = toml
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
        toml_keys: set[str] = set()
        for field in cls._fields().values():
            if used.intersection(field.names):
                raise TypeError("Environment names must belong to only one field")
            used.update(field.names)
            toml_key = field.toml or cast(str, field.field)
            if toml_key in toml_keys:
                raise TypeError("TOML keys must belong to only one field")
            toml_keys.add(toml_key)

    @classmethod
    def _fields(cls) -> dict[str, Var[Any]]:
        attributes: dict[str, object] = {}
        for base in reversed(cls.__mro__):
            attributes.update(vars(base))
        return {name: value for name, value in attributes.items() if isinstance(value, Var)}

    @classmethod
    def from_mapping(cls, source: Mapping[str, str | None]) -> Self:
        """Validate a mapping without reading or changing the process environment."""
        return cls._from_mapping(source, {})

    @classmethod
    def _from_mapping(cls, source: Mapping[str, str | None], sources: Mapping[str, str]) -> Self:
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
                    problems.append(Problem(name, field.names, "value is invalid", sources.get(present[0][0])))
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


def _toml_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return json.dumps(value, separators=(",", ":"))
    raise ValueError


def _read_toml_files(schema: type[Env], files: Iterable[str | Path]) -> tuple[dict[str, str | None], dict[str, str]]:
    values: dict[str, str | None] = {}
    sources: dict[str, str] = {}
    fields = {field.toml or name: field for name, field in schema._fields().items()}
    for filename in files:
        path = Path(filename)
        try:
            with path.open("rb") as stream:
                document = tomllib.load(stream)
        except tomllib.TOMLDecodeError:
            raise ValueError(f"Invalid TOML syntax in {path}") from None
        problems: list[Problem] = []
        for key, value in document.items():
            field = fields.get(key)
            if field is None:
                problems.append(Problem(key, (key,), "unknown TOML key", str(path)))
                continue
            try:
                values[field.names[0]] = _toml_value(value)
                sources[field.names[0]] = str(path)
            except (TypeError, ValueError):
                problems.append(
                    Problem(cast(str, field.field), field.names, "TOML value type is unsupported", str(path))
                )
        if problems:
            raise ValidationError(problems)
    return values, sources


def _overlay(
    schema: type[Env],
    values: dict[str, str | None],
    sources: dict[str, str],
    layer: Mapping[str, str | None],
) -> None:
    for field in schema._fields().values():
        if any(name in layer for name in field.names):
            for name in field.names:
                values.pop(name, None)
                sources.pop(name, None)
    values.update(layer)


def load(
    schema: type[E],
    *,
    toml_files: Iterable[str | Path] = (),
    files: Iterable[str | Path] = (),
    environ: Mapping[str, str | None] | None = None,
    overrides: Mapping[str, str | None] | None = None,
) -> E:
    """Load TOML, dotenv, environment, and explicit override layers, then validate.

    Later files win within each kind. An explicit environ mapping replaces the
    process source, including an empty mapping for file-only validation.
    """
    values, sources = _read_toml_files(schema, toml_files)
    _overlay(schema, values, sources, _read_files(files))
    _overlay(schema, values, sources, os.environ if environ is None else environ)
    _overlay(schema, values, sources, overrides or {})
    return schema._from_mapping(values, sources)
