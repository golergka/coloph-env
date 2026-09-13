"""Build, smoke-test, and publish the exact versioned artifacts."""

import argparse
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def artifacts(version: str) -> list[Path]:
    wheel = list((ROOT / "dist").glob(f"coloph_env-{version}-*.whl"))
    source = list((ROOT / "dist").glob(f"coloph_env-{version}.tar.gz"))
    if len(wheel) != 1 or len(source) != 1:
        raise SystemExit("Expected one wheel and one source distribution for the release")
    return wheel + source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build", "publish"])
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if args.tag != f"v{version}":
        raise SystemExit("Release tag does not match pyproject.toml")
    if args.command == "build":
        subprocess.run(["uv", "build", "--no-sources"], cwd=ROOT, check=True)
        with tempfile.TemporaryDirectory(prefix="coloph-env-smoke-") as directory:
            for artifact in artifacts(version):
                artifact_directory = Path(directory) / artifact.name
                artifact_directory.mkdir()
                subprocess.run(
                    [
                        "uv",
                        "run",
                        "--isolated",
                        "--no-project",
                        "--refresh-package",
                        "coloph-env",
                        "--with",
                        str(artifact),
                        "python",
                        str(ROOT / "scripts/smoke.py"),
                    ],
                    cwd=artifact_directory,
                    check=True,
                )
    else:
        subprocess.run(
            ["uv", "publish", "--trusted-publishing", "always", *map(str, artifacts(version))], cwd=ROOT, check=True
        )


if __name__ == "__main__":
    main()
