# config.py
# Single source of truth for all environment variables and app-wide constants.
# Every other module imports settings from here — never call load_dotenv elsewhere.

from __future__ import annotations

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# ──────────────────────────────────────────────────────────────
# Ollama (local LLM)
# ──────────────────────────────────────────────────────────────

OLLAMA_MODEL       = os.getenv("OLLAMA_MODEL",       "llama3.2:3b")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.5"))

# ──────────────────────────────────────────────────────────────
# Google Gemini  (image generation)
# ──────────────────────────────────────────────────────────────

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ──────────────────────────────────────────────────────────────
# Tavily  (web research)
# ──────────────────────────────────────────────────────────────

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ──────────────────────────────────────────────────────────────
# PostgreSQL
# ──────────────────────────────────────────────────────────────

PG_USER     = os.getenv("PG_USER",     "blogger")
PG_PASSWORD = os.getenv("PG_PASSWORD", "abcd1234")
PG_HOST     = os.getenv("PG_HOST",     "localhost")
PG_PORT     = os.getenv("PG_PORT",     "5432")
PG_DB       = os.getenv("PG_DB",       "blogs")

DATABASE_URL = (
    f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}"
    f"@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

# ──────────────────────────────────────────────────────────────
# LangGraph SQLite checkpoint DB
# ──────────────────────────────────────────────────────────────

HITL_DB = os.getenv("HITL_DB", "blog_hitl.db")

# ──────────────────────────────────────────────────────────────
# Blog output directory  (static website root)
# ──────────────────────────────────────────────────────────────

BLOGS_DIR = os.getenv("BLOGS_DIR", "Blogs")


# ──────────────────────────────────────────────────────────────
# Github Repository for auto-pushing blogs
# ──────────────────────────────────────────────────────────────
GITHUB_REPO_DIR = os.getenv("GITHUB_REPO_DIR", BLOGS_DIR)

