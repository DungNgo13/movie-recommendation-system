import { describe, expect, it } from 'vitest';
import { formatBytes } from './formatBytes';

describe('formatBytes', () => {
  it('formats small values in bytes', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(999)).toBe('999 B');
  });

  it('uses decimal units', () => {
    expect(formatBytes(11_509)).toBe('11.5 kB');
    expect(formatBytes(2_500_000)).toBe('2.5 MB');
    expect(formatBytes(5_000_000_000)).toBe('5.0 GB');
  });

  it('guards invalid input', () => {
    expect(formatBytes(Number.NaN)).toBe('0 B');
    expect(formatBytes(-5)).toBe('0 B');
  });
});
