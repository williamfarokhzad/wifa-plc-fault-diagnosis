import io
import itertools
import json
from pathlib import Path
import subprocess
import sys
import unittest

from diagnose import COLUMNS, Sample, diagnose, read_samples


ROOT = Path(__file__).resolve().parents[1]
DRIVE = "DRIVE_FAULT"
TIMEOUT = "RUN_FEEDBACK_TIMEOUT"


def run_trace(name, *args):
    return subprocess.run(
        [sys.executable, "diagnose.py", "examples/" + name + ".csv", *args],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )


def samples(*bits):
    return [Sample(10 * n, *(bool(x) for x in b)) for n, b in enumerate(bits)]


def timeline(result):
    return [(x["t_ms"], x["raised"]) for x in result["events"]]


class DiagnosisTests(unittest.TestCase):
    def test_four_examples_from_cli(self):
        cases = {
            "healthy": [],
            "drive-first": [(20, [DRIVE]), (40, [TIMEOUT])],
            "feedback-first": [(40, [TIMEOUT]), (50, [DRIVE])],
            "same-scan": [(40, [DRIVE, TIMEOUT])],
        }
        for name, want in cases.items():
            with self.subTest(name=name):
                r = json.loads(run_trace(name).stdout)
                self.assertEqual(timeline(r), want)
                self.assertEqual(r["first_fault"], r["events"][0] if want else None)
                self.assertEqual(r["samples"], 7)

    def test_first_context_survives_a_later_event(self):
        r = json.loads(run_trace("drive-first").stdout)
        first, second = r["events"]
        self.assertEqual(first["snapshot"], {
            "t_ms": 20, "run_cmd": True, "run_fb": False, "drive_fault": True,
        })
        self.assertEqual([x["t_ms"] for x in first["history"]], [0, 10])
        self.assertEqual([x["t_ms"] for x in second["history"]], [10, 20, 30])
        self.assertEqual(second["active"], [DRIVE, TIMEOUT])
        self.assertEqual(r["first_fault"], first)

    def test_feedback_on_exact_deadline_has_no_timeout(self):
        r = diagnose(samples((0,0,0), (1,0,0), (1,0,0), (1,0,0), (1,1,0)), 30, 2)
        self.assertIsNone(r["first_fault"])

    def test_dropout_after_feedback_starts_new_timer(self):
        r = diagnose(samples((1,0,0), (1,1,0), (1,0,0), (1,0,0), (1,0,0)), 20, 0)
        self.assertEqual(timeline(r), [(40, [TIMEOUT])])
        self.assertEqual(r["first_fault"]["history"], [])

    def test_non_multiple_waits_for_next_sample(self):
        r = json.loads(run_trace("feedback-first", "--timeout-ms", "25").stdout)
        self.assertEqual(r["first_fault"]["t_ms"], 40)

    def test_drive_bit_can_raise_again_after_clearing(self):
        r = diagnose(samples((0,0,1), (0,0,1), (0,0,0), (0,0,1)), 30, 2)
        self.assertEqual(timeline(r), [(0, [DRIVE]), (30, [DRIVE])])

    def test_gaps_duplicates_and_bad_bits_rejected(self):
        header = ",".join(COLUMNS) + "\n"
        for trace in ["", "10,0,0,0\n", "0,0,0,0\n20,1,0,0\n",
                      "0,0,0,0\n0,1,0,0\n", "0,0,,0\n", "0,0,0,0,0\n"]:
            with self.subTest(trace=trace), self.assertRaises(ValueError):
                read_samples(io.StringIO(header + trace), 10)

    def test_invalid_cli_settings_have_no_json_result(self):
        for args in [("--timeout-ms", "0"), ("--scan-ms", "20"), ("--history-scans", "-1")]:
            with self.subTest(args=args), self.assertRaises(subprocess.CalledProcessError) as cm:
                run_trace("drive-first", *args)
            self.assertEqual(cm.exception.returncode, 2)
            self.assertEqual(cm.exception.stdout, "")
            self.assertIn("Invalid trace or settings", cm.exception.stderr)

    def test_exhaustive_four_scan_oracle(self):
        # Independent oracle: a sliding window of three mismatched samples is
        # required for 20 ms at 10 ms spacing. Compare each individual edge.
        possible = list(itertools.product((False, True), repeat=3))
        for trace in itertools.product(possible, repeat=4):
            mismatches = [cmd and not fb for cmd, fb, _ in trace]
            drive = [fault for _, _, fault in trace]
            timeout = [n >= 2 and all(mismatches[n-2:n+1]) for n in range(4)]
            expected = []
            for n in range(4):
                codes = [name for name, series in ((DRIVE, drive), (TIMEOUT, timeout))
                         if series[n] and (n == 0 or not series[n-1])]
                if codes:
                    expected.append((n * 10, codes))
            self.assertEqual(timeline(diagnose(samples(*trace), 20, 2)), expected)


if __name__ == "__main__":
    unittest.main()
