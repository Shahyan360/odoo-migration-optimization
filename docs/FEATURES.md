# Source scope

Date/location/company-filtered movement balances, an actual ORM N+1 baseline,
an ORM-rule-filtered SQL aggregate, bounded synthetic stock move generation,
median repeated benchmark recording, optional candidate indexing and QWeb
measurement summaries are authored. Product quantities use stock UoM.
Stock balances derive from done moves before/from the date range; internal
movements cancel within a selected aggregate while remaining visible per location.

No benchmark has been run and no before/after number is supplied. The user's
historical 30-second-to-5-second statement is not adopted as this lab's result.
Warm caches and baseline-first order are disclosed in recorded measurements.
Use EXPLAIN ANALYZE only after reviewing the generated query and dataset, then
measure candidate indexes before retaining them. JSON results currently expose
product/location IDs rather than a polished large-data reporting UI.
See MIGRATION_GUIDE.md for the two source variants and core-upgrade boundary.
