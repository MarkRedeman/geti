"""Unified Interactive AI API entrypoint.

Phase 1+2: dataset and project import/export endpoints are integrated
incrementally in a single API process.
"""

from contextlib import asynccontextmanager
import importlib
import sys
from fastapi import FastAPI
import uvicorn


app = FastAPI(title="interactive_ai_api", version="0.1.0")


def _import_service_main(service_root: str, module_path: str, purge_prefixes: tuple[str, ...] = ("communication",)):
    def _matches_prefix(module_name: str) -> bool:
        return any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in purge_prefixes)

    for module_name in [m for m in list(sys.modules) if _matches_prefix(m)]:
        sys.modules.pop(module_name, None)

    sys.path.insert(0, service_root)
    try:
        return importlib.import_module(module_path)
    finally:
        try:
            sys.path.remove(service_root)
        except ValueError:
            pass


_dataset_ie_main = _import_service_main(
    "/interactive_ai/services/dataset_ie",
    "communication.endpoints.main",
    purge_prefixes=("communication", "features"),
)
_project_ie_main = _import_service_main(
    "/interactive_ai/services/project_ie",
    "communication.endpoints.main",
    purge_prefixes=("communication", "features"),
)
_director_main = _import_service_main(
    "/interactive_ai/services/director/app",
    "communication.main",
    purge_prefixes=(
        "communication",
        "entities",
        "service",
        "storage",
        "configuration",
        "environment",
        "usecases",
        "features",
        "active_learning",
        "coordination",
        "managers",
        "metrics",
    ),
)

sys.path.insert(0, "/interactive_ai/services/jobs")
try:
    _jobs_router_module = importlib.import_module("microservice.rest.job_endpoints")
finally:
    try:
        sys.path.remove("/interactive_ai/services/jobs")
    except ValueError:
        pass


@asynccontextmanager
async def _lifespan(app_instance: FastAPI):  # noqa: ANN201
    async with _dataset_ie_main.lifespan(app_instance):
        async with _project_ie_main.lifespan(app_instance):
            async with _director_main.lifespan(app_instance):
                yield


app.router.lifespan_context = _lifespan


def _register_dataset_ie_routes() -> None:
    app.include_router(_dataset_ie_main.upload_router)
    app.include_router(_dataset_ie_main.import_router)
    app.include_router(_dataset_ie_main.export_router)


def _register_project_ie_routes() -> None:
    app.include_router(_project_ie_main.upload_router)
    app.include_router(_project_ie_main.import_router)
    app.include_router(_project_ie_main.export_router)


def _register_jobs_routes() -> None:
    app.include_router(_jobs_router_module.router)


def _mount_director_app() -> None:
    app.mount("/", _director_main.app)


@app.get("/api/v1/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "interactive_ai_api"}


_register_dataset_ie_routes()
_register_project_ie_routes()
_register_jobs_routes()
_mount_director_app()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
