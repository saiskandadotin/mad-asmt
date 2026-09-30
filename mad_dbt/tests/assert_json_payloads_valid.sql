-- dbt singular test: any rows returned = test fails
-- check for other fields later?
select raw_id, raw_json, location_ids_list
from {{ ref('stg_weather__payloads') }}
where not is_valid_json
   or not is_valid_location_ids