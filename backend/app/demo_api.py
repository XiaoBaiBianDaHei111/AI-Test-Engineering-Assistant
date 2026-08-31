"""Deterministic demo API (Phase 9, canned responses).

Stable target for API test-cases; credentials match the demo SPA
(testuser / Test@1234). Deterministic: same input -> same output.
"""

import time

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/demo-api", tags=["demo-api"])

_VALID_USERNAME = "testuser"
_VALID_PASSWORD = "Test@1234"


class LoginBody(BaseModel):
    username: str | None = None
    password: str | None = None


@router.post("/login")
def login(body: LoginBody | None = None):
    if body is None or body.username is None or body.password is None:
        return JSONResponse({"message": "参数缺失"}, status_code=400)

    if body.username != _VALID_USERNAME or body.password != _VALID_PASSWORD:
        return JSONResponse({"message": "用户名或密码错误"}, status_code=401)

    return JSONResponse({
        "token": f"demo-token-{int(time.time())}",
        "user": {"username": body.username, "role": "tester"},
    }, status_code=200)


@router.get("/tasks")
def list_tasks(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        return JSONResponse({"message": "未授权"}, status_code=401)
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return JSONResponse({"message": "未授权"}, status_code=401)
    return JSONResponse({"tasks": []}, status_code=200)
