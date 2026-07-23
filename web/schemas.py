# web/schemas.py — B-3 统一 API 响应模型
from pydantic import BaseModel
from datetime import datetime
from typing import Any


class APIResponse(BaseModel):
    success: bool
    data: Any | None = None
    message: str = ""
    timestamp: str = ""

    @classmethod
    def ok(cls, data=None, message: str = "ok") -> "APIResponse":
        return cls(
            success=True, data=data, message=message,
            timestamp=datetime.now().isoformat(),
        )

    @classmethod
    def fail(cls, message: str = "error") -> "APIResponse":
        return cls(
            success=False, message=message,
            timestamp=datetime.now().isoformat(),
        )
