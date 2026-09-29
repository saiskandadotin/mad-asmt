"""Env/dbt-profile resolution and the SQLAlchemy table definitions.

CLAUDE.md req 1: read ENV_NAME from .env, look that key up under
~/.dbt/profiles.yml -> mad_dbt_skanda -> outputs, and hand back everything
under it for the SQLAlchemy connection. Missing values are hard errors;
dev/prod are never hardcoded.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    func,
    text,
)

PROFILE_NAME = "mad_dbt_skanda"
SCHEMA = "weather_raw"
PROJECT_ROOT = Path(__file__).resolve().parent


class ConfigError(Exception):
    """Missing or incomplete env/profile configuration."""


def resolve_tz() -> ZoneInfo:
    """Timezone from TZ in .env - used for the DB session and all datetimes."""
    load_dotenv(PROJECT_ROOT / ".env")
    name = (os.environ.get("TZ") or "").strip().strip("\"'")
    if not name:
        raise ConfigError("TZ is missing or empty in .env")
    try:
        return ZoneInfo(name)
    except Exception as exc:  # ZoneInfoNotFoundError / ValueError
        raise ConfigError(f"invalid TZ {name!r} in .env: {exc}") from exc


def now_local(tz: ZoneInfo) -> datetime:
    """Wall-clock now in the configured TZ (naive), matching our
    `timestamp without time zone` columns, which hold TZ wall time."""
    return datetime.now(tz).replace(tzinfo=None)


def resolve_target() -> dict:
    """Return the dbt profile output named by ENV_NAME in .env."""
    load_dotenv(PROJECT_ROOT / ".env")
    env_name = (os.environ.get("ENV_NAME") or "").strip()
    if not env_name:
        raise ConfigError("ENV_NAME is missing or empty in .env")

    profiles_path = Path.home() / ".dbt" / "profiles.yml"
    profiles = yaml.safe_load(profiles_path.read_text()) or {}
    profile = profiles.get(PROFILE_NAME)
    if profile is None:
        raise ConfigError(f"profile '{PROFILE_NAME}' not found in {profiles_path}")

    outputs = profile.get("outputs") or {}
    target = outputs.get(env_name)
    if target is None:
        available = ", ".join(sorted(outputs)) or "<none>"
        raise ConfigError(
            f"output '{env_name}' (from ENV_NAME) not found in profile "
            f"'{PROFILE_NAME}'; available outputs: {available}"
        )
    return target


def make_engine(target: dict):
    """Build a SQLAlchemy engine from a dbt profile output mapping."""
    missing = [k for k in ("host", "port", "user", "database") if not target.get(k)]
    if missing:
        raise ConfigError(f"profile output is missing keys: {', '.join(missing)}")

    url = (
        f"postgresql+psycopg://{target['user']}:{target['password']}"
        f"@{target['host']}:{target['port']}/{target['database']}"
    )
    # every pooled connection/session runs with TimeZone set, so server-side
    # defaults (insert_ts = now()) and casts store wall time in TZ
    tz_name = resolve_tz().key
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": f"-c TimeZone={tz_name}"},
    )


metadata = MetaData()

# CLAUDE.md req 2: raw API payload store
py_raw_json = Table(
    "py_raw_json",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("source_api_id", Integer, nullable=False),
    Column("raw_json", Text, nullable=False),
    Column("insert_ts", DateTime, nullable=False, server_default=func.now()),
    Column("location_ids_list", Text),
    Column("params_list", Text),
    Column("data_tm_from", DateTime),
    Column("data_tm_to", DateTime),
    schema=SCHEMA,
)

# CLAUDE.md req 2: one row per API call
py_api_log = Table(
    "py_api_log",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("api_id", Integer, nullable=False),
    Column("status_code", Integer),
    Column("insert_ts", DateTime, nullable=False, server_default=func.now()),
    schema=SCHEMA,
)


def ensure_tables(engine) -> None:
    """Create weather_raw (if needed) and our two tables (if needed)."""
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
    metadata.create_all(engine)
