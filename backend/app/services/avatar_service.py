"""
Avatar upload service.

Handles file validation (type + size), storage, old-file cleanup, and DB update.
Follows the same pattern as movie_asset_service.py for consistency.
"""

import os
import logging
from datetime import datetime
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from ..models.user import User

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 MB
AVATAR_DIR = "media/images/avatars"

_EXT_MAP = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def upload_avatar(db: Session, user: User, file: UploadFile) -> User:
    """
    Validate, store, and persist a user avatar.

    Steps:
      1. Validate content type (JPEG / PNG / WebP only).
      2. Validate file size (≤ 2 MB) by reading at most MAX + 1 bytes.
      3. Write to media/images/avatars/user_{uuid}/avatar_{timestamp}.{ext}.
      4. Delete the previous avatar file if one exists.
      5. Update user.avatar_path and commit.

    Raises HTTPException(400) on validation failure.
    Returns the updated User ORM instance.
    """
    # ── Type validation ───────────────────────────────────────────────────────
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only JPEG, PNG, or WebP images are allowed.",
        )

    # ── Size validation ───────────────────────────────────────────────────────
    # Read at most MAX + 1 bytes.  If we get MAX + 1, the file is too large.
    contents = file.file.read(MAX_AVATAR_BYTES + 1)
    if len(contents) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum avatar size is 2 MB.",
        )

    # ── Write to disk ─────────────────────────────────────────────────────────
    ext = _EXT_MAP.get(file.content_type, "jpg")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(AVATAR_DIR, f"user_{user.id}")
    os.makedirs(folder, exist_ok=True)

    filename = f"avatar_{timestamp}.{ext}"
    physical_path = os.path.join(folder, filename)

    with open(physical_path, "wb") as f:
        f.write(contents)

    # ── Cleanup old avatar ────────────────────────────────────────────────────
    old_path = user.avatar_path
    if old_path and not old_path.startswith("http"):
        if os.path.exists(old_path) and os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except OSError as exc:
                logger.warning("Failed to remove old avatar [%s]: %s", old_path, exc)

    # ── Persist ───────────────────────────────────────────────────────────────
    relative_path = physical_path.replace("\\", "/")
    user.avatar_path = relative_path
    db.commit()
    db.refresh(user)
    return user
