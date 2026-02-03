"""Authentication routes"""

from fastapi import APIRouter, Request, Query, HTTPException, Header
from fastapi.responses import RedirectResponse
from typing import Optional
import logging
import urllib.parse

from app.config import settings
from app.core.oauth import google_oauth_handler
from app.core.jwt_handler import jwt_handler
from app.core.project_config import project_config_manager
from app.core.validators import validate_user_access, validate_redirect_uri
from app.core import validators  # Import validators module for is_student_email()
from app.core.firestore_client import firestore_manager
from app.core.workspace_admin import workspace_admin_client
from app.core.errors import ProjectNotFoundError
from app.models.schemas import UserInfo, ErrorResponse, TokenResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/login/{project_id}")
async def login(
    request: Request,
    project_id: str,
    redirect_uri: Optional[str] = Query(None),
    state: Optional[str] = Query(None)
):
    """
    Initiate OAuth login flow

    Args:
        request: FastAPI request
        project_id: Project identifier
        redirect_uri: Optional custom redirect URI
        state: Optional state parameter from client

    Returns:
        Redirect to Google OAuth
    """
    try:
        # Get project configuration
        project_config = await project_config_manager.get_project_config(project_id)

        # Validate redirect URI if provided
        if redirect_uri:
            allowed_uris = project_config.get('redirect_uris', [])
            if not validate_redirect_uri(redirect_uri, allowed_uris):
                # セキュリティ: 本番環境では許可URIリストを露出しない
                detail_msg = "Invalid redirect_uri"
                if settings.is_development:
                    detail_msg += f". Allowed URIs: {allowed_uris}"
                raise HTTPException(
                    status_code=400,
                    detail=detail_msg
                )

        # Store redirect_uri and state in session for later use
        if redirect_uri:
            request.session['client_redirect_uri'] = redirect_uri
        if state:
            request.session['client_state'] = state

        # Create Google OAuth authorization URL
        auth_url, oauth_state = await google_oauth_handler.create_authorization_url(
            request, project_id
        )

        logger.info(f"Initiating OAuth for project: {project_id}")
        return RedirectResponse(url=auth_url)

    except ProjectNotFoundError as e:
        logger.error(f"Project not found: {project_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/callback/{project_id}")
async def callback(
    request: Request,
    project_id: str,
    code: str = Query(...),
    state: str = Query(...)
):
    """
    Handle OAuth callback

    Args:
        request: FastAPI request
        project_id: Project identifier
        code: Authorization code from Google
        state: State token for CSRF protection

    Returns:
        Redirect to client with token
    """
    try:
        # Get project configuration
        project_config = await project_config_manager.get_project_config(project_id)

        # Handle OAuth callback and get user info
        user_info, _ = await google_oauth_handler.handle_callback(
            request, code, state, project_id
        )

        # グループと組織部門の情報を取得（設定されている場合のみ）
        # サービスアカウントを使用するため、ユーザーのaccess_tokenは不要
        user_groups = None
        user_org_unit = None

        # role_rulesでgroup_membershipが使われているかチェック
        role_rules = project_config.get('role_rules', [])
        needs_groups_for_role = any(
            rule.get('condition_type') == 'group_membership'
            for rule in role_rules
        ) if role_rules else False

        # プロジェクト設定にグループまたはOU検証が含まれている場合、またはrole_rulesでグループが必要な場合
        if (project_config.get('required_groups') or
            project_config.get('allowed_groups') or
            project_config.get('required_org_units') or
            project_config.get('allowed_org_units') or
            needs_groups_for_role):

            # サービスアカウントが初期化されているか確認
            if workspace_admin_client.is_initialized:
                try:
                    # グループ情報の取得（サービスアカウント使用）
                    # allowed_groups/required_groupsまたはrole_rulesでグループが必要な場合
                    if (project_config.get('required_groups') or
                        project_config.get('allowed_groups') or
                        needs_groups_for_role):
                        user_groups = await workspace_admin_client.get_user_groups(
                            user_info['email']
                        )
                        logger.info(f"Retrieved {len(user_groups)} groups for {user_info['email']}")

                    # 組織部門情報の取得（サービスアカウント使用）
                    if project_config.get('required_org_units') or project_config.get('allowed_org_units'):
                        user_org_unit = await workspace_admin_client.get_user_org_unit(
                            user_info['email']
                        )
                        logger.info(f"Retrieved org unit '{user_org_unit}' for {user_info['email']}")

                except Exception as e:
                    logger.warning(f"Failed to retrieve workspace info: {str(e)}")
                    # グループ・OU情報の取得に失敗した場合でも、検証は続行
                    # （空リスト/Noneとして扱われる）
            else:
                logger.warning("Workspace Admin client not initialized. Group/OU validation will be skipped.")

        # Validate user access with groups and org unit
        try:
            validate_user_access(
                user_info['email'],
                project_config,
                user_groups=user_groups,
                user_org_unit=user_org_unit
            )
        except Exception as e:
            # Log failed attempt with enhanced details
            # ドメイン抽出（バリデーション付き）
            domain = validators.extract_domain(user_info['email'])
            await firestore_manager.log_audit_event(
                event_type='login_failed',
                project_id=project_id,
                user_email=user_info['email'],
                details={
                    'reason': str(e),
                    'error_code': getattr(e, 'error_code', 'UNKNOWN'),
                    'domain': domain if domain else 'unknown',
                    'is_student': validators.is_student_email(user_info['email']),
                    'groups': user_groups,
                    'org_unit': user_org_unit
                },
                ip_address=request.client.host,
                user_agent=request.headers.get('user-agent')
            )
            raise

        # ロール判定（role_rulesが設定されている場合）
        user_role = None
        if role_rules:
            # priorityでソートしてルールを評価
            sorted_rules = sorted(role_rules, key=lambda r: r.get('priority', 999))
            for rule in sorted_rules:
                condition_type = rule.get('condition_type')
                role = rule.get('role')

                if not condition_type or not role:
                    continue

                matched = False

                if condition_type == 'default':
                    # デフォルトルールは常にマッチ
                    matched = True

                elif condition_type == 'group_membership':
                    # グループメンバーシップ判定
                    group_email = rule.get('group_email')
                    if group_email and user_groups:
                        # user_groupsはメールアドレスのリスト
                        matched = group_email.lower() in [g.lower() for g in user_groups]

                elif condition_type == 'email_pattern':
                    # メールパターンマッチ
                    import re
                    pattern = rule.get('email_pattern')
                    if pattern:
                        try:
                            matched = bool(re.match(pattern, user_info['email']))
                        except re.error:
                            logger.warning(f"Invalid regex pattern: {pattern}")

                elif condition_type == 'email_list':
                    # メールリストマッチ
                    email_list = rule.get('email_list', [])
                    matched = user_info['email'].lower() in [e.lower() for e in email_list]

                if matched:
                    user_role = role
                    logger.info(f"Role resolved: {user_info['email']} -> {user_role} (condition: {condition_type})")
                    break

            if not user_role:
                logger.warning(f"No matching role rule for {user_info['email']}")

        # Create JWT token with optional role claim
        token_expiry_days = project_config.get('token_expiry_days', settings.jwt_expiry_days)
        additional_claims = {}
        if user_role:
            additional_claims['role'] = user_role
        # Google OAuthから取得したpictureとsubも追加
        if user_info.get('picture'):
            additional_claims['picture'] = user_info['picture']
        if user_info.get('sub'):
            additional_claims['sub'] = user_info['sub']

        token = jwt_handler.create_token(
            email=user_info['email'],
            name=user_info['name'],
            project_id=project_id,
            expiry_days=token_expiry_days,
            additional_claims=additional_claims if additional_claims else None
        )

        # Log successful login with enhanced details
        domain = validators.extract_domain(user_info['email'])
        await firestore_manager.log_audit_event(
            event_type='login_success',
            project_id=project_id,
            user_email=user_info['email'],
            details={
                'name': user_info['name'],
                'domain': domain if domain else 'unknown',
                'is_student': validators.is_student_email(user_info['email']),
                'login_method': 'google_oauth',
                'token_expiry_days': project_config.get('token_expiry_days', 30),
                'groups': user_groups,
                'org_unit': user_org_unit,
                'role': user_role
            },
            ip_address=request.client.host,
            user_agent=request.headers.get('user-agent')
        )

        # Determine redirect URL (セッションから取得後、削除してクリーンアップ)
        client_redirect_uri = request.session.pop('client_redirect_uri', None)
        if not client_redirect_uri:
            # Use default redirect URI from project config
            redirect_uris = project_config.get('redirect_uris', [])
            if not redirect_uris:
                raise ValueError("No redirect_uris configured for project")
            client_redirect_uri = redirect_uris[0]

        # Get client state if provided (セッションから取得後、削除してクリーンアップ)
        client_state = request.session.pop('client_state', None)

        # Build redirect URL based on token delivery method
        token_delivery = project_config.get('token_delivery', 'query_param')

        if token_delivery == 'query_param':
            # Add token as query parameter
            params = {'token': token}
            if client_state:
                params['state'] = client_state

            separator = '&' if '?' in client_redirect_uri else '?'
            redirect_url = f"{client_redirect_uri}{separator}{urllib.parse.urlencode(params)}"

            return RedirectResponse(url=redirect_url)

        elif token_delivery == 'cookie':
            # Set token as HttpOnly cookie
            response = RedirectResponse(url=client_redirect_uri)
            response.set_cookie(
                key='auth_token',
                value=token,
                httponly=True,
                secure=settings.is_production,
                samesite='lax',
                max_age=token_expiry_days * 24 * 3600
            )
            if client_state:
                # Add state as query parameter even with cookie delivery
                separator = '&' if '?' in client_redirect_uri else '?'
                response.headers['Location'] = f"{client_redirect_uri}{separator}state={client_state}"

            return response

        else:
            raise ValueError(f"Unknown token delivery method: {token_delivery}")

    except ProjectNotFoundError as e:
        logger.error(f"Project not found: {project_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Callback error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/api/verify",
    response_model=UserInfo,
    responses={
        200: {
            "description": "Token is valid",
            "model": UserInfo
        },
        401: {
            "description": "Token is invalid or expired",
            "model": ErrorResponse
        }
    },
    summary="Verify JWT token",
    description="Verify the JWT token and return user information"
)
async def verify_token(
    token: Optional[str] = Query(None, description="JWT token from query parameter"),
    authorization: Optional[str] = Header(None, description="Authorization header (Bearer token)")
):
    """
    Verify JWT token

    Accepts token from either:
    - Query parameter: ?token=xxx
    - Authorization header: Bearer xxx

    Returns user information if token is valid.
    """
    # Get token from header or query parameter
    token_str: Optional[str] = None
    if authorization and authorization.startswith('Bearer '):
        token_str = authorization[7:]
    elif token:
        token_str = token

    if not token_str:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "AUTH_004",
                "detail": "No token provided",
                "message": "Authentication token is required"
            }
        )

    try:
        # Verify token
        payload = jwt_handler.verify_token(token_str)
        return UserInfo(
            email=payload['email'],
            name=payload['name'],
            project_id=payload['project_id'],
            exp=payload['exp'],
            valid=True
        )

    except Exception as e:
        logger.warning(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "AUTH_004",
                "detail": str(e),
                "message": "Invalid token"
            }
        )


@router.post(
    "/api/refresh",
    response_model=TokenResponse,
    responses={
        200: {
            "description": "Token refreshed successfully",
            "model": TokenResponse
        },
        401: {
            "description": "Token refresh failed",
            "model": ErrorResponse
        }
    },
    summary="Refresh JWT token",
    description="Refresh an existing JWT token with a new expiry time"
)
async def refresh_token(
    token: Optional[str] = Query(None, description="JWT token from query parameter"),
    expiry_days: Optional[int] = Query(None, description="New token expiry in days"),
    authorization: Optional[str] = Header(None, description="Authorization header (Bearer token)")
):
    """
    Refresh JWT token

    Accepts token from either:
    - Query parameter: ?token=xxx
    - Authorization header: Bearer xxx

    Returns a new token with updated expiry time.
    """
    # Get token from header or query parameter
    token_str: Optional[str] = None
    if authorization and authorization.startswith('Bearer '):
        token_str = authorization[7:]
    elif token:
        token_str = token

    if not token_str:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "AUTH_004",
                "detail": "No token provided",
                "message": "Authentication token is required"
            }
        )

    try:
        # Refresh token
        new_token = jwt_handler.refresh_token(token_str, expiry_days)
        expiry_time = jwt_handler.get_token_expiry(new_token)

        return TokenResponse(
            token=new_token,
            expiry=expiry_time.isoformat() if expiry_time else ""
        )

    except Exception as e:
        logger.warning(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "AUTH_005",
                "detail": str(e),
                "message": "Cannot refresh token"
            }
        )


@router.get("/logout")
async def logout(
    return_url: Optional[str] = Query(None)
):
    """
    Logout user

    Args:
        return_url: URL to return to after logout

    Returns:
        Redirect to Google logout
    """
    logout_url = google_oauth_handler.get_logout_url(return_url)
    return RedirectResponse(url=logout_url)