-- Step 3: one row per (payload, city, hour).
-- hourly.time and hourly.temperature_2m are parallel arrays. ROWS FROM zips them
-- by position (and pads with NULL if one is shorter -> caught by a test).
-- If you later add more hourly variables, just add another jsonb_array_elements_text(...) below.

select
    c.raw_id,
    c.city_idx,
    c.location_id,
    h.hour_idx::int                                                     as hour_idx,
    to_timestamp(h.ts::bigint)                                          as ts_utc,
    to_timestamp(h.ts::bigint) at time zone c.timezone                  as ts_local,
    h.temperature_c::numeric                                            as temperature_c
from {{ ref('stg_weather__cities') }} c
cross join lateral rows from (
    jsonb_array_elements_text(c.hourly -> 'time'),
    jsonb_array_elements_text(c.hourly -> 'temperature_2m')
) with ordinality as h(ts, temperature_c, hour_idx)