# Bug fixes — Insights tab broken on first deploy
Tags: bugfix insights postgresql round cast import_exists salesimport salesdata
Date: 2026-03-30

## Bugs

### 1. import_exists on wrong class
`import_exists` was accidentally placed on `SalesData` instead of `SalesImport`.
The import route called `SalesImport.import_exists(...)` which caused:
`AttributeError: type object 'SalesImport' has no attribute 'import_exists'`

Fix: moved the method to `SalesImport` where it belongs.

### 2. PostgreSQL ROUND type error
SQLite accepts `ROUND(float, int)` but PostgreSQL does not implicitly cast `double precision`:
`psycopg2.errors.UndefinedFunction: function round(double precision, integer) does not exist`

Fix: wrap the argument with an explicit cast:
```sql
-- Before (SQLite only)
ROUND(SUM(units)*100.0/SUM(sessions), 1)

-- After (works on both)
ROUND(CAST(SUM(units)*100.0/SUM(sessions) AS NUMERIC), 1)
```

This affected both `top_performers` and `category_summary` queries in `SalesData`.

## Lesson
When writing SQL that runs on both SQLite (local dev) and PostgreSQL (production),
always use explicit CAST for ROUND — PostgreSQL is stricter about type coercion.
Test DB-touching code against PostgreSQL, not just SQLite.
