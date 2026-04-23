<div align="center">

<img src="https://cdn2.steamgriddb.com/hero/7b5ebd860c3b11f9633155a5073a2688.png" alt="The Machine — Game Boy Color" width="100%">

<br>

# The Machine — Language Patcher

**A clean, redistributable ROM patching toolkit for _The Machine_ (Game Boy Color).**

Verifies your ROM before touching it. Ships with a Brazilian Portuguese pack ready to use.

<br>

![Python](https://img.shields.io/badge/Python-3.11%2B-5a6af0?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Game%20Boy%20Color-8a2be2?style=flat-square)
![Pack](https://img.shields.io/badge/Included%20pack-PT--BR-2eb88a?style=flat-square)
![Dependencies](https://img.shields.io/badge/Core%20deps-stdlib%20only-f0c040?style=flat-square)
![ROM](https://img.shields.io/badge/ROM-not%20included-c0392b?style=flat-square)

<br>

[Getting started](#getting-started) · [CLI reference](#cli-reference) · [Validation](#validating-a-language-pack) · [New packs](#creating-a-new-language-pack) · [QA tools](#optional-emulator-qa)

</div>

---

<details>
<summary><b>Table of contents</b></summary>

- [Overview](#overview)
- [Requirements](#requirements)
- [Repository layout](#repository-layout)
- [Getting started](#getting-started)
- [CLI reference](#cli-reference)
  - [Options](#options)
- [Validating a language pack](#validating-a-language-pack)
- [Creating a new language pack](#creating-a-new-language-pack)
  - [Pack schema](#pack-schema)
- [Optional emulator QA](#optional-emulator-qa)
- [Brazilian Portuguese pack](#brazilian-portuguese-pack)
- [Legal](#legal)

</details>

---

## Overview

This repository provides tooling to apply language patches to the original *The Machine* Game Boy Color ROM. It ships **tooling and language-pack data only** — the game ROM is not included.

The core patcher verifies the source ROM by SHA-256, internal title, and file size before writing a single byte. If any check fails, the process is aborted with no output written.

**What the toolkit provides:**

| Component | Description |
|---|---|
| `patch.py` | Interactive end-user patcher with automatic pack discovery |
| `scripts/patch_rom.py` | Headless core patching engine |
| `scripts/validate_language_pack.py` | Pack structure and ROM compatibility validator |
| `scripts/language_pack.py` | Pack discovery and resolution helpers |
| `scripts/rom_text_codec.py` | Font patching and runtime token-expansion logic |
| `scripts/pyboy_smoke_test.py` | Optional PyBoy boot and input automation |
| `scripts/qa_textboxes.py` | Optional dialogue-box boundary QA |
| `langs/ptbr/pack.json` | Finalised Brazilian Portuguese language pack |

---

## Requirements

The core patcher uses **only the Python standard library** — no extra packages needed to patch.

```
Python 3.11 or newer
The original The Machine GBC ROM (legally obtained)
```

Optional QA tools require two additional packages:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-qa.txt
# installs: pyboy, pillow
```

> [!NOTE]
> The QA tools are intended for pack maintainers. End users patching a ROM do not need them.

---

## Repository Layout

```
patch.py                          Interactive end-user patcher
langs/
  ptbr/
    pack.json                     Brazilian Portuguese language pack
scripts/
  language_pack.py                Pack discovery and resolution helpers
  patch_rom.py                    Core ROM patching engine
  validate_language_pack.py       Language-pack validator
  rom_text_codec.py               Font patching and runtime token-expansion logic
  pyboy_smoke_test.py             Optional boot/input automation
  qa_textboxes.py                 Optional dialogue-box boundary QA
```

---

## Getting Started

**1.** Place your original `.gbc` ROM anywhere on disk.

**2.** Run the interactive patcher:

```bash
python3 patch.py
```

**3.** Select a language pack from the list. Pack discovery is automatic — any folder under `langs/` containing a valid `pack.json` will appear.

**4.** Enter the path to your original ROM. The default output name is `the_machine_<code>.gbc` in the current directory.

The patcher validates the pack and verifies the ROM before writing. If either check fails, it reports all issues and exits without producing output.

> [!IMPORTANT]
> The patcher only accepts the exact ROM revision identified by the SHA-256 in the pack. Headered, trimmed, or otherwise modified ROMs will be rejected.

---

## CLI Reference

List available language packs without patching:

```bash
python3 patch.py --list-langs
```

Patch non-interactively:

```bash
python3 patch.py \
  --lang   ptbr \
  --rom    /path/to/THEMACHINE.gbc \
  --output /path/to/the_machine_ptbr.gbc \
  --overwrite
```

Call the core engine directly (bypasses interactive prompts):

```bash
python3 scripts/patch_rom.py \
  --rom    /path/to/THEMACHINE.gbc \
  --pack   langs/ptbr/pack.json \
  --output /path/to/the_machine_ptbr.gbc \
  --overwrite
```

### Options

| Flag | Description |
|---|---|
| `--lang <code>` | Language pack code to apply (e.g. `ptbr`). Triggers interactive selection if omitted. |
| `--rom <path>` | Path to the source `.gbc` ROM. Prompted interactively if omitted. |
| `--output <path>` | Output path for the patched ROM. Defaults to `the_machine_<code>.gbc` in the working directory. |
| `--report <path>` | Optional path to write a JSON patch report. |
| `--overwrite` | Allow overwriting an existing output file. Enabled automatically when using the default output name. |
| `--list-langs` | Print all discovered language packs and exit. |

---

## Validating a Language Pack

Structure-only validation (no ROM required):

```bash
python3 scripts/validate_language_pack.py --pack langs/ptbr/pack.json
```

Full validation against a ROM:

```bash
python3 scripts/validate_language_pack.py \
  --pack langs/ptbr/pack.json \
  --rom  /path/to/THEMACHINE.gbc
```

The validator checks all of the following before reporting a result:

- Required metadata fields are present and well-formed
- No duplicate or malformed entry IDs
- All tokens listed in `tokens_to_preserve` are present in the translation
- Line count and per-line length constraints are satisfied
- Every character in the translation is supported by the current font patch
- Compressed byte budget is respected for every string
- Source ROM identity (SHA-256, size, internal title) matches the pack declaration

> [!TIP]
> Run structure-only validation during translation work, and reserve full ROM validation for a final pre-release check.

---

## Creating a New Language Pack

Each pack lives in its own subdirectory under `langs/` and must contain a `pack.json`.

### Pack schema

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

| Field | Description |
|---|---|
| `pack_version` | Must be `1`. |
| `language.code` | Short identifier used as the `--lang` argument and output filename suffix. |
| `rom.sha256` | SHA-256 of the exact ROM revision this pack targets. |
| `rom.size` | Expected ROM size in bytes. |
| `entries[].absolute_offset` | Byte offset in the ROM where this string begins. |
| `entries[].length` | Maximum byte length of the compressed string in ROM. |
| `entries[].line_count` | Number of display lines the textbox allows. |
| `entries[].max_line_length` | Maximum tile-width of a single line. |
| `entries[].tokens_to_preserve` | Script tokens that must remain verbatim in the translation. |
| `entries[].translation` | Translated string. Use literal `\\n` for line breaks. |

> [!WARNING]
> The pack must reference the exact ROM SHA-256 above unless intentionally targeting a different revision. Packs targeting unknown revisions will fail ROM identity validation.

> [!NOTE]
> The current codec supports ASCII plus common Latin-1 accented characters. If your language requires additional glyphs, extend `scripts/rom_text_codec.py` with the necessary tile mappings before running validation.

---

## Optional Emulator QA

These tools automate visual inspection of the patched ROM using PyBoy. They require the optional dependencies from `requirements-qa.txt`.

**Boot smoke test** — launches the ROM and verifies it reaches a playable state:

```bash
python3 scripts/pyboy_smoke_test.py \
  /path/to/the_machine_ptbr.gbc \
  --output-dir    build/pyboy_smoke \
  --boot-defaults
```

**Textbox boundary QA** — loads a save state and checks that translated strings fit within their dialogue boxes:

```bash
python3 scripts/qa_textboxes.py \
  /path/to/the_machine_ptbr.gbc \
  --load-state  /path/to/some.state \
  --output-dir  build/textbox_qa \
  --report      build/textbox_qa/report.json
```

The textbox QA tool writes screenshots and a JSON report for every checked string, making it straightforward to spot overflow without playing through the game manually.

---

## Brazilian Portuguese Pack

The repository ships with `langs/ptbr/pack.json`, the finalised PT-BR pack used to produce the official Brazilian Portuguese build.

---

## Legal

This repository distributes tooling and language-pack data only. You must provide your own legally obtained copy of the original game ROM. The SHA-256 in the pack metadata is used solely for ROM identity verification and is not used to distribute or reproduce the game in any form.
