#!/usr/bin/env python3
"""Run PyBoy dialogue-box QA and verify rendered text stays inside the window box."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_checkpoint(raw: str) -> tuple[str, int, list[str]]:
    parts = raw.split(":")
    if len(parts) not in {2, 3}:
        raise argparse.ArgumentTypeError(
            "checkpoint must use NAME:FRAMES or NAME:FRAMES:button1,button2"
        )

    name = parts[0].strip()
    if not name:
        raise argparse.ArgumentTypeError("checkpoint name cannot be empty")

    try:
        frames = int(parts[1])
    except ValueError as error:
        raise argparse.ArgumentTypeError("checkpoint frame count must be an integer") from error

    buttons = []
    if len(parts) == 3 and parts[2].strip():
        buttons = [button.strip().lower() for button in parts[2].split(",") if button.strip()]
    return name, frames, buttons


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("build/textbox_qa"))
    parser.add_argument(
        "--checkpoint",
        action="append",
        type=parse_checkpoint,
        help="Capture screenshot after NAME:FRAMES[:button1,button2]. May be repeated.",
    )
    parser.add_argument("--load-state", type=Path)
    parser.add_argument("--window", default="null")
    parser.add_argument("--log-level", default="ERROR")
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--settle-max-frames",
        type=int,
        default=0,
        help="After each checkpoint, keep ticking until the dialogue buffer is stable or this frame cap is reached.",
    )
    parser.add_argument(
        "--settle-stable-frames",
        type=int,
        default=8,
        help="How many consecutive identical dialogue-buffer frames define a stable textbox.",
    )
    return parser


def wait_for_stable_dialogue(pyboy, max_frames: int, stable_frames: int) -> int:
    if max_frames <= 0:
        return 0

    last_snapshot = None
    stable = 0
    elapsed = 0
    while elapsed < max_frames:
        pyboy.tick(1, True, False)
        elapsed += 1
        _, window_position = pyboy.screen.get_tilemap_position()
        top_row = max(0, min(31, window_position[1] // 8))
        rows = range(top_row, min(32, top_row + 4))
        snapshot = tuple(
            pyboy.tilemap_window[x, y]
            for y in rows
            for x in range(20)
        )
        if snapshot == last_snapshot:
            stable += 1
            if stable >= stable_frames:
                break
        else:
            last_snapshot = snapshot
            stable = 1
    return elapsed


def analyze_dialogue_box(image, window_position: tuple[int, int]) -> dict:
    left, top = window_position
    width, height = image.size

    if top >= height:
        return {
            "has_dialogue_box": False,
            "pass": True,
            "skipped": True,
            "reason": "window is off-screen",
        }

    box = {
        "left": max(0, left),
        "top": top,
        "right": width - 1,
        "bottom": min(height - 1, top + 31),
    }
    scan_left = box["left"] + 2
    scan_right = box["right"] - 2
    scan_top = box["top"] + 8
    scan_bottom = box["bottom"] - 2

    pixels = image.convert("RGB").load()
    text_pixels: list[tuple[int, int]] = []
    for y in range(scan_top, scan_bottom + 1):
        for x in range(scan_left, scan_right + 1):
            r, g, b = pixels[x, y]
            if r >= 220 and g >= 220 and b >= 220:
                text_pixels.append((x, y))

    if not text_pixels:
        return {
            "has_dialogue_box": True,
            "pass": True,
            "skipped": True,
            "reason": "dialogue window found but no bright text pixels detected",
            "box": box,
        }

    min_x = min(x for x, _ in text_pixels)
    max_x = max(x for x, _ in text_pixels)
    min_y = min(y for _, y in text_pixels)
    max_y = max(y for _, y in text_pixels)

    inner_left = box["left"] + 2
    inner_right = box["right"] - 2
    inner_top = box["top"] + 2
    inner_bottom = box["bottom"] - 2

    passed = (
        min_x >= inner_left
        and max_x <= inner_right
        and min_y >= inner_top
        and max_y <= inner_bottom
    )

    return {
        "has_dialogue_box": True,
        "pass": passed,
        "skipped": False,
        "box": box,
        "text_bounds": {
            "left": min_x,
            "top": min_y,
            "right": max_x,
            "bottom": max_y,
        },
        "margins": {
            "left": min_x - inner_left,
            "right": inner_right - max_x,
            "top": min_y - inner_top,
            "bottom": inner_bottom - max_y,
        },
    }


def main() -> int:
    args = build_parser().parse_args()

    try:
        from pyboy import PyBoy
    except ModuleNotFoundError as error:
        raise SystemExit(
            "PyBoy is not installed. Create a venv and run `pip install pyboy pillow` first."
        ) from error

    checkpoints = list(args.checkpoint or [])
    if not checkpoints:
        checkpoints = [(f"step{index:02d}", 40, ["a"]) for index in range(1, 41)]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.report or (args.output_dir / "report.json")

    pyboy = PyBoy(
        str(args.rom),
        window=args.window,
        sound_emulated=False,
        log_level=args.log_level,
    )
    pyboy.set_emulation_speed(0)

    if args.load_state:
        with args.load_state.open("rb") as handle:
            pyboy.load_state(handle)

    rows: list[dict] = []
    try:
        for name, frames, buttons in checkpoints:
            for button in buttons:
                pyboy.button(button)
            pyboy.tick(frames, True, False)
            settle_elapsed = wait_for_stable_dialogue(
                pyboy,
                args.settle_max_frames,
                args.settle_stable_frames,
            )

            image = pyboy.screen.image
            if image is None:
                raise SystemExit("PyBoy did not produce a rendered frame for screenshot capture")

            image_path = args.output_dir / f"{name}.png"
            image.save(image_path)

            _, window_position = pyboy.screen.get_tilemap_position()
            analysis = analyze_dialogue_box(image, window_position)
            row = {
                "checkpoint": name,
                "frames": frames,
                "settle_frames": settle_elapsed,
                "buttons": buttons,
                "screenshot": str(image_path),
                "window_position": {"x": window_position[0], "y": window_position[1]},
                **analysis,
            }
            rows.append(row)
            if row.get("skipped"):
                status = "SKIP"
            else:
                status = "PASS" if row["pass"] else "FAIL"
            print(f"{name}: {status} -> {image_path}")
    finally:
        pyboy.stop()

    report = {
        "rom": str(args.rom),
        "checkpoints": rows,
        "dialogue_frames": sum(1 for row in rows if row["has_dialogue_box"] and not row.get("skipped")),
        "all_passed": all(row["pass"] for row in rows if not row.get("skipped")),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report: {report_path}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
