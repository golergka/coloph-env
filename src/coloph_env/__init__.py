"""Strict startup environment configuration."""

from importlib.metadata import version

from .schema import Env, Problem, ValidationError, Var, load

__all__ = ["Env", "Problem", "ValidationError", "Var", "load"]
__version__ = version("coloph-env")
