## python poc to be built

0. a simple uv python project is enabled, use uv to add relevant deps, run scripts etc. ignore readme for now.
1. check .env for `ENV_NAME` and read ~/.dbt/profiles.yml - mad_dbt_skanda -> outputs -> dev/prod depending on env set and return everything under it for sqlalchemy db connection - for now there is only dev, error on missing value (dont hardcode dev/prod)
2. use sql alchemy to connect to the database that is managed by dbt, initiate these tables:
    - `py_raw_json` under `weather_raw` schema - columns - id(auto increment), source_api_id, raw_json, insert_ts, location_ids_list, params_list, data_tm_from, data_tm_to 
    - `py_api_log` under `weather_raw` schema - everytime the api is called, log it with its id and status code - id, api_id, status_code, insert_ts
3. explanation of metadata tables under schema `weather_raw` that is used to call the api (note: these are maintained by dbt):
 - `raw_weather_source_api` - with columns `id,api_base,path,auth_type,limit,limit_unit` - lists apis that need to be called - append `api_base` and `path` to form the base - for now error if id <> 1 and auth <> null
 - `raw_weather_source_api_params` - with columns `id,source_api_id,parameter,value` - query for source_api_id = id in the source table and append `parameter` as a url query param and equate its value to `value`
 - `raw_weather_locations` with columns `id,location,location_type,var_1,var_2,var_3,var_4` join to `raw_weather_location_type` with columns `id,type,description,type_regex` on location_type=id - error if not type = 1. then use var_1 and var_2 as inputs to the `latitude` and `longitude` url query params - if there is more than one location then add a comma seperated values for example `&latitude=41.3,32.3,56.8&longitude=44.6,67.8,33.6`
 - if needed, verify columns under `mad_dbt/seeds/raw_weather_*.csv`
4. make the api call with the full url constructed from the above tables - log response in `py_api_log` and insert json into `py_raw_json`
5. before making the call, check `limit` and `limit_unit` in `raw_weather_source_api` - and accordingly query the log table, the current unit used is DAY and number is 10 but parse from the table on run - if passed then do not run, end with a WARNING log