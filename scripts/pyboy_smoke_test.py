#!/usr/bin/env python3
"""Run a scripted PyBoy smoke test against a Game Boy / Game Boy Color ROM."""

from __future__ import annotations

import argparse
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
    parser.add_argument("--output-dir", type=Path, default=Path("build/pyboy-smoke"))
    parser.add_argument(
        "--checkpoint",
        action="append",
        type=parse_checkpoint,
        help="Capture screenshot after NAME:FRAMES[:button1,button2]. May be repeated.",
    )
    parser.add_argument("--load-state", type=Path)
    parser.add_argument("--save-state", type=Path)
    parser.add_argument("--window", default="null")
    parser.add_argument("--log-level", default="ERROR")
    parser.add_argument("--boot-defaults", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        from pyboy import PyBoy
    except ModuleNotFoundError as error:
        raise SystemExit(
            "PyBoy is not installed. Create a venv and run `pip install pyboy` first."
        ) from error

    checkpoints = list(args.checkpoint or [])
    if args.boot_defaults and not checkpoints:
        checkpoints = [
            ("boot_600", 600, []),
            ("boot_1200", 600, []),
            ("press_start", 10, ["start"]),
            ("after_start_300", 300, []),
            ("after_start_900", 600, []),
        ]
    if not checkpoints:
        checkpoints = [("boot_600", 600, [])]

    args.output_dir.mkdir(parents=True, exist_ok=True)

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

    try:
        for name, frames, buttons in checkpoints:
            for button in buttons:
                pyboy.button(button)
            pyboy.tick(frames, True, False)
            image = pyboy.screen.image
            if image is None:
                raise SystemExit("PyBoy did not produce a rendered frame for screenshot capture")
            output_path = args.output_dir / f"{name}.png"
            image.save(output_path)
            print(f"{name}: saved {output_path}")

        if args.save_state:
            args.save_state.parent.mkdir(parents=True, exist_ok=True)
            with args.save_state.open("wb") as handle:
                pyboy.save_state(handle)
            print(f"saved state {args.save_state}")
    finally:
        pyboy.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
