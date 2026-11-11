"""Provider-agnostic LLM location summary.

One entry point: summarize(table) -> str.
Any OpenAI-compatible chat-completions API works; the provider is chosen in .env:

    LLM_PROVIDER=groq
    LLM_MODEL=openai/gpt-oss-120b
    LLM_API_KEY=...
    LLM_BASE_URL=https://api.groq.com/openai/v1

Switching provider (e.g. OpenRouter) should only need different .env values.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Convenience defaults only; every value can be overridden in .env.
PROVIDER_DEFAULTS = {
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-120b"},
}
TEMPERATURE = 0.2
MAX_TOKENS = 4096        # ceiling, not length: reasoning models (gpt-oss) can spend ~1000+
                         # hidden reasoning tokens before the visible answer
REQUEST_TIMEOUT_S = 60
MAX_ATTEMPTS = 4         # 1 call + 3 retries on HTTP 429
UNAVAILABLE_TEXT = "AI summary unavailable."
MAX_WORDS = 110          # asked for in the prompt; longer output is kept but logged

SYSTEM_PROMPT = """You write short location summaries for property location reports.

Rules:
- Use ONLY the facts in the JSON analysis table given by the user. Do not add place names,
  distances, counts, amenities or opinions (quality, safety, prices, views, atmosphere)
  that are not in the table.
- Distances are straight-line distances, not walking routes. Never convert them into
  walking or driving times.
- If nearest_m is null, that category was not found in the data within the search radius.
  You may say so, but do not speculate why.
- You may round distances (e.g. 746 m -> about 750 m). Never change counts.
- Do not describe trends or comparisons between the 500 m and 1 km counts unless you state
  the exact numbers. Do not use vague words such as "slightly" or "significantly".
- Never say a count "increases", "rises" or "grows" when count_500 equals count_1000.
- Mention the 1 km count only when count_1000 differs from count_500. When they are equal,
  give the single count with "within 500 m" (e.g. "five pharmacies within 500 m").
- Always name the radius in plain words ("within 500 m", "within 1 km"); never write
  vague phrases such as "within radii" or "in the area".
- If nearest_name is null but nearest_m is set, the nearest place has no name in the data:
  say "an unnamed <category>" (e.g. "an unnamed stop") or give only the distance.
  Never invent a name.
- Use short sentences, one category (or a few closely related ones) per sentence.
  Do not use "respectively" or parallel lists that the reader has to match up.
- Write 3 to 4 sentences of plain, professional English, at most {max_words} words.
  No headings, lists, emojis or marketing superlatives (e.g. stunning, perfect, best).
- Output only the summary text.""".format(max_words=MAX_WORDS)


class LlmError(RuntimeError):
    pass


class LlmConfigError(LlmError):
    pass


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    model: str
    base_url: str
    api_key: str = ""

    def __repr__(self):  # never leak the key into logs/tracebacks
        return f"LlmConfig(provider={self.provider!r}, model={self.model!r}, base_url={self.base_url!r})"


def load_config(env=None) -> LlmConfig:
    env = os.environ if env is None else env
    provider = (env.get("LLM_PROVIDER") or "groq").strip().lower()
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    model = (env.get("LLM_MODEL") or defaults.get("model") or "").strip()
    base_url = (env.get("LLM_BASE_URL") or defaults.get("base_url") or "").strip()
    api_key = (env.get("LLM_API_KEY") or "").strip()

    missing = [name for name, value in (("LLM_API_KEY", api_key), ("LLM_MODEL", model),
                                         ("LLM_BASE_URL", base_url)) if not value]
    if missing:
        raise LlmConfigError(
            f"LLM is not configured: missing {', '.join(missing)}. "
            "Set them in .env (see .env.example) or run with --no-summary."
        )
    return LlmConfig(provider=provider, model=model, base_url=base_url, api_key=api_key)


def _real_name(name, label):
    """None for the 'Unnamed <label>' placeholder set in analysis.py (not an OSM name)."""
    if not name or name == f"Unnamed {str(label).lower()}":
        return None
    return name


def prompt_table(summary: dict) -> dict:
    """Reduce summary.json to the facts the model may use (no coordinates, CRS, timestamps)."""
    return {
        "property_name": summary.get("name"),
        "address": summary.get("address"),
        "radii_m": summary.get("buffers_m"),
        "poi_search_radius_m": summary.get("poi_search_radius_m"),
        "distance_type": "straight-line",
        "categories": [
            {
                "category": s.get("label", key),
                **{k: v for k, v in s.items() if k.startswith("count_")},
                "nearest_m": s.get("nearest_m"),
                "nearest_name": _real_name(s.get("nearest_name"), s.get("label", key)),
            }
            for key, s in (summary.get("categories") or {}).items()
        ],
    }


def build_messages(table: dict) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Analysis table (JSON):\n" + json.dumps(table, ensure_ascii=False, indent=1)},
    ]


def _client(cfg: LlmConfig):
    from openai import OpenAI  # imported lazily: only needed when a summary is requested
    return OpenAI(api_key=cfg.api_key, base_url=cfg.base_url,
                  timeout=REQUEST_TIMEOUT_S, max_retries=0)  # retries handled below


def _retry_after(exc) -> float | None:
    try:
        value = exc.response.headers.get("retry-after")
        return min(float(value), 60.0) if value else None
    except (AttributeError, TypeError, ValueError):
        return None


def summarize(table: dict, config: LlmConfig | None = None, client=None) -> str:
    """Return a 3-4 sentence English summary of the analysis table. Raises LlmError."""
    import openai

    cfg = config or load_config()
    client = client or _client(cfg)
    messages = build_messages(table)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.chat.completions.create(
                model=cfg.model, messages=messages,
                temperature=TEMPERATURE, max_tokens=MAX_TOKENS,
            )
            break
        except openai.RateLimitError as exc:
            if attempt == MAX_ATTEMPTS:
                raise LlmError(f"LLM rate limit (429) persisted after {MAX_ATTEMPTS} attempts") from exc
            wait = _retry_after(exc) or 2.0 ** attempt  # 2 s, 4 s, 8 s
            log.warning("LLM rate limited (429), retrying in %.0f s (attempt %d/%d)",
                        wait, attempt, MAX_ATTEMPTS)
            time.sleep(wait)
        except openai.AuthenticationError as exc:
            raise LlmError("LLM API key was rejected (401). Check LLM_API_KEY.") from exc
        except openai.APIStatusError as exc:
            raise LlmError(f"LLM API error (HTTP {exc.status_code})") from exc
        except (openai.APITimeoutError, openai.APIConnectionError) as exc:
            raise LlmError(f"Could not reach the LLM API at {cfg.base_url}: {type(exc).__name__}") from exc

    choice = resp.choices[0]
    if choice.finish_reason == "length":
        raise LlmError(f"LLM output was cut off (max_tokens={MAX_TOKENS} reached, "
                       "possibly spent on hidden reasoning)")
    text = " ".join((choice.message.content or "").split())
    if not text:
        raise LlmError("LLM returned an empty summary")
    words = len(text.split())
    if words > MAX_WORDS:
        log.warning("AI summary has %d words (limit %d); keeping it", words, MAX_WORDS)
    return text


def try_summarize(summary: dict) -> dict:
    """Never raises: returns {'status', 'text', 'provider', 'model', 'error'} for the report."""
    result = {"status": "unavailable", "text": UNAVAILABLE_TEXT,
              "provider": None, "model": None, "error": None}
    try:
        cfg = load_config()
        result.update(provider=cfg.provider, model=cfg.model)
        log.info("Requesting AI summary from %s (%s)", cfg.provider, cfg.model)
        result.update(status="ok", text=summarize(prompt_table(summary), cfg))
    except LlmError as exc:
        result["error"] = str(exc)
        log.warning("AI summary unavailable: %s", exc)
    except Exception as exc:  # report must still be produced
        result["error"] = f"{type(exc).__name__}: {exc}"
        log.warning("AI summary unavailable (unexpected error): %s", result["error"])
    return result
