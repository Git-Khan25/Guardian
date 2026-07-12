# backend/main.py
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api.routes import router  # noqa: E402  (must load env first)

app = FastAPI(
    title="Contract Guardian API",
    description="Verifies whether a website's real network behavior matches "
    "the promises in its privacy policy — and shows the evidence.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo tool, no auth/user data at risk
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {"service": "contract-guardian-api", "status": "running"}
