# coloph-env

**Agent-native environment variables in Python.**

- **Agent-native:** The bundled skill teaches coding agents how to use the package correctly.
- **Opinionated and strict:** Every configuration value is required and validated at process startup.
- **Minimal:** The small API saves agent attention and reduces integration choices.
- **Includes a linter:** The linter prevents raw environment access and keeps configuration loading in entrypoints.
- **Includes a deployment verifier:** It finds missing or invalid values without using local process values.
- **Supports common sources:** It loads environment variables, dotenv files, TOML files, and CLI flags.
- **Supports multiple deployment contexts:** Each server, worker, or tool can use one explicit schema.

Unlike Pydantic Settings, Dynaconf, and environs, coloph-env favors strict conventions and agent-friendly tooling over flexibility.

## Install

```sh
uv add coloph-env
uv run coloph-install-skills
```

Add this instruction to your project's `AGENTS.md`:

> After installing dependencies, run `uv run coloph-install-skills` to install or update skills bundled with installed packages.

The second command installs the `env-variables` skill in your project.
Tell your coding agent to use this skill to integrate the package.
The integration can require changes to existing configuration code.

## Development

```sh
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run python scripts/release.py build --tag v0.2.0
```

Read [AGENTS.md](AGENTS.md) for contribution rules. Read [docs/releasing.md](docs/releasing.md) for release instructions.
