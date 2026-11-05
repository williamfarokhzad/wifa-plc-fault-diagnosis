"""Replay sampled PLC signals. No drivers, network connections, or output writes."""
import argparse
import csv
import json
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path


COLUMNS = ("t_ms", "run_cmd", "run_fb", "drive_fault")


@dataclass(frozen=True)
class Sample:
    t_ms: int
    run_cmd: bool
    run_fb: bool
    drive_fault: bool


def read_samples(file, scan_ms):
    """Read a complete, uniformly sampled CSV. Reject missing or ambiguous data."""
    if type(scan_ms) is not int or scan_ms <= 0:
        raise ValueError("scan interval must be a positive integer")
    reader = csv.reader(file, strict=True)
    if next(reader, None) != list(COLUMNS):
        raise ValueError("CSV header must be: " + ",".join(COLUMNS))
    rows = []
    for line, row in enumerate(reader, 2):
        expected = len(rows) * scan_ms
        if len(row) != 4 or any(bit not in ("0", "1") for bit in row[1:]):
            raise ValueError(f"row {line}: expected time and three 0/1 values")
        if row[0] != str(expected):
            raise ValueError(f"row {line}: expected t_ms={expected}; missing, repeated or irregular sample")
        rows.append(Sample(expected, *(bit == "1" for bit in row[1:])))
    if not rows:
        raise ValueError("CSV must include at least one sample")
    return rows


def diagnose(samples, timeout_ms, history_scans):
    """Evaluate a validated trace and capture rising diagnostic events."""
    if type(timeout_ms) is not int or timeout_ms <= 0:
        raise ValueError("timeout must be a positive integer in milliseconds")
    if type(history_scans) is not int or history_scans < 0:
        raise ValueError("history length must be a nonnegative integer")
    history = deque(maxlen=min(history_scans, len(samples)))
    start = None
    previous = ()
    events = []
    for sample in samples:
        active = []
        if sample.drive_fault:
            active.append("DRIVE_FAULT")
        if sample.run_cmd and not sample.run_fb:
            if start is None:
                start = sample.t_ms
            if sample.t_ms - start >= timeout_ms:
                active.append("RUN_FEEDBACK_TIMEOUT")
        else:
            start = None
        raised = [code for code in active if code not in previous]
        if raised:
            events.append({
                "t_ms": sample.t_ms,
                "raised": raised,
                "active": active,
                "snapshot": asdict(sample),
                "history": list(history),
            })
        previous = active
        history.append(asdict(sample))
    return {"samples": len(samples), "first_fault": events[0] if events else None, "events": events}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("trace", type=Path)
    p.add_argument("--scan-ms", type=int, default=10)
    p.add_argument("--timeout-ms", type=int, default=30)
    p.add_argument("--history-scans", type=int, default=3)
    a = p.parse_args()
    try:
        with a.trace.open(encoding="utf-8-sig", newline="") as f:
            samples = read_samples(f, a.scan_ms)
        result = diagnose(samples, a.timeout_ms, a.history_scans)
    except (OSError, ValueError, csv.Error) as e:
        p.exit(2, f"Invalid trace or settings: {e}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
