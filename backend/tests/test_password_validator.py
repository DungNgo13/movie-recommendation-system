"""Tests for the password complexity validator."""

import pytest
from app.core.password_validator import validate_password_complexity


class TestValidatePasswordComplexity:
    """Unit tests for validate_password_complexity()."""

    def test_valid_complex_password(self):
        errors = validate_password_complexity("MyStr0ng!Pass")
        assert errors == []

    def test_too_short(self):
        errors = validate_password_complexity("Ab1!xyz")
        assert any("8 characters" in e for e in errors)

    def test_no_uppercase(self):
        errors = validate_password_complexity("abcdefg1!")
        assert any("uppercase" in e for e in errors)

    def test_no_digit(self):
        errors = validate_password_complexity("Abcdefgh!")
        assert any("digit" in e for e in errors)

    def test_no_special_character(self):
        errors = validate_password_complexity("Abcdefg1")
        assert any("special" in e for e in errors)

    def test_contains_email_local_part(self):
        errors = validate_password_complexity("JohnDoe1!xx", email="johndoe@example.com")
        assert any("email" in e for e in errors)

    def test_short_email_local_part_skipped(self):
        """Local parts shorter than 3 chars should not trigger the email check."""
        errors = validate_password_complexity("AbCdEfg1!", email="ab@example.com")
        assert not any("email" in e for e in errors)

    def test_blocklisted_password(self):
        errors = validate_password_complexity("Password123!")
        assert any("too common" in e for e in errors)

    def test_blocklist_case_sensitive(self):
        """Blocklist is case-sensitive — altered casing should pass."""
        errors = validate_password_complexity("password123!")
        # Should fail on uppercase rule, but NOT on blocklist
        assert not any("too common" in e for e in errors)

    def test_multiple_violations(self):
        """A very weak password should fail multiple rules at once."""
        errors = validate_password_complexity("abc")
        assert len(errors) >= 3  # short, no uppercase, no digit, no special

    def test_empty_password(self):
        errors = validate_password_complexity("")
        assert len(errors) >= 4
