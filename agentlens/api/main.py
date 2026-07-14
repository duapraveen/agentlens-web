"""FastAPI app factory: CORS for the local Vite dev server, router mounts."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentlens.api.routers import (
    clusters,
    conversations,
    fix_workbench,
    jobs,
    overview,
    review_queue,
)


def create_app() -> FastAPI:
    """Build the AgentLens API app with all routers mounted under /api."""
    app = FastAPI(title="AgentLens API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(overview.router, prefix="/api")
    app.include_router(conversations.router, prefix="/api")
    app.include_router(clusters.router, prefix="/api")
    app.include_router(review_queue.router, prefix="/api")
    app.include_router(fix_workbench.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    return app


app = create_app()
