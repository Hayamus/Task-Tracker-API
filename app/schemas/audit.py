from enum import Enum
from pydantic import BaseModel
from typing import Optional

class AuditAction(str, Enum):
    USER_REGISTERED = "USER_REGISTERED"
    USER_DELETED = "USER_DELETED"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    
    TEAM_CREATED = "TEAM_CREATED"
    TEAM_DELETED = "TEAM_DELETED"
    TEAM_UPDATED = "TEAM_UPDATED"
    
    MEMBER_ADDED = "MEMBER_ADDED"
    MEMBER_REMOVED = "MEMBER_REMOVED"
    MEMBER_ROLE_CHANGED = "MEMBER_ROLE_CHANGED"

    TASK_CREATED = "TASK_CREATED"
    TASK_UPDATED = "TASK_UPDATED"
    TASK_DELETED = "TASK_DELETED"
    TASK_COMPLETED = "TASK_COMPLETED"

class AuditLog(BaseModel):
    user_id: int
    username: str
    action: AuditAction
    target_type: str
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    ip_address: str
    limit: Optional[int] = None
    offset: Optional[int] = None

class AuditFilterParams(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: Optional[AuditAction] = None
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    ip_address: Optional[str] = None
    limit: Optional[int] = 50
    offset: Optional[int] = 0