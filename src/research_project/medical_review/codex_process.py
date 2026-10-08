"""Bounded subprocess streams, process-group cancellation and a kernel concurrency lock."""

from __future__ import annotations

import fcntl
import os
import selectors
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def session_lock(path: Path) -> Iterator[int]:
    """A crashed controller releases its kernel lock; never unlink a lock inode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("A Codex reading session is already active.") from error
        try:
            yield stream.fileno()
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _terminate(process: subprocess.Popen) -> None:
    # The group may still contain children after the leader has exited.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except PermissionError:
        # macOS may deny signaling an exited, unreaped sandbox group. Reap only
        # an exited leader, then require the group itself to be absent.
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            raise PermissionError("Cannot terminate a live Codex process group.") from None
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        raise
    try:
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def bounded_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    prompt: bytes,
    output: Path,
    final: Path,
    duration: float,
    event_bytes: int,
    stderr_bytes: int,
    final_bytes: int,
    lock_fd: int | None = None,
    cleanup_directory: Path | None = None,
) -> int:
    """Preserve received bytes. On any cap/error stop the entire group, without retry."""
    output.mkdir(parents=True, exist_ok=True)
    stdin = output / "stdin.txt"
    with stdin.open("xb") as stream:
        stream.write(prompt)
    started = time.monotonic()
    with (
        stdin.open("rb") as incoming,
        (output / "events.jsonl").open("xb") as events,
        (output / "stderr.txt").open("xb") as errors,
    ):
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=incoming,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            guardian = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    str(Path(__file__).with_name("codex_guardian.py")),
                    str(process.pid),
                    str(os.getpid()),
                    str(started + duration),
                    *([str(cleanup_directory)] if cleanup_directory else []),
                ],
                env={"PATH": os.defpath},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                pass_fds=(lock_fd,) if lock_fd is not None else (),
                start_new_session=True,
            )
        except BaseException:
            _terminate(process)
            process.stdout.close()
            process.stderr.close()
            raise
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, (events, event_bytes))
            selector.register(process.stderr, selectors.EVENT_READ, (errors, stderr_bytes))
            counts = {events: 0, errors: 0}
            try:
                while selector.get_map():
                    if time.monotonic() - started >= duration:
                        raise TimeoutError("Codex deadline exceeded; no automatic retry.")
                    if final.is_symlink():
                        raise ValueError("Codex final-output symlink refused.")
                    if final.exists() and final.stat().st_size > final_bytes:
                        raise ValueError("Codex final-output byte limit exceeded.")
                    for key, _ in selector.select(timeout=0.05):
                        block = os.read(key.fileobj.fileno(), 16384)
                        if not block:
                            selector.unregister(key.fileobj)
                            continue
                        stream, limit = key.data
                        stream.write(block)
                        stream.flush()
                        counts[stream] += len(block)
                        if counts[stream] > limit:
                            raise ValueError(
                                "Codex stream byte limit exceeded; partial bytes retained."
                            )
                remaining = duration - (time.monotonic() - started)
                code = process.wait(timeout=max(0.001, remaining))
                if time.monotonic() - started >= duration:
                    raise TimeoutError("Codex deadline exceeded; no automatic retry.")
                if final.is_symlink() or (final.exists() and final.stat().st_size > final_bytes):
                    raise ValueError("Codex final output exceeds its safe boundary/byte limit.")
                return code
            finally:
                _terminate(process)
                guardian.terminate()
                guardian.wait(timeout=5)
                process.stdout.close()
                process.stderr.close()
