"""Metadata-driven weather API ingestion (CLAUDE.md reqs 3-5).

All request shape comes from the dbt-maintained tables in weather_raw:

- raw_weather_source_api           which API to call (api_base + path) and the
                                   call-rate limit (limit / limit_unit)
- raw_weather_source_api_params    fixed query params for that API
- raw_weather_locations            locations (var_1/var_2 = lat/long), joined
                                   to raw_weather_location_type on
                                   location_type = id; only type id 1
                                   (SINGLE_POINT) is supported
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import Engine

from db import SCHEMA, now_local, py_api_log, py_raw_json

UNIT_DELTAS = {
    "SECOND": timedelta(seconds=1),
    "MINUTE": timedelta(minutes=1),
    "HOUR": timedelta(hours=1),
    "DAY": timedelta(days=1),
    "WEEK": timedelta(weeks=1),
}

def _table_exists(engine: Engine, name: str) -> bool:
    return inspect(engine).has_table(name, schema=SCHEMA)


def load_source_api(engine: Engine) -> dict:
    """Single source-API row; req 3 guards: only id 1, no auth yet."""
    if not _table_exists(engine, "raw_weather_source_api"):
        raise RuntimeError(
            f"{SCHEMA}.raw_weather_source_api does not exist - run `dbt build` first"
        )
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f'select id, api_base, path, auth_type, "limit", limit_unit '
                f'from "{SCHEMA}".raw_weather_source_api'
            )
        ).mappings().all()

    if not rows:
        raise RuntimeError("raw_weather_source_api is empty - run `dbt build` first")
    for row in rows:
        if row["id"] != 1:
            raise RuntimeError(f"only source api id 1 is supported, got id={row['id']}")
        if row["auth_type"] is not None:
            raise RuntimeError(
                f"source api id 1 has auth_type={row['auth_type']}; "
                "authenticated APIs are not supported yet"
            )
    return dict(rows[0])


def load_params(engine: Engine, source_api_id: int) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"select parameter, value from {SCHEMA}.raw_weather_source_api_params "
                "where source_api_id = :id"
            ),
            {"id": source_api_id},
        ).mappings().all()
    return [dict(r) for r in rows]


_PARAM_FLAG_COLUMNS = {"forecast_flag", "current_flag"}


def load_weather_params(engine: Engine, flag: str) -> list[str]:
    """open_meteo names selected by a raw_weather_params flag column."""
    if flag not in _PARAM_FLAG_COLUMNS:
        raise ValueError(f"unknown flag {flag!r}")
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"select open_meteo_name from {SCHEMA}.raw_weather_params "
                f"where {flag} order by id"
            )
        ).scalars().all()
    return list(rows)


def assemble_params(engine: Engine, source_api_id: int) -> list[dict]:
    """Fixed query params + `hourly`/`current` lists from raw_weather_params."""
    params = load_params(engine, source_api_id)
    for param_name, flag in (("hourly", "forecast_flag"), ("current", "current_flag")):
        names = load_weather_params(engine, flag)
        if names:
            params.append({"parameter": param_name, "value": ",".join(names)})
    return params


def load_locations(engine: Engine) -> list[dict]:
    """Locations joined to their type; only location_type id 1 is allowed."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                select l.id, l.location, l.location_type, l.var_1, l.var_2, t.type
                from {SCHEMA}.raw_weather_locations l
                join {SCHEMA}.raw_weather_location_type t on t.id = l.location_type
                """
            )
        ).mappings().all()

    if not rows:
        raise RuntimeError("raw_weather_locations is empty - run `dbt build` first")
    for row in rows:
        if row["location_type"] != 1:
            raise RuntimeError(
                f"location id {row['id']} has location_type={row['location_type']} "
                "(joined type id must be 1 / SINGLE_POINT)"
            )
        if row["var_1"] is None or row["var_2"] is None:
            raise RuntimeError(
                f"location id {row['id']} is missing var_1/var_2 (latitude/longitude)"
            )
    return [dict(r) for r in rows]


def rate_limit_ok(
    engine: Engine, api: dict, tz: ZoneInfo, now: datetime | None = None
) -> bool:
    """Req 5: compare calls in the last limit window against limit/limit_unit."""
    limit = api["limit"]
    unit = (api["limit_unit"] or "").upper()
    if limit is None or unit not in UNIT_DELTAS:
        raise RuntimeError(
            f"invalid rate limit config: limit={limit} limit_unit={api['limit_unit']!r}"
        )

    since = (now or now_local(tz)) - UNIT_DELTAS[unit]
    with engine.connect() as conn:
        count = conn.execute(
            select(func.count())
            .where(py_api_log.c.api_id == api["id"])
            .where(py_api_log.c.insert_ts >= since)
        ).scalar_one()
    return count < limit


def build_request(api: dict, params: list[dict], locations: list[dict]) -> tuple[str, dict]:
    """base = api_base + path; fixed params; comma-joined lat/long per req 3."""
    base = str(api["api_base"]).rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    url = base + str(api["path"])

    query = {p["parameter"]: str(p["value"]) for p in params}
    query["latitude"] = ",".join(str(loc["var_1"]) for loc in locations)
    query["longitude"] = ",".join(str(loc["var_2"]) for loc in locations)
    return url, query


def call_api(url: str, query: dict) -> requests.Response:
    return requests.get(url, params=query, timeout=30)


def log_api_call(engine: Engine, api_id: int, status_code: int | None) -> None:
    with engine.begin() as conn:
        conn.execute(py_api_log.insert().values(api_id=api_id, status_code=status_code))


def store_response(
    engine: Engine,
    api_id: int,
    body: str,
    location_ids: list[int],
    query: dict,
    data_tm_from: datetime | None,
    data_tm_to: datetime | None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            py_raw_json.insert().values(
                source_api_id=api_id,
                raw_json=body,
                location_ids_list=json.dumps(location_ids),
                params_list=json.dumps(query, sort_keys=True),
                data_tm_from=data_tm_from,
                data_tm_to=data_tm_to,
            )
        )


def extract_data_window(
    payload: dict, tz: ZoneInfo
) -> tuple[datetime | None, datetime | None]:
    """Least/highest `time` value under hourly, as wall time in TZ.

    Values are unixtime ints (timeformat=unixtime) or ISO strings; ISO
    strings are already wall time in the response timezone, which the
    seed pins to the same zone as .env TZ.
    """
    times = (payload.get("hourly") or {}).get("time") or []
    if not times:
        return None, None
    return _to_wall(min(times), tz), _to_wall(max(times), tz)


def _to_wall(value, tz: ZoneInfo) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=tz).replace(tzinfo=None)
    return datetime.fromisoformat(str(value))
