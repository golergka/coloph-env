---
name: env-variables
description: Build, maintain, load, and use application configuration from environment variables, dotenv files, TOML files, and CLI flags.
---

This skill is bundled with the `coloph-env` package.

**ALL env vars are validated at process startup. No lazy loading. No on-demand instantiation.**

## Building configuration

Configuration is defined in a single schema class inherited from `coloph_env.Env`:

```python
# config.py
from coloph_env import Env, Var


class ServerEnv(Env):
    database_url = Var("DATABASE_URL")
    port = Var("PORT", parse=int)
    api_key = Var("API_KEY")
```

### Multiple configurations for different environments

If an application has multiple deployment contexts, such as a local CLI, server containers, worker processes, or a deployment script, each context should have its own configuration class. Configurations can inherit shared fields from a base class.

```python
# common/config.py
from coloph_env import Env, Var


class BaseEnv(Env):
    application_name = Var("APPLICATION_NAME")
    version = Var("VERSION")


class ServerEnv(BaseEnv):
    database_url = Var("DATABASE_URL")
    port = Var("PORT", parse=int)
    api_key = Var("API_KEY")


class WorkerEnv(ServerEnv):
    worker_id = Var("WORKER_ID")


# common/startup.py
from config import BaseEnv


def start_common(env: BaseEnv):
    print(f"Starting {env.application_name} v{env.version}")
    # ...
```

## Load configuration on startup

Load configuration once in each process entrypoint. Configuration errors will stop the process immediately.

```python
# main.py
from coloph_env import load
from config import ServerEnv

env = load(ServerEnv, files=[".env", ".env.local"], toml_files=["config.toml", "config.local.toml"])
connect(env.database_url)
serve(port=env.port)
```

### Multiple entrypoints for different environments

If a project contains multiple entrypoints for different deployment contexts, each entrypoint loads its corresponding configuration class.

```python
# server/main.py
from coloph_env import load
from config import ServerEnv

env = load(ServerEnv, files=[".env.server"])
connect(env.database_url)
serve(port=env.port)
start_common(env)

# worker/main.py
from coloph_env import load
from config import WorkerEnv

env = load(WorkerEnv, files=[".env.worker"])
init_worker(env.worker_id)
start_common(env)
```

### Load from dotenv, toml files and CLI flags

Pass ordered dotenv files with `files=` and ordered TOML files with `toml_files=`. Later files override earlier files. Process environment values override file values.

Use `add_arguments()` to attach selected schema fields to an application-owned argument parser, then use `load_arguments()` instead of `load()`. Omitted flags do not override other sources.

```python
import argparse

from coloph_env import add_arguments, load_arguments
from config import ServerEnv

parser = argparse.ArgumentParser()
add_arguments(
    parser,
    ServerEnv,
    flags={"database_url": "--database-url", "port": ("--port", "-p")},
    help={"port": "Server port"},
)
args = parser.parse_args()
env = load_arguments(parser, ServerEnv, args, files=[".env"])
```

For exact precedence and validation behavior, read [the configuration contract](references/contract.md).

## Linting the codebase

Unfortunately, coding agents sometimes add direct `os.environ` access in the codebase. This is a violation of the contract and should be detected and fixed. Integrate this linting check to flag this:

Declare entrypoints and excluded paths in `pyproject.toml`:

```toml
[tool.coloph-env]
entrypoints = ["src/example/main.py"]
exclude = ["tests/*"]
```

Run `coloph-env lint .` in development and CI. Fix `ENV001` by replacing raw environment access with a schema field. Fix `ENV002` by moving configuration loading into a declared entrypoint. The diagnostics direct agents to this skill.

## Validating environment before running the application

In CI/CD pipelines, it can be beneficial to surface problems with configuration before starting the application. Use `coloph-env validate` to check that all required environment variables are present and valid:

```sh
coloph-env validate config:ServerEnv --file .env.server
```

Repeat `--file` or `--toml-file` for ordered layers. Use `--module-path src` when the schema module is under `src/`. Validation excludes process environment values, so developer credentials cannot hide missing deployment values.

## Exit codes

Both commands use these exit codes:

| Code | Meaning |
| --- | --- |
| `0` | The check completed without findings. |
| `1` | The configuration is invalid, the linter found a violation, or the requested input cannot be checked. |
| `2` | The command-line arguments are invalid. This is the standard `argparse` status. |
| `70` | An unexpected internal error occurred. This is the BSD `EX_SOFTWARE` status. |

Internal-error diagnostics do not include exception text because it can contain configuration values.

## Rules

- **NEVER** instantiate env classes at runtime or on-demand, except calling the `load()` function in the entrypoint.
- **NEVER** read `os.environ` (enforced by `coloph-env lint .`).
- **NEVER** add per-feature env classes — all vars for a context go in that context's single class.
- **NEVER** add descriptor defaults or default-valued env vars. If an implementation plan asks for an env var "with a default value" or "empty default", push back on that part of the plan and require the var explicitly in the relevant env file plus tests.
