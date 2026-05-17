"""
Password Complexity Validator

Centralised validation rules for all password creation / change flows.
Returns a list of human-readable violation messages (empty list = valid).

Rules:
  1. Minimum 8 characters
  2. At least one uppercase letter
  3. At least one digit
  4. At least one special character
  5. Must not contain the email local part (before @)
  6. Must not be in a blocklist of commonly guessable passwords
"""

import re

# Passwords that trivially satisfy all character-class rules but are still
# highly guessable.  Keep this list small and targeted.
COMMON_PASSWORD_BLOCKLIST = {
    "Password123!",
    "Qwerty123!",
    "Admin123!",
    "Welcome1!",
    "Changeme1!",
    "Abcd1234!",
    "P@ssw0rd!",
    "Passw0rd!",
    "Test1234!",
    "Letmein1!",
}

_SPECIAL_CHARS = re.compile(r"[!@#$%^&*()\-_+=\[\]{}|;:'\",.<>?/`~\\]")


def validate_password_complexity(password: str, email: str = "") -> list[str]:
    """
    Validate a password against the project's complexity policy.

    Args:
        password: The candidate password string.
        email:    The user's email (used to check that the password does not
                  contain the local part of the email).

    Returns:
        A list of violation messages.  An empty list means the password is valid.
    """
    errors: list[str] = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")

    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter.")

    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit.")

    if not _SPECIAL_CHARS.search(password):
        errors.append("Password must contain at least one special character.")

    # Check if the password contains the email local-part (case-insensitive)
    if email:
        local_part = email.split("@")[0].lower()
        if len(local_part) >= 3 and local_part in password.lower():
            errors.append("Password must not contain your email username.")

    # Blocklist check (case-sensitive — intentional; these are exact patterns)
    if password in COMMON_PASSWORD_BLOCKLIST:
        errors.append("This password is too common. Please choose a stronger one.")

    return errors

