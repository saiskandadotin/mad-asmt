with c as (
    select
        c.*,
        row_number() over (
            partition by c.location_id
            order by c.loaded_at desc, raw_id desc
        ) - 1 as prediction_recency
    from {{ ref('stg_weather__cities') }} c
)

-- current as () -- need to figure out how to make current make sense here

select c.raw_id, -- should ideally be from __payloads?
	   c.loaded_at,
	   l."location",
       c.prediction_recency,
	   l.location_type_name as location_type,
	   c.latitude || ', ' || c.longitude as api_result_location,
	   c.elevation_m,
	   h.ts_local,
	   h.temperature_c
from c
left join {{ ref('stg_weather__locations_ref') }} l on l.id = c.location_id
left join {{ ref('stg_weather__hourly') }} h on c.raw_id = h.raw_id