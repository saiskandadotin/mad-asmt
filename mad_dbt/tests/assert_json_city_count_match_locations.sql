select raw_id, n_cities, n_location_ids, location_ids_list
from {{ ref('stg_weather__payloads') }}
where is_valid_json
  and is_valid_location_ids
  and n_cities is distinct from n_location_ids