from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.enums import UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    role: UserRole
