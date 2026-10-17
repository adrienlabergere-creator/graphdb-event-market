"""Pagination shared by the list endpoints."""

from typing import Annotated, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel

T = TypeVar("T")


class Pagination(BaseModel):
    """`limit` (default 20, maximum 100) and `offset` of a list endpoint."""

    limit: int
    offset: int


def pagination(limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0) -> Pagination:
    """Read the pagination query parameters."""
    return Pagination(limit=limit, offset=offset)


Page = Annotated[Pagination, Depends(pagination)]


def paginate(rows: list[T], page: Pagination) -> list[T]:
    """Return the requested slice of a list."""
    return rows[page.offset : page.offset + page.limit]
