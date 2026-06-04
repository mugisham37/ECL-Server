from fastapi import APIRouter

api_router = APIRouter()

# Module routers registered as they are implemented
def _register_routers() -> None:
    from app.modules.audit.router import router as audit_router
    from app.modules.auth.router import router as auth_router
    from app.modules.collateral.router import router as collateral_router
    from app.modules.invites.router import router as invites_router
    from app.modules.platform.router import router as platform_router
    from app.modules.segments.router import router as segments_router
    from app.modules.sessions.router import router as sessions_router
    from app.modules.tenants.router import router as tenants_router

    api_router.include_router(auth_router, prefix="/api/v1")
    api_router.include_router(invites_router, prefix="/api/v1")
    api_router.include_router(sessions_router, prefix="/api/v1")
    api_router.include_router(tenants_router, prefix="/api/v1")
    api_router.include_router(segments_router, prefix="/api/v1")
    api_router.include_router(collateral_router, prefix="/api/v1")
    api_router.include_router(platform_router, prefix="/api/v1")
    api_router.include_router(audit_router, prefix="/api/v1")


_register_routers()
