# URL Content Fetcher (CSV)

Separate Chrome extension for **fetching and extracting content for a list of URLs** (to handle cases where Node fetchers get blocked with 403/anti-bot).

## Input
- Upload a CSV containing a `url` column.

## Output
- Download a CSV with:
  - `page_title`, `meta_description`, `canonical_url`
  - `published_date`, `modified_date`
  - `has_schema_markup`, `js_render_suspected`
  - `content` (optionally truncated)

## Install (Chrome)
1. Go to `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select this folder: `tools/URL Content Fetcher/`

## Notes
- This extension fetches HTML in the background service worker and extracts text/metadata in the sidepanel using DOMParser.
- If you want perfect parity with the Bing scraper extraction, keep the same selectors/cleaning rules (this is intentionally similar).

