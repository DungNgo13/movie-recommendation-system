/**
 * Password Complexity Validator (client-side mirror)
 *
 * Mirrors the backend rules in core/password_validator.py so the UI can
 * provide real-time feedback without a round-trip to the server.
 */

export interface PasswordRequirement {
  /** Human-readable description of the requirement. */
  label: string;
  /** Whether the current password satisfies this requirement. */
  met: boolean;
}

const SPECIAL_CHAR_REGEX = /[!@#$%^&*()\-_+=[\]{}|;:'",.<>?/`~\\]/;

const COMMON_BLOCKLIST = new Set([
  'Password123!',
  'Qwerty123!',
  'Admin123!',
  'Welcome1!',
  'Changeme1!',
  'Abcd1234!',
  'P@ssw0rd!',
  'Passw0rd!',
  'Test1234!',
  'Letmein1!',
]);

/**
 * Evaluate password against all complexity requirements.
 *
 * @param password - The candidate password.
 * @param email    - Optional user email. If provided, checks that the password
 *                   does not contain the email local-part.
 * @returns An array of requirement objects with `met` status.
 */
export function validatePassword(
  password: string,
  email?: string,
): PasswordRequirement[] {
  const requirements: PasswordRequirement[] = [
    {
      label: 'At least 8 characters',
      met: password.length >= 8,
    },
    {
      label: 'At least one uppercase letter',
      met: /[A-Z]/.test(password),
    },
    {
      label: 'At least one digit',
      met: /\d/.test(password),
    },
    {
      label: 'At least one special character',
      met: SPECIAL_CHAR_REGEX.test(password),
    },
    {
      label: 'Not a commonly used password',
      met: !COMMON_BLOCKLIST.has(password),
    },
  ];

  // Only add the email check when an email is provided and has a meaningful local part
  if (email) {
    const localPart = email.split('@')[0]?.toLowerCase() ?? '';
    if (localPart.length >= 3) {
      requirements.push({
        label: 'Must not contain your email username',
        met: !password.toLowerCase().includes(localPart),
      });
    }
  }

  return requirements;
}

/**
 * Returns true if all password requirements are met.
 */
export function isPasswordValid(password: string, email?: string): boolean {
  return validatePassword(password, email).every((r) => r.met);
}
