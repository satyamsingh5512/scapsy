from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select

from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole
from app.security.passwords import hash_password


async def seed_admin() -> int:
    settings = get_settings()
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL") or settings.bootstrap_admin_email
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or settings.bootstrap_admin_password
    if not email or not password:
        print("BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD are required.")
        return 1

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email.lower()))
        existing = result.scalar_one_or_none()
        if existing:
            print("Admin user already exists.")
            return 0

        user = User(
            email=email.lower(),
            role=UserRole.admin,
            password_hash=hash_password(password),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print("Admin user created.")
        return 0


def main() -> None:
    raise SystemExit(asyncio.run(seed_admin()))


if __name__ == "__main__":
    main()
