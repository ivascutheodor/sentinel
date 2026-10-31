from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints, model_validator

from app.core.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, USERNAME_PATTERN
from app.db.enums import UserRole
from app.schemas.auth import UserResponse


def _normalize_username(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


# Normalized like the login does, *before* the pattern (StringConstraints checks it first).
Username = Annotated[
    str,
    BeforeValidator(_normalize_username),
    StringConstraints(pattern=USERNAME_PATTERN.pattern),
]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
# Not stripped: spaces are allowed in passwords and must not be silently removed.
NewPassword = Annotated[
    str, StringConstraints(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
]


class UserAdminResponse(UserResponse):
    """What an admin sees in the user list; never the password hash."""

    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Username
    display_name: DisplayName
    role: UserRole = UserRole.USER
    password: NewPassword  # a temporary password the admin passes on to the person


class UserUpdate(BaseModel):
    """Only the fields sent are changed; none of them may be null."""

    model_config = ConfigDict(extra="forbid")

    display_name: DisplayName | None = None
    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def no_nulls(self) -> Self:
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Fields cannot be set to null; leave them out instead.")
        return self


class PasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: NewPassword


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: Annotated[str, StringConstraints(max_length=MAX_PASSWORD_LENGTH)]
    new_password: NewPassword

    @model_validator(mode="after")
    def must_differ(self) -> Self:
        if self.new_password == self.current_password:
            raise ValueError("The new password must differ from the current one.")
        return self
