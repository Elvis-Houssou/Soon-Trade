from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import get_session

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    status: str


class ReadinessStatus(BaseModel):
    status: str
    database: str


@router.get("")
def liveness() -> HealthStatus:
    """Le processus répond. Ne touche à aucune dépendance."""
    return HealthStatus(status="ok")


@router.get("/ready", responses={503: {"model": ReadinessStatus}})
def readiness(session: Annotated[Session, Depends(get_session)], response: Response) -> ReadinessStatus:
    """L'API peut servir du trafic : la base répond."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessStatus(status="unavailable", database="down")
    return ReadinessStatus(status="ok", database="up")
