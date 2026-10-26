"""Upload validation and safe document parsing.

Rules enforced before anything reaches the model:
  * extension allow-list and magic-byte agreement
  * size, page-count, and pixel limits
  * encrypted/corrupt PDFs are rejected
  * files are read as bytes only; nothing is executed

PDFs with little or no text are rendered to images for the vision model.
"""

from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf as fitz  # PyMuPDF
from PIL import Image, ImageSequence, UnidentifiedImageError

from app.config import Settings

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
PDF_MAGIC = b"%PDF-"

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
EXTENSION_MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

MIN_TEXT_CHARS_FOR_TEXT_MODE = 200
MAX_MODEL_TEXT_CHARS = 24_000
MAX_RENDER_PAGES = 3


class UploadValidationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass
class ParsedDocument:
    filename: str
    extension: str
    mime_type: str
    size_bytes: int
    sha256: str
    page_count: int
    text: str
    text_mode: str  # "text" | "image"
    image_data_urls: list[str] = field(default_factory=list)
    width: int | None = None
    height: int | None = None

    @property
    def has_text(self) -> bool:
        return len(self.text.strip()) >= MIN_TEXT_CHARS_FOR_TEXT_MODE


def sanitize_filename(filename: str | None) -> str:
    raw = Path(filename or "upload").name
    cleaned = "".join(
        char for char in raw if char.isalnum() or char in {" ", ".", "_", "-", "(", ")"}
    ).strip()
    cleaned = cleaned[:120].strip(" .")
    return cleaned or "upload"


def detect_magic(data: bytes) -> str | None:
    if data.startswith(PDF_MAGIC):
        return "application/pdf"
    if data.startswith(PNG_MAGIC):
        return "image/png"
    if data.startswith(JPEG_MAGIC):
        return "image/jpeg"
    return None


def _to_data_url_jpeg(image_bytes: bytes, max_width: int = 1500) -> str:
    with Image.open(io.BytesIO(image_bytes)) as image:
        image.load()
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        if image.width > max_width:
            ratio = max_width / image.width
            image = image.resize(
                (max_width, max(1, int(image.height * ratio))),
                Image.Resampling.LANCZOS,
            )
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=86, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _validate_pdf(data: bytes, settings: Settings) -> tuple[int, str, list[str]]:
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several types
        raise UploadValidationError(
            "corrupt_pdf",
            "This PDF could not be opened. It may be corrupted or password-protected.",
        ) from exc

    try:
        if document.needs_pass:
            raise UploadValidationError(
                "encrypted_pdf",
                "Password-protected PDFs are not supported. Upload an unlocked copy.",
            )
        if not document.is_pdf:
            raise UploadValidationError(
                "unsupported_type", "The file is not a valid PDF document."
            )
        page_count = document.page_count
        if page_count < 1:
            raise UploadValidationError("empty_pdf", "The PDF has no pages.")
        if page_count > settings.max_pdf_pages:
            raise UploadValidationError(
                "too_many_pages",
                f"The PDF has {page_count} pages; the demo limit is "
                f"{settings.max_pdf_pages}. Upload only the invoice pages.",
            )

        text_parts: list[str] = []
        for page in document:
            text_parts.append(page.get_text("text") or "")
        text = "\n".join(text_parts).strip()

        images: list[str] = []
        if len(text) < MIN_TEXT_CHARS_FOR_TEXT_MODE:
            for page in document[:MAX_RENDER_PAGES]:
                pixmap = page.get_pixmap(dpi=130, alpha=False)
                images.append(_to_data_url_jpeg(pixmap.tobytes("png")))
        return page_count, text[:MAX_MODEL_TEXT_CHARS], images
    finally:
        document.close()


def _validate_image(
    data: bytes, extension: str, settings: Settings
) -> tuple[int, int, list[str]]:
    Image.MAX_IMAGE_PIXELS = settings.max_image_pixels
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            if width < 32 or height < 32:
                raise UploadValidationError(
                    "image_too_small",
                    "The image is too small to read. Use at least 32 x 32 pixels.",
                )
            if width * height > settings.max_image_pixels:
                raise UploadValidationError(
                    "image_too_large",
                    f"The image is {width} x {height}; the demo limit is "
                    f"{settings.max_image_pixels:,} pixels.",
                )
            frames = sum(1 for _ in ImageSequence.Iterator(image))
            if frames > 1:
                # Animated images are not invoices; use the first frame only.
                image.seek(0)
            buffer = io.BytesIO()
            rgb = image.convert("RGB")
            rgb.save(buffer, format="PNG", optimize=True)
            normalized = buffer.getvalue()
    except UploadValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UploadValidationError(
            "corrupt_image",
            "This image could not be read. Upload a valid PNG or JPEG.",
        ) from exc

    return width, height, [_to_data_url_jpeg(normalized)]


def validate_and_parse(
    data: bytes,
    filename: str | None,
    declared_content_type: str | None,
    settings: Settings,
) -> ParsedDocument:
    if not data:
        raise UploadValidationError("empty_file", "The uploaded file is empty.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise UploadValidationError(
            "too_large",
            f"The file is {len(data) / 1024 / 1024:.1f} MB; the demo limit is "
            f"{settings.max_upload_mb} MB.",
            status_code=413,
        )

    safe_name = sanitize_filename(filename)
    extension = Path(safe_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            "unsupported_extension",
            "Only PDF, PNG, JPG, and JPEG files are accepted.",
        )

    magic = detect_magic(data)
    if magic is None:
        raise UploadValidationError(
            "unsupported_type",
            "The file content is not a PDF, PNG, or JPEG. Renaming a file does not "
            "change its format.",
        )

    if EXTENSION_MIME[extension] != magic:
        raise UploadValidationError(
            "content_type_mismatch",
            f"The file is named {extension} but its contents are {magic}. "
            "Upload the original file instead of renaming it.",
        )

    if declared_content_type and declared_content_type not in {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "application/octet-stream",
    }:
        # Browsers sometimes send a generic type; magic bytes are authoritative.
        declared_content_type = magic

    sha256 = hashlib.sha256(data).hexdigest()

    if magic == "application/pdf":
        page_count, text, images = _validate_pdf(data, settings)
        return ParsedDocument(
            filename=safe_name,
            extension=".pdf",
            mime_type=magic,
            size_bytes=len(data),
            sha256=sha256,
            page_count=page_count,
            text=text,
            text_mode="text" if len(text) >= MIN_TEXT_CHARS_FOR_TEXT_MODE else "image",
            image_data_urls=images,
        )

    width, height, images = _validate_image(data, extension, settings)
    return ParsedDocument(
        filename=safe_name,
        extension=extension,
        mime_type=magic,
        size_bytes=len(data),
        sha256=sha256,
        page_count=1,
        text="",
        text_mode="image",
        image_data_urls=images,
        width=width,
        height=height,
    )


def store_upload(data: bytes, source: Path, parsed: ParsedDocument) -> Path:
    """Persist the original bytes under a generated name; never use user paths."""
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(data)
    return source
