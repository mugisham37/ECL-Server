from typing import Generic, TypeVar

from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=200)
    sort: str | None = None
    order: str = "asc"
    search: str | None = None


class PageMeta(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool


class Page(BaseModel, Generic[T]):
    data: list[T]
    meta: PageMeta


async def paginate(
    session: AsyncSession,
    query: Select[tuple[T]],
    params: PageParams,
) -> Page[T]:
    count_q = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    offset = (params.page - 1) * params.per_page
    items_q = query.offset(offset).limit(params.per_page)
    result = await session.execute(items_q)
    items = list(result.scalars().all())

    pages = max(1, (total + params.per_page - 1) // params.per_page)
    return Page(
        data=items,
        meta=PageMeta(
            total=total,
            page=params.page,
            per_page=params.per_page,
            pages=pages,
            has_next=params.page < pages,
            has_prev=params.page > 1,
        ),
    )
