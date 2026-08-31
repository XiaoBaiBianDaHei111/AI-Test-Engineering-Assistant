"""Seed demo data: Demo project + Golden PRD (login + task management).

Creates a demo project, the structured requirements derived from the Golden PRD,
and a handful of sample test cases (with steps). Idempotent: re-running is safe.

Usage (from the ``backend/`` directory):

    python scripts/seed.py
    # or inside Docker:
    docker compose exec backend python scripts/seed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Project  # noqa: E402
from app.schemas import ProjectCreate, RequirementCreate, TestCaseCreate  # noqa: E402
from app.services.assets import (  # noqa: E402
    project_service,
    requirement_service,
    test_case_service,
)

DEMO_PROJECT_NAME = "Demo — 登录与任务管理"
PRD_DOC_REF = "scripts/fixtures/golden_prd.md"


def seed(db) -> None:
    existing = db.scalar(select(Project).where(Project.name == DEMO_PROJECT_NAME))
    if existing is not None:
        print(f"[seed] demo project already exists (id={existing.id}); nothing to do.")
        return

    project = project_service.create_project(
        db,
        ProjectCreate(
            name=DEMO_PROJECT_NAME,
            description="Golden PRD：登录 + 任务管理演示项目（用于后续 Phase 演示与测试）",
        ),
    )

    login_req = requirement_service.create_requirement(
        db,
        project.id,
        RequirementCreate(
            title="用户登录",
            description="用户通过用户名和密码登录系统。",
            acceptance_criteria=[
                "登录成功后跳转到任务列表页",
                "用户名或密码错误时提示「用户名或密码错误」",
                "用户名或密码为空时提示必填",
                "连续 5 次登录失败后锁定账号 10 分钟",
                "用户不存在时提示「用户不存在」",
            ],
            risks=["密码暴力破解"],
            gaps=["锁定策略的解锁方式未明确"],
            ambiguities=["错误提示文案未统一"],
            status="confirmed",
            source="manual",
            doc_ref=PRD_DOC_REF,
        ),
    )

    task_req = requirement_service.create_requirement(
        db,
        project.id,
        RequirementCreate(
            title="任务管理",
            description="登录后对任务进行查看、创建、编辑、删除与状态流转。",
            acceptance_criteria=[
                "可查看任务列表（标题、状态、优先级、创建时间）",
                "创建任务：标题必填，优先级默认「中」",
                "可编辑任务标题与优先级",
                "删除任务前需二次确认",
                "可将任务标记为「完成」",
                "支持按状态过滤任务（全部/待办/完成）",
            ],
            status="confirmed",
            source="manual",
            doc_ref=PRD_DOC_REF,
        ),
    )

    test_case_service.create_test_case(
        db,
        project.id,
        TestCaseCreate(
            title="登录成功跳转任务列表",
            case_id="TC-001",
            priority="P0",
            type="functional",
            requirement_id=login_req.id,
            precondition="已注册一个有效账号",
            steps=[
                {"step_number": 1, "action": "打开登录页", "expected_result": "显示用户名和密码输入框"},
                {"step_number": 2, "action": "输入正确的用户名和密码", "expected_result": "输入框接受输入"},
                {"step_number": 3, "action": "点击登录按钮", "expected_result": "跳转到任务列表页"},
            ],
            expected_result="登录成功并进入任务列表页",
        ),
    )

    test_case_service.create_test_case(
        db,
        project.id,
        TestCaseCreate(
            title="错误密码登录失败",
            case_id="TC-002",
            priority="P0",
            type="exception",
            requirement_id=login_req.id,
            precondition="已注册一个有效账号",
            steps=[
                {"step_number": 1, "action": "打开登录页", "expected_result": "显示登录表单"},
                {"step_number": 2, "action": "输入正确用户名和错误密码", "expected_result": "输入框接受输入"},
                {"step_number": 3, "action": "点击登录按钮", "expected_result": "提示「用户名或密码错误」且停留在登录页"},
            ],
            expected_result="提示错误信息且不跳转",
        ),
    )

    test_case_service.create_test_case(
        db,
        project.id,
        TestCaseCreate(
            title="创建任务成功",
            case_id="TC-003",
            priority="P1",
            type="functional",
            requirement_id=task_req.id,
            precondition="已登录",
            steps=[
                {"step_number": 1, "action": "在任务列表页点击「新建任务」", "expected_result": "显示新建表单"},
                {"step_number": 2, "action": "填写标题并提交", "expected_result": "任务出现在列表中"},
            ],
            expected_result="新任务出现在任务列表",
        ),
    )

    print("[seed] created:")
    print(f"  project     : {project.name} (id={project.id})")
    print(f"  requirement : {login_req.title}")
    print(f"  requirement : {task_req.title}")
    print("  test cases  : TC-001, TC-002, TC-003")
    print(f"  golden prd  : {PRD_DOC_REF}")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
