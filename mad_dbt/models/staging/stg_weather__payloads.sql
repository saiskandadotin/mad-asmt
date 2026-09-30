-- Step 1: string -> jsonb, WITHOUT ever failing on bad rows.
-- A plain raw_json::jsonb blows up the whole query on the first invalid row,
-- so we test with IS JSON first (Postgres 16+) and only cast the valid ones.
-- Bad rows stay visible (is_valid_json = false) and are caught by tests.

with src as (

    select
        id          as raw_id,
        source_api_id,
        raw_json,
        location_ids_list,
        params_list,
        data_tm_from,
        data_tm_to,
        insert_ts as loaded_at
    from {{ source('weather_seeds', 'py_raw_json') }}

),

validated as (

    select
        *,
        coalesce(raw_json is json, false)                   as is_valid_json,
        coalesce(location_ids_list is json array, false)    as is_valid_location_ids
    from src

),

parsed as (

    select
        raw_id,
        loaded_at,
        raw_json,
        location_ids_list,
        is_valid_json,
        is_valid_location_ids,
        case when is_valid_json          then raw_json::jsonb           end as payload,
        case when is_valid_location_ids  then location_ids_list::jsonb  end as location_ids
    from validated

),

normalised as (

    select
        *,
        -- single city arrives as an object, multiple as an array of objects.
        -- Wrap the single object in an array so everything downstream is one shape.
        case jsonb_typeof(payload)
            when 'array'  then payload
            when 'object' then jsonb_build_array(payload)
        end as payload_array
    from parsed

)

select
    *,
    jsonb_array_length(payload_array) as n_cities,
    jsonb_array_length(location_ids)  as n_location_ids
from normalised