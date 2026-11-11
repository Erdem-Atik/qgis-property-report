# Property Location Report Generator

Turns an address or coordinate into a map-based PDF location report (nearby amenities,
straight-line distances, 500 m / 1 km radius analysis) using headless QGIS (PyQGIS)
and OpenStreetMap data.

> Work in progress. Full documentation follows in a later phase.

## LLM settings (AI location summary)

The report includes a 3–4 sentence location summary written by an LLM. The model only
receives the analysis table (category counts, nearest straight-line distances and POI names
from `summary.json`) and is instructed not to add any information that is not in it.

Any OpenAI-compatible chat-completions API can be used. Configure it in `.env`
(copy `.env.example`):

| Variable | Example | Notes |
|---|---|---|
| `LLM_PROVIDER` | `groq` | Label; `groq` also provides defaults for the two settings below |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Model id at the provider |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | OpenAI-compatible endpoint |
| `LLM_API_KEY` | – | Required; never commit it (`.env` is git-ignored) |

Only Groq has been tested so far. Behaviour:

- Temperature 0.2. HTTP 429 is retried up to 3 times with backoff (honours `Retry-After`).
- If the key is missing or the call fails, the PDF is still produced and the summary reads
  "AI summary unavailable."; the reason is written to `ai_summary.json`.
- `--no-summary` skips the LLM call entirely.

## Data sources and limitations

- Map data and basemap © OpenStreetMap contributors.
- POIs are queried from the Overpass API. Public Overpass instances are rate-limited and
  occasionally unavailable; responses are cached locally. Sample responses are bundled for
  offline demos. Data snapshot date: 2026-11-11 (OSM base timestamps 05:30–05:34 UTC,
  bundled responses in `samples/overpass_cache/`).
- Distances are straight-line, not walking routes.
