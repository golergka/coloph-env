import json
import traceback

import pytest

from coloph_env import Env, ValidationError, Var, load


class Server(Env):
    key = Var("KEY", "OLD_KEY")
    port = Var("PORT", parse=int)


def test_aggregate_errors_never_expose_values():
    source = {"KEY": "secret", "OLD_KEY": "other-secret", "PORT": "port-secret"}
    with pytest.raises(ValidationError) as caught:
        Server.from_mapping(source)
    assert len(caught.value.problems) == 2
    assert [p.field for p in caught.value.problems] == ["key", "port"]
    assert "multiple aliases" in str(caught.value)
    assert "secret" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("value", [None, "", "  \t "])
def test_missing_and_empty(value):
    with pytest.raises(ValidationError) as caught:
        Server.from_mapping({"KEY": value})
    assert len(caught.value.problems) == 2


def test_alias_parsing_snapshot_and_readonly(monkeypatch):
    source = {"OLD_KEY": "  secret  ", "PORT": "42"}
    env = Server.from_mapping(source)
    source["PORT"] = "99"
    monkeypatch.setenv("PORT", "100")
    assert env.port == 42
    assert env.key == "secret"
    assert "secret" not in repr(env)
    with pytest.raises(AttributeError):
        env.port = 2
    with pytest.raises(AttributeError):
        del env.port


def test_inheritance_and_override():
    class Child(Server):
        port = Var("CHILD_PORT", parse=int)
        name = Var("NAME")

    env = Child.from_mapping({"KEY": "k", "CHILD_PORT": "12", "NAME": "child"})
    assert (env.port, env.name, env.key) == (12, "child", "k")


def test_multiple_inheritance_uses_python_mro():
    class Left(Env):
        value = Var("LEFT")

    class Right(Env):
        value = Var("RIGHT")

    class Child(Left, Right):
        pass

    assert Child.from_mapping({"LEFT": "left"}).value == "left"


def test_invalid_schema_names_and_collisions():
    with pytest.raises(ValueError):
        Var()
    with pytest.raises(ValueError):
        Var("A", "A")
    with pytest.raises(ValueError):
        Var("BAD\nNAME")
    with pytest.raises(TypeError):

        class Duplicate(Env):
            a = Var("SAME")
            b = Var("SAME")

    with pytest.raises(TypeError):

        class Reserved(Env):
            from_mapping = Var("VALUE")

    with pytest.raises(TypeError):
        Server()


def test_custom_parser_failures():
    def expected(value):
        raise ValueError(value)

    class Expected(Env):
        value = Var("VALUE", parse=expected)

    source = {"VALUE": "secret"}
    with pytest.raises(ValidationError) as caught:
        Expected.from_mapping(source)
    assert "secret" not in "".join(traceback.format_exception(caught.value))

    def unexpected(value):
        raise RuntimeError("programming error")

    class Unexpected(Env):
        value = Var("VALUE", parse=unexpected)

    with pytest.raises(RuntimeError, match="programming error"):
        Unexpected.from_mapping({"VALUE": "test"})


def test_layer_precedence_and_no_environment_mutation(tmp_path, monkeypatch):
    first = tmp_path / "base.env"
    second = tmp_path / "local.env"
    first.write_text("KEY=file-key\nPORT=1\n")
    second.write_text("PORT=2\n")
    monkeypatch.setenv("PORT", "3")
    monkeypatch.delenv("KEY", raising=False)
    monkeypatch.delenv("OLD_KEY", raising=False)
    assert load(Server, files=[first, second]).port == 3
    assert load(Server, files=[first, second], environ={}).port == 2
    import os

    assert "KEY" not in os.environ
    assert os.environ["PORT"] == "3"
    with pytest.raises(ValidationError):
        load(Server, files=[first], environ={"PORT": ""})


def test_files_are_literal_and_file_only_validation_is_isolated(tmp_path, monkeypatch):
    path = tmp_path / "config.env"
    path.write_text('KEY="${AMBIENT_SECRET}"\nPORT=1\n')
    monkeypatch.setenv("AMBIENT_SECRET", "must-not-leak")
    assert load(Server, files=[path], environ={}).key == "${AMBIENT_SECRET}"
    path.write_text("PORT=1\n")
    monkeypatch.setenv("KEY", "ambient-key")
    with pytest.raises(ValidationError):
        load(Server, files=[path], environ={})


def test_files_must_exist_and_have_valid_syntax(tmp_path):
    with pytest.raises(FileNotFoundError):
        load(Server, files=[tmp_path / "missing"], environ={})
    path = tmp_path / "bad.env"
    path.write_text('KEY=k\nPORT=1\nBAD="secret\n')
    with pytest.raises(ValueError, match="line 3") as caught:
        load(Server, files=[path], environ={})
    assert "secret" not in str(caught.value)


def test_dotenv_quoting_export_comments_and_multiline(tmp_path):
    path = tmp_path / "config.env"
    path.write_text('export KEY="first\nsecond" # comment\nPORT=7\n')
    assert load(Server, files=[path], environ={}).key == "first\nsecond"


def test_toml_types_order_and_all_later_layers(tmp_path):
    class Typed(Env):
        text = Var("TEXT")
        count = Var("COUNT", parse=int)
        ratio = Var("RATIO", parse=float)
        enabled = Var("ENABLED", parse=lambda value: value == "true")
        names = Var("NAMES", toml="servers", parse=json.loads)

    first = tmp_path / "base.toml"
    second = tmp_path / "local.toml"
    dotenv = tmp_path / ".env"
    first.write_text('text = "base"\ncount = 1\nratio = 1.5\nenabled = true\nservers = ["a", "b"]\n')
    second.write_text('text = "local"\n')
    dotenv.write_text("COUNT=2\n")
    env = load(
        Typed,
        toml_files=[first, second],
        files=[dotenv],
        environ={"RATIO": "2.5"},
        overrides={"TEXT": "cli"},
    )
    assert (env.text, env.count, env.ratio, env.enabled, env.names) == ("cli", 2, 2.5, True, ["a", "b"])


def test_toml_unknown_keys_types_missing_files_and_final_fields(tmp_path):
    unknown = tmp_path / "unknown.toml"
    unknown.write_text('secret_key = "secret"\n')
    with pytest.raises(ValidationError) as caught:
        load(Server, toml_files=[unknown], environ={})
    assert caught.value.problems[0].source == str(unknown)
    assert "secret_key" in str(caught.value)
    assert '"secret"' not in str(caught.value)

    unsupported = tmp_path / "unsupported.toml"
    unsupported.write_text("key = { nested = 'secret' }\nport = 1\n")
    with pytest.raises(ValidationError) as caught:
        load(Server, toml_files=[unsupported], environ={})
    assert "secret" not in str(caught.value)

    partial = tmp_path / "partial.toml"
    partial.write_text('key = "value"\n')
    with pytest.raises(ValidationError) as caught:
        load(Server, toml_files=[partial], environ={})
    assert [problem.field for problem in caught.value.problems] == ["port"]
    with pytest.raises(FileNotFoundError):
        load(Server, toml_files=[tmp_path / "missing.toml"], environ={})


def test_invalid_toml_parser_value_identifies_source_without_value(tmp_path):
    path = tmp_path / "invalid.toml"
    path.write_text('key = "safe"\nport = "port-secret"\n')
    with pytest.raises(ValidationError) as caught:
        load(Server, toml_files=[path], environ={})
    assert caught.value.problems[0].source == str(path)
    assert str(path) in str(caught.value)
    assert "port-secret" not in str(caught.value)
