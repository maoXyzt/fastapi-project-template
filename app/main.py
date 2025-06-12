from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router, assets_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan setup"""
    # setup
    try:
        yield
    finally:
        # teardown
        pass


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


def create_app():
    app = FastAPI(
        title=settings.PROJECT_NAME,
        docs_url=f"{settings.API_V1_STR}/docs",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
        generate_unique_id_function=custom_generate_unique_id,
    )

    # Set all CORS enabled origins
    if settings.all_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.all_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_routers(app)
    return app


def register_routers(app: FastAPI):
    app.include_router(assets_router, prefix="/assets")
    app.include_router(api_router, prefix=settings.API_V1_STR)

    async def redirect_to_docs(_: Request):
        return RedirectResponse(url=f"{settings.API_V1_STR}/docs")

    app.add_route("/", redirect_to_docs, methods=["GET"])
