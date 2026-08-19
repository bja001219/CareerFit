"""Typed domain errors mapped to HTTP status codes by the global handler.

Each class carries the intended status code so the router layer only needs
one exception handler (``app.api.errors``).  Messages are safe to surface to
end users — internal traceback stays in the server log.
"""
from __future__ import annotations


class CareerFitError(Exception):
    """Base class.  Sets a default 500; subclasses override."""

    status_code: int = 500
    default_message: str = "서버 오류가 발생했습니다."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)

    @property
    def message(self) -> str:
        return str(self)


class ConfigurationError(CareerFitError):
    status_code = 500
    default_message = "서버 설정 오류입니다."


class InvalidUploadError(CareerFitError):
    status_code = 400
    default_message = "지원하지 않는 파일 형식입니다."


class PayloadTooLargeError(CareerFitError):
    status_code = 413
    default_message = "파일이 너무 큽니다."


class EmptyExtractedTextError(CareerFitError):
    status_code = 400
    default_message = "텍스트를 추출할 수 없는 파일입니다. 스캔본은 OCR 미지원."


class UrlExtractionError(CareerFitError):
    status_code = 400
    default_message = "URL 에서 본문을 가져올 수 없습니다."


class AnalysisFailedError(CareerFitError):
    status_code = 502
    default_message = "AI 분석이 실패했습니다."


class MissingCredentialsError(CareerFitError):
    status_code = 500
    default_message = "LIVE 모드인데 API 키가 없습니다."


class DuplicateAnalysisError(CareerFitError):
    """Raised when POST /api/fit/analyze hits UNIQUE(profile_id, posting_id).

    ``existing_id`` lets the API layer respond with the id of the already
    stored analysis so the frontend can redirect to it.
    """

    status_code = 409
    default_message = "동일 (프로필, 공고) 조합의 분석이 이미 존재합니다."

    def __init__(self, existing_id: int, message: str | None = None) -> None:
        super().__init__(message)
        self.existing_id = existing_id


class ReferencedDocumentError(CareerFitError):
    status_code = 409
    default_message = "이 문서를 참조하는 이전 프로필이 존재합니다."

    def __init__(self, referenced_by: list[int], message: str | None = None) -> None:
        super().__init__(message)
        self.referenced_by = referenced_by


class NotFoundError(CareerFitError):
    status_code = 404
    default_message = "해당 리소스를 찾을 수 없습니다."
