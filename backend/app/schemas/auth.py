from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.security import MAX_PASSWORD_LENGTH
from app.db.enums import UserRole


class LoginRequest(BaseModel):
    username: Annotated[str, StringConstraints(max_length=200)]
    # Capped so a huge body can't make Argon2 work on it; no minimum, old passwords still work.
    password: Annotated[str, StringConstraints(max_length=MAX_PASSWORD_LENGTH)]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    role: UserRole
