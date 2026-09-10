"""Exercise an installed distribution outside the source tree."""

from importlib.metadata import version

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
main(["--version"])  # argparse exits successfully here.
