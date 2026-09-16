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

    async def get_audit(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        action: Optional[AuditAction] = None,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        query = "SELECT * FROM audit_logs WHERE TRUE"
        params = []
        if user_id is not None:
            query += " AND user_id = $%d" % (len(params) + 1)
            params.append(user_id)
        if username is not None:
            query += " AND username = $%d" % (len(params) + 1)
            params.append(username)
        if action is not None:
            query += " AND action = $%d" % (len(params) + 1)
            params.append(action.value)
        if target_type is not None:
            query += " AND target_type = $%d" % (len(params) + 1)
            params.append(target_type)
        if target_id is not None:
            query += " AND target_id = $%d" % (len(params) + 1)
            params.append(target_id)
        if ip_address is not None:
            query += " AND ip_address = $%d" % (len(params) + 1)
            params.append(ip_address)

        query += " ORDER BY created_at DESC LIMIT $%d OFFSET $%d" % (len(params) + 1, len(params) + 2)
        params.extend([limit, offset])

        rows = await self.conn.fetch(query, *params)
        return [dict(row) for row in rows]