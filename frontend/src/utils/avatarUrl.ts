/**
 * Normalize an avatar path into a usable image URL.
 *
 * The backend may return avatar_url in several formats depending on
 * when the avatar was uploaded and what config was active:
 *
 *   - Full URL:  "https://cdn.example.com/img.jpg"   → use as-is
 *   - Root-relative path:  "/media/images/avatars/user_xxx/img.jpg" → use as-is
 *   - Bare filename:       "avatar_20260628_115901.png"
 *     → convert to "/media/images/avatars/<filename>"
 *
 * This helper guarantees a valid src for `<img>` tags, or null if absent.
 */
export function getAvatarUrl(avatarPath: string | null | undefined): string | null {
  if (!avatarPath) return null;

  // Full URL — use as-is (e.g. social login avatar)
  if (avatarPath.startsWith('http://') || avatarPath.startsWith('https://')) {
    return avatarPath;
  }

  // Root-relative path — already correct
  if (avatarPath.startsWith('/')) {
    return avatarPath;
  }

  // Relative path with directory info (e.g. "media/images/avatars/user_xxx/img.jpg")
  if (avatarPath.includes('/')) {
    return `/${avatarPath}`;
  }

  // Bare filename — assume legacy upload in default avatar dir
  return `/media/images/avatars/${avatarPath}`;
}
