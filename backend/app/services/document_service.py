"""File upload validation, safe storage, text extraction.

Handles the three career document formats:

* ``.pdf`` — pypdf, page-wise extract, rejects scanned-image PDFs.
* ``.docx`` — python-docx, paragraph join.
* ``.txt`` — encoding auto-detect (utf-8 → cp949 → utf-16 → latin-1).

Also home to :pyfunc:`sanitize_filename` — the whitelist from SPEC §18 is
enforced here (NFC + `[A-Za-z0-9._가-힣\\-]+`, 200 char cap) so no other
module needs to think about path traversal or Windows-reserved names.
"""
from __future__ import annotations

import io
import re
import unicodedata
import uuid
from pathlib import Path

from app.database import UPLOADS_ROOT
from app.models.career_document import CAREER_DOCUMENT_KINDS
from app.models.errors import (
    EmptyExtractedTextError,
    InvalidUploadError,
    PayloadTooLargeError,
)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}
MIN_EXTRACTED_CHARS = 200

# Only these characters survive sanitization; everything else becomes '_'.
# Regex covers ASCII alnum, dot, underscore, dash, and precomposed Hangul.
_SAFE_CHAR_PATTERN = re.compile(r"[^A-Za-z0-9._\-가-힣]")


def sanitize_filename(raw: str) -> str:
    """Return an NFC-normalised, whitelist-filtered filename.

    Steps: strip both ``/`` and ``\\`` path components (defensive on both
    platforms — never trust the host OS to interpret the separator right),
    NFC normalise, replace unsafe chars with '_', collapse repeated
    underscores, cap at 200 characters, ensure non-empty.
    """
    if not raw:
        return "file"
    # Cross-platform separator stripping — Path().name only strips the
    # separator the host OS recognises.  On Linux, Path("a\\b").name == "a\\b".
    for sep in ("/", "\\"):
        if sep in raw:
            raw = raw.rsplit(sep, 1)[-1]
    name = unicodedata.normalize("NFC", raw)
    name = _SAFE_CHAR_PATTERN.sub("_", name)
    name = re.sub(r"_+", "_", name).strip("_.") or "file"
    return name[:200] or "file"


def _extension_of(filename: str) -> str:
    return Path(filename).suffix.lower()


def _career_dir(kind: str) -> Path:
    if kind not in CAREER_DOCUMENT_KINDS:
        raise InvalidUploadError(
            f"지원하지 않는 문서 종류입니다: '{kind}'. "
            f"허용: {', '.join(CAREER_DOCUMENT_KINDS)}"
        )
    return UPLOADS_ROOT / "career" / kind


def _job_dir() -> Path:
    return UPLOADS_ROOT / "job"


def _enforce_size(content: bytes, max_bytes: int) -> None:
    if len(content) == 0:
        raise InvalidUploadError("빈 파일은 업로드할 수 없습니다.")
    if len(content) > max_bytes:
        raise PayloadTooLargeError(
            f"파일이 너무 큽니다. 최대 {max_bytes // (1024 * 1024)}MB 까지 업로드 가능합니다."
        )


def _resolve_within(root: Path, path: Path) -> Path:
    """Resolve ``path`` and reject anything not inside ``root``.

    Belt-and-suspenders: sanitize_filename already blocks separators, but
    an explicit resolve() check catches symlink escapes and future bugs.
    """
    resolved = path.resolve()
    root_resolved = root.resolve()
    if not str(resolved).startswith(str(root_resolved)):
        raise InvalidUploadError("잘못된 파일 경로입니다.")
    return resolved


def save_career_document(
    *,
    kind: str,
    filename: str,
    content: bytes,
    max_bytes: int,
) -> tuple[Path, str, int, str]:
    """Save the uploaded bytes for the given career-document ``kind``.

    Returns ``(stored_path, mime, size_bytes, extracted_text)``.  Raises
    :pyclass:`InvalidUploadError`, :pyclass:`PayloadTooLargeError`, or
    :pyclass:`EmptyExtractedTextError`.
    """
    ext = _extension_of(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidUploadError(
            f"지원하지 않는 파일 형식입니다. ({', '.join(sorted(ALLOWED_EXTENSIONS))} 만 지원)"
        )

    _enforce_size(content, max_bytes)

    kind_dir = _career_dir(kind)
    kind_dir.mkdir(parents=True, exist_ok=True)

    safe = sanitize_filename(filename)
    stored = _resolve_within(kind_dir, kind_dir / f"{uuid.uuid4().hex[:12]}_{safe}")
    stored.write_bytes(content)

    extracted = extract_text(stored, ext)
    if len(extracted.strip()) < MIN_EXTRACTED_CHARS:
        # Clean up so we don't accumulate orphan files on rejected uploads.
        try:
            stored.unlink()
        except OSError:
            pass
        raise EmptyExtractedTextError(
            "텍스트를 추출할 수 없는 파일입니다 "
            f"(추출 문자 수 {len(extracted.strip())} < 최소 {MIN_EXTRACTED_CHARS}). "
            "스캔본은 OCR 미지원."
        )

    return stored, MIME_BY_EXT[ext], len(content), extracted


def save_job_posting_pdf(
    *,
    filename: str,
    content: bytes,
    max_bytes: int,
) -> tuple[Path, int, str]:
    """Persist a job-posting PDF; returns ``(stored_path, size_bytes, text)``."""
    ext = _extension_of(filename)
    if ext != ".pdf":
        raise InvalidUploadError("공고 파일은 PDF 만 지원합니다.")

    _enforce_size(content, max_bytes)

    job_dir = _job_dir()
    job_dir.mkdir(parents=True, exist_ok=True)

    safe = sanitize_filename(filename)
    stored = _resolve_within(job_dir, job_dir / f"{uuid.uuid4().hex[:12]}_{safe}")
    stored.write_bytes(content)

    extracted = extract_text(stored, ext)
    if len(extracted.strip()) < MIN_EXTRACTED_CHARS:
        try:
            stored.unlink()
        except OSError:
            pass
        raise EmptyExtractedTextError(
            "공고 PDF 에서 텍스트를 추출할 수 없습니다. 스캔본은 OCR 미지원."
        )

    return stored, len(content), extracted


def extract_text(path: Path, ext: str | None = None) -> str:
    """Route to the extractor for the given extension."""
    ext = (ext or path.suffix).lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".docx":
        return _extract_docx(path)
    if ext == ".txt":
        return _extract_txt(path)
    raise InvalidUploadError(f"지원하지 않는 파일 형식입니다: {ext}")


def _extract_pdf(path: Path) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(str(path))
    except (PdfReadError, OSError, ValueError) as exc:
        raise InvalidUploadError(f"PDF 파일을 열 수 없습니다: {exc}") from exc

    if not reader.pages:
        return ""

    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 — pypdf raises assorted types
            parts.append("")
    return "\n".join(parts).strip()


def _extract_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise InvalidUploadError(f"python-docx 로드 실패: {exc}") from exc

    try:
        doc = Document(str(path))
    except Exception as exc:  # noqa: BLE001 — python-docx raises assorted types
        raise InvalidUploadError(f"DOCX 파일을 열 수 없습니다: {exc}") from exc

    return "\n".join(p.text for p in doc.paragraphs if p.text).strip()


def _extract_txt(path: Path) -> str:
    for enc in ("utf-8", "cp949", "utf-16", "latin-1"):
        try:
            return path.read_text(encoding=enc).strip()
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def replace_document_atomic(
    *,
    old_path: Path,
    new_stored_path: Path,
) -> None:
    """Delete the previous file after the DB row has already been updated.

    Called by the API layer after committing the row update.  If unlink
    fails we log rather than raise: the row is authoritative, and the
    orphan file will be swept by the future cleanup job (SPEC §17 TODO).
    """
    try:
        if old_path.exists() and old_path != new_stored_path:
            old_path.unlink()
    except OSError:
        # Non-fatal; DB row already reflects the new file.
        pass


__all__ = [
    "ALLOWED_EXTENSIONS",
    "MIN_EXTRACTED_CHARS",
    "extract_text",
    "replace_document_atomic",
    "sanitize_filename",
    "save_career_document",
    "save_job_posting_pdf",
]
