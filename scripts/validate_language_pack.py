#!/usr/bin/env python3
"""Validate a The Machine language pack, optionally against a specific ROM file."""

from __future__ import annotations

import argparse
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.language_pack import load_json, validate_pack_structure
from scripts.patch_rom import analyze_language_pack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True, help="Path to a language pack JSON file.")
    parser.add_argument(
        "--rom",
        type=Path,
        help="Optional ROM file. When provided, the validator also checks SHA-256, character support, and byte budgets.",
    )
    parser.add_argument("--show", type=int, default=20, help="Maximum issue examples to print.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = load_json(args.pack)
    issues = validate_pack_structure(payload)

    if args.rom and not issues:
        rom_data = args.rom.read_bytes()
        analysis, _ = analyze_language_pack(payload, rom_data)
        issues = analysis.issues

    language = payload.get("language", {})
    entries = payload.get("entries", [])

    print(f"Language: {language.get('name', '<unknown>')} [{language.get('code', '<unknown>')}]")
    print(f"Entries: {len(entries)}")
    print(f"Issues: {len(issues)}")

    for issue in issues[: args.show]:
        print(f"- {issue}")

    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
