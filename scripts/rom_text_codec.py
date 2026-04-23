#!/usr/bin/env python3
"""Custom text codec and runtime token expansion helpers for The Machine."""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


FONT_BASE_OFFSET = 0x17E00
NEWLINE_BYTE = 0x0A
TOKEN_EXPAND_JP_OFFSET = 0x2E3F
TOKEN_EXPAND_ROUTINE_ADDR = 0x3722

TEXT_NORMALIZATION = str.maketrans(
    {
        "…": "...",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "\u00A0": " ",
    }
)

MAX_PATTERN_LENGTH = 8
MAX_PATTERN_CANDIDATES = 2048

ACCENTED_GLYPHS = {
    "á": ("a", "acute"),
    "à": ("a", "grave"),
    "â": ("a", "circumflex"),
    "ã": ("a", "tilde"),
    "é": ("e", "acute"),
    "è": ("e", "grave"),
    "ê": ("e", "circumflex"),
    "ë": ("e", "diaeresis"),
    "í": ("i", "acute"),
    "ì": ("i", "grave"),
    "ï": ("i", "diaeresis"),
    "ó": ("o", "acute"),
    "ò": ("o", "grave"),
    "ô": ("o", "circumflex"),
    "õ": ("o", "tilde"),
    "ö": ("o", "diaeresis"),
    "ú": ("u", "acute"),
    "ù": ("u", "grave"),
    "ü": ("u", "diaeresis"),
    "ä": ("a", "diaeresis"),
    "ñ": ("n", "tilde"),
    "ç": ("c", "cedilla"),
    "Á": ("A", "acute"),
    "À": ("A", "grave"),
    "Â": ("A", "circumflex"),
    "Ã": ("A", "tilde"),
    "É": ("E", "acute"),
    "È": ("E", "grave"),
    "Ê": ("E", "circumflex"),
    "Ë": ("E", "diaeresis"),
    "Í": ("I", "acute"),
    "Ì": ("I", "grave"),
    "Ï": ("I", "diaeresis"),
    "Ó": ("O", "acute"),
    "Ò": ("O", "grave"),
    "Ô": ("O", "circumflex"),
    "Õ": ("O", "tilde"),
    "Ö": ("O", "diaeresis"),
    "Ú": ("U", "acute"),
    "Ù": ("U", "grave"),
    "Ü": ("U", "diaeresis"),
    "Ä": ("A", "diaeresis"),
    "Ñ": ("N", "tilde"),
    "Ç": ("C", "cedilla"),
    "ª": ("a", "ordinal"),
    "º": ("o", "ordinal"),
}

SPACE_WIDTH = 2
PLACEHOLDER_BASE = 0xE000


class AsmBuilder:
    def __init__(self, base_addr: int) -> None:
        self.base_addr = base_addr
        self.buffer = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str, str]] = []

    def mark(self, name: str) -> None:
        self.labels[name] = len(self.buffer)

    def emit(self, *values: int) -> None:
        self.buffer.extend(values)

    def emit_word(self, value: int) -> None:
        self.buffer.extend((value & 0xFF, (value >> 8) & 0xFF))

    def emit_word_ref(self, label: str) -> None:
        self.fixups.append((len(self.buffer), label, "word"))
        self.buffer.extend((0x00, 0x00))

    def emit_jr(self, opcode: int, label: str) -> None:
        self.buffer.append(opcode)
        self.fixups.append((len(self.buffer), label, "jr"))
        self.buffer.append(0x00)

    def build(self) -> bytes:
        output = bytearray(self.buffer)
        for position, label, kind in self.fixups:
            target = self.base_addr + self.labels[label]
            if kind == "word":
                output[position] = target & 0xFF
                output[position + 1] = (target >> 8) & 0xFF
                continue
            if kind == "jr":
                current = self.base_addr + position + 1
                delta = target - current
                if not -128 <= delta <= 127:
                    raise ValueError(f"JR target out of range for {label}: {delta}")
                output[position] = delta & 0xFF
                continue
            raise ValueError(f"Unsupported fixup kind: {kind}")
        return bytes(output)


def normalize_rom_text(text: str) -> str:
    return text.translate(TEXT_NORMALIZATION)


def ascii_fold_rom_text(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return folded.replace("ª", "a").replace("º", "o")


def decode_glyph(raw: bytes) -> list[list[int]]:
    mask = [[0] * 8 for _ in range(8)]
    for row in range(8):
        bits = (~raw[row * 2]) & 0xFF
        for col in range(8):
            mask[row][col] = 1 if bits & (1 << (7 - col)) else 0
    return mask


def encode_glyph(mask: list[list[int]]) -> bytes:
    data = bytearray()
    for row in mask:
        bits = 0
        for col, value in enumerate(row[:8]):
            if value:
                bits |= 1 << (7 - col)
        stored = (~bits) & 0xFF
        data.extend((stored, stored))
    return bytes(data)


def empty_mask(width: int = 8) -> list[list[int]]:
    return [[0] * width for _ in range(8)]


def copy_mask(mask: list[list[int]]) -> list[list[int]]:
    return [row[:] for row in mask]


def shift_down(mask: list[list[int]], rows: int) -> list[list[int]]:
    shifted = empty_mask()
    for y in range(7, -1, -1):
        src = y - rows
        if src < 0:
            continue
        shifted[y] = mask[src][:]
    return shifted


def overlay(base: list[list[int]], extra: list[list[int]]) -> list[list[int]]:
    merged = copy_mask(base)
    for y in range(8):
        for x in range(8):
            merged[y][x] = 1 if base[y][x] or extra[y][x] else 0
    return merged


def crop_mask(mask: list[list[int]]) -> list[list[int]]:
    cols = [index for index in range(len(mask[0])) if any(row[index] for row in mask)]
    if not cols:
        return empty_mask(0)
    left = cols[0]
    right = cols[-1] + 1
    return [row[left:right] for row in mask]


def scale_width(mask: list[list[int]], width: int) -> list[list[int]]:
    src_width = len(mask[0])
    if src_width == width:
        return copy_mask(mask)
    if src_width == 0:
        return empty_mask(width)
    scaled = empty_mask(width)
    for y in range(8):
        for x in range(width):
            src_x = min(src_width - 1, int(x * src_width / width))
            scaled[y][x] = mask[y][src_x]
    return scaled


def pad_to_width(mask: list[list[int]], width: int) -> list[list[int]]:
    current = len(mask[0])
    if current >= width:
        return copy_mask(mask)
    left = (width - current) // 2
    padded = empty_mask(width)
    for y in range(8):
        for x in range(current):
            padded[y][left + x] = mask[y][x]
    return padded


def space_piece() -> list[list[int]]:
    return empty_mask(SPACE_WIDTH)


def horizontal_concat(parts: list[tuple[list[list[int]], bool]]) -> list[list[int]]:
    width = 0
    last_was_space = True
    for mask, is_space in parts:
        if width and not last_was_space and not is_space:
            width += 1
        width += len(mask[0])
        last_was_space = is_space

    canvas = empty_mask(width)
    offset = 0
    last_was_space = True
    for mask, is_space in parts:
        if offset and not last_was_space and not is_space:
            offset += 1
        piece_width = len(mask[0])
        for y in range(8):
            for x in range(piece_width):
                canvas[y][offset + x] = mask[y][x]
        offset += piece_width
        last_was_space = is_space
    return canvas


def acute_mask() -> list[list[int]]:
    mask = empty_mask()
    for y, x in ((0, 5), (1, 4), (2, 3)):
        mask[y][x] = 1
    return mask


def grave_mask() -> list[list[int]]:
    mask = empty_mask()
    for y, x in ((0, 3), (1, 4), (2, 5)):
        mask[y][x] = 1
    return mask


def circumflex_mask() -> list[list[int]]:
    return [
        [0, 0, 0, 0, 1, 0, 0, 0],
        [0, 0, 0, 1, 0, 1, 0, 0],
        [0, 0, 1, 0, 0, 0, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ]


def tilde_mask() -> list[list[int]]:
    return [
        [0, 0, 1, 1, 0, 1, 1, 0],
        [0, 1, 1, 0, 1, 1, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ]


def diaeresis_mask() -> list[list[int]]:
    mask = empty_mask()
    for y, x in ((0, 2), (0, 5), (1, 2), (1, 5)):
        mask[y][x] = 1
    return mask


def cedilla_mask() -> list[list[int]]:
    mask = empty_mask()
    for y, x in ((6, 4), (7, 3)):
        mask[y][x] = 1
    return mask


def ordinal_mask(base_mask: list[list[int]]) -> list[list[int]]:
    cropped = crop_mask(base_mask)
    width = min(5, max(3, len(cropped[0])))
    scaled = scale_width(cropped, width)
    small = empty_mask()
    for y in range(5):
        src_y = min(7, int(y * 8 / 5))
        for x in range(width):
            small[y][x + 1] = scaled[src_y][x]
    return small


def synthesize_accented(base_mask: list[list[int]], accent: str, uppercase: bool) -> list[list[int]]:
    working = shift_down(base_mask, 1) if uppercase and accent != "cedilla" else copy_mask(base_mask)
    if accent == "acute":
        return overlay(working, acute_mask())
    if accent == "grave":
        return overlay(working, grave_mask())
    if accent == "circumflex":
        return overlay(working, circumflex_mask())
    if accent == "tilde":
        return overlay(working, tilde_mask())
    if accent == "diaeresis":
        return overlay(working, diaeresis_mask())
    if accent == "cedilla":
        return overlay(working, cedilla_mask())
    if accent == "ordinal":
        return ordinal_mask(base_mask)
    raise ValueError(f"Unsupported accent style: {accent}")


def visible_characters(texts: Iterable[str], ascii_fold: bool) -> set[str]:
    chars: set[str] = set()
    for text in texts:
        display = normalize_rom_text(text).replace("\\n", "\n")
        if ascii_fold:
            display = ascii_fold_rom_text(display)
        chars.update(ch for ch in display if ch not in {"\n", "\x00"})
    return chars


def normalize_display_text(text: str, ascii_fold: bool) -> str:
    display = normalize_rom_text(text).replace("\\n", "\n")
    if ascii_fold:
        display = ascii_fold_rom_text(display)
    return display


def collect_pattern_candidates(texts: list[str]) -> list[str]:
    scores: Counter[str] = Counter()
    frequencies: Counter[str] = Counter()

    for text in texts:
        for length in range(2, MAX_PATTERN_LENGTH + 1):
            for index in range(0, len(text) - length + 1):
                pattern = text[index : index + length]
                if "\n" in pattern or "$" in pattern or "\x00" in pattern:
                    continue
                scores[pattern] += length - 1
                frequencies[pattern] += 1

    ranked = sorted(
        (
            (pattern, score, frequencies[pattern])
            for pattern, score in scores.items()
            if frequencies[pattern] >= 2
        ),
        key=lambda row: (-row[1], -row[2], -len(row[0]), row[0]),
    )
    return [pattern for pattern, _, _ in ranked[:MAX_PATTERN_CANDIDATES]]


def encoded_length_with_patterns(text: str, patterns: list[str]) -> int:
    encoded = text
    for pattern in sorted(patterns, key=len, reverse=True):
        encoded = encoded.replace(pattern, "#")
    return len(encoded)


def select_runtime_patterns(entries: list[tuple[str, int]], max_patterns: int) -> list[str]:
    texts = [text for text, _ in entries]
    candidates = collect_pattern_candidates(texts)
    if not candidates or max_patterns <= 0:
        return []

    selected = candidates[: min(16, max_patterns)]
    remaining = [pattern for pattern in candidates if pattern not in selected]
    remaining_set = set(remaining)

    while len(selected) < max_patterns:
        overflows: list[tuple[str, int, int]] = []
        for text, limit in entries:
            current_length = encoded_length_with_patterns(text, selected)
            if current_length > limit:
                overflows.append((text, limit, current_length))
        if not overflows:
            break

        overflow_candidates = collect_pattern_candidates([text for text, _, _ in overflows])
        for pattern in overflow_candidates:
            if pattern in selected or pattern in remaining_set:
                continue
            remaining.append(pattern)
            remaining_set.add(pattern)

        best_pattern = None
        best_score = None
        for pattern in remaining:
            total_gain = 0
            overflow_gain = 0
            for text, limit, current_length in overflows:
                new_length = encoded_length_with_patterns(text, selected + [pattern])
                gain = current_length - new_length
                if gain <= 0:
                    continue
                total_gain += gain
                overflow_gain += min(current_length - limit, gain)

            if overflow_gain <= 0:
                continue

            score = (overflow_gain, total_gain, len(pattern))
            if best_score is None or score > best_score:
                best_score = score
                best_pattern = pattern

        if best_pattern is None:
            break

        selected.append(best_pattern)
        remaining.remove(best_pattern)
        remaining_set.remove(best_pattern)

    return selected


def build_single_masks(rom_data: bytes, chars: set[str]) -> dict[str, list[list[int]]]:
    masks: dict[str, list[list[int]]] = {}
    for ch in sorted(chars):
        code = ord(ch)
        if code < 128:
            offset = FONT_BASE_OFFSET + code * 16
            masks[ch] = decode_glyph(rom_data[offset : offset + 16])
            continue
        if ch not in ACCENTED_GLYPHS:
            raise ValueError(f"Unsupported non-ASCII glyph in translation corpus: {ch!r}")
        base_char, accent = ACCENTED_GLYPHS[ch]
        if base_char not in masks:
            base_code = ord(base_char)
            offset = FONT_BASE_OFFSET + base_code * 16
            masks[base_char] = decode_glyph(rom_data[offset : offset + 16])
        masks[ch] = synthesize_accented(masks[base_char], accent, base_char.isupper())
    return masks


def compose_pattern_mask(pattern: str, glyph_masks: dict[str, list[list[int]]]) -> list[list[int]]:
    parts: list[tuple[list[list[int]], bool]] = []
    for ch in pattern:
        if ch == " ":
            parts.append((space_piece(), True))
            continue
        piece = crop_mask(glyph_masks[ch])
        parts.append((piece, False))
    merged = horizontal_concat(parts)
    if len(merged[0]) > 8:
        merged = scale_width(merged, 8)
    elif len(merged[0]) < 8:
        merged = pad_to_width(merged, 8)
    return merged


def assemble_token_expander(
    base_addr: int,
    token_code_to_bytes: dict[int, bytes],
) -> bytes:
    builder = AsmBuilder(base_addr)

    builder.mark("start")
    builder.emit(0xF8, 0x02)  # ld hl, sp+2
    builder.emit(0x2A)  # ld a, (hl+)
    builder.emit(0x5F)  # ld e, a
    builder.emit(0x56)  # ld d, (hl)

    builder.mark("scan_dest")
    builder.emit(0x1A)  # ld a, (de)
    builder.emit(0xB7)  # or a
    builder.emit_jr(0x28, "load_source")  # jr z, load_source
    builder.emit(0x13)  # inc de
    builder.emit_jr(0x18, "scan_dest")  # jr scan_dest

    builder.mark("load_source")
    builder.emit(0xF8, 0x04)  # ld hl, sp+4
    builder.emit(0x2A)  # ld a, (hl+)
    builder.emit(0x66)  # ld h, (hl)
    builder.emit(0x6F)  # ld l, a

    builder.mark("copy_loop")
    builder.emit(0x2A)  # ld a, (hl+)
    builder.emit(0xB7)  # or a
    builder.emit_jr(0x28, "finish")  # jr z, finish
    builder.emit(0xFE, 0x80)  # cp $80
    builder.emit_jr(0x38, "literal")  # jr c, literal
    builder.emit(0xE5)  # push hl
    builder.emit(0xF5)  # push af
    builder.emit(0xD6, 0x80)  # sub $80
    builder.emit(0x87)  # add a, a
    builder.emit(0x4F)  # ld c, a
    builder.emit(0x06, 0x00)  # ld b, $00
    builder.emit(0x21)  # ld hl, table
    builder.emit_word_ref("table")
    builder.emit(0x09)  # add hl, bc
    builder.emit(0x2A)  # ld a, (hl+)
    builder.emit(0x66)  # ld h, (hl)
    builder.emit(0x6F)  # ld l, a
    builder.emit(0x7C)  # ld a, h
    builder.emit(0xB5)  # or l
    builder.emit_jr(0x28, "token_as_literal")  # jr z, token_as_literal
    builder.emit(0xF1)  # pop af

    builder.mark("token_loop")
    builder.emit(0x2A)  # ld a, (hl+)
    builder.emit(0xB7)  # or a
    builder.emit_jr(0x28, "token_done")  # jr z, token_done
    builder.emit(0x12)  # ld (de), a
    builder.emit(0x13)  # inc de
    builder.emit_jr(0x18, "token_loop")  # jr token_loop

    builder.mark("token_done")
    builder.emit(0xE1)  # pop hl
    builder.emit_jr(0x18, "copy_loop")  # jr copy_loop

    builder.mark("token_as_literal")
    builder.emit(0xF1)  # pop af
    builder.emit(0xE1)  # pop hl

    builder.mark("literal")
    builder.emit(0x12)  # ld (de), a
    builder.emit(0x13)  # inc de
    builder.emit_jr(0x18, "copy_loop")  # jr copy_loop

    builder.mark("finish")
    builder.emit(0x12)  # ld (de), a
    builder.emit(0xC9)  # ret

    builder.mark("table")
    for code in range(0x80, 0x100):
        pattern = token_code_to_bytes.get(code)
        if pattern is None:
            builder.emit_word(0x0000)
            continue
        builder.emit_word_ref(f"pattern_{code:02X}")

    for code, pattern_bytes in sorted(token_code_to_bytes.items()):
        builder.mark(f"pattern_{code:02X}")
        builder.buffer.extend(pattern_bytes)
        builder.emit(0x00)

    return builder.build()


@dataclass
class RomTextCodec:
    char_to_code: dict[str, int]
    placeholder_to_code: dict[str, int]
    glyph_patches: dict[int, bytes]
    runtime_patch: bytes
    ordered_patterns: list[str]
    ordered_pattern_placeholders: list[tuple[str, str]]

    @classmethod
    def build(
        cls,
        rom_data: bytes,
        entries: Iterable[tuple[str, int]],
        *,
        ascii_fold: bool = False,
    ) -> "RomTextCodec":
        materialized_entries = list(entries)
        texts = [text for text, _ in materialized_entries]
        chars = visible_characters(texts, ascii_fold)
        glyph_masks = build_single_masks(rom_data, chars)

        char_to_code: dict[str, int] = {}
        used_codes: set[int] = {0x00, NEWLINE_BYTE}
        for ch in sorted(chars):
            code = ord(ch)
            if code > 0xFF:
                raise ValueError(f"Character outside single-byte range: {ch!r}")
            char_to_code[ch] = code
            used_codes.add(code)

        pattern_codes = [
            code
            for code in range(0x80, 0x100)
            if code not in used_codes
        ]
        normalized_entries = [
            (normalize_display_text(text, ascii_fold), limit)
            for text, limit in materialized_entries
        ]
        selected_patterns = select_runtime_patterns(normalized_entries, len(pattern_codes))

        placeholder_to_code: dict[str, int] = {}
        glyph_patches: dict[int, bytes] = {}
        token_code_to_pattern: dict[int, str] = {}

        for index, pattern in enumerate(selected_patterns):
            code = pattern_codes[index]
            placeholder = chr(PLACEHOLDER_BASE + index)
            placeholder_to_code[placeholder] = code
            token_code_to_pattern[code] = pattern
            glyph_patches[code] = encode_glyph(compose_pattern_mask(pattern, glyph_masks))

        for ch, code in char_to_code.items():
            if code >= 0x80:
                glyph_patches[code] = encode_glyph(glyph_masks[ch])

        token_code_to_bytes = {
            code: bytes(char_to_code[ch] for ch in pattern)
            for code, pattern in token_code_to_pattern.items()
        }
        runtime_patch = assemble_token_expander(
            TOKEN_EXPAND_ROUTINE_ADDR,
            token_code_to_bytes,
        )

        ordered_patterns = sorted(selected_patterns, key=len, reverse=True)
        ordered_pattern_placeholders = [
            (pattern, chr(PLACEHOLDER_BASE + selected_patterns.index(pattern)))
            for pattern in ordered_patterns
        ]
        return cls(
            char_to_code=char_to_code,
            placeholder_to_code=placeholder_to_code,
            glyph_patches=glyph_patches,
            runtime_patch=runtime_patch,
            ordered_patterns=ordered_patterns,
            ordered_pattern_placeholders=ordered_pattern_placeholders,
        )

    def encode_text(self, text: str, *, ascii_fold: bool = False) -> bytes:
        display = normalize_rom_text(text).replace("\\n", "\n")
        if ascii_fold:
            display = ascii_fold_rom_text(display)

        encoded = display
        for pattern, placeholder in self.ordered_pattern_placeholders:
            encoded = encoded.replace(pattern, placeholder)

        output = bytearray()
        for ch in encoded:
            if ch == "\n":
                output.append(NEWLINE_BYTE)
                continue
            if ch in self.placeholder_to_code:
                output.append(self.placeholder_to_code[ch])
                continue
            try:
                output.append(self.char_to_code[ch])
            except KeyError as error:
                raise ValueError(f"Unsupported character after codec normalization: {ch!r}") from error
        return bytes(output)

    def patch_font(self, rom_data: bytearray) -> None:
        for code, glyph in self.glyph_patches.items():
            start = FONT_BASE_OFFSET + code * 16
            rom_data[start : start + 16] = glyph

    def patch_runtime(self, rom_data: bytearray) -> None:
        rom_data[TOKEN_EXPAND_JP_OFFSET : TOKEN_EXPAND_JP_OFFSET + 3] = bytes(
            (
                0xC3,
                TOKEN_EXPAND_ROUTINE_ADDR & 0xFF,
                (TOKEN_EXPAND_ROUTINE_ADDR >> 8) & 0xFF,
            )
        )
        start = TOKEN_EXPAND_ROUTINE_ADDR
        rom_data[start : start + len(self.runtime_patch)] = self.runtime_patch
