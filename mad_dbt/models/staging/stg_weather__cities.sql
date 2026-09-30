-- Step 2: one row per (payload, city). Scalars are pulled out, the hourly
-- block is kept as jsonb and exploded in the next model.
--
-- Quick cheat sheet:
--   j -> 'key'      returns jsonb   (use to keep drilling down)
--   j ->> 'key'     returns text    (use at the leaf, then cast)
--   j -> 0          array element by 0-based index
--   jsonb_array_elements(arr) WITH ORDINALITY   one row per element + 1-based position

-- should this be called cities_current? :/

with payloads as (

    select *
    from {{ ref('stg_weather__payloads') }}
    -- quarantine: bad json, or city count != location_ids_list length.
    -- These rows are reported by the tests in /tests instead of silently mis-joining.
    where is_valid_json
      and is_valid_location_ids
      and n_cities = n_location_ids

)

select
    p.raw_id,
    p.loaded_at,
    c.city_idx::int                                             as city_idx,

    -- location_ids_list[i] lines up with payload[i] (same order as requested)
    (p.location_ids ->> (c.city_idx - 1)::int)::int             as location_id,

    (c.city ->> 'latitude')::numeric                            as latitude,
    (c.city ->> 'longitude')::numeric                           as longitude,
    (c.city ->> 'elevation')::numeric                           as elevation_m,
    c.city ->> 'timezone'                                       as timezone,
    (c.city ->> 'utc_offset_seconds')::int                      as utc_offset_seconds,
    (c.city ->> 'generationtime_ms')::numeric                   as generationtime_ms,

    to_timestamp((c.city #>> '{current,time}')::bigint)         as current_ts_utc,
    (c.city #>> '{current,temperature_2m}')::numeric            as current_temperature_c,

    c.city -> 'hourly'                                          as hourly

from payloads p
cross join lateral jsonb_array_elements(p.payload_array) with ordinality as c(city, city_idx)