"""Validation functions for authentication"""

import re
from typing import Tuple, Optional, List, Dict, Any
import logging

from app.core.errors import (
    InvalidDomainError,
    StudentNotAllowedError,
    AdminOnlyError,
    GroupMembershipRequiredError,
    NoMatchingGroupError,
    OrgUnitMembershipRequiredError,
    NoMatchingOrgUnitError
)

logger = logging.getLogger(__name__)

# 基本的なメールアドレス形式の正規表現
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def is_valid_email(email: str) -> bool:
    """
    Validate basic email format

    Args:
        email: Email address to validate

    Returns:
        True if email format is valid
    """
    if not email or not isinstance(email, str):
        return False
    return EMAIL_REGEX.match(email) is not None


def extract_domain(email: str) -> str:
    """
    Extract domain from email address

    Args:
        email: Email address

    Returns:
        Domain part of the email (empty string if invalid)
    """
    if not is_valid_email(email):
        logger.warning(f"Invalid email format: {email}")
        return ""
    return email.split('@')[1].lower()


def is_student_email(email: str) -> bool:
    """
    Check if email belongs to a student account

    情政府高校の学生メールパターン:
    - 7桁の学籍番号（数字のみ）@ドメイン（例: 1234567@i-seifu.jp）

    教職員メールパターン:
    - ローマ字を含むアカウント名（例: tanaka.taro@i-seifu.jp, yamada@i-seifu.jp）
    - 数字のみのアカウントは学生の学籍番号を意味するため、教職員には存在しない

    Args:
        email: Email address to check

    Returns:
        True if email appears to be a student account
    """
    if not is_valid_email(email):
        return False

    local_part = email.split('@')[0]

    # 7桁の学籍番号パターン（情政府高校固有）
    if re.match(r'^\d{7}$', local_part):
        logger.debug(f"Email {email} identified as student (7-digit student ID)")
        return True

    return False


def validate_domain(
    email: str,
    allowed_domains: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    Validate email domain against allowed domains

    セキュリティ: サブドメインは許可しない（完全一致のみ）
    例: i-seifu.jp は許可、sub.i-seifu.jp は拒否

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

    # 完全一致のみチェック（サブドメイン不許可）
    if domain in allowed_domains_lower:
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


def validate_org_unit_membership(
    user_org_unit: Optional[str],
    required_org_units: List[str],
    allowed_org_units: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    組織部門（OU）のメンバーシップ要件を検証

    Args:
        user_org_unit: ユーザーが属する組織部門パス（例: '/教職員/専任教員'）
        required_org_units: 必須の組織部門リスト（AND条件）
        allowed_org_units: 許可された組織部門リスト（OR条件）

    Returns:
        Tuple of (is_valid, error_message)
    """
    from app.core.workspace_admin import workspace_admin_client

    # ユーザーのOUが取得できない場合はチェックをスキップ
    if user_org_unit is None:
        if required_org_units or allowed_org_units:
            logger.warning("User org unit is None but OU validation is configured")
            return False, "Unable to retrieve user's organizational unit"
        return True, None

    # パスの正規化（末尾のスラッシュを削除）
    user_org_unit_normalized = user_org_unit.rstrip('/')

    # 必須OUチェック（ユーザーはすべての必須OUに属している必要がある）
    if required_org_units:
        missing_org_units = []
        for required_ou in required_org_units:
            if not workspace_admin_client.check_org_unit_hierarchy(
                user_org_unit_normalized,
                required_ou
            ):
                missing_org_units.append(required_ou)

        if missing_org_units:
            return False, f"User is not a member of required organizational units: {', '.join(missing_org_units)}"

    # 許可されたOUチェック（ユーザーは少なくとも1つの許可されたOUに属している必要がある）
    if allowed_org_units:
        is_member_of_allowed = False
        for allowed_ou in allowed_org_units:
            if workspace_admin_client.check_org_unit_hierarchy(
                user_org_unit_normalized,
                allowed_ou
            ):
                is_member_of_allowed = True
                break

        if not is_member_of_allowed:
            return False, f"User is not a member of any allowed organizational units: {', '.join(allowed_org_units)}"

    return True, None


def validate_user_access(
    email: str,
    project_config: Dict[str, Any],
    user_groups: Optional[List[str]] = None,
    user_org_unit: Optional[str] = None
) -> Tuple[bool, str]:
    """
    包括的なユーザーアクセス検証

    Args:
        email: ユーザーのメールアドレス
        project_config: プロジェクト設定辞書
        user_groups: ユーザーが属するグループのリスト（オプション）
        user_org_unit: ユーザーが属する組織部門パス（オプション）

    Returns:
        Tuple of (is_valid, error_message)
        有効な場合、error_messageは空文字列

    Raises:
        検証失敗に基づく各種AuthErrorエラー
    """
    # 1. ドメイン検証
    is_valid, error_msg = validate_domain(
        email,
        project_config.get('allowed_domains', [])
    )
    if not is_valid:
        raise InvalidDomainError(
            extract_domain(email),
            project_config.get('allowed_domains', [])
        )

    # 2. 学生アカウント検証
    is_valid, error_msg = validate_student_access(
        email,
        project_config.get('student_allowed', True)
    )
    if not is_valid:
        raise StudentNotAllowedError(email)

    # 3. 管理者専用検証
    is_valid, error_msg = validate_admin_access(
        email,
        project_config.get('admin_emails', [])
    )
    if not is_valid:
        raise AdminOnlyError(email)

    # 4. グループメンバーシップ検証（グループが提供されている場合）
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

    # 5. 組織部門（OU）メンバーシップ検証（OUが提供されている場合）
    if user_org_unit is not None:
        is_valid, error_msg = validate_org_unit_membership(
            user_org_unit,
            project_config.get('required_org_units', []),
            project_config.get('allowed_org_units', [])
        )
        if not is_valid:
            if 'required' in error_msg:
                raise OrgUnitMembershipRequiredError(
                    project_config.get('required_org_units', [])
                )
            else:
                raise NoMatchingOrgUnitError(
                    project_config.get('allowed_org_units', [])
                )

    logger.info(f"User {email} passed all validation checks")
    return True, ""


def validate_redirect_uri(
    redirect_uri: str,
    allowed_uris: List[str]
) -> bool:
    """
    Validate redirect URI against allowed URIs

    セキュリティ: Open Redirect攻撃を防ぐため、スキーム・ホスト・ポートを厳密に検証

    Args:
        redirect_uri: URI to validate
        allowed_uris: List of allowed URIs

    Returns:
        True if URI is allowed
    """
    from urllib.parse import urlparse

    try:
        parsed_redirect = urlparse(redirect_uri)

        # スキームとホストが必須
        if not parsed_redirect.scheme or not parsed_redirect.netloc:
            logger.warning(f"Invalid redirect URI format: {redirect_uri}")
            return False

        # 正規化: スキーム://ホスト:ポート
        redirect_base = f"{parsed_redirect.scheme.lower()}://{parsed_redirect.netloc.lower()}"
        redirect_path = parsed_redirect.path.rstrip('/')

        for allowed_uri in allowed_uris:
            try:
                parsed_allowed = urlparse(allowed_uri)

                if not parsed_allowed.scheme or not parsed_allowed.netloc:
                    logger.warning(f"Invalid allowed URI format: {allowed_uri}")
                    continue

                allowed_base = f"{parsed_allowed.scheme.lower()}://{parsed_allowed.netloc.lower()}"
                allowed_path = parsed_allowed.path.rstrip('/')

                # スキーム・ホスト・ポートが一致
                if redirect_base != allowed_base:
                    continue

                # パスの検証（完全一致 または サブディレクトリ）
                if redirect_path == allowed_path:
                    logger.debug(f"Redirect URI matched (exact): {redirect_uri}")
                    return True

                # サブディレクトリマッチ（許可URIのパス配下）
                if allowed_path and redirect_path.startswith(allowed_path + '/'):
                    logger.debug(f"Redirect URI matched (subdirectory): {redirect_uri}")
                    return True

                # 許可URIがルートパス（/）の場合、全パスを許可
                if not allowed_path or allowed_path == '/':
                    logger.debug(f"Redirect URI matched (root path): {redirect_uri}")
                    return True

            except Exception as e:
                logger.error(f"Error parsing allowed URI '{allowed_uri}': {str(e)}")
                continue

        logger.warning(f"Redirect URI not in allowed list: {redirect_uri}")
        return False

    except Exception as e:
        logger.error(f"Error validating redirect URI '{redirect_uri}': {str(e)}")
        return False