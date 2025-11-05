from fastapi import APIRouter, Depends, HTTPException

from core.config import users_table
from core.security import get_current_user


router = APIRouter(tags=["users"])


@router.get("/me")
def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user.get("sub"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "phone": current_user.get("phone_number", ""),
        "email_verified": current_user.get("email_verified", False),
        "token_use": current_user.get("token_use"),
    }


@router.get("/users/{user_id}")
def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    try:
        resp = users_table.get_item(Key={"userId": user_id})
        user_data = resp.get("Item", {})
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        if current_user.get("sub") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return user_data
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to retrieve user: {str(e)}")


