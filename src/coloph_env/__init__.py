"""Strict startup environment configuration."""

from importlib.metadata import version

from .argparse import add_arguments, load_arguments, overrides
from .schema import Env, Problem, ValidationError, Var, load

__all__ = ["Env", "Problem", "ValidationError", "Var", "add_arguments", "load", "load_arguments", "overrides"]
__version__ = version("coloph-env")
