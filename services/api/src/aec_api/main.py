"""FastAPI app entry (guide §7). Run: uvicorn aec_api.main:app --reload"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import (analysis, authoring, bim, convert, cost, dashboard, drawings, exports,
                      modules, proforma, properties, schedule)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AEC BIM Platform API", version="0.1.0", lifespan=lifespan)

# In production the web app calls the API same-origin via nginx's /api proxy, so CORS
# is moot. CORS only matters for the dev server (:5173) or direct cross-origin access;
# AEC_CORS_ORIGINS (comma-separated) overrides the dev default.
_cors = os.environ.get("AEC_CORS_ORIGINS", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(bim.router, tags=["bim"])
app.include_router(properties.router, tags=["properties"])
app.include_router(exports.router, tags=["exports"])
app.include_router(analysis.router, tags=["analysis"])
app.include_router(drawings.router, tags=["drawings"])
app.include_router(authoring.router, tags=["authoring"])
app.include_router(modules.router, tags=["modules"])
app.include_router(cost.router, tags=["cost"])
app.include_router(schedule.router, tags=["schedule"])
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(proforma.router, tags=["proforma"])
app.include_router(convert.router, tags=["convert"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
