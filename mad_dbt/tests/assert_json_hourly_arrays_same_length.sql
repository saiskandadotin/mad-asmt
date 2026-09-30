select raw_id, city_idx,
       jsonb_array_length(hourly -> 'time')           as n_time,
       jsonb_array_length(hourly -> 'temperature_2m') as n_temp
from {{ ref('stg_weather__cities') }}
where jsonb_array_length(hourly -> 'time') is distinct from jsonb_array_length(hourly -> 'temperature_2m')