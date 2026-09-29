## overview (me talking to me)

3-4 hours seems tight so here are what i think should be done in priority order

1. figure out how free open-meteo api works - start with just current weather and 1 day forecast for 1 city (but check how multiple cities / large data ranges affect api response)
2. design a simple table structure (try dbt seed table first for meta? should ideally be CDCed - maybe later)
3. build only the fetch portion on python - fetch and store raw data on postgres - no api backfill
4. set raw-sql/dbt logic to create intermediate tables and views - dbt to transform the text to jsonb and then usable tables
5. a simple dashboard on superset (local)

optional if time permits:

6. add data checks to dbt
6. see how to maintain the metadata tables using dbt snapshots - then a model on top to actv_flag = 1
7. setup a backfill mechanism in case of missed runs, errors etc
8. hopefully i designed the tables to auto-account for new parameters like say humidity - see how easy/difficult it is to add/remove params - if not do it
9. knowing you, you would have created a auto-refreshing mat view instead of proper pipeline, if yes - change it
10. create a reproducible script that re-creates everything including superset and dashboards on hiring team machine (really stretching it here - dont do this)
10. audit how difficult it would be to switch the data provider in the future - hopefully not a lot?

## pre-build notes

1. example api req - `https://api.open-meteo.com/v1/forecast?latitude=12.9719&longitude=77.5937&hourly=temperature_2m&current=temperature_2m&timezone=auto&forecast_days=3`
    - max `forecast_days` is 16
    - multi location is allowed via comma seperated lat,long inputs (no limit specified in the docs)
    - hourly and current are comma seperated list of weather vars
    - timezone - auto (but script/run env may not be configured correctly so check asia/kolkata)
    - out of scope for now but dbt should be able to handle additional fields?
        - as long as its just a new weather var, current setup should work
        - past forecasting etc not handled - see above docs
    - no apparent failure points or pagination due to existing strict constraints, for now just model on above?


## deliverables

[ ] code on github
[ ] superset dashboard - maybe export and save to the repo?
[ ] readme - maybe evolve this as it progresses
[ ] add major ai use cases, manual changes/overides to readme. optionally the redacted claude chat json file

# The Actual Readme (when possible add/update)

## Intro

This is a simple dbt based weather api ELT script (sourced from open-meteo)

Currently seed tables in dbt are used to configure the api and locations, the main python script uses this to fetch and save the raw json to dbt

## To be built

dbt needs to take the raw json string and see if it can be stored in a jsonb field - to check for valid json
then it needs to parse the past, current and future values from the json and organize this data - staging table structure design is pending
post this, create a analyst friendly view of the most up to date actuals, forecast which can be analyzed

## Setup

0. pre-req:
    - `uv` is required to manage and run this project - install from [Here](https://docs.astral.sh/uv/getting-started/installation/)
    - a postgres database, preferrably local
    - You are on a linux/mac machine with bash/zsh terminal. if running from windows try from WSL2 (un-tested)
1. clone to local, use `uv` to initialize the project with `uv sync`
2. do you already have dbt on your local machine?
    - Yes! - Add a new profile called `mad_dbt_skanda` with the template below
    - No... - copy template below to a file called profiles.yml under `<USER_HOME>/.dbt/`

```
mad_dbt_skanda:
  target: dev
  outputs:
    dev:
      type: postgres
      port: 5432
      database: mad_asmt
      schema: weather
      threads: 10
      host: localhost
      user: postgres
      password: postgres
```

3. Update the user and password to your local postgres - this user should have persmission to create schemas, run any DML etc (basically admin preferred)
4. open a terminal at the root of this repo / open in your ide
    - IDEs usually activate the python env automatically, if not run `source .venv/bin/activate`
5. cd into mad_dbt and run `uv run dbt build`
    - This should seed api related metadata into postgres
6. now cd back to the root and run `uv run main.py`

NOTE: This is as far as I have reached in about ~4 hours