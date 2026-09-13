from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_bundled_skill_installs_with_all_supporting_files(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "coloph_install_skills"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    installed = tmp_path / ".agents" / "skills" / "env-variables"
    link = tmp_path / ".claude" / "skills" / "env-variables"
    assert (installed / "SKILL.md").is_file()
    assert (installed / "references" / "contract.md").is_file()
    assert link.is_symlink()
    assert link.resolve() == installed.resolve()
