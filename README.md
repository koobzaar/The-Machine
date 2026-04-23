# The Machine Language Patcher

This repository contains a clean, redistributable patching tool for **The Machine** (Game Boy Color).

It does **not** include the original game ROM. Instead, it provides:

- a runtime-safe ROM patcher;
- a language-pack validator;
- an optional PyBoy-based QA toolkit;
- a ready-to-use **Brazilian Portuguese** language pack in `langs/ptbr/`.

The patcher verifies the source ROM SHA-256 before it writes anything, so it only patches the correct base game.

## Features

- Interactive patching workflow with automatic language-pack discovery.
- Strict ROM identity check by SHA-256, size, and internal title.
- Automatic token compression in ROM and runtime token expansion in the game engine.
- Custom font patching for accented Latin characters.
- Validation before patching: line counts, line lengths, preserved tokens, supported characters, and byte budget.
- Optional emulator automation for smoke tests and textbox-boundary checks.

## Requirements

- Python 3.11 or newer.
- The original `The Machine` Game Boy Color ROM.

The core patcher uses only the Python standard library.

Optional QA tools require:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-qa.txt
```

## Repository Layout

```text
patch.py                         Interactive end-user patcher
langs/
  ptbr/
    pack.json                    Brazilian Portuguese language pack
scripts/
  language_pack.py               Pack discovery and validation helpers
  patch_rom.py                   Core ROM patching engine
  validate_language_pack.py      Language-pack validator
  rom_text_codec.py              Font patching and runtime token-expansion logic
  pyboy_smoke_test.py            Optional boot/input automation
  qa_textboxes.py                Optional dialogue-box boundary QA
```

## Quick Start

1. Place your original ROM anywhere on disk.
2. Run the patcher:

```bash
python3 patch.py
```

3. Select a language pack.
4. Enter the path to your original `.gbc` file.
5. Choose the output path.

If the ROM hash matches and the pack validates, the patcher writes a new playable `.gbc` file.

## Non-Interactive Usage

List available packs:

```bash
python3 patch.py --list-langs
```

Patch directly:

```bash
python3 patch.py \
  --lang ptbr \
  --rom /path/to/THEMACHINE.gbc \
  --output /path/to/the_machine_ptbr.gbc \
  --overwrite
```

You can also call the core patcher directly:

```bash
python3 scripts/patch_rom.py \
  --rom /path/to/THEMACHINE.gbc \
  --pack langs/ptbr/pack.json \
  --output /path/to/the_machine_ptbr.gbc \
  --overwrite
```

## Validate a Language Pack

Structure-only validation:

```bash
python3 scripts/validate_language_pack.py --pack langs/ptbr/pack.json
```

Full validation against a ROM:

```bash
python3 scripts/validate_language_pack.py \
  --pack langs/ptbr/pack.json \
  --rom /path/to/THEMACHINE.gbc
```

This checks:

- required metadata fields;
- duplicate or malformed entries;
- preserved script tokens;
- line-count and line-length rules;
- supported characters for the current font patch;
- compressed byte budget for every string;
- source ROM identity.

## Creating a New Language Pack

Each pack lives in its own folder under `langs/` and must contain a `pack.json`.

Minimal shape:

```json
{
  "pack_version": 1,
  "language": {
    "code": "example",
    "name": "Example Language"
  },
  "rom": {
    "title": "THE MACHINE",
    "sha256": "f6c292282e6a086f803aae5ad96b516fa7bdc4435c7d840d36576bfdaa270575",
    "size": 2097152
  },
  "entries": [
    {
      "id": "STR_00002",
      "absolute_offset": 489313,
      "length": 39,
      "line_count": 3,
      "max_line_length": 17,
      "tokens_to_preserve": [],
      "translation": "Your translated text\\nwith literal breaks\\nhere."
    }
  ]
}
```

Notes:

- `translation` must keep display breaks as literal `\\n`.
- `tokens_to_preserve` must remain present in the translated line when used.
- The pack must target the exact ROM identified by the SHA-256 above, unless you intentionally build a pack for another revision.
- The current codec is designed for ASCII plus common Latin-1 accented characters. If your language needs more glyphs, extend `scripts/rom_text_codec.py`.

## Optional Emulator QA

Boot smoke test:

```bash
python3 scripts/pyboy_smoke_test.py \
  /path/to/the_machine_ptbr.gbc \
  --output-dir build/pyboy_smoke \
  --boot-defaults
```

Textbox boundary QA:

```bash
python3 scripts/qa_textboxes.py \
  /path/to/the_machine_ptbr.gbc \
  --load-state /path/to/some.state \
  --output-dir build/textbox_qa \
  --report build/textbox_qa/report.json
```

These QA helpers are optional and are meant for maintainers preparing or reviewing language packs.

## Brazilian Portuguese Pack

The repository ships with:

- `langs/ptbr/pack.json`

This is the finalized Brazilian Portuguese patch pack used to produce the PT-BR build.

## Legal Note

This repository distributes tooling and language-pack data only.

You must provide your own legally obtained copy of the original game ROM.
