"""File validation and repository lint commands."""

from __future__ import annotations

import argparse
import importlib
import sys
from enum import IntEnum
from pathlib import Path

from . import __version__
from .lint import lint
from .schema import Env, ValidationError, load


class ExitCode(IntEnum):
    OK = 0
    CHECK_FAILED = 1
    INTERNAL_ERROR = 70


class _SchemaImportError(Exception):
    pass


def _guidance() -> None:
    print("Use the env-variables skill for integration instructions.", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="coloph-env", description="Strict startup environment configuration")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate explicit dotenv files without process values")
    validate.add_argument("schema", help="Importable module:EnvSubclass")
    validate.add_argument("--file", action="append", default=[], type=Path)
    validate.add_argument("--toml-file", action="append", default=[], type=Path)
    validate.add_argument(
        "--module-path", type=Path, default=Path.cwd(), help="Schema import directory (default: current directory)"
    )
    lint_parser = commands.add_parser("lint", help="Find raw environment access and misplaced configuration loading")
    lint_parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    lint_parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            module, separator, attribute = args.schema.partition(":")
            if not separator or not module or not attribute:
                parser.error("Supply the schema as module:Class")
            # Import application code only for an explicit validation request.
            sys.path.insert(0, str(args.module_path.resolve()))
            try:
                try:
                    schema = getattr(importlib.import_module(module), attribute, None)
                except (ModuleNotFoundError, SyntaxError):
                    raise
                except Exception:
                    raise _SchemaImportError from None
                if not isinstance(schema, type) or not issubclass(schema, Env):
                    parser.error("The schema must name an Env subclass")
                if not args.file and not args.toml_file:
                    parser.error("Supply at least one --file or --toml-file")
                load(schema, toml_files=args.toml_file, files=args.file, environ={})
            finally:
                sys.path.pop(0)
            print("Configuration is valid")
        else:
            findings = lint(args.root, args.config)
            for finding in findings:
                print(finding)
            return ExitCode.CHECK_FAILED if findings else ExitCode.OK
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        _guidance()
        return ExitCode.CHECK_FAILED
    except (ValueError, OSError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        _guidance()
        return ExitCode.CHECK_FAILED
    except SyntaxError as exc:
        print(f"Invalid Python syntax in {exc.filename} at line {exc.lineno}", file=sys.stderr)
        _guidance()
        return ExitCode.CHECK_FAILED
    except ModuleNotFoundError:
        print("Cannot import the schema or one of its dependencies", file=sys.stderr)
        _guidance()
        return ExitCode.CHECK_FAILED
    except Exception:
        print("An internal coloph-env error occurred.", file=sys.stderr)
        _guidance()
        return ExitCode.INTERNAL_ERROR
    return ExitCode.OK
