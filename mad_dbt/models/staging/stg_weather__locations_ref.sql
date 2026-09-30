select l.*,
       lt.type as location_type_name,
       lt.description as location_type_description
from {{ ref('raw_weather_locations') }} l
left join {{ ref('raw_weather_location_type') }} lt on l.location_type=lt.id