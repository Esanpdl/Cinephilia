import re
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator

COMMON_TYPO_DOMAINS = {
    "gmail.co": "gmail.com",
    "gmail.cm": "gmail.com",
    "gmail.con": "gmail.com",
    "gmail.cmo": "gmail.com",
    "gmail.org": "gmail.com",
    "gmail.net": "gmail.com",
    "yahoo.co": "yahoo.com",
    "yahoo.cm": "yahoo.com",
    "yahoo.con": "yahoo.com",
    "hotmail.co": "hotmail.com",
    "hotmail.cm": "hotmail.com",
    "hotmail.con": "hotmail.com",
    "outlook.co": "outlook.com",
    "outlook.cm": "outlook.com",
    "icloud.co": "icloud.com",
    "icloud.cm": "icloud.com",
}

GMAIL_DOMAIN_RE = re.compile(r"^gmail\.", re.IGNORECASE)
VALID_TLD_RE = re.compile(r"^[a-zA-Z]{2,24}$")
VALID_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,30}$")

RESERVED_USERNAMES = frozenset({
    "admin",
    "administrator",
    "root",
    "system",
    "superuser",
    "staff",
    "cinephilia",
})


def validate_custom_email(value: str) -> str:
    """Validate email format, reject known typos like gmail.co, and enforce valid TLD."""
    if not value:
        return ""
    email = value.strip()
    if not email:
        return ""

    # Standard Django email validator
    EmailValidator(message="Enter a valid email address.")(email)

    parts = email.split("@")
    if len(parts) != 2:
        raise DjangoValidationError("Enter a valid email address.")

    local_part, domain = parts[0], parts[1].lower()

    if domain in COMMON_TYPO_DOMAINS:
        suggestion = COMMON_TYPO_DOMAINS[domain]
        raise DjangoValidationError(f"Invalid email domain '{domain}'. Did you mean '{suggestion}'?")

    # Specifically for @gmail.*, it must end with .com
    if GMAIL_DOMAIN_RE.match(domain):
        if domain != "gmail.com":
            raise DjangoValidationError("Invalid Gmail address. Gmail addresses must end with @gmail.com.")

    domain_parts = domain.split(".")
    if len(domain_parts) < 2:
        raise DjangoValidationError("Email domain must contain a valid top-level domain.")

    tld = domain_parts[-1]
    if not VALID_TLD_RE.match(tld):
        raise DjangoValidationError("Email must end with a valid top-level domain (e.g. .com, .org, .edu).")

    for part in domain_parts:
        if not part or not re.match(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", part):
            raise DjangoValidationError("Email domain contains invalid characters.")

    return email


def validate_custom_username(value: str) -> str:
    """Username must be 3-30 chars, alphanumeric with hyphens and underscores."""
    username = value.strip() if value else ""
    if not VALID_USERNAME_RE.match(username):
        raise DjangoValidationError(
            "Username must be between 3 and 30 characters and contain only letters, numbers, underscores, or hyphens."
        )
    return username


def validate_custom_password(password: str) -> None:
    """Password must be at least 8 characters, with at least one letter and one number or special char."""
    if not password or len(password) < 8:
        raise DjangoValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[a-zA-Z]", password):
        raise DjangoValidationError("Password must contain at least one letter.")
    if not re.search(r"[0-9!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", password):
        raise DjangoValidationError("Password must contain at least one digit or special character.")
