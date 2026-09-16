"""FastAPI app: serves the dashboard HTML and every /api/* route. One
deployable service -- the frontend now talks only to this, never to
Supabase directly except for login/logout."""
from __future__ import annotations
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # must run before importing db/routers, which read os.environ at import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import get_pool, close_pool
from .routers import daily, weight, plan, lifts, coach, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
    await close_pool()


app = FastAPI(title="Physique OS", lifespan=lifespan)

app.include_router(daily.router)
app.include_router(weight.router)
app.include_router(plan.router)
app.include_router(lifts.router)
app.include_router(coach.router)
app.include_router(reports.router)


@app.get("/health")
def health():
    return {"ok": True}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
