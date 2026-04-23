#!/usr/bin/env python3
"""Apply a validated language pack to a The Machine Game Boy Color ROM."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.language_pack import (
    BASE_DIR,
    compute_sha256,
    load_json,
    read_internal_rom_title,
    validate_pack_structure,
    validate_translation_content,
)
from scripts.rom_text_codec import RomTextCodec


GLOBAL_CHECKSUM_START = 0x014E
GLOBAL_CHECKSUM_END = 0x014F


@dataclass
class PatchAnalysis:
    patched_entries: int
    issues: list[str]
    language_code: str
    language_name: str
    rom_sha256: str

    @property
    def is_valid(self) -> bool:
        return not self.issues


def update_global_checksum(data: bytearray) -> None:
    checksum = 0
    for index, value in enumerate(data):
        if GLOBAL_CHECKSUM_START <= index <= GLOBAL_CHECKSUM_END:
            continue
        checksum = (checksum + value) & 0xFFFF
    data[GLOBAL_CHECKSUM_START] = (checksum >> 8) & 0xFF
    data[GLOBAL_CHECKSUM_END] = checksum & 0xFF


def analyze_language_pack(payload: dict, rom_data: bytes) -> tuple[PatchAnalysis, RomTextCodec | None]:
    issues = validate_pack_structure(payload)
    language = payload.get("language", {})
    rom_metadata = payload.get("rom", {})
    entries = payload.get("entries", [])

    actual_sha = compute_sha256_bytes(rom_data)
    expected_sha = rom_metadata.get("sha256")
    if expected_sha and actual_sha != expected_sha:
        issues.append(f"base ROM checksum mismatch: expected {expected_sha}, got {actual_sha}")

    expected_size = rom_metadata.get("size")
    if expected_size and len(rom_data) != expected_size:
        issues.append(f"base ROM size mismatch: expected {expected_size}, got {len(rom_data)}")

    expected_title = rom_metadata.get("title")
    if expected_title:
        actual_title = read_internal_rom_title(rom_data)
        if actual_title != expected_title:
            issues.append(f"base ROM title mismatch: expected {expected_title!r}, got {actual_title!r}")

    if issues:
        return (
            PatchAnalysis(
                patched_entries=0,
                issues=issues,
                language_code=str(language.get("code", "")),
                language_name=str(language.get("name", "")),
                rom_sha256=actual_sha,
            ),
            None,
        )

    samples = [(entry["translation"], entry["length"]) for entry in entries]
    try:
        codec = RomTextCodec.build(rom_data, samples)
    except ValueError as error:
        issues.append(str(error))
        codec = None
        return (
            PatchAnalysis(
                patched_entries=0,
                issues=issues,
                language_code=str(language.get("code", "")),
                language_name=str(language.get("name", "")),
                rom_sha256=actual_sha,
            ),
            codec,
        )

    patched = 0
    for entry in entries:
        text = entry["translation"]
        _, _, entry_issues = validate_translation_content(entry, text, require_text=True)
        if entry_issues:
            issues.append(f"{entry['id']}: {'; '.join(entry_issues)}")
            continue

        try:
            encoded = codec.encode_text(text)
        except ValueError as error:
            issues.append(f"{entry['id']}: {error}")
            continue

        if len(encoded) > entry["length"]:
            issues.append(
                f"{entry['id']}: encoded length {len(encoded)} > original length {entry['length']}"
            )
            continue

        patched += 1

    return (
        PatchAnalysis(
            patched_entries=patched,
            issues=issues,
            language_code=str(language.get("code", "")),
            language_name=str(language.get("name", "")),
            rom_sha256=actual_sha,
        ),
        codec,
    )


def compute_sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def patch_language_pack(
    rom_path: Path,
    pack_path: Path,
    output_path: Path,
    *,
    report_path: Path | None = None,
    overwrite: bool = False,
) -> PatchAnalysis:
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing output ROM: {output_path}")

    rom_data = bytearray(rom_path.read_bytes())
    payload = load_json(pack_path)
    analysis, codec = analyze_language_pack(payload, rom_data)
    if not analysis.is_valid or codec is None:
        return analysis

    for entry in payload["entries"]:
        encoded = codec.encode_text(entry["translation"])
        start = entry["absolute_offset"]
        end = start + entry["length"]
        rom_data[start:end] = encoded.ljust(entry["length"], b"\x00")

    codec.patch_font(rom_data)
    codec.patch_runtime(rom_data)
    update_global_checksum(rom_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(rom_data)

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "language": payload["language"],
                    "rom": payload["rom"],
                    "patched_entries": analysis.patched_entries,
                    "issues": analysis.issues,
                    "output_rom": str(output_path),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    return analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True, help="Path to the source .gbc ROM file.")
    parser.add_argument("--pack", type=Path, required=True, help="Path to a language pack JSON file.")
    parser.add_argument("--output", type=Path, required=True, help="Output path for the patched ROM.")
    parser.add_argument("--report", type=Path, help="Optional JSON report path.")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    analysis = patch_language_pack(
        args.rom,
        args.pack,
        args.output,
        report_path=args.report,
        overwrite=args.overwrite,
    )
    if not analysis.is_valid:
        print("Refusing to patch ROM due to validation errors:")
        for issue in analysis.issues[:50]:
            print(f"- {issue}")
        if len(analysis.issues) > 50:
            print(f"- ... {len(analysis.issues) - 50} more")
        return 1

    print(
        f"Patched {analysis.patched_entries} entries "
        f"for {analysis.language_name} into {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
