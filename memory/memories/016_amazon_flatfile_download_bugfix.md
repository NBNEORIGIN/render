# Bug fix — Amazon flatfile "Generate" button never downloaded (2026-04-01)
Tags: bugfix export amazon flatfile download xlsx stream endpoint
Date: 2026-04-01

## Symptom
Gabby reported: "Amazon flatfile is generated but doesn't download."
The Generate Amazon Flatfile button showed success but no file appeared.

## Root cause
`exportAmazonFlatfile()` in index.html called `/api/generate/amazon-flatfile`
which saves the XLSX to disk and returns JSON — it never streams a file.
A separate "Download Amazon Flatfile" button existed but was not prominent
and Gabby didn't know to click it after generating.

Two endpoints existed for the same job:
- `POST /api/generate/amazon-flatfile` — saves to disk, returns JSON (used by Step 3 pipeline)
- `POST /api/export/amazon-flatfile-download` — streams XLSX blob directly (correct for download)

The Generate button was wired to the wrong one.

## Fix
Switched `exportAmazonFlatfile()` to call `/api/export/amazon-flatfile-download`
which streams the blob. Triggers browser download via object URL, same pattern
as eBay CSV and Etsy XLSX.

## Pattern
All export buttons must call streaming endpoints that return file blobs.
Never wire a download button to a JSON endpoint — even if it says "success",
the user gets nothing. See also: 013_m_folders_download_bugfix.md (same class of bug).

## Commit
bb5d535 fix(export): Amazon flatfile generate button now streams download
