"""Create a user account from the command line.

Run from backend/:
    uv run python -m app.cli.create_user admin "Admin Name" --admin
"""

import argparse
import getpass

from sqlalchemy import select

from app.core.security import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    USERNAME_PATTERN,
    hash_password,
)
from app.db.enums import UserRole
from app.db.models import User
from app.db.session import SessionFactory


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Sentinel user account.")
    parser.add_argument("username")
    parser.add_argument("display_name")
    parser.add_argument("--admin", action="store_true", help="give the account the admin role")
    args = parser.parse_args()

    username = args.username.strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise SystemExit("Username must be 3-50 characters: letters, digits, '.', '_' or '-'.")

    password = getpass.getpass("Password: ")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise SystemExit(
            f"Password must be {MIN_PASSWORD_LENGTH} to {MAX_PASSWORD_LENGTH} characters."
        )
    if getpass.getpass("Repeat password: ") != password:
        raise SystemExit("Passwords do not match.")

    with SessionFactory() as session:
        if session.scalar(select(User).where(User.username == username)) is not None:
            raise SystemExit(f"A user named {username!r} already exists.")
        session.add(
            User(
                username=username,
                display_name=args.display_name.strip(),
                password_hash=hash_password(password),
                role=UserRole.ADMIN if args.admin else UserRole.USER,
            )
        )
        session.commit()

    print(f"Created {'admin' if args.admin else 'user'} {username}.")


if __name__ == "__main__":
    main()
