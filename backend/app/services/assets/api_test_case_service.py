"""APITestCase business logic (Phase 9): CRUD + AI-generation persistence."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models import APITestCase, Project
from app.schemas import ApiTestCaseCreate, ApiTestCaseUpdate


def _get(db: Session, api_case_id: int) -> APITestCase:
    api_case = db.get(APITestCase, api_case_id)
    if api_case is None:
        raise NotFoundError("API test case not found", {"id": api_case_id})
    return api_case


def list_api_test_cases(db: Session, project_id: int) -> list[APITestCase]:
    return list(
        db.scalars(
            select(APITestCase)
            .where(APITestCase.project_id == project_id)
            .order_by(APITestCase.id.desc())
        )
    )


def create_api_test_case(db: Session, project_id: int, data: ApiTestCaseCreate) -> APITestCase:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", {"id": project_id})
    if data.requirement_id is not None:
        from app.models import Requirement
        if db.get(Requirement, data.requirement_id) is None:
            raise NotFoundError("Requirement not found", {"id": data.requirement_id})

    api_case = APITestCase(
        project_id=project_id,
        requirement_id=data.requirement_id,
        name=data.name,
        method=data.method.value,
        url=data.url,
        headers=data.headers,
        body=data.body,
        assertions=[a.model_dump(mode="json", exclude_none=True) for a in data.assertions],
        status=data.status.value,
    )
    db.add(api_case)
    db.commit()
    db.refresh(api_case)
    return api_case


def get_api_test_case(db: Session, api_case_id: int) -> APITestCase:
    return _get(db, api_case_id)


def update_api_test_case(db: Session, api_case_id: int, data: ApiTestCaseUpdate) -> APITestCase:
    api_case = _get(db, api_case_id)
    fields = data.model_dump(exclude_unset=True, mode="json")

    if "assertions" in fields and fields["assertions"] is not None:
        if len(fields["assertions"]) == 0:
            raise ValidationFailedError("assertions must not be empty", {"id": api_case_id})
        fields["assertions"] = [a.model_dump(mode="json", exclude_none=True) for a in data.assertions]
    if "method" in fields and fields["method"] is not None:
        fields["method"] = data.method.value
    if "status" in fields and fields["status"] is not None:
        fields["status"] = data.status.value

    for field, value in fields.items():
        if value is not None or field in ("body", "headers"):
            setattr(api_case, field, value)
    db.commit()
    db.refresh(api_case)
    return api_case


def delete_api_test_case(db: Session, api_case_id: int) -> None:
    api_case = _get(db, api_case_id)
    db.delete(api_case)
    db.commit()


def create_from_generated(
    db: Session, project_id: int, requirement_id: int | None, items: list[dict]
) -> tuple[list[APITestCase], list[str]]:
    """Persist AI-generated API test cases (assertions already validated).

    B-1: dedupe against the project's existing active cases by (method, url, name)
    and against the current batch — duplicates are skipped with a warning (aligning
    with the other AI agents). Returns ``(created, warnings)``.
    """
    def _key(item: dict) -> tuple[str, str, str]:
        return (
            item["method"].upper(),
            item["url"].strip(),
            item["name"].strip().lower(),
        )

    existing = {
        _key({"method": c.method, "url": c.url, "name": c.name})
        for c in db.scalars(
            select(APITestCase).where(
                APITestCase.project_id == project_id,
                APITestCase.status == "active",
            )
        )
    }

    created: list[APITestCase] = []
    warnings: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = _key(item)
        if key in existing or key in seen:
            warnings.append(f"与已有接口用例重复，已跳过：{item['name']}")
            continue
        seen.add(key)
        api_case = APITestCase(
            project_id=project_id,
            requirement_id=requirement_id,
            name=item["name"],
            method=item["method"],
            url=item["url"],
            headers=item.get("headers") or {},
            body=item.get("body"),
            assertions=item["assertions"],
            status="active",
        )
        db.add(api_case)
        created.append(api_case)
    db.commit()
    for api_case in created:
        db.refresh(api_case)
    return created, warnings
