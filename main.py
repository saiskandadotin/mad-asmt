"""Entry point: resolve config, check the rate limit, call the weather API,
log the call, and store the payload (CLAUDE.md reqs 1-5)."""

from __future__ import annotations

import json
import logging
import sys

from db import ConfigError, ensure_tables, make_engine, resolve_target, resolve_tz
from ingest import (
    assemble_params,
    build_request,
    call_api,
    extract_data_window,
    load_locations,
    load_source_api,
    log_api_call,
    rate_limit_ok,
    store_response,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mad")


def main() -> int:
    try:
        # req 1: .env ENV_NAME -> profiles.yml output -> engine
        tz = resolve_tz()
        target = resolve_target()
        engine = make_engine(target)
        log.info("timezone: %s", tz.key)
        # req 2: py_raw_json + py_api_log
        ensure_tables(engine)

        api = load_source_api(engine)
        log.info("source api id=%s base=%s path=%s", api["id"], api["api_base"], api["path"])

        # req 5: rate limit gate (limit/limit_unit parsed from the table)
        if not rate_limit_ok(engine, api, tz):
            log.warning(
                "rate limit reached for api id=%s (%s %s) - skipping this run",
                api["id"], api["limit"], api["limit_unit"],
            )
            return 0

        params = assemble_params(engine, api["id"])
        locations = load_locations(engine)
        url, query = build_request(api, params, locations)
        log.info("GET %s?%s", url, json.dumps(query, sort_keys=True))

        # req 4: call, log status, store payload
        resp = call_api(url, query)
        log_api_call(engine, api["id"], resp.status_code)
        log.info("response status=%s bytes=%s", resp.status_code, len(resp.content))

        if not resp.ok:
            log.error("non-2xx response, not storing payload: %s", resp.text[:300])
            return 1

        payload = resp.json()
        data_from, data_to = extract_data_window(payload, tz)
        store_response(
            engine,
            api_id=api["id"],
            body=resp.text,
            location_ids=[loc["id"] for loc in locations],
            query=query,
            data_tm_from=data_from,
            data_tm_to=data_to,
        )
        log.info("stored payload in %s.py_raw_json (data window %s .. %s)",
                 "weather_raw", data_from, data_to)
        return 0

    except (ConfigError, RuntimeError) as exc:
        log.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
