"""Append-only hash-chained task transactions; evaluator-owned, never policy-owned."""
import fcntl
import json
import os
import stat
from pathlib import Path

from experiment.rsi_v25.commitments import canonical, digest

ZERO = "0" * 64


class Archive:
    def __init__(self, path, binding, *, create=False):
        self.path = Path(path)
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            self.append("header", binding)
        events = self.read()
        if not events or events[0]["kind"] != "header" or events[0]["data"] != binding:
            raise ValueError("Archive binding differs from the pinned evaluator, stream or arm")

    @staticmethod
    def decode(raw):
        if raw and not raw.endswith(b"\n"):
            raise ValueError("Torn archive tail; no automatic truncation or free retry")
        events, previous = [], ZERO
        for line in raw.splitlines():
            row = json.loads(line)
            if (set(row) != {"seq", "previous", "kind", "data", "sha256"}
                    or type(row["seq"]) is not int or row["seq"] != len(events)
                    or row["previous"] != previous or row["sha256"] != digest(
                        {key: value for key, value in row.items() if key != "sha256"})):
                raise ValueError("Altered archive chain, order or receipt")
            if row["kind"] not in ("header", "start", "episode") or (events and row["kind"] == "header"):
                raise ValueError("Unknown or repeated archive event")
            events.append(row)
            previous = row["sha256"]
        return events

    def _open(self, flags):
        fd = os.open(self.path, flags | os.O_NOFOLLOW)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise ValueError("Archive must be a regular file")
        return fd

    def read(self, *, expected_head=None):
        fd = self._open(os.O_RDONLY)
        with os.fdopen(fd, "rb") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            events = self.decode(stream.read())
        if expected_head is not None and (not events or events[-1]["sha256"] != expected_head):
            raise ValueError("Archive differs from the externally retained head")
        return events

    def append(self, kind, data, *, expected_head=None):
        fd = self._open(os.O_RDWR)
        with os.fdopen(fd, "r+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            events = self.decode(stream.read())
            previous = events[-1]["sha256"] if events else ZERO
            if expected_head is not None and previous != expected_head:
                raise ValueError("Concurrent archive writer or stale checkpoint")
            row = {"seq": len(events), "previous": previous, "kind": kind, "data": data}
            row["sha256"] = digest(row)
            # Validate before appending. Flush and fsync before returning authority.
            encoded = canonical(row) + b"\n"
            self.decode(b"".join(canonical(x) + b"\n" for x in events) + encoded)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        return row["sha256"]

    def episodes(self):
        events = self.read()
        rows = []
        pending = None
        for event in events[1:]:
            if event["kind"] == "start":
                if pending is not None:
                    raise ValueError("Unfinished reserved task; quarantine it, do not retry")
                pending = event["data"]
            elif event["kind"] == "episode":
                row = event["data"]
                if (pending is None or pending["task_sha256"] != row["task_sha256"]
                        or pending["position"] != len(rows) or row["position"] != len(rows)
                        or row["charged_evaluations"] > pending["reserved_evaluations"]):
                    raise ValueError("Episode escaped its task reservation")
                rows.append(row)
                pending = None
        if pending is not None:
            raise ValueError("Unfinished reserved task; unknown calls remain charged, no automatic retry")
        return rows

    def programs(self):
        result = {}
        for episode in self.episodes():
            for program in episode["programs"]:
                result.setdefault(program["source_sha256"], program)
        return result
