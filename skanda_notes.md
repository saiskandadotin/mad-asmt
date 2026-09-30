## overview (me talking to me)

3-4 hours seems tight so here are what i think should be done in priority order

1. figure out how free open-meteo api works - start with just current weather and 1 day forecast for 1 city (but check how multiple cities / large data ranges affect api response)
2. design a simple table structure (try dbt seed table first for meta? should ideally be CDCed - maybe later)
3. build only the fetch portion on python - fetch and store raw data on postgres - no api backfill
4. set raw-sql/dbt logic to create intermediate tables and views - dbt to transform the text to jsonb and then usable tables
5. a simple dashboard on superset (local)

optional if time permits:

6. add data checks to dbt
7. see how to maintain the metadata tables using dbt snapshots - then a model on top to actv_flag = 1
8. setup a backfill mechanism in case of missed runs, errors etc
9. hopefully i designed the tables to auto-account for new parameters like say humidity - see how easy/difficult it is to add/remove params - if not do it
10. create a reproducible script that re-creates everything including superset and dashboards on hiring team machine (really stretching it here - dont do this)
11. audit how difficult it would be to switch the data provider in the future - hopefully not a lot?

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

[x] code on github

[x] superset dashboard - maybe export and save to the repo?

[x] readme - maybe evolve this as it progresses

[x] add major ai use cases, manual changes/overides to readme. optionally the redacted claude chat json file
