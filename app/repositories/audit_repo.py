import asyncpg
from typing import Optional, Dict, Any
from app.schemas.audit import AuditAction

class AuditRepository:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def log_action(
        self,
        user_id: Optional[int],
        username: Optional[str],
        action: AuditAction,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        target_name: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        try:
            await self.conn.execute(
                """
                INSERT INTO audit_logs (
                    user_id, username, action, target_type, target_id,
                    target_name, changes, ip_address, user_agent, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                """,
                user_id,
                username,
                action.value,
                target_type,
                target_id,
                target_name,
                changes,
                ip_address,
                user_agent
            )
        except Exception as e:
            print(f"Failed to write audit log: {e}")