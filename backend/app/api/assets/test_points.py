"""TestPoint endpoints.

  GET/POST         /requirements/{requirement_id}/test-points
  GET/PATCH/DELETE /test-points/{test_point_id}
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import TestPointCreate, TestPointRead, TestPointUpdate
from app.services.assets import test_point_service

router = APIRouter()


@router.get(
    "/requirements/{requirement_id}/test-points", response_model=list[TestPointRead]
)
def list_test_points(requirement_id: int, db: Session = Depends(get_db)) -> list:
    test_point_service.get_requirement_or_404(db, requirement_id)
    return test_point_service.list_test_points(db, requirement_id)


@router.post(
    "/requirements/{requirement_id}/test-points",
    response_model=TestPointRead,
    status_code=status.HTTP_201_CREATED,
)
def create_test_point(
    requirement_id: int, payload: TestPointCreate, db: Session = Depends(get_db)
):
    test_point_service.get_requirement_or_404(db, requirement_id)
    return test_point_service.create_test_point(db, requirement_id, payload)


@router.get("/test-points/{test_point_id}", response_model=TestPointRead)
def get_test_point(test_point_id: int, db: Session = Depends(get_db)):
    return test_point_service.get_test_point_or_404(db, test_point_id)


@router.patch("/test-points/{test_point_id}", response_model=TestPointRead)
def update_test_point(
    test_point_id: int, payload: TestPointUpdate, db: Session = Depends(get_db)
):
    test_point = test_point_service.get_test_point_or_404(db, test_point_id)
    return test_point_service.update_test_point(db, test_point, payload)


@router.delete("/test-points/{test_point_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_point(test_point_id: int, db: Session = Depends(get_db)):
    test_point = test_point_service.get_test_point_or_404(db, test_point_id)
    test_point_service.delete_test_point(db, test_point)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
