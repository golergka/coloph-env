# coloph-env

Strict environment configuration for Python applications.

Declare every required value in a schema. Validate the complete schema at process startup.
Missing, empty, ambiguous, or invalid values stop startup with one error report.

## Install

```sh
pip install coloph-env
```

Python 3.12 or later is required. Licensed under GPL-3.0-only.

## Declare and load

```python
# config.py
from coloph_env import Env, Var


class ServerEnv(Env):
    database_url = Var("DATABASE_URL")
    port = Var("PORT", parse=int)
    api_key = Var("API_KEY")
```

```python
# main.py
from coloph_env import load
from config import ServerEnv

env = load(ServerEnv, files=[".env", ".env.local"])
# Start application work only after load() succeeds.
connect(env.database_url)
serve(port=env.port)
```

Each deployment context owns one schema. Schemas can inherit shared fields.
The entrypoint loads the selected schema and passes the configuration to application code.
Importing a schema does not read configuration.

Containers use the same schema with injected environment values:

```python
env = load(ServerEnv)
```

## Contract

- Every field is required. There are no field defaults.
- Empty and whitespace-only values count as missing. Other values lose surrounding whitespace.
- Later files override earlier files. Process values override files, including empty process values.
- Every specified file must exist. The package does not search parent directories.
- Dotenv values remain literal. Variable interpolation and shell commands do not run.
- Loading does not change `os.environ`. Configuration attributes are read-only.
- Parsers run once per load. Mutable parser results remain the responsibility of the application.

Custom parsers accept a string and raise `ValueError` for invalid input.
Other exceptions propagate as programming errors.
`ValidationError.problems` contains field names, environment names, and reasons.
Validation diagnostics omit values and parser exception text. Configuration `repr()` also omits values.

Alternate names require exactly one non-empty value:

```python
class DatabaseEnv(Env):
    url = Var("DATABASE_URL", "DB_URL")
```

An explicit mapping supports tests and application-owned sources:

```python
env = DatabaseEnv.from_mapping({"DB_URL": "postgresql://localhost/example"})
env = load(DatabaseEnv, files=["deployment.env"], environ={})
```

## Validate before deployment

```sh
coloph-env validate config:ServerEnv --file .env.server
```

Repeat `--file` for ordered layers. Use `--module-path src` for schemas under `src/`.
This command excludes process values. Developer credentials cannot hide missing deployment values.
The command imports the schema module, which must contain declarations without startup side effects.
Success returns exit code 0. Invalid configuration returns 1. Invalid command arguments return 2.

## Enforce ownership

Declare repository paths in `pyproject.toml`:

```toml
[tool.coloph-env]
entrypoints = ["src/example/main.py"]
configuration = ["src/example/config.py"]
exclude = ["tests/*"]
```

```sh
coloph-env lint .
```

`ENV001` detects direct environment access outside entrypoints and configuration modules.
`ENV002` detects loading outside entrypoints.
The AST rules recognize import aliases and ignore comments and strings.
They do not trace dynamic imports, reassigned aliases, or application wrapper functions.
Path patterns use repository-relative paths. Hidden directories, build output, and symbolic links are excluded.

## Development

```sh
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run python scripts/release.py build --tag v0.1.0
```

Read [AGENTS.md](AGENTS.md) for contribution rules and [docs/releasing.md](docs/releasing.md) for releases.
Future CLI override generation is tracked in GitHub issues.
