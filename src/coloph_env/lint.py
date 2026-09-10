"""AST rules for explicit environment ownership."""

from __future__ import annotations

import ast
import fnmatch
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}"


def inspect_source(source: str, *, path: str, entrypoint: bool, configuration: bool) -> list[Finding]:
    """Detect direct imports and module aliases without executing source code."""
    tree = ast.parse(source, filename=path)
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name if item.asname else item.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for item in node.names:
                aliases[item.asname or item.name] = f"{node.module}.{item.name}"

    def name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{name(node.value)}.{node.attr}"
        return ""

    findings: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        resolved = name(node)
        if isinstance(node, (ast.Name, ast.Attribute)) and resolved in {"os.environ", "os.environb", "os.getenv"}:
            if not (entrypoint or configuration):
                findings.add(
                    (node.lineno, "ENV001: raw environment access belongs in an entrypoint or configuration module")
                )
        if isinstance(node, ast.Call) and name(node.func) in {
            "coloph_env.load",
            "coloph_env.schema.load",
            "dotenv.load_dotenv",
            "dotenv.dotenv_values",
            "dotenv.main.load_dotenv",
            "dotenv.main.dotenv_values",
        }:
            if not entrypoint:
                findings.add((node.lineno, "ENV002: environment loading belongs in an entrypoint"))
    return [Finding(path, line, rule) for line, rule in sorted(findings)]


def lint(root: Path, config_path: Path | None = None) -> list[Finding]:
    """Read repository rules from [tool.coloph-env] in pyproject.toml."""
    root = root.resolve()
    path = config_path or root / "pyproject.toml"
    with path.open("rb") as stream:
        config = tomllib.load(stream).get("tool", {}).get("coloph-env", {})
    if not isinstance(config, dict) or set(config) - {"entrypoints", "configuration", "exclude"}:
        raise ValueError("Use entrypoints, configuration, and exclude in [tool.coloph-env]")
    for patterns in config.values():
        if not isinstance(patterns, list) or not all(isinstance(pattern, str) for pattern in patterns):
            raise ValueError("Each lint configuration value must be an array of path patterns")

    def matches(relative: str, key: str) -> bool:
        return any(fnmatch.fnmatchcase(relative, pattern) for pattern in config.get(key, []))

    findings: list[Finding] = []

    def walk_error(error: OSError) -> None:
        raise error

    for directory, subdirectories, filenames in root.walk(on_error=walk_error):
        subdirectories[:] = sorted(
            name for name in subdirectories if not name.startswith(".") and name not in {"__pycache__", "dist", "build"}
        )
        for filename in sorted(filenames):
            file = directory / filename
            relative = file.relative_to(root).as_posix()
            if (
                not filename.endswith(".py")
                or filename.startswith(".")
                or file.is_symlink()
                or matches(relative, "exclude")
            ):
                continue
            findings.extend(
                inspect_source(
                    file.read_text(encoding="utf-8"),
                    path=relative,
                    entrypoint=matches(relative, "entrypoints"),
                    configuration=matches(relative, "configuration"),
                )
            )
    return findings
