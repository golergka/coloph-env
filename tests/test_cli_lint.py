import argparse
import os
import subprocess
import sys

import pytest

from coloph_env import Env, ValidationError, Var, add_arguments, load, load_arguments, overrides
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


def test_cli_validates_toml_file(tmp_path):
    (tmp_path / "schema.py").write_text(
        'from coloph_env import Env, Var\nclass App(Env):\n    port = Var("PORT", parse=int)\n'
    )
    path = tmp_path / "values.toml"
    path.write_text("port = 8080\n")
    result = subprocess.run(
        [sys.executable, "-m", "coloph_env", "validate", "schema:App", "--toml-file", str(path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


class CliEnv(Env):
    key = Var("KEY", "OLD_KEY")
    port = Var("PORT", parse=int)


def test_generated_arguments_override_environment_and_omit_absent_values():
    parser = argparse.ArgumentParser()
    add_arguments(parser, CliEnv, flags={"key": ("--key", "-k"), "port": "--port"}, help={"port": "Port"})
    namespace = parser.parse_args(["--key", "cli"])
    env = load(CliEnv, environ={"OLD_KEY": "environment", "PORT": "7"}, overrides=overrides(CliEnv, namespace))
    assert (env.key, env.port) == ("cli", 7)
    assert "Port" in parser.format_help()


def test_generated_arguments_support_parent_parser_and_app_subparser():
    parent = argparse.ArgumentParser(add_help=False)
    add_arguments(parent, CliEnv, flags={"key": "--key"})
    parser = argparse.ArgumentParser(parents=[parent])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    add_arguments(run, CliEnv, flags={"port": "--listen-port"})
    namespace = parser.parse_args(["--key", "value", "run", "--listen-port", "8"])
    env = load(CliEnv, environ={}, overrides=overrides(CliEnv, namespace))
    assert (env.key, env.port) == ("value", 8)


def test_generated_arguments_empty_invalid_aliases_and_conflicts_are_safe():
    parser = argparse.ArgumentParser()
    add_arguments(parser, CliEnv, flags={"key": "--key", "port": "--port"})
    with pytest.raises(ValidationError) as caught:
        load(
            CliEnv,
            environ={"KEY": "environment", "PORT": "7"},
            overrides=overrides(CliEnv, parser.parse_args(["--key", ""])),
        )
    assert "required value" in str(caught.value)

    with pytest.raises(ValidationError) as caught:
        load(
            CliEnv,
            environ={"KEY": "secret", "PORT": "7"},
            overrides=overrides(CliEnv, parser.parse_args(["--port", "port-secret"])),
        )
    assert "port-secret" not in str(caught.value)

    parser.add_argument("--taken")
    with pytest.raises(argparse.ArgumentError):
        add_arguments(parser, CliEnv, flags={"key": "--taken"})


def test_invalid_generated_argument_is_a_redacted_argparse_error(capsys):
    parser = argparse.ArgumentParser(prog="app")
    add_arguments(parser, CliEnv, flags={"port": "--port"})
    namespace = parser.parse_args(["--port", "port-secret"])
    with pytest.raises(SystemExit) as caught:
        load_arguments(parser, CliEnv, namespace, environ={"KEY": "key"})
    assert caught.value.code == 2
    error = capsys.readouterr().err
    assert "value is invalid" in error
    assert "port-secret" not in error
