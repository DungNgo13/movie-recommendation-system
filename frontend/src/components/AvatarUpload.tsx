import React, { useState, useRef } from 'react';
import { uploadAvatar } from '../services/authService';
import { useAuth } from '../hooks/useAuth';

const MAX_SIZE_BYTES = 2 * 1024 * 1024; // 2 MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const ALLOWED_ACCEPT = '.jpg,.jpeg,.png,.webp';

const AvatarUpload: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [preview, setPreview] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setSuccess(null);

    const file = e.target.files?.[0];
    if (!file) return;

    // Client-side type check
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError('Invalid file type. Only JPEG, PNG, or WebP images are allowed.');
      return;
    }

    // Client-side size check
    if (file.size > MAX_SIZE_BYTES) {
      setError('File too large. Maximum avatar size is 2 MB.');
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
      setSuccess('Avatar updated successfully!');
      setSelectedFile(null);
      setPreview(null);
      // Reset file input
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
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

  const displayUrl = preview || user?.avatar_url || null;

  return (
    <div className="avatar-upload" id="avatar-upload">
      <div className="avatar-upload__preview-wrapper">
        {displayUrl ? (
          <img
            src={displayUrl}
            alt="Avatar"
            className="avatar-upload__preview"
          />
        ) : (
          <div className="avatar-upload__placeholder">
            <span>📷</span>
          </div>
        )}
        <button
          type="button"
          className="avatar-upload__change-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          Change
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
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
          <button
            type="button"
            className="btn btn--secondary"
            onClick={handleCancel}
            disabled={uploading}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
};

export default AvatarUpload;
