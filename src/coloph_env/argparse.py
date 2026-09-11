"""Composable argparse arguments for configuration overrides."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TypeVar

from .schema import Env, ValidationError, load

E = TypeVar("E", bound=Env)


def add_arguments(
    parser: argparse.ArgumentParser,
    schema: type[Env],
    *,
    flags: Mapping[str, str | tuple[str, ...]],
    help: Mapping[str, str] | None = None,
) -> None:
    """Add selected schema fields to an application-owned parser."""
    fields = schema._fields()
    unknown = (set(flags) | set(help or {})) - fields.keys()
    if unknown:
        raise ValueError(f"Unknown schema field: {sorted(unknown)[0]}")
    for field, option_strings in flags.items():
        options = (option_strings,) if isinstance(option_strings, str) else option_strings
        parser.add_argument(
            *options,
            dest=f"_coloph_env_{field}",
            default=argparse.SUPPRESS,
            help=(help or {}).get(field),
        )


def overrides(schema: type[Env], namespace: argparse.Namespace) -> dict[str, str]:
    """Extract supplied configuration arguments as a final load() layer."""
    values = vars(namespace)
    return {
        field.names[0]: values[f"_coloph_env_{name}"]
        for name, field in schema._fields().items()
        if f"_coloph_env_{name}" in values
    }


def load_arguments(
    parser: argparse.ArgumentParser,
    schema: type[E],
    namespace: argparse.Namespace,
    *,
    toml_files: Iterable[str | Path] = (),
    files: Iterable[str | Path] = (),
    environ: Mapping[str, str | None] | None = None,
) -> E:
    """Load all sources and report invalid configuration as an argparse error."""
    try:
        return load(
            schema,
            toml_files=toml_files,
            files=files,
            environ=environ,
            overrides=overrides(schema, namespace),
        )
    except ValidationError as exc:
        parser.error(str(exc))
