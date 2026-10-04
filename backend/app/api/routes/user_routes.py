from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user, get_user_service, require_admin
from app.models.users import User
from app.schemas.user_schema import UserCreateRequest, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    user_data: UserCreateRequest,
    service: UserService = Depends(get_user_service),
    _: User = Depends(require_admin),
):
    """Legacy user creation. Prefer /auth/register for customers and /auth/invite for agents."""
    try:
        return service.create_user(user_data)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
    _: User = Depends(get_current_user),
):
    user = service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

    

