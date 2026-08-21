from fastapi import APIRouter, Depends, HTTPException, status

from backend.models.auth import AuthResponse, GoogleLoginRequest, LoginRequest, ModInvitePublic, ModInviteRequest, UserCreateRequest, UserPublic, UserRoleUpdateRequest, UserStatusUpdateRequest
from backend.services.auth_service import current_user, get_auth_store, issue_token, require_roles, verify_google

router = APIRouter(prefix="/auth", tags=["authentication"])

def _response(user: UserPublic) -> AuthResponse: return AuthResponse(access_token=issue_token(user), user=user)

@router.get("/google/config")
def google_config() -> dict[str, str | bool]:
    """A Google OAuth client ID is public; expose it so Vite needn't embed env values."""
    from backend.config import get_settings
    client_id = get_settings().google_oauth_client_id.strip()
    return {"enabled": bool(client_id), "client_id": client_id}

@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    user = get_auth_store().login_password(str(payload.email), payload.password)
    if not user: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng.")
    return _response(user)

@router.post("/google", response_model=AuthResponse)
def google_login(payload: GoogleLoginRequest) -> AuthResponse:
    subject, email, name = verify_google(payload.credential)
    try:
        user = get_auth_store().login_google(subject, email, name, payload.password)
    except ValueError as exc:
        if str(exc) == "CREATE_PASSWORD_REQUIRED":
            raise HTTPException(status_code=428, detail="Hãy tạo mật khẩu có ít nhất 8 ký tự để hoàn tất tài khoản.") from exc
        raise
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email Google này chưa nhận được lời mời từ Admin.") from exc
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản Google này chưa được Admin cấp quyền hoặc đã bị vô hiệu hoá.")
    return _response(user)

@router.get("/me", response_model=UserPublic)
def me(user: UserPublic = Depends(current_user)) -> UserPublic: return user

@router.get("/users", response_model=list[UserPublic])
def users(_: UserPublic = Depends(require_roles("admin"))) -> list[UserPublic]: return get_auth_store().list_users()

@router.post("/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreateRequest, admin: UserPublic = Depends(require_roles("admin"))) -> UserPublic:
    try: return get_auth_store().create_user(email=str(payload.email), display_name=payload.display_name, role=payload.role, password=payload.password, created_by=admin.user_id)
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.get("/mod-invites", response_model=list[ModInvitePublic])
def mod_invites(_: UserPublic = Depends(require_roles("admin"))) -> list[ModInvitePublic]:
    return get_auth_store().list_mod_invites()

@router.post("/mod-invites", response_model=ModInvitePublic, status_code=status.HTTP_201_CREATED)
def invite_mod(payload: ModInviteRequest, admin: UserPublic = Depends(require_roles("admin"))) -> ModInvitePublic:
    try:
        return get_auth_store().invite_mod(payload.email, admin.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.delete("/mod-invites/{email}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mod_invite(email: str, _: UserPublic = Depends(require_roles("admin"))) -> None:
    if not get_auth_store().delete_mod_invite(email):
        raise HTTPException(status_code=404, detail="Không tìm thấy lời mời đang chờ.")

@router.patch("/users/{user_id}/role", response_model=UserPublic)
def update_role(user_id: str, payload: UserRoleUpdateRequest, _: UserPublic = Depends(require_roles("admin"))) -> UserPublic:
    from uuid import UUID
    try: return get_auth_store().update_role(UUID(user_id), payload.role)
    except KeyError as exc: raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.") from exc
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.patch("/users/{user_id}/status", response_model=UserPublic)
def update_status(user_id: str, payload: UserStatusUpdateRequest, _: UserPublic = Depends(require_roles("admin"))) -> UserPublic:
    from uuid import UUID
    try: return get_auth_store().update_status(UUID(user_id), payload.is_active)
    except KeyError as exc: raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.") from exc
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, admin: UserPublic = Depends(require_roles("admin"))) -> None:
    from uuid import UUID
    try:
        target = UUID(user_id)
        if target == admin.user_id:
            raise HTTPException(status_code=409, detail="Không thể tự xóa tài khoản đang đăng nhập.")
        get_auth_store().delete_user(target)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
