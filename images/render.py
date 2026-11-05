"""Regenerate editable SVG and WebP figures. Optional: Inkscape and Pillow."""
import html
from pathlib import Path
import subprocess
import sys
import tempfile
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from diagnose import diagnose, read_samples

WIDTH, HEIGHT = 1080, 548
PAPER = "#f5f8f6"
INK = "#162f34"
X0, DX = 246, 116


def label(x, y, value, size=23, color=INK, weight=500, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{html.escape(value)}</text>')


def figure(case, stem, title, subtitle, summary):
    with (HERE.parent / "examples" / (case + ".csv")).open(newline="") as f:
        trace = read_samples(f, 10)
    result = diagnose(trace, 30, 3)
    events = {x["t_ms"]: x["raised"] for x in result["events"]}
    series = [("Run command", [x.run_cmd for x in trace], "#00616a"),
              ("Run feedback", [x.run_fb for x in trace], "#354c83"),
              ("Drive fault", [x.drive_fault for x in trace], "#923e21")]
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" font-family="DejaVu Sans, sans-serif">',
           f'<rect width="{WIDTH}" height="{HEIGHT}" rx="24" fill="{PAPER}"/>',
           label(43, 59, title, 36, weight=700), label(43, 95, subtitle, 22),
           label(43, 124, "Synthetic data  |  10 ms sample interval  |  30 ms feedback window", 20, "#3d5a5d")]
    for i, sample in enumerate(trace):
        x = X0 + i * DX
        svg += [f'<path d="M{x} 155 V395" stroke="#bacac7" stroke-dasharray="4 6"/>',
                label(x, 425, str(sample.t_ms), 21, anchor="middle")]
        if sample.t_ms in events:
            svg += [f'<path d="M{x} 156 V392" stroke="#8b5016" stroke-width="2"/>',
                    f'<circle cx="{x}" cy="151" r="13" fill="#8b5016"/>',
                    label(x, 158, str(list(events).index(sample.t_ms)+1), 18, "#ffffff", 700, "middle")]
    for k, (name, values, color) in enumerate(series):
        y = 208 + k * 79
        svg += [label(43, y-10, name, 21, color, 700), label(224, y-24, "1", 18),
                label(224, y+6, "0", 18)]
        yy = [y - 30 * v for v in values]
        path = f"M{X0} {yy[0]}" + "".join(f" H{X0+DX*i} V{v}" for i, v in enumerate(yy[1:],1)) + " h36"
        svg.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="5" stroke-linejoin="round"/>')
        for i, ypt in enumerate(yy):
            svg.append(f'<circle cx="{X0+DX*i}" cy="{ypt}" r="5" fill="{color}"/>')
    svg += [label(43, 425, "Time (ms)", 22, weight=700),
            '<rect x="43" y="454" width="994" height="65" rx="10" fill="#e7efea"/>',
            label(60, 495, summary, 24, weight=700), "</svg>"]
    dest = HERE / (stem + ".svg")
    dest.write_text("\n".join(svg) + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "trace.png"
        subprocess.run(["inkscape", str(dest), "--export-filename=" + str(png)], check=True)
        with Image.open(png) as image:
            image.save(HERE / (stem + ".webp"), lossless=True, method=6)
            image.resize((600, 304), Image.Resampling.LANCZOS).save(
                HERE / (stem + "-600.webp"), quality=88, method=6)


if __name__ == "__main__":
    figure("drive-first", "plc-diagnostic-first-event", "Keep the first recorded alarm",
           "The drive reports a fault while the feedback timer is still counting.",
           "1  Drive fault at 20 ms.    2  Feedback timeout at 40 ms.")
    figure("same-scan", "plc-diagnostic-same-scan", "Keep both alarms in a tie",
           "The drive fault and feedback timeout first appear in the same row.",
           "1  Both alarms observed at 40 ms. Their order is unknown.")
