# PLC fault diagnosis: capture the first alarm from a scan trace

Read the full [WIFA Robotics lesson](https://wifarobotics.com/learn/plc-fault-diagnosis/). This repository replays synthetic PLC signal snapshots in Python. It reads local CSV files and prints JSON. It does not connect to a controller or actuate equipment.

## Start here

1. Install Python 3.11 or newer. On Windows and macOS, use the [Python downloads page](https://www.python.org/downloads/). On Linux, use your distribution's Python 3 package. Check `python3 --version` on macOS/Linux or `py -3 --version` in Windows PowerShell.
2. Use **Code → Download ZIP** on GitHub, extract the ZIP, then open your terminal in the extracted directory containing `diagnose.py`. If Git is already installed you can use the commands below instead.
3. Use the standard library only. No `pip install` step is needed.

```sh
git clone https://github.com/williamfarokhzad/wifa-plc-fault-diagnosis.git
cd wifa-plc-fault-diagnosis
python3 diagnose.py examples/healthy.csv
python3 diagnose.py examples/drive-first.csv
python3 diagnose.py examples/feedback-first.csv
python3 diagnose.py examples/same-scan.csv
python3 -m unittest discover -s tests -v
```

On Windows, replace `python3` with `py -3` in each command. These instructions are provided for Windows, but the supplied checks ran on Linux.

| CSV | First recorded alarm | Later raised alarm |
| --- | --- | --- |
| healthy.csv | None | None |
| drive-first.csv | `DRIVE_FAULT` at 20 ms | `RUN_FEEDBACK_TIMEOUT` at 40 ms |
| feedback-first.csv | `RUN_FEEDBACK_TIMEOUT` at 40 ms | `DRIVE_FAULT` at 50 ms |
| same-scan.csv | Both codes at 40 ms | None |

JSON contains `samples`, `first_fault` (or `null`) and `events`. Each event includes newly raised codes, all currently active codes, the observed snapshot and up to three preceding samples by default. The preceding history excludes the event row. A valid trace exits 0 even if it contains a simulated fault; malformed inputs exit 2 and do not produce a diagnosis.

### Try one change

```sh
python3 diagnose.py examples/feedback-first.csv --timeout-ms 25 --history-scans 1
```

The mismatch starts at 10 ms. The 25 ms delay expires at 35 ms between samples, so the reported timeout is still at 40 ms. The event history contains only the row at 30 ms.

### CSV rules

Use the header `t_ms,run_cmd,run_fb,drive_fault`. Start at zero and include a row every 10 ms, or supply your synthetic grid with `--scan-ms`. Bits must be exactly `0` or `1`. A gap, duplicate, irregular timestamp, malformed row or missing bit invalidates the entire trace. The model does not interpolate missing observations. The timer starts at the first sampled command-without-feedback and resets when the command goes low or feedback is observed. Feedback sampled present at the deadline prevents a timeout in this model.

### Troubleshooting

- “No such file”: move into the extracted folder and check the file is still called `drive-first.csv`, rather than `drive-first.csv.txt`.
- “Expected t_ms”: use the original trace or check the grid and the `--scan-ms` setting. Do not fill lost rows with zeros.
- Both codes on one row: the file cannot establish which happened first. The array order is for display.
- No first fault: the replay never satisfied either detector. A short or badly mapped real trace could still miss a fault.

## Project layout and scope

`diagnose.py` reads and evaluates a trace; `examples/` contains four scenarios. `tests/` includes a 4,096 trace independent oracle and explicit timing and input validation tests. `images/` contains the original figures, editable SVGs and the optional render script. Rebuilding images needs Inkscape on PATH and Pillow installed in a separate Python environment; running the project needs neither.

Real I/O buses, task jitter, PLC alarm retention, sensor filtering and vendor-specific drive fault meanings are not modeled. A first recorded alarm is evidence to investigate, not proof of the physical cause. This is an offline teaching model, not a PLC program, restart procedure, or safety function.
