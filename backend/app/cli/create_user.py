"""Create a user account from the command line.

Run from backend/:
    uv run python -m app.cli.create_user admin "Admin Name" --admin
"""

import argparse
import getpass
import re

from sqlalchemy import select

from app.core.security import hash_password
from app.db.enums import UserRole
from app.db.models import User
from app.db.session import SessionFactory

MIN_PASSWORD_LENGTH = 12

# Same rule as the `users.username` CHECK; checked here first for a readable error.
USERNAME_PATTERN = re.compile(r"[a-z0-9._-]{3,50}")


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
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
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
