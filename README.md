<div align="center">

<img src="https://cdn2.steamgriddb.com/hero/7b5ebd860c3b11f9633155a5073a2688.png" alt="The Machine — Game Boy Color" width="100%">

<br>

# The Machine — Language Patcher

**A clean, redistributable ROM patching toolkit for The Machine (Game Boy Color).**  
No ROM included. Bring your own.

<br>

![Python](https://img.shields.io/badge/Python-3.11%2B-5a6af0?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Game%20Boy%20Color-8a2be2?style=flat-square)
![Pack](https://img.shields.io/badge/Included%20pack-PT--BR-2eb88a?style=flat-square)
![Dependencies](https://img.shields.io/badge/Core%20deps-stdlib%20only-f0c040?style=flat-square)
![ROM](https://img.shields.io/badge/ROM-not%20included-c0392b?style=flat-square)

</div>

---

## Overview

This repository provides tooling to apply language patches to the original *The Machine* Game Boy Color ROM. It does **not** distribute the game.

What it ships:

- A runtime-safe ROM patcher with SHA-256 identity verification
- A language-pack validator
- An optional PyBoy-based QA toolkit for maintainers
- A ready-to-use **Brazilian Portuguese** language pack (`langs/ptbr/`)

The patcher verifies the source ROM by SHA-256, size, and internal title before writing a single byte.

---

## Requirements

**Core patcher** — Python standard library only, no extra packages needed:

```
Python 3.11 or newer
The original The Machine GBC ROM (legally obtained)
```

**Optional QA tools:**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-qa.txt
```

---

## Repository Layout

```
patch.py                          Interactive end-user patcher
langs/
  ptbr/
    pack.json                     Brazilian Portuguese language pack
scripts/
  language_pack.py                Pack discovery and validation helpers
  patch_rom.py                    Core ROM patching engine
  validate_language_pack.py       Language-pack validator
  rom_text_codec.py               Font patching and runtime token-expansion logic
  pyboy_smoke_test.py             Optional boot/input automation
  qa_textboxes.py                 Optional dialogue-box boundary QA
```

---

## Quick Start

1. Place your original `.gbc` ROM anywhere on disk.
2. Run the patcher:

```bash
python3 patch.py
```

3. Select a language pack from the interactive list.
4. Enter the path to the original ROM and a destination path.

If the ROM hash matches and the pack validates, a patched `.gbc` file is written.

---

## CLI Reference

**List available language packs:**

```bash
python3 patch.py --list-langs
```

**Patch directly (non-interactive):**

```bash
python3 patch.py \
  --lang   ptbr \
  --rom    /path/to/THEMACHINE.gbc \
  --output /path/to/the_machine_ptbr.gbc \
  --overwrite
```

**Call the core patcher directly:**

```bash
python3 scripts/patch_rom.py \
  --rom    /path/to/THEMACHINE.gbc \
  --pack   langs/ptbr/pack.json \
  --output /path/to/the_machine_ptbr.gbc \
  --overwrite
```

---

## Validating a Language Pack

Structure-only (no ROM required):

```bash
python3 scripts/validate_language_pack.py --pack langs/ptbr/pack.json
```

Full validation against a ROM:

```bash
python3 scripts/validate_language_pack.py \
  --pack langs/ptbr/pack.json \
  --rom  /path/to/THEMACHINE.gbc
```

The validator checks: required metadata fields, duplicate or malformed entries, preserved script tokens, line-count and line-length rules, supported characters for the current font patch, compressed byte budget per string, and source ROM identity.

---

## Creating a New Language Pack

Each pack lives in `langs/<code>/pack.json`. Minimal required shape:

```json
{
  "pack_version": 1,
  "language": {
    "code": "example",
    "name": "Example Language"
  },
  "rom": {
    "title":  "THE MACHINE",
    "sha256": "f6c292282e6a086f803aae5ad96b516fa7bdc4435c7d840d36576bfdaa270575",
    "size":   2097152
  },
  "entries": [
    {
      "id":                 "STR_00002",
      "absolute_offset":    489313,
      "length":             39,
      "line_count":         3,
      "max_line_length":    17,
      "tokens_to_preserve": [],
      "translation":        "Your translated text\\nwith literal breaks\\nhere."
    }
  ]
}
```

> **Notes**
> - `translation` must encode display breaks as literal `\\n`.
> - Every token in `tokens_to_preserve` must remain present in the translated string.
> - The pack must target the exact ROM identified by the SHA-256 above, unless intentionally targeting another revision.
> - To support additional glyphs beyond ASCII + common Latin-1, extend `scripts/rom_text_codec.py`.

---

## Optional Emulator QA

These tools are intended for maintainers preparing or reviewing packs. They require the optional dependencies.

**Boot smoke test:**

```bash
python3 scripts/pyboy_smoke_test.py \
  /path/to/the_machine_ptbr.gbc \
  --output-dir    build/pyboy_smoke \
  --boot-defaults
```

**Textbox boundary QA:**

```bash
python3 scripts/qa_textboxes.py \
  /path/to/the_machine_ptbr.gbc \
  --load-state  /path/to/some.state \
  --output-dir  build/textbox_qa \
  --report      build/textbox_qa/report.json
```

---

## Brazilian Portuguese Pack

The repository ships with `langs/ptbr/pack.json` — the finalised PT-BR pack used to produce the official Brazilian Portuguese build.

---

## Legal

This repository distributes tooling and language-pack data only. You must provide your own legally obtained copy of the original game ROM. The SHA-256 in the pack metadata is used solely to verify that the correct base ROM is being patched.
