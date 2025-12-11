"""Validation functions for authentication"""

import re
from typing import Tuple, Optional, List, Dict, Any
import logging

from app.core.errors import (
    InvalidDomainError,
    StudentNotAllowedError,
    AdminOnlyError,
    GroupMembershipRequiredError,
    NoMatchingGroupError
)

logger = logging.getLogger(__name__)


def extract_domain(email: str) -> str:
    """
    Extract domain from email address

    Args:
        email: Email address

    Returns:
        Domain part of the email
    """
    if '@' not in email:
        return ""
    return email.split('@')[1].lower()


def is_student_email(email: str) -> bool:
    """
    Check if email belongs to a student account

    Student emails typically follow patterns like:
    - 8-digit number@domain (e.g., 12345678@i-seifu.jp)
    - student.name@domain
    - s12345@domain

    Args:
        email: Email address to check

    Returns:
        True if email appears to be a student account
    """
    local_part = email.split('@')[0] if '@' in email else email

    # Check for 8-digit student ID pattern
    if re.match(r'^\d{8}$', local_part):
        logger.debug(f"Email {email} identified as student (8-digit ID)")
        return True

    # Check for common student prefixes
    student_patterns = [
        r'^s\d+',           # s12345
        r'^student\.',      # student.name
        r'^\d{6,}',         # 6+ digit numbers
    ]

    for pattern in student_patterns:
        if re.match(pattern, local_part.lower()):
            logger.debug(f"Email {email} identified as student (pattern: {pattern})")
            return True

    return False


def validate_domain(
    email: str,
    allowed_domains: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    Validate email domain against allowed domains

    Args:
        email: Email address to validate
        allowed_domains: List of allowed domains

    Returns:
        Tuple of (is_valid, error_message)
    """
    domain = extract_domain(email)

    if not domain:
        return False, "Invalid email format"

    # Convert to lowercase for comparison
    allowed_domains_lower = [d.lower() for d in allowed_domains]

    if domain in allowed_domains_lower:
        return True, None

    # Check for subdomain matches (e.g., sub.i-seifu.jp matches i-seifu.jp)
    for allowed_domain in allowed_domains_lower:
        if domain.endswith('.' + allowed_domain):
            return True, None

    return False, f"Domain '{domain}' is not in allowed domains: {', '.join(allowed_domains)}"


def validate_student_access(
    email: str,
    student_allowed: bool
) -> Tuple[bool, Optional[str]]:
    """
    Validate student account access

    Args:
        email: Email address to check
        student_allowed: Whether students are allowed for this project

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not student_allowed and is_student_email(email):
        return False, "Student accounts are not allowed for this project"

    return True, None


def validate_admin_access(
    email: str,
    admin_emails: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    Validate admin-only access

    Args:
        email: Email address to check
        admin_emails: List of admin email addresses (empty list means no restriction)

    Returns:
        Tuple of (is_valid, error_message)
    """
    # If admin_emails is empty, no admin restriction
    if not admin_emails:
        return True, None

    # Check if email is in admin list (case-insensitive)
    admin_emails_lower = [e.lower() for e in admin_emails]
    if email.lower() in admin_emails_lower:
        return True, None

    return False, "Access restricted to administrators only"


def validate_group_membership(
    user_groups: List[str],
    required_groups: List[str],
    allowed_groups: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    Validate group membership requirements

    Args:
        user_groups: List of groups the user belongs to
        required_groups: Groups user must belong to (AND condition)
        allowed_groups: Groups user can belong to (OR condition)

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Convert to lowercase for comparison
    user_groups_lower = [g.lower() for g in user_groups]

    # Check required groups (user must be in ALL required groups)
    if required_groups:
        required_groups_lower = [g.lower() for g in required_groups]
        missing_groups = [
            g for g in required_groups_lower
            if g not in user_groups_lower
        ]
        if missing_groups:
            return False, f"User is not a member of required groups: {', '.join(missing_groups)}"

    # Check allowed groups (user must be in AT LEAST ONE allowed group)
    if allowed_groups:
        allowed_groups_lower = [g.lower() for g in allowed_groups]
        if not any(g in allowed_groups_lower for g in user_groups_lower):
            return False, f"User is not a member of any allowed groups: {', '.join(allowed_groups)}"

    return True, None


def validate_user_access(
    email: str,
    project_config: Dict[str, Any],
    user_groups: Optional[List[str]] = None
) -> Tuple[bool, str]:
    """
    Comprehensive user access validation

    Args:
        email: User's email address
        project_config: Project configuration dictionary
        user_groups: Optional list of user's groups

    Returns:
        Tuple of (is_valid, error_message)
        If valid, error_message will be empty string

    Raises:
        Various AuthError exceptions based on validation failure
    """
    # 1. Domain validation
    is_valid, error_msg = validate_domain(
        email,
        project_config.get('allowed_domains', [])
    )
    if not is_valid:
        raise InvalidDomainError(
            extract_domain(email),
            project_config.get('allowed_domains', [])
        )

    # 2. Student account validation
    is_valid, error_msg = validate_student_access(
        email,
        project_config.get('student_allowed', True)
    )
    if not is_valid:
        raise StudentNotAllowedError(email)

    # 3. Admin-only validation
    is_valid, error_msg = validate_admin_access(
        email,
        project_config.get('admin_emails', [])
    )
    if not is_valid:
        raise AdminOnlyError(email)

    # 4. Group membership validation (if groups provided)
    if user_groups is not None:
        is_valid, error_msg = validate_group_membership(
            user_groups,
            project_config.get('required_groups', []),
            project_config.get('allowed_groups', [])
        )
        if not is_valid:
            if 'required' in error_msg:
                raise GroupMembershipRequiredError(
                    project_config.get('required_groups', [])
                )
            else:
                raise NoMatchingGroupError(
                    project_config.get('allowed_groups', [])
                )

    logger.info(f"User {email} passed all validation checks")
    return True, ""


def validate_redirect_uri(
    redirect_uri: str,
    allowed_uris: List[str]
) -> bool:
    """
    Validate redirect URI against allowed URIs

    Args:
        redirect_uri: URI to validate
        allowed_uris: List of allowed URIs

    Returns:
        True if URI is allowed
    """
    # Normalize URIs for comparison
    redirect_uri = redirect_uri.lower().rstrip('/')

    for allowed_uri in allowed_uris:
        allowed_uri = allowed_uri.lower().rstrip('/')

        # Exact match
        if redirect_uri == allowed_uri:
            return True

        # Allow subdirectory matches
        if redirect_uri.startswith(allowed_uri + '/'):
            return True

    return False