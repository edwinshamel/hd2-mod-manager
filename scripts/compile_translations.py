#!/usr/bin/env python3
"""
compile_translations.py
Pure-Python .po -> .mo compiler. No gettext CLI required.
Usage: python3 scripts/compile_translations.py [locale_dir]
"""
import struct, os, sys, codecs


def unescape(s):
    """Unescape a PO quoted string value (handles \\n, \\t, \\\\, etc.)."""
    try:
        return codecs.decode(s.encode("utf-8"), "unicode_escape").encode("latin-1").decode("utf-8")
    except Exception:
        return s


def parse_po(po_path):
    """Parse a .po file; returns list of (msgid_bytes, msgstr_bytes)."""
    entries = []
    msgid = None
    msgstr = None
    state = None  # "id" | "str" | None

    def flush():
        nonlocal msgid, msgstr, state
        if msgid is not None and msgstr is not None:
            mid = msgid.encode("utf-8")
            mst = msgstr.encode("utf-8")
            if mst or msgid == "":  # always include metadata (msgid="")
                entries.append((mid, mst))
        msgid = None
        msgstr = None
        state = None

    with open(po_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")

            if line.strip() == "" or line.startswith("#"):
                flush()
                continue

            if line.startswith("msgid "):
                flush()
                msgid = unescape(line[7:-1])
                state = "id"
            elif line.startswith("msgstr "):
                msgstr = unescape(line[8:-1])
                state = "str"
            elif line.startswith('"'):
                val = unescape(line[1:-1])
                if state == "id" and msgid is not None:
                    msgid += val
                elif state == "str" and msgstr is not None:
                    msgstr += val

    flush()
    return entries


def compile_mo(entries, mo_path):
    """Write entries as a valid little-endian MO binary."""
    entries = sorted(entries, key=lambda x: x[0])
    N = len(entries)

    header_size = 20  # MO header: 5 × uint32 = 20 bytes
    id_table_off = header_size
    str_table_off = header_size + N * 8
    ids_data_off = str_table_off + N * 8

    id_blobs = [k + b"\x00" for k, _ in entries]
    str_blobs = [v + b"\x00" for _, v in entries]

    pos = ids_data_off
    id_offsets = []
    for blob in id_blobs:
        id_offsets.append((len(blob) - 1, pos))
        pos += len(blob)

    str_data_off = pos
    pos = str_data_off
    str_offsets = []
    for blob in str_blobs:
        str_offsets.append((len(blob) - 1, pos))
        pos += len(blob)

    with open(mo_path, "wb") as f:
        f.write(struct.pack("<IIIII", 0x950412de, 0, N, id_table_off, str_table_off))
        for length, offset in id_offsets:
            f.write(struct.pack("<II", length, offset))
        for length, offset in str_offsets:
            f.write(struct.pack("<II", length, offset))
        for blob in id_blobs:
            f.write(blob)
        for blob in str_blobs:
            f.write(blob)


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    locale_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(repo_root, "locale")

    compiled = 0
    for lang in sorted(os.listdir(locale_dir)):
        lc_dir = os.path.join(locale_dir, lang, "LC_MESSAGES")
        if not os.path.isdir(lc_dir):
            continue
        for fname in sorted(os.listdir(lc_dir)):
            if not fname.endswith(".po"):
                continue
            po_path = os.path.join(lc_dir, fname)
            mo_path = os.path.join(lc_dir, fname[:-3] + ".mo")
            entries = parse_po(po_path)
            compile_mo(entries, mo_path)
            print(f"  Compiled {lang}: {len(entries)} entries -> {mo_path}")
            compiled += 1

    print(f"\nDone. {compiled} file(s) compiled.")


if __name__ == "__main__":
    main()
