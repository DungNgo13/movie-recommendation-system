"""
Machine-readable API errors.

``CodedHTTPException`` behaves exactly like ``HTTPException`` but adds a
stable ``code`` field to the JSON body:

    {"detail": "<human-readable message>", "code": "<stable_snake_case_code>"}

``detail`` is unchanged, so existing clients keep working (backward
compatible); new clients should branch on ``code`` instead of parsing text.
"""

from typing import Dict, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class CodedHTTPException(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        code: str,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


async def coded_http_exception_handler(request: Request, exc: CodedHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
        headers=exc.headers,
    )


# ── Stable error codes ───────────────────────────────────────────────────────
# Direct-to-R2 uploads (retryable = the same request may succeed later
# without uploading the file again).
MOVIE_NOT_FOUND = "movie_not_found"
UPLOAD_TOO_LARGE = "upload_too_large"
PRESIGN_FAILED = "presign_failed"                        # retryable
UPLOAD_SESSION_NOT_FOUND = "upload_session_not_found"
UPLOAD_SESSION_FORBIDDEN = "upload_session_forbidden"
UPLOAD_SESSION_NOT_PENDING = "upload_session_not_pending"
UPLOAD_SESSION_EXPIRED = "upload_session_expired"
UPLOAD_OBJECT_MISSING = "upload_object_missing"          # retryable
UPLOAD_VERIFICATION_FAILED = "upload_verification_failed"
STORAGE_NOT_CONFIGURED = "storage_not_configured"        # retryable
STORAGE_UNAVAILABLE = "storage_unavailable"              # retryable

# HLS processing
HLS_R2_SOURCE_UNSUPPORTED = "hls_r2_source_unsupported"
