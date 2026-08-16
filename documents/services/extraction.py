from pathlib import Path

from docx import Document as DocxDocument


class UnsupportedFormatError(Exception):
    pass


def extract_text(file_path: str, extension: str) -> str:
    ext = (extension or "").lower()
    if ext == "docx":
        return _extract_docx(file_path)
    if ext == "txt":
        return _extract_txt(file_path)
    raise UnsupportedFormatError(f"فرمت فایل پشتیبانی نمی‌شود: {extension}")


def _extract_docx(file_path: str) -> str:
    doc = DocxDocument(file_path)
    parts = [paragraph.text for paragraph in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text)
    return "\n".join(parts).strip()


def _extract_txt(file_path: str) -> str:
    return Path(file_path).read_text(encoding="utf-8", errors="replace").strip()