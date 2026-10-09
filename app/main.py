from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routes import auth, profile, quotes
from app.services.rendering_service import renderer_diagnostics
from app.services.translation_service import assert_catalog_completeness


@asynccontextmanager
async def lifespan(app: FastAPI):
    assert_catalog_completeness()
    get_settings().generated_files_dir.mkdir(parents=True, exist_ok=True)
    app.state.renderer = await asyncio.to_thread(renderer_diagnostics, True)
    yield


app = FastAPI(title="Insurance Quote Builder", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")
app.include_router(auth.router)
app.include_router(quotes.router)
app.include_router(profile.router)


@app.get("/health")
def health():
    renderer = getattr(app.state, "renderer", renderer_diagnostics())
    return {"status": "ok" if renderer["ready"] else "degraded", "renderer": renderer}
