"""Terminate an orphaned generation group if its controller dies or its deadline expires."""

from __future__ import annotations

import os
import shutil
import signal
import sys
import time
from pathlib import Path


def main() -> None:
    worker, parent = map(int, sys.argv[1:3])
    deadline = float(sys.argv[3])
    cleanup = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    while True:
        orphan = os.getppid() != parent
        if orphan or time.monotonic() >= deadline:
            try:
                os.killpg(worker, signal.SIGKILL)
            except ProcessLookupError:
                pass
            if orphan and cleanup is not None:
                if cleanup.name.startswith("medical-codex-session-") and not cleanup.is_symlink():
                    for root, directories, _ in os.walk(cleanup, followlinks=False):
                        Path(root).chmod(0o700)
                        for directory in directories:
                            path = Path(root) / directory
                            if not path.is_symlink():
                                path.chmod(0o700)
                    shutil.rmtree(cleanup, ignore_errors=True)
            return
        try:
            os.kill(worker, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)


if __name__ == "__main__":
    main()
