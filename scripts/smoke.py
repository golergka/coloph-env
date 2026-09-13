"""Exercise an installed distribution outside the source tree."""

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from coloph_env import Env, ValidationError, Var, __version__
from coloph_env.cli import main


class App(Env):
    port = Var("PORT", parse=int)


assert __version__ == version("coloph-env")
assert App.from_mapping({"PORT": "8080"}).port == 8080
try:
    App.from_mapping({})
except ValidationError:
    pass
else:
    raise AssertionError("Missing values must fail")

subprocess.run([sys.executable, "-m", "coloph_install_skills"], check=True)
installed_skill = Path(".agents/skills/env-variables")
claude_skill = Path(".claude/skills/env-variables")
assert (installed_skill / "SKILL.md").is_file()
assert (installed_skill / "references/contract.md").is_file()
assert claude_skill.is_symlink()
assert claude_skill.resolve() == installed_skill.resolve()

main(["--version"])  # argparse exits successfully here.
