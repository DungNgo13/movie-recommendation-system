import { describe, it, expect } from 'vitest';
import { validatePassword, isPasswordValid } from './passwordValidator';

describe('validatePassword', () => {
  it('rejects a password shorter than 8 characters', () => {
    const reqs = validatePassword('Ab1!xyz');
    const lengthReq = reqs.find((r) => r.label.includes('8 characters'));
    expect(lengthReq?.met).toBe(false);
  });

  it('rejects a password with no uppercase letter', () => {
    const reqs = validatePassword('abcdefg1!');
    const upperReq = reqs.find((r) => r.label.includes('uppercase'));
    expect(upperReq?.met).toBe(false);
  });

  it('rejects a password with no digit', () => {
    const reqs = validatePassword('Abcdefgh!');
    const digitReq = reqs.find((r) => r.label.includes('digit'));
    expect(digitReq?.met).toBe(false);
  });

  it('rejects a password with no special character', () => {
    const reqs = validatePassword('Abcdefg1');
    const specialReq = reqs.find((r) => r.label.includes('special'));
    expect(specialReq?.met).toBe(false);
  });

  it('rejects a common blocklisted password', () => {
    const reqs = validatePassword('Password123!');
    const commonReq = reqs.find((r) => r.label.includes('commonly'));
    expect(commonReq?.met).toBe(false);
  });

  it('accepts a strong, valid password', () => {
    const reqs = validatePassword('MyStr0ng!Pass');
    expect(reqs.every((r) => r.met)).toBe(true);
  });

  it('rejects password containing email local part', () => {
    const reqs = validatePassword('JohnDoe1!xx', 'johndoe@example.com');
    const emailReq = reqs.find((r) => r.label.includes('email'));
    expect(emailReq?.met).toBe(false);
  });

  it('skips email check when local part is too short', () => {
    const reqs = validatePassword('AbCdEfg1!', 'ab@example.com');
    // No email requirement should be added for 2-char local parts
    const emailReq = reqs.find((r) => r.label.includes('email'));
    expect(emailReq).toBeUndefined();
  });
});

describe('isPasswordValid', () => {
  it('returns true for a fully valid password', () => {
    expect(isPasswordValid('Secure99!')).toBe(true);
  });

  it('returns false for a weak password', () => {
    expect(isPasswordValid('weak')).toBe(false);
  });

  it('returns false for a blocklisted password', () => {
    expect(isPasswordValid('Password123!')).toBe(false);
  });
});
