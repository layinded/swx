"""
Control FastAPI Project - User API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()


# Models
class User(BaseModel):
    id: Optional[int] = None
    email: str
    username: str
    is_active: bool = True


class UserCreate(BaseModel):
    email: str
    username: str
    password: str


class UserUpdate(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


# In-memory storage
users_db: List[User] = []
user_id_counter = 1


@router.get("/users", response_model=List[User])
async def list_users():
    return users_db


@router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    for user in users_db:
        if user.id == user_id:
            return user
    raise HTTPException(status_code=404, detail="User not found")


@router.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate):
    global user_id_counter
    new_user = User(
        id=user_id_counter,
        email=user.email,
        username=user.username
    )
    users_db.append(new_user)
    user_id_counter += 1
    return new_user


@router.put("/users/{user_id}", response_model=User)
async def update_user(user_id: int, user: UserUpdate):
    for existing in users_db:
        if existing.id == user_id:
            if user.email is not None:
                existing.email = user.email
            if user.username is not None:
                existing.username = user.username
            if user.is_active is not None:
                existing.is_active = user.is_active
            return existing
    raise HTTPException(status_code=404, detail="User not found")


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int):
    for i, user in enumerate(users_db):
        if user.id == user_id:
            users_db.pop(i)
            return
    raise HTTPException(status_code=404, detail="User not found")
