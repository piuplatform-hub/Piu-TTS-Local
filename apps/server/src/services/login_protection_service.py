"""
Application-Level Login Protection & Rate Limiting Service
Protects against brute-force attacks and password spraying without hardcoded IP lockouts.
Multi-process safe via SQLite transaction-backed attempt records.
"""

from datetime import datetime, timezone, timedelta
import math
from typing import Optional, Tuple
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.errors import AppException
from ..models.login_attempt import LoginAttemptRecord


class LoginProtectionService:
    @staticmethod
    async def check_rate_limit(
        db: AsyncSession,
        ip_address: str,
        username: str,
    ) -> Tuple[bool, int]:
        """
        Checks whether the given IP or username is currently rate-limited.
        Returns: (is_limited: bool, retry_after_seconds: int)
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=settings.LOGIN_LOCKOUT_WINDOW_MINUTES)
        normalized_user = username.strip().lower()

        # 1. Check failed attempts for this username within window
        stmt_user = (
            select(func.count(LoginAttemptRecord.id), func.max(LoginAttemptRecord.attempted_at))
            .where(
                func.lower(LoginAttemptRecord.username) == normalized_user,
                LoginAttemptRecord.attempted_at >= window_start,
                LoginAttemptRecord.success == False,
            )
        )
        res_user = await db.execute(stmt_user)
        user_count, user_last_attempt = res_user.first() or (0, None)

        if user_count >= settings.LOGIN_MAX_FAILED_ATTEMPTS_USER and user_last_attempt:
            # Calculate remaining seconds in lockout window
            # Ensure timezone awareness
            if user_last_attempt.tzinfo is None:
                user_last_attempt = user_last_attempt.replace(tzinfo=timezone.utc)
            lockout_expiry = user_last_attempt + timedelta(minutes=settings.LOGIN_LOCKOUT_WINDOW_MINUTES)
            remaining_seconds = max(1, math.ceil((lockout_expiry - now).total_seconds()))
            return True, remaining_seconds

        # 2. Check failed attempts for this IP within window (spraying protection)
        stmt_ip = (
            select(func.count(LoginAttemptRecord.id), func.max(LoginAttemptRecord.attempted_at))
            .where(
                LoginAttemptRecord.ip_address == ip_address,
                LoginAttemptRecord.attempted_at >= window_start,
                LoginAttemptRecord.success == False,
            )
        )
        res_ip = await db.execute(stmt_ip)
        ip_count, ip_last_attempt = res_ip.first() or (0, None)

        if ip_count >= settings.LOGIN_MAX_FAILED_ATTEMPTS_IP and ip_last_attempt:
            if ip_last_attempt.tzinfo is None:
                ip_last_attempt = ip_last_attempt.replace(tzinfo=timezone.utc)
            lockout_expiry = ip_last_attempt + timedelta(minutes=settings.LOGIN_LOCKOUT_WINDOW_MINUTES)
            remaining_seconds = max(1, math.ceil((lockout_expiry - now).total_seconds()))
            return True, remaining_seconds

        return False, 0

    @staticmethod
    async def record_attempt(
        db: AsyncSession,
        ip_address: str,
        username: str,
        success: bool,
    ) -> None:
        """
        Records login attempt outcome. On success, clears historical failed attempts for the user/ip.
        """
        now = datetime.now(timezone.utc)
        normalized_user = username.strip().lower()

        if success:
            # On successful login, clear failed history to reset lock count
            del_stmt = delete(LoginAttemptRecord).where(
                func.lower(LoginAttemptRecord.username) == normalized_user,
            )
            await db.execute(del_stmt)
            await db.commit()
        else:
            # Record failed attempt
            attempt = LoginAttemptRecord(
                ip_address=ip_address,
                username=normalized_user,
                attempted_at=now,
                success=False,
            )
            db.add(attempt)
            await db.commit()

        # Opportunistic background cleanup of attempts older than 24h
        cutoff = now - timedelta(hours=24)
        clean_stmt = delete(LoginAttemptRecord).where(LoginAttemptRecord.attempted_at < cutoff)
        await db.execute(clean_stmt)
        await db.commit()
