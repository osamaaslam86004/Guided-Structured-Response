# auth.py
# This file contains the authentication logic for the FastAPI application. 
# It includes a dependency function to retrieve the current authenticated user from the session.

from fastapi import HTTPException, Request
from sqlalchemy import select

from database import AsyncSessionLocal, UserDB


async def get_current_user(
    request: Request,
) -> UserDB:

    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(UserDB).where(
                UserDB.id == user_id
            )
        )

        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=401,
                detail="User no longer exists",
            )

        return user