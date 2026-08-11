import React, { useState, useRef } from 'react';
import { uploadAvatar } from '../services/authService';
import { useAuth } from '../hooks/useAuthHook';
import { getAvatarUrl } from '../utils/avatarUrl';
import { useTranslation } from 'react-i18next';

const MAX_SIZE_BYTES = 2 * 1024 * 1024; // 2 MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const ALLOWED_ACCEPT = '.jpg,.jpeg,.png,.webp';

// ── Known backend error → i18n key mapping ────────────────────────────────────
const KNOWN_API_ERRORS: Record<string, string> = {
  'Invalid file type. Only JPEG, PNG, or WebP images are allowed.': 'profile.avatar.errors.invalidType',
  'File too large. Maximum avatar size is 2 MB.': 'profile.avatar.errors.tooLarge',
};

const AvatarUpload: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const { t } = useTranslation(['auth']);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [preview, setPreview] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  /** Translate known API error messages; pass unknown ones through unchanged. */
  const translateApiError = (msg: string): string => {
    const key = KNOWN_API_ERRORS[msg];
    return key ? t(`auth:${key}`) : msg;
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setSuccess(null);

    const file = e.target.files?.[0];
    if (!file) return;

    // Client-side type check
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError(t("auth:profile.avatar.errors.invalidType"));
      return;
    }

    // Client-side size check
    if (file.size > MAX_SIZE_BYTES) {
      setError(t("auth:profile.avatar.errors.tooLarge"));
      return;
    }

    setSelectedFile(file);

    // Generate preview
    const reader = new FileReader();
    reader.onload = (ev) => {
      setPreview(ev.target?.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setError(null);
    setSuccess(null);
    setUploading(true);

    try {
      await uploadAvatar(selectedFile);
      await refreshUser();
      setSuccess(t("auth:profile.avatar.success"));
      setSelectedFile(null);
      setPreview(null);
      // Reset file input
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      const raw = err instanceof Error ? err.message : t("auth:profile.avatar.errors.uploadFailed");
      setError(translateApiError(raw));
    } finally {
      setUploading(false);
    }
  };

  const handleCancel = () => {
    setSelectedFile(null);
    setPreview(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const displayUrl = preview || getAvatarUrl(user?.avatar_url) || null;
  const initial = user?.email?.charAt(0).toUpperCase() || 'U';

  return (
    <div className="avatar-upload" id="avatar-upload">
      <div className="avatar-upload__preview-wrapper">
        {displayUrl ? (
          <img
            src={displayUrl}
            alt={t("auth:profile.avatar.alt")}
            className="avatar-upload__preview"
            onError={(e) => {
              // Hide broken image and show text placeholder
              e.currentTarget.style.display = 'none';
              const next = e.currentTarget.nextElementSibling as HTMLElement | null;
              if (next) next.style.display = '';
            }}
          />
        ) : null}
        <div
          className="avatar-upload__placeholder"
          style={displayUrl ? { display: 'none' } : undefined}
        >
          <span>{initial}</span>
        </div>
        <button
          type="button"
          className="avatar-upload__change-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          {t("auth:profile.avatar.change")}
        </button>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept={ALLOWED_ACCEPT}
        onChange={handleFileSelect}
        style={{ display: 'none' }}
        id="avatar-file-input"
      />

      {error && <p className="auth-error">{error}</p>}
      {success && <p className="auth-success-message">{success}</p>}

      {selectedFile && (
        <div className="avatar-upload__actions">
          <button
            type="button"
            className="btn btn--primary"
            onClick={handleUpload}
            disabled={uploading}
          >
            {uploading ? t("auth:profile.avatar.uploading") : t("auth:profile.avatar.upload")}
          </button>
          <button
            type="button"
            className="btn btn--secondary"
            onClick={handleCancel}
            disabled={uploading}
          >
            {t("auth:profile.avatar.cancel")}
          </button>
        </div>
      )}
    </div>
  );
};

export default AvatarUpload;
