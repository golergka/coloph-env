import os
import subprocess
import sys

import pytest

from coloph_env.lint import inspect_source, lint


@pytest.mark.parametrize(
    "source",
    [
        'import os; x = os.environ["KEY"]',
        'import os as system; x = system.getenv("KEY")',
        'from os import environ as values; x = values.get("KEY")',
        'from os import getenv as value; x = value("KEY")',
        'import os; os.environ["KEY"] = "value"',
    ],
)
def test_raw_environment_aliases(source):
    findings = inspect_source(source, path="app.py", entrypoint=False, configuration=False)
    assert len(findings) == 1
    assert "ENV001" in findings[0].rule
    assert not inspect_source(source, path="app.py", entrypoint=False, configuration=True)


@pytest.mark.parametrize(
    "source",
    [
        "from coloph_env import load as startup; startup(Schema)",
        "import coloph_env as env; env.load(Schema)",
        "from dotenv import load_dotenv as read; read()",
        'import dotenv; dotenv.dotenv_values(".env")',
    ],
)
def test_loading_only_at_entrypoints(source):
    findings = inspect_source(source, path="app.py", entrypoint=False, configuration=True)
    assert len(findings) == 1
    assert "ENV002" in findings[0].rule
    assert not inspect_source(source, path="app.py", entrypoint=True, configuration=False)


def test_comments_and_literals_are_not_code():
    assert not inspect_source(
        '# os.getenv("KEY")\nx = "load_dotenv()"', path="app.py", entrypoint=False, configuration=False
    )


def test_repository_lint_config_and_exclusions(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.coloph-env]\nentrypoints=["main.py"]\nexclude=["tests/*"]\n')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_app.py").write_text("import os\nx = os.environ\n")
    (tmp_path / "main.py").write_text("from coloph_env import load\nload(Schema)\n")
    (tmp_path / "app.py").write_text("import os\nx = os.environ\n")
    assert [f.path for f in lint(tmp_path)] == ["app.py"]
    (tmp_path / "pyproject.toml").write_text('[tool.coloph-env]\nentrypoints="main.py"\n')
    with pytest.raises(ValueError):
        lint(tmp_path)


def test_cli_validates_files_in_separate_process(tmp_path):
    (tmp_path / "schema.py").write_text('from coloph_env import Env, Var\nclass App(Env):\n    key = Var("KEY")\n')
    path = tmp_path / "values.env"
    path.write_text("KEY=test\n")
    command = [sys.executable, "-m", "coloph_env", "validate", "schema:App", "--file", str(path)]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    path.write_text("")
    result = subprocess.run(
        command, cwd=tmp_path, env={**os.environ, "KEY": "secret"}, capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 1
    assert "required value" in result.stderr
    assert "secret" not in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_help_needs_no_configuration(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "coloph_env", "--help"], cwd=tmp_path, capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0
    assert "validate" in result.stdout
