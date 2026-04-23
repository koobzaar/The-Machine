#!/usr/bin/env python3
"""Interactive patcher for The Machine language packs."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.language_pack import discover_language_packs, resolve_language_pack
from scripts.patch_rom import patch_language_pack


def choose_language() -> str:
    packs = discover_language_packs()
    if not packs:
        raise SystemExit("No language packs were found in ./langs")

    print("Available language packs:")
    for index, pack in enumerate(packs, start=1):
        suffix = f" - {pack.description}" if pack.description else ""
        print(f"  {index}. {pack.name} [{pack.code}]{suffix}")

    while True:
        raw = input("Select a language pack by number or code: ").strip()
        if not raw:
            continue
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(packs):
                return packs[index - 1].code
        else:
            try:
                resolve_language_pack(raw)
                return raw
            except KeyError:
                pass
        print("Invalid selection. Try again.")


def prompt_path(label: str, *, default: Path | None = None) -> Path:
    while True:
        suffix = f" [{default}]" if default else ""
        raw = input(f"{label}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        path = Path(raw).expanduser()
        if path:
            return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", help="Language pack code, such as ptbr.")
    parser.add_argument("--rom", type=Path, help="Path to the source .gbc ROM file.")
    parser.add_argument("--output", type=Path, help="Output path for the patched ROM.")
    parser.add_argument("--report", type=Path, help="Optional JSON report path.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--list-langs", action="store_true", help="List installed language packs and exit.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.list_langs:
        packs = discover_language_packs()
        if not packs:
            print("No language packs were found.")
            return 1
        for pack in packs:
            suffix = f" - {pack.description}" if pack.description else ""
            print(f"{pack.code}: {pack.name}{suffix}")
        return 0

    language_code = args.lang or choose_language()
    pack = resolve_language_pack(language_code)

    rom_path = args.rom or prompt_path("Path to the original The Machine .gbc ROM")
    default_output = Path(f"the_machine_{pack.code}.gbc")
    output_path = args.output or prompt_path("Output ROM path", default=default_output)

    analysis = patch_language_pack(
        rom_path=rom_path,
        pack_path=pack.path,
        output_path=output_path,
        report_path=args.report,
        overwrite=args.overwrite or output_path == default_output,
    )

    if not analysis.is_valid:
        print("Patch failed:")
        for issue in analysis.issues[:50]:
            print(f"- {issue}")
        if len(analysis.issues) > 50:
            print(f"- ... {len(analysis.issues) - 50} more")
        return 1

    print(
        f"Success: patched {analysis.patched_entries} entries "
        f"for {analysis.language_name} into {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
