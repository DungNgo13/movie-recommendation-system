/**
 * Human-readable byte size in DECIMAL units (1 kB = 1000 B), matching how the
 * backend expresses limits (R2 single-PUT cap = 5,000,000,000 B = "5.0 GB").
 */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 1000) return `${Math.max(0, Math.floor(bytes || 0))} B`;
  const units = ['kB', 'MB', 'GB', 'TB'];
  let value = bytes / 1000;
  let i = 0;
  while (value >= 1000 && i < units.length - 1) {
    value /= 1000;
    i += 1;
  }
  return `${value.toFixed(1)} ${units[i]}`;
}
