# Bug fix — PUBLIC_BASE_URL not defined in generate_amazon_flatfile (2026-03-31)
Tags: bugfix amazon flatfile export PUBLIC_BASE_URL config import
Date: 2026-03-31

## Symptom
Step 3 "Generate Amazon Content & Images" failed at the flatfile generation stage:
`Error: name 'PUBLIC_BASE_URL' is not defined`

Images and AI content generated fine (steps 1 and 2 passed), only flatfile failed.

## Root cause
`generate_amazon_flatfile()` in app.py uses `PUBLIC_BASE_URL` in ~10 places
to build marketplace image URLs, but the function never imported it.

Every other route that uses `PUBLIC_BASE_URL` has an inline import:
```python
from config import PUBLIC_BASE_URL
```
This one was missed during the original refactor from the monolithic app.

## Fix
Added to the top of `generate_amazon_flatfile()`:
```python
from config import PUBLIC_BASE_URL
```

## Pattern to watch
`PUBLIC_BASE_URL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` and other config values
are not imported at module level in app.py — they are imported inline inside each
function that needs them. Any new function using these must include its own import.
