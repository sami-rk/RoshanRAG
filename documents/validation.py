"""Lightweight content sniffing for uploaded documents.

The file extension alone is easy to spoof (a renamed binary passed as
``.txt``), so uploads are also checked against a few magic bytes before the
heavy extraction pipeline runs. This is a first-line filter, not a
file-format validator — the extraction service still produces the definitive
error message for files that pass here but are malformed.
"""

MAGIC_PDF = b"%PDF-"
MAGIC_ZIP = b"PK\x03\x04"
PDF_HEADER_BYTES = 1024
TEXT_SNIFF_BYTES = 8192


def _looks_like_text(chunk: bytes) -> bool:
    # UTF-16/32 text carries a BOM and would otherwise look "binary" because
    # ASCII-range characters include NUL bytes.
    if chunk[:4] in (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"):
        return True
    if chunk[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return True
    return b"\x00" not in chunk


def validate_upload_file(file) -> str | None:
    """Return an error message when the file content does not match the
    extension it claims, or ``None`` when it plausibly does.

    The file position is restored to the start so callers can save it.
    """
    name = (getattr(file, "name", "") or "").lower()
    extension = name.rsplit(".", 1)[-1] if "." in name else ""
    file.seek(0)
    head = file.read(TEXT_SNIFF_BYTES)
    file.seek(0)

    if extension == "pdf" and MAGIC_PDF not in head[:PDF_HEADER_BYTES]:
        return "محتوای فایل با پسوند pdf همخوانی ندارد"
    if extension == "docx" and not head.startswith(MAGIC_ZIP):
        return "محتوای فایل با پسوند docx همخوانی ندارد"
    if extension == "txt" and not _looks_like_text(head):
        return "محتوای فایل با پسوند txt همخوانی ندارد"
    return None