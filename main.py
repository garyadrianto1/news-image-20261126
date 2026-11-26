#!/usr/bin/env python3
"""news-image-20261126 entrypoint.

Copies the pre-rendered front page (entry.png, shipped in this
repository) into the output directory the platform provides, then
self-checks the copy: it must be a complete valid PNG, exactly
1024x1024, under one mebibyte. Any failure exits non-zero with a
clear message on stderr.

Stdlib only, no network, deterministic: the output bytes are
identical on every run. Reads no file outside this repository.
"""

import os
import struct
import sys
import zlib

ENTRY = "entry.png"
EXPECTED_WIDTH = 1024
EXPECTED_HEIGHT = 1024
MAX_BYTES = 1024 * 1024


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def png_size(data):
    # IHDR: width and height are the first 8 bytes after the 8-byte
    # signature, the 4-byte chunk length and the 4-byte "IHDR" tag.
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def png_ok(data):
    # Walk the chunks, checking lengths and CRCs, and prove the IDAT
    # payload decompresses to exactly one full RGB frame.
    pos = 8
    seen_iend = False
    idat = bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        end = pos + 8 + length + 4
        if end > len(data):
            return False
        chunk = data[pos + 8:pos + 8 + length]
        crc_stored = struct.unpack(">I", data[pos + 8 + length:end])[0]
        crc = zlib.crc32(ctype)
        crc = zlib.crc32(chunk, crc)
        if crc != crc_stored:
            return False
        if ctype == b"IHDR":
            if length != 13:
                return False
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            seen_iend = True
            if end != len(data):
                return False
            break
        pos = end
    if not seen_iend or not idat:
        return False
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error:
        return False
    width, height = png_size(data)
    # One filter byte plus 3 bytes per pixel (RGB, 8-bit) per scanline.
    if len(raw) != height * (1 + width * 3):
        return False
    return True


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, ENTRY)
    try:
        with open(src, "rb") as f:
            data = f.read()
    except OSError as exc:
        fail(f"cannot read {ENTRY}: {exc}")
    if len(data) > MAX_BYTES:
        fail(f"{ENTRY} is {len(data)} bytes, over the 1 MiB limit")
    if len(data) < 8 or data[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"{ENTRY} is not a PNG file")
    if not png_ok(data):
        fail(f"{ENTRY} failed PNG validation")
    width, height = png_size(data)
    if (width, height) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        fail(f"{ENTRY} is {width}x{height}, expected 1024x1024")
    dst = os.path.join(out_dir, ENTRY)
    try:
        os.makedirs(out_dir, exist_ok=True)
        with open(dst, "wb") as f:
            f.write(data)
    except OSError as exc:
        fail(f"cannot write {dst}: {exc}")
    with open(dst, "rb") as f:
        written = f.read()
    if written != data:
        fail("written output does not match entry.png")
    print(f"wrote {dst} ({len(data)} bytes, {width}x{height})")


if __name__ == "__main__":
    main()
