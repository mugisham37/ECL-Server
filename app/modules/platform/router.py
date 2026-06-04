from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from app.core.pagination import Page, PageMeta, PageParams
from app.core.security import hash_password, new_ulid
from app.dependencies import DbSession, PlatformAdmin
from app.modules.auth.models import User
from app.modules.platform.schemas import (
    CreatePlatformTenantRequest,
    PlatformTenantOut,
    PlatformTenantsResponse,
    PlatformUserOut,
    PlatformUsersResponse,
    UpdatePlatformTenantRequest,
    UpdatePlatformUserRequest,
)
from app.modules.tenants.models import Tenant, TenantMembership
from app.core.enums import MemberStatus, UserRole
from app.modules.auth.utils import unique_slug

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/tenants")
async def list_platform_tenants(
    db: DbSession,
    _admin: PlatformAdmin,
    params: PageParams = Depends(),
    status_filter: str | None = None,
) -> PlatformTenantsResponse:
    q = select(Tenant).where(Tenant.deleted_at.is_(None)).order_by(Tenant.created_at.desc())
    if status_filter:
        q = q.where(Tenant.status == status_filter)
    from sqlalchemy import func

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    offset = (params.page - 1) * params.per_page
    result = await db.execute(q.offset(offset).limit(params.per_page))
    tenants = result.scalars().all()
    data = [
        PlatformTenantOut(
            id=t.id,
            name=t.name,
            slug=t.slug,
            plan=t.plan,
            status=t.status,
            created_at=t.created_at,
        )
        for t in tenants
    ]
    pages = max(1, (total + params.per_page - 1) // params.per_page)
    return PlatformTenantsResponse(
        data=data,
        meta=PageMeta(
            total=total,
            page=params.page,
            per_page=params.per_page,
            pages=pages,
            has_next=params.page < pages,
            has_prev=params.page > 1,
        ),
    )


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def create_platform_tenant(
    body: CreatePlatformTenantRequest,
    db: DbSession,
    _admin: PlatformAdmin,
) -> dict[str, object]:
    slugs = {r[0] for r in (await db.execute(select(Tenant.slug))).all()}
    slug = await unique_slug(body.name, slugs)
    tenant = Tenant(id=new_ulid(), name=body.name, slug=slug, plan=body.plan)
    user = User(
        id=new_ulid(),
        email=body.admin_email.lower(),
        name=body.admin_name,
        hashed_password=hash_password("ChangeMe123!"),
        is_email_verified=False,
    )
    membership = TenantMembership(
        id=new_ulid(),
        user_id=user.id,
        tenant_id=tenant.id,
        role=UserRole.ADMINISTRATOR.value,
        status=MemberStatus.ACTIVE.value,
    )
    db.add_all([tenant, user, membership])
    return {"data": {"tenant_id": tenant.id, "user_id": user.id}, "message": "Tenant created."}


@router.patch("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def patch_platform_tenant(
    tenant_id: str,
    body: UpdatePlatformTenantRequest,
    db: DbSession,
    _admin: PlatformAdmin,
) -> None:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    t = result.scalar_one_or_none()
    if not t:
        from app.core.exceptions import ECLException

        raise ECLException("RESOURCE_NOT_FOUND", "Tenant not found.", 404)
    if body.name:
        t.name = body.name
    if body.plan:
        t.plan = body.plan
    if body.status:
        t.status = body.status


@router.get("/users")
async def list_platform_users(
    db: DbSession,
    _admin: PlatformAdmin,
    params: PageParams = Depends(),
) -> PlatformUsersResponse:
    from sqlalchemy import func

    q = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    offset = (params.page - 1) * params.per_page
    result = await db.execute(q.offset(offset).limit(params.per_page))
    users = result.scalars().all()
    data = [
        PlatformUserOut(
            id=u.id,
            name=u.name,
            email=u.email,
            is_active=u.is_active,
            is_platform_admin=u.is_platform_admin,
            last_login_at=u.last_login_at,
        )
        for u in users
    ]
    pages = max(1, (total + params.per_page - 1) // params.per_page)
    return PlatformUsersResponse(
        data=data,
        meta=PageMeta(
            total=total,
            page=params.page,
            per_page=params.per_page,
            pages=pages,
            has_next=params.page < pages,
            has_prev=params.page > 1,
        ),
    )


@router.patch("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def patch_platform_user(
    user_id: str,
    body: UpdatePlatformUserRequest,
    db: DbSession,
    _admin: PlatformAdmin,
) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        from app.core.exceptions import ECLException

        raise ECLException("RESOURCE_NOT_FOUND", "User not found.", 404)
    if body.is_active is not None:
        u.is_active = body.is_active
