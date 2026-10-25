"""
Cloudflare R2 storage service (S3-compatible, via boto3).

Responsibilities (intentionally small):
  * ``presign_put``      — short-lived presigned PUT URL bound to a Content-Type
  * ``head_object``      — read size / type / ETag of an uploaded object
  * ``download_to_path`` — stream a private object to a local file (atomic)

Security rules:
  * Credentials are read from environment variables only and are never
    logged, printed or included in ``repr()`` / exception messages.
  * Presigned URLs are returned to the caller and must NOT be logged or
    persisted by callers.
  * The bucket is expected to be PRIVATE; this module never creates public
    URLs or changes bucket policy.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ─── Limits ───────────────────────────────────────────────────────────────────
# Single PUT uploads are capped below Cloudflare R2's single-request upload
# limit (~5 GiB).  Larger files would need multipart upload (out of scope).
R2_SINGLE_PUT_MAX_BYTES = 5 * 1000 * 1000 * 1000          # 5 GB (decimal)
DEFAULT_PRESIGN_EXPIRES_SECONDS = 900                     # 15 minutes
MIN_PRESIGN_EXPIRES_SECONDS = 60
MAX_PRESIGN_EXPIRES_SECONDS = 3600

REQUIRED_ENV_VARS = (
    "R2_ENDPOINT",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
)

_NOT_FOUND_CODES = {"404", "NoSuchKey", "NotFound"}
_DOWNLOAD_CHUNK_BYTES = 8 * 1024 * 1024

# ─── Retry policy (single place; botocore's own retries are disabled) ────────
DEFAULT_MAX_ATTEMPTS = 3            # total attempts, including the first
DEFAULT_BACKOFF_BASE_SECONDS = 0.5  # 0.5s, 1s, ... between attempts
_TRANSIENT_ERROR_CODES = {
    "500", "502", "503", "504", "429",
    "InternalError", "ServiceUnavailable", "SlowDown",
    "RequestTimeout", "Throttling", "TooManyRequests",
}


class R2NotConfiguredError(RuntimeError):
    """Raised when one or more required R2 environment variables are missing."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        # Only variable NAMES are included — never values.
        super().__init__(f"R2 storage is not configured (missing: {', '.join(missing)})")


class R2StorageError(RuntimeError):
    """Raised for unexpected R2/S3 errors.  Message never contains secrets."""


@dataclass(frozen=True)
class R2Settings:
    endpoint_url: str
    bucket_name: str
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    presign_expires_seconds: int = DEFAULT_PRESIGN_EXPIRES_SECONDS
    max_upload_bytes: int = R2_SINGLE_PUT_MAX_BYTES

    @classmethod
    def from_env(cls, environ: Optional[dict[str, str]] = None) -> "R2Settings":
        env = os.environ if environ is None else environ
        missing = [name for name in REQUIRED_ENV_VARS if not (env.get(name) or "").strip()]
        if missing:
            raise R2NotConfiguredError(missing)

        return cls(
            endpoint_url=env["R2_ENDPOINT"].strip(),
            bucket_name=env["R2_BUCKET_NAME"].strip(),
            access_key_id=env["R2_ACCESS_KEY_ID"].strip(),
            secret_access_key=env["R2_SECRET_ACCESS_KEY"].strip(),
            presign_expires_seconds=_clamp_int(
                env.get("R2_PRESIGN_EXPIRES_SECONDS"),
                default=DEFAULT_PRESIGN_EXPIRES_SECONDS,
                low=MIN_PRESIGN_EXPIRES_SECONDS,
                high=MAX_PRESIGN_EXPIRES_SECONDS,
            ),
            max_upload_bytes=_clamp_int(
                env.get("R2_MAX_UPLOAD_BYTES"),
                default=R2_SINGLE_PUT_MAX_BYTES,
                low=1,
                high=R2_SINGLE_PUT_MAX_BYTES,
            ),
        )


@dataclass(frozen=True)
class R2ObjectInfo:
    size: int
    content_type: Optional[str]
    etag: Optional[str]


def _clamp_int(raw: Optional[str], default: int, low: int, high: int) -> int:
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        logger.warning("Ignoring non-integer R2 setting; using default %s", default)
        return default
    return max(low, min(high, value))


def build_s3_client(settings: R2Settings) -> Any:
    """Create a boto3 S3 client pointed at the R2 endpoint (no network I/O)."""
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            # Retries are handled explicitly by R2StorageService._call so the
            # total number of attempts stays bounded and testable.
            # NOTE: botocore's "max_attempts" counts retries only; use
            # "total_max_attempts" to make it exactly one request per call.
            retries={"total_max_attempts": 1, "mode": "standard"},
            connect_timeout=10,
            read_timeout=60,
            # botocore >= 1.36 adds CRC checksums by default; restrict them to
            # operations that require them so browser PUTs to presigned URLs
            # do not need to send extra checksum headers.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


class R2StorageService:
    """Thin wrapper around a boto3 S3 client for a single private R2 bucket."""

    def __init__(
        self,
        settings: R2Settings,
        client: Any = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings
        self._client = client if client is not None else build_s3_client(settings)
        self._max_attempts = max(1, max_attempts)
        self._backoff_base = max(0.0, backoff_base_seconds)
        self._sleep = sleep

    @property
    def client(self) -> Any:
        return self._client

    def __repr__(self) -> str:  # never leak credentials
        return f"R2StorageService(bucket={self.settings.bucket_name!r})"

    # ── Retry helper ─────────────────────────────────────────────────────────
    def _call(self, operation: str, fn: Callable[[], T]) -> T:
        """
        Run ``fn`` with bounded retries for transient errors only (5xx,
        throttling, connection/timeouts).  Non-transient errors (403, 404,
        validation...) are raised immediately.  Errors are re-raised unchanged
        so callers can classify them.
        """
        attempt = 1
        while True:
            try:
                return fn()
            except Exception as exc:  # classified below
                if attempt >= self._max_attempts or not _is_transient(exc):
                    raise
                delay = self._backoff_base * (2 ** (attempt - 1))
                logger.warning("R2 %s transient error (%s); retry %d/%d in %.1fs",
                               operation, _error_code(exc), attempt,
                               self._max_attempts - 1, delay)
                self._sleep(delay)
                attempt += 1

    # ── Presign ──────────────────────────────────────────────────────────────
    def presign_put(self, object_key: str, content_type: str,
                    expires_in: Optional[int] = None) -> str:
        """
        Return a presigned PUT URL.  ``Content-Type`` is part of the signature,
        so the browser MUST send exactly the same header.  Generating the URL
        is a local signing operation — no request is sent to R2.
        """
        expires = expires_in or self.settings.presign_expires_seconds
        return self._client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.settings.bucket_name,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires,
            HttpMethod="PUT",
        )

    # ── HeadObject ───────────────────────────────────────────────────────────
    def head_object(self, object_key: str) -> Optional[R2ObjectInfo]:
        """Return object metadata, or ``None`` if the object does not exist."""
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            resp = self._call("head_object", lambda: self._client.head_object(
                Bucket=self.settings.bucket_name, Key=object_key))
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in _NOT_FOUND_CODES:
                return None
            logger.error("R2 head_object failed (code=%s)", code)
            raise R2StorageError(f"R2 head_object failed (code={code})") from None
        except BotoCoreError as exc:
            logger.error("R2 head_object transport error: %s", type(exc).__name__)
            raise R2StorageError("R2 head_object transport error") from None

        etag = resp.get("ETag")
        return R2ObjectInfo(
            size=int(resp.get("ContentLength", 0)),
            content_type=resp.get("ContentType"),
            etag=etag.strip('"') if isinstance(etag, str) else None,
        )

    # ── Download ─────────────────────────────────────────────────────────────
    def download_to_path(self, object_key: str, dest_path: str) -> int:
        """
        Stream an object to ``dest_path``.  Writes to ``<dest>.part`` first and
        renames on success, so a failed download never leaves a truncated file
        at ``dest_path``.  Returns the number of bytes written.
        """
        from botocore.exceptions import BotoCoreError, ClientError

        tmp_path = f"{dest_path}.part"
        written = 0
        try:
            resp = self._call("get_object", lambda: self._client.get_object(
                Bucket=self.settings.bucket_name, Key=object_key))
            body = resp["Body"]
            with open(tmp_path, "wb") as fh:
                for chunk in body.iter_chunks(chunk_size=_DOWNLOAD_CHUNK_BYTES):
                    if chunk:
                        fh.write(chunk)
                        written += len(chunk)
            os.replace(tmp_path, dest_path)
            return written
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            logger.error("R2 get_object failed (code=%s)", code)
            raise R2StorageError(f"R2 get_object failed (code={code})") from None
        except BotoCoreError as exc:
            logger.error("R2 get_object transport error: %s", type(exc).__name__)
            raise R2StorageError("R2 get_object transport error") from None
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    logger.warning("Could not remove partial download file")

    # ── Delete (used ONLY by the opt-in cleanup job) ─────────────────────────
    def delete_object(self, object_key: str) -> None:
        """
        Delete a single object.  S3/R2 DeleteObject is idempotent: deleting a
        missing key succeeds.  Transient errors are retried (bounded).
        """
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self._call("delete_object", lambda: self._client.delete_object(
                Bucket=self.settings.bucket_name, Key=object_key))
        except ClientError as exc:
            code = _error_code(exc)
            logger.error("R2 delete_object failed (code=%s)", code)
            raise R2StorageError(f"R2 delete_object failed (code={code})") from None
        except BotoCoreError as exc:
            logger.error("R2 delete_object transport error: %s", type(exc).__name__)
            raise R2StorageError("R2 delete_object transport error") from None


def _error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return str(response.get("Error", {}).get("Code", ""))
    return type(exc).__name__


def _is_transient(exc: Exception) -> bool:
    from botocore.exceptions import (
        ClientError,
        ConnectionClosedError,
        ConnectTimeoutError,
        EndpointConnectionError,
        ReadTimeoutError,
    )

    if isinstance(exc, (EndpointConnectionError, ConnectionClosedError,
                        ConnectTimeoutError, ReadTimeoutError)):
        return True
    if isinstance(exc, ClientError):
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return _error_code(exc) in _TRANSIENT_ERROR_CODES or (
            isinstance(status, int) and (status >= 500 or status == 429)
        )
    return False


def load_r2_storage_from_env() -> R2StorageService:
    """Build a service from environment variables (raises R2NotConfiguredError)."""
    return R2StorageService(R2Settings.from_env())


def get_r2_storage() -> R2StorageService:
    """
    FastAPI dependency: build the storage service from the environment.

    Raises ``HTTPException(503)`` if R2 is not configured, so the rest of the
    API keeps working when R2 variables are absent.  Tests override this
    dependency with a Stubber-backed instance.
    """
    from ..core import api_errors

    try:
        return load_r2_storage_from_env()
    except R2NotConfiguredError as exc:
        logger.warning("%s", exc)
        raise api_errors.CodedHTTPException(
            503, "R2 storage is not configured.", api_errors.STORAGE_NOT_CONFIGURED
        )


def get_optional_r2_storage() -> Optional[R2StorageService]:
    """
    FastAPI dependency for endpoints that need R2 only on some code paths
    (e.g. completion: an already-completed session is answered from the DB).
    Returns ``None`` when R2 is not configured.
    """
    try:
        return load_r2_storage_from_env()
    except R2NotConfiguredError as exc:
        logger.warning("%s", exc)
        return None
