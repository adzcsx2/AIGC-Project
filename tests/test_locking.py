import os
import subprocess
import sys

import pytest

from autodl_video.errors import AutoDLError
from autodl_video.locking import resource_lock

CHILD = """
from pathlib import Path
import os, sys
from autodl_video.errors import AutoDLError
from autodl_video.locking import resource_lock
try:
    with resource_lock(Path(sys.argv[1]), root=Path(sys.argv[2]), timeout=0):
        if len(sys.argv) > 3:
            os._exit(0)
except AutoDLError:
    sys.exit(2)
"""


def child(target, root, *extra):
    return subprocess.run(
        [sys.executable, "-B", "-X", "utf8", "-c", CHILD, str(target), str(root), *extra],
        capture_output=True, timeout=10,
    )


def test_resource_lock_excludes_processes_and_releases_on_exception(tmp_path):
    target = tmp_path / "project.yaml"
    alias = tmp_path / "unused/../project.yaml"
    with pytest.raises(RuntimeError):
        with resource_lock(target, root=tmp_path):
            assert child(alias, tmp_path).returncode == 2
            assert child(tmp_path / "materials.yaml", tmp_path).returncode == 0
            if os.name == "nt":
                assert child(str(target).swapcase(), tmp_path).returncode == 2
            raise RuntimeError("synthetic writer failure")
    result = child(alias, tmp_path)
    assert result.returncode == 0, result.stderr


def test_resource_lock_releases_after_abrupt_process_exit(tmp_path):
    target = tmp_path / "project.yaml"
    assert child(target, tmp_path, "exit").returncode == 0
    with resource_lock(target, root=tmp_path, timeout=0):
        pass


@pytest.mark.parametrize("timeout", [-1, True, float("inf"), float("nan")])
def test_resource_lock_rejects_invalid_timeout_without_side_effects(tmp_path, timeout):
    with pytest.raises(AutoDLError, match="timeout"):
        with resource_lock(tmp_path / "project.yaml", root=tmp_path, timeout=timeout):
            pytest.fail("invalid timeout acquired a lock")
    assert not (tmp_path / ".autodl").exists()
