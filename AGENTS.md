# Working on coloph-env

Keep this package small. Solve established problems with explicit behavior.
Keep design and implementation in the same feature issue.
Use plain English and concrete examples. Read the installed `env-variables` skill for the public contract.
Public documents must stand alone. Never link or refer to private repositories.

Keep every configuration value explicit. Do not add field defaults or lazy loading.
Keep application schemas, runtime identity, deployment, and secret storage outside this package.
Use structured validation errors. Never include input values or parser exception text in diagnostics.
Unexpected parser exceptions must propagate. Catch ValueError for invalid input only.

Documentation is contained in `src/coloph_env/bundled_agent_skills/env-variables`. It is installed into host repositories. When you finish a package code change, check that this documentation is current. When you finish a documentation change, check that it is consistent with the package code.

Before a release, run Ruff, mypy, pytest, and the artifact smoke tests in docs/releasing.md.
Keep the package version in pyproject.toml. Never duplicate it in source code.
Release tags must identify the tested commit on the public main branch.
Never replace a published version or tag. Publish changes under a new version.

- **NEVER** add `get_*_env()` lazy accessor functions.
- **NEVER** add descriptor defaults or default-valued env vars. If an implementation plan asks for an env var "with a default value" or "empty default", disregard that part of the plan and require the var explicitly in the relevant env file plus tests.
