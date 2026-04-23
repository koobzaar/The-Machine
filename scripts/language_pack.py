#!/usr/bin/env python3
"""Helpers for discovering, validating, and loading language packs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
LANGS_DIR = BASE_DIR / "langs"
PACK_FILENAME = "pack.json"
ROM_TITLE_OFFSET = 0x0134
ROM_TITLE_LENGTH = 16


@dataclass(frozen=True)
class LanguagePackInfo:
    code: str
    name: str
    path: Path
    description: str
    author: str


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_translation_text(text: str) -> str:
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "\\n")


def split_translation_text(text: str) -> list[str]:
    normalized = normalize_translation_text(text)
    if not normalized:
        return []
    return normalized.split("\\n")


def validate_translation_content(entry: dict, text: str, require_text: bool) -> tuple[str, list[str], list[str]]:
    normalized = normalize_translation_text(text)
    lines = split_translation_text(normalized)
    issues: list[str] = []

    if require_text and not normalized:
        issues.append("empty translated text")

    if normalized and len(lines) != entry["line_count"]:
        issues.append(f"line count {len(lines)} != {entry['line_count']}")

    if normalized:
        for index, line in enumerate(lines, start=1):
            if len(line) > entry["max_line_length"]:
                issues.append(f"line {index} length {len(line)} > {entry['max_line_length']}")

    missing_tokens = [
        token
        for token in entry.get("tokens_to_preserve", [])
        if normalized and token not in normalized
    ]
    if missing_tokens:
        issues.append("missing tokens: " + ", ".join(missing_tokens))

    return normalized, lines, issues


def validate_pack_structure(payload: dict) -> list[str]:
    issues: list[str] = []

    if not isinstance(payload, dict):
        return ["pack root must be a JSON object"]

    required_top_level = {"pack_version", "language", "rom", "entries"}
    missing_top_level = sorted(required_top_level - set(payload))
    if missing_top_level:
        issues.append("missing top-level keys: " + ", ".join(missing_top_level))
        return issues

    language = payload["language"]
    rom = payload["rom"]
    entries = payload["entries"]

    if not isinstance(language, dict):
        issues.append("language must be an object")
    else:
        for field in ("code", "name"):
            value = language.get(field, "")
            if not isinstance(value, str) or not value.strip():
                issues.append(f"language.{field} must be a non-empty string")

    if not isinstance(rom, dict):
        issues.append("rom must be an object")
    else:
        sha256 = rom.get("sha256", "")
        if not isinstance(sha256, str) or len(sha256) != 64:
            issues.append("rom.sha256 must be a 64-character SHA-256 string")
        if "size" in rom and (not isinstance(rom["size"], int) or rom["size"] <= 0):
            issues.append("rom.size must be a positive integer when present")

    if not isinstance(entries, list) or not entries:
        issues.append("entries must be a non-empty list")
        return issues

    seen_ids: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        prefix = f"entries[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{prefix} must be an object")
            continue

        for field in ("id", "absolute_offset", "length", "line_count", "max_line_length", "translation"):
            if field not in entry:
                issues.append(f"{prefix} missing {field}")

        entry_id = entry.get("id")
        if isinstance(entry_id, str):
            if entry_id in seen_ids:
                issues.append(f"duplicate entry id: {entry_id}")
            seen_ids.add(entry_id)
        else:
            issues.append(f"{prefix}.id must be a string")

        for field in ("absolute_offset", "length", "line_count", "max_line_length"):
            value = entry.get(field)
            if not isinstance(value, int) or value < 0:
                issues.append(f"{prefix}.{field} must be a non-negative integer")

        translation = entry.get("translation")
        if not isinstance(translation, str):
            issues.append(f"{prefix}.translation must be a string")

        tokens = entry.get("tokens_to_preserve", [])
        if tokens and not (
            isinstance(tokens, list)
            and all(isinstance(token, str) for token in tokens)
        ):
            issues.append(f"{prefix}.tokens_to_preserve must be a list of strings")

    return issues


def discover_language_packs(langs_dir: Path = LANGS_DIR) -> list[LanguagePackInfo]:
    packs: list[LanguagePackInfo] = []
    if not langs_dir.exists():
        return packs

    for directory in sorted(path for path in langs_dir.iterdir() if path.is_dir()):
        pack_path = directory / PACK_FILENAME
        if not pack_path.exists():
            continue
        payload = load_json(pack_path)
        language = payload.get("language", {})
        packs.append(
            LanguagePackInfo(
                code=str(language.get("code", directory.name)),
                name=str(language.get("name", directory.name)),
                path=pack_path,
                description=str(language.get("description", "")),
                author=str(language.get("author", "")),
            )
        )
    return packs


def resolve_language_pack(identifier: str, langs_dir: Path = LANGS_DIR) -> LanguagePackInfo:
    normalized = identifier.strip().lower()
    for pack in discover_language_packs(langs_dir):
        if pack.code.lower() == normalized or pack.path.parent.name.lower() == normalized:
            return pack
    raise KeyError(f"Unknown language pack: {identifier}")


def read_internal_rom_title(rom_data: bytes) -> str:
    raw = rom_data[ROM_TITLE_OFFSET : ROM_TITLE_OFFSET + ROM_TITLE_LENGTH]
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
