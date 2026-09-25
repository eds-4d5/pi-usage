#!/usr/bin/env python3
"""Pi agent token usage collector.

Reads local Pi (and omp fork) session transcripts and prints one JSON
record with token totals: today / last 7 days / all-time + per-model
input/output/cache split.

Sources:
  ~/.pi/agent/sessions/**/*.jsonl
  ~/.omp/agent/sessions/**/*.jsonl

Line format (from omarchy-agent-usage-claude/codex collectors):
  {"type": "message",
   "message": {"role": "assistant", "provider": "...", "model": "...",
               "usage": {"input": N, "output": N,
                         "cacheRead": N, "cacheWrite": N,
                         "totalTokens": N}},
   "timestamp": <ms|s|ISO-8601>}

Only stdlib. Read-only, never writes auth state. The OpenRouter API key
is read locally to query the credits balance; it is never printed or
stored anywhere except the volunteered auth file.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

AGENT_ID = "pi"
AGENT_NAME = "Pi"
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/auth/key"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
MODELS_CACHE_TTL_SEC = 86400  # 24 h between model-list fetches
BALANCE_CACHE_TTL_SEC = 900  # 15 min between network checks
MAX_FILES_PER_SOURCE = 10_000
MAX_LINE_LEN = 1_000_000


def number(value) -> int:
    try:
        n = float(value or 0)
        if n != n:  # NaN
            return 0
        return int(round(n))
    except Exception:
        return 0


def usage_token(usage: dict, *keys) -> int:
    for key in keys:
        if key in usage and usage[key] is not None:
            v = number(usage[key])
            if v:
                return v
    return 0


def local_day(value) -> str:
    """Normalize ms/s/ISO timestamps to local YYYY-MM-DD."""
    today = datetime.now().strftime("%Y-%m-%d")
    if value is None:
        return today
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:  # ms -> s (pi message timestamps are ms)
            ts = ts / 1000
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            return today
    text = str(value).strip()
    if not text:
        return today
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(text)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    # plain epoch string?
    try:
        return local_day(float(text))
    except Exception:
        return today


def to_epoch(value) -> float | None:
    """Any supported timestamp shape -> epoch seconds, else None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:  # ms -> s
            ts = ts / 1000
        return ts if ts > 0 else None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(text)
        return dt.timestamp()
    except Exception:
        pass
    try:
        return to_epoch(float(text))
    except Exception:
        return None


def empty_bucket() -> dict:
    return {
        "inputTokens": 0,
        "outputTokens": 0,
        "cacheReadInputTokens": 0,
        "cacheCreationInputTokens": 0,
    }


PROVIDER_NAMES = {
    "openrouter": "OpenRouter",
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google",
    "xai": "xAI",
    "deepseek": "DeepSeek",
}


def provider_name(pid: str) -> str:
    if pid in PROVIDER_NAMES:
        return PROVIDER_NAMES[pid]
    return pid[:1].upper() + pid[1:] if pid else "Local"


def session_roots() -> list[Path]:
    home = Path.home()
    return [
        home / ".pi" / "agent" / "sessions",
        home / ".omp" / "agent" / "sessions",
    ]


def new_agg(recent_dates: list[str]) -> dict:
    return {
        "sessions": set(),
        "active_days": set(),
        "today_sessions": set(),
        "today_tokens_by_model": {},
        "model_usage": {},
        "model_last_seen": {},
        "prompts": 0,
        "today_prompts": 0,
        "today_total": 0,
        "recent": {d: 0 for d in recent_dates},
    }


def agg_add(
    agg: dict,
    *,
    model: str,
    day: str,
    total: int,
    inp: int,
    out: int,
    cread: int,
    cwrite: int,
    path: str,
    today: str,
    ts: float | None,
) -> None:
    agg["sessions"].add(path)
    agg["active_days"].add(day)
    agg["prompts"] += 1
    if ts is not None and ts >= agg["model_last_seen"].get(model, 0):
        agg["model_last_seen"][model] = ts
    bucket = agg["model_usage"].setdefault(model, empty_bucket())
    bucket["inputTokens"] += inp
    bucket["outputTokens"] += out
    bucket["cacheReadInputTokens"] += cread
    bucket["cacheCreationInputTokens"] += cwrite
    if day in agg["recent"]:
        agg["recent"][day] += total
    if day == today:
        agg["today_prompts"] += 1
        agg["today_sessions"].add(path)
        agg["today_total"] += total
        agg["today_tokens_by_model"][model] = (
            agg["today_tokens_by_model"].get(model, 0) + total
        )


def finalize_agg(agg: dict, recent_dates: list[str]) -> dict:
    top_model = ""
    top_total = 0
    for model_id, bucket in agg["model_usage"].items():
        bucket_total = (
            bucket["inputTokens"]
            + bucket["outputTokens"]
            + bucket["cacheReadInputTokens"]
            + bucket["cacheCreationInputTokens"]
        )
        if bucket_total > top_total:
            top_total = bucket_total
            top_model = model_id
    active_model = ""
    active_ts = 0.0
    for model_id, ts in agg["model_last_seen"].items():
        if ts >= active_ts:
            active_ts = ts
            active_model = model_id
    return {
        "todayPrompts": agg["today_prompts"],
        "todaySessions": len(agg["today_sessions"]),
        "todayTotalTokens": agg["today_total"],
        "todayTokensByModel": agg["today_tokens_by_model"],
        "recentDays": [
            {"date": d, "messageCount": agg["recent"][d]} for d in recent_dates
        ],
        "totalPrompts": agg["prompts"],
        "totalSessions": len(agg["sessions"]),
        "activeDays": len(agg["active_days"]),
        "activeDates": sorted(agg["active_days"]),
        "modelUsage": agg["model_usage"],
        "topModel": top_model,
        "activeModel": active_model,
        "activeAt": (
            datetime.fromtimestamp(active_ts).astimezone().isoformat()
            if active_ts > 0
            else ""
        ),
    }


def collect() -> dict:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    recent_dates = [(now - timedelta(days=o)).strftime("%Y-%m-%d") for o in range(6, -1, -1)]
    recent = {d: {"date": d, "messageCount": 0} for d in recent_dates}

    sessions: set[str] = set()
    seen: set[str] = set()
    glob = new_agg(recent_dates)
    provs: dict[str, dict] = {}
    prov_last_seen: dict[str, float] = {}

    for root in session_roots():
        if not root.is_dir():
            continue
        count = 0
        try:
            files = sorted(root.rglob("*.jsonl"))
        except OSError:
            continue
        for path in files:
            if count >= MAX_FILES_PER_SOURCE:
                break
            count += 1
            try:
                with path.open("r", encoding="utf-8", errors="replace") as fh:
                    for line_no, line in enumerate(fh, 1):
                        if len(line) > MAX_LINE_LEN:
                            continue
                        if '"usage"' not in line or '"assistant"' not in line:
                            continue
                        try:
                            entry = json.loads(line)
                        except Exception:
                            continue
                        msg = entry.get("message")
                        if not isinstance(msg, dict):
                            continue
                        if entry.get("type") != "message" or msg.get("role") != "assistant":
                            continue
                        key = f"{path}:{entry.get('id') or line_no}"
                        if key in seen:
                            continue
                        seen.add(key)
                        usage = msg.get("usage") or {}
                        if not isinstance(usage, dict):
                            continue
                        inp = usage_token(usage, "input", "input_tokens", "inputTokens")
                        out = usage_token(usage, "output", "output_tokens", "outputTokens")
                        cread = usage_token(
                            usage, "cacheRead", "cache_read_input_tokens", "cacheReadInputTokens"
                        )
                        cwrite = usage_token(
                            usage, "cacheWrite", "cache_creation_input_tokens",
                            "cacheCreationInputTokens",
                        )
                        total = inp + out + cread + cwrite
                        stated = number((usage or {}).get("totalTokens"))
                        if stated > total:
                            # Provider-billed total (e.g. excludes reasoning
                            # tokens); trust it over our partial sum.
                            total = stated
                            inp = total - out - cread - cwrite
                            if inp < 0:
                                inp = 0
                        if total <= 0:
                            total = number(usage.get("totalTokens"))
                            inp = total
                        if total <= 0:
                            continue
                        # Pi writes provider placeholder in message.model
                        # ("openrouter/free"); the real id is responseModel.
                        model = str(
                            msg.get("responseModel") or msg.get("model") or "pi"
                        )
                        day = local_day(entry.get("timestamp") or msg.get("timestamp"))
                        ts = to_epoch(entry.get("timestamp") or msg.get("timestamp"))
                        provider = str(msg.get("provider") or "local")
                        path_str = str(path)
                        entry_args = dict(
                            model=model,
                            day=day,
                            total=total,
                            inp=inp,
                            out=out,
                            cread=cread,
                            cwrite=cwrite,
                            path=path_str,
                            today=today,
                            ts=ts,
                        )
                        agg_add(glob, **entry_args)
                        agg_add(provs.setdefault(provider, new_agg(recent_dates)), **entry_args)
                        sessions.add(path_str)
                        if ts is not None and ts >= prov_last_seen.get(provider, 0):
                            prov_last_seen[provider] = ts
            except OSError:
                continue

    stats = finalize_agg(glob, recent_dates)
    prompts = stats["totalPrompts"]

    providers: dict[str, dict] = {}
    for pid, agg in provs.items():
        providers[pid] = {"id": pid, "name": provider_name(pid)}
        providers[pid].update(finalize_agg(agg, recent_dates))

    # Active provider = most recently seen: what is in use now.
    active_provider = ""
    active_prov_ts = 0.0
    for pid, ts in prov_last_seen.items():
        if ts >= active_prov_ts:
            active_prov_ts = ts
            active_provider = pid
    active_model = stats["activeModel"]
    pricing_model = active_model or stats["topModel"]

    record = {
        "schemaVersion": 1,
        "id": AGENT_ID,
        "name": AGENT_NAME,
        "ready": prompts > 0,
        "hasLocalStats": True,
        "usageStatusText": "" if prompts > 0 else "No Pi sessions found yet",
        "authHelpText": "Pi has no quota endpoint — local transcript stats only.",
        "tierLabel": "",
        "limits": [],
        "todayPrompts": stats["todayPrompts"],
        "todaySessions": stats["todaySessions"],
        "todayTotalTokens": stats["todayTotalTokens"],
        "todayTokensByModel": stats["todayTokensByModel"],
        "recentDays": stats["recentDays"],
        "totalPrompts": stats["totalPrompts"],
        "totalSessions": stats["totalSessions"],
        "activeDays": stats["activeDays"],
        "activeDates": stats["activeDates"],
        "modelUsage": stats["modelUsage"],
        "topModel": stats["topModel"],
        "activeModel": stats["activeModel"],
        "activeAt": stats["activeAt"],
        "activeProvider": active_provider,
        "providers": providers,
        "balance": openrouter_balance(pricing_model),
        "updatedAt": datetime.now().astimezone().isoformat(),
    }
    return record


# ------------------------------------------------------- OpenRouter balance


def cache_file() -> Path:
    cache_dir = Path(
        os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    ) / "omarchy" / "pi-usage"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(cache_dir, 0o700)
    except OSError:
        pass
    return cache_dir / "openrouter.json"


def read_openrouter_key() -> str:
    """API key from env or the Pi auth file. Never logged or printed."""
    env_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if env_key:
        return env_key
    try:
        data = json.loads((Path.home() / ".pi" / "agent" / "auth.json").read_text())
    except Exception:
        return ""
    node = data.get("openrouter") if isinstance(data, dict) else None
    if isinstance(node, str):
        return node.strip()
    if isinstance(node, dict):
        for field in ("key", "api_key", "apiKey", "token"):
            value = node.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def read_cached_balance(path: Path, max_age_sec: float) -> dict | None:
    try:
        cached = json.loads(path.read_text())
    except Exception:
        return None
    if not isinstance(cached, dict) or not cached.get("available"):
        return None
    try:
        age = time.time() - float(cached.get("fetchedAtEpoch", 0))
    except Exception:
        return None
    if age < 0 or age > max_age_sec:
        return None
    cached["cached"] = True
    return cached


def write_cached_balance(path: Path, payload: dict) -> None:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload))
        os.chmod(tmp, 0o600)
        tmp.replace(path)
    except OSError:
        pass


def api_get(url: str, key: str) -> dict:
    """GET JSON with bearer auth. Raises on network/HTTP errors."""
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def error_label(exc: Exception) -> str:
    status = getattr(exc, "code", None)
    return f"http-{status}" if status else type(exc).__name__


def openrouter_balance(top_model: str = "") -> dict:
    """OpenRouter budget with token figures. Key never leaves this function.

    Primary source is /credits (purchased credits minus usage). When that
    reports no funding (total <= 0), /auth/key is used as fallback: a key
    with a provisioned cap reports {limit, usage} which gives the meter a
    ceiling. A key with limit=null is uncapped — remaining is unbounded.

    Token figures come from the top-used model's pricing (/models, cached
    24 h): free model → unlimited; priced model → USD converted to tokens
    (estimate, blended prompt/completion price).
    """
    path = cache_file()
    key = read_openrouter_key()
    if not key:
        stale = read_cached_balance(path, float("inf"))
        if stale:
            return ensure_token_figures(stale, "", top_model)
        return {"available": False, "error": "no-key"}
    result = read_cached_balance(path, BALANCE_CACHE_TTL_SEC)
    if result is None:
        result = fetch_balance(path, key)
    if result.get("available"):
        result = ensure_token_figures(result, key, top_model)
        write_cached_balance(path, result)
    return result


def fetch_balance(path: Path, key: str) -> dict:
    try:
        payload = api_get(OPENROUTER_CREDITS_URL, key)
    except Exception as exc:
        # Never include the key or URL in the error; keep class/code only.
        stale = read_cached_balance(path, float("inf"))
        if stale:
            stale["stale"] = True
            return stale
        return {"available": False, "error": error_label(exc)}
    try:
        data = payload.get("data", {})
        total = float(data.get("total_credits", 0))
        used = float(data.get("total_usage", 0))
    except Exception:
        return {"available": False, "error": "bad-response"}
    source = "credits"
    if total <= 0:
        # No purchased credits — maybe a capped provisioned key.
        try:
            key_info = api_get(OPENROUTER_KEY_URL, key).get("data", {})
            limit = key_info.get("limit")
            if limit is not None:
                total = float(limit)
                used = float(key_info.get("usage", 0))
                source = "key-limit"
        except Exception:
            pass  # keep credits figures; meter simply shows empty
    result = {
        "available": True,
        "currency": "USD",
        "total": round(total, 4),
        "used": round(used, 4),
        "remaining": round(total - used, 4),
        "source": source,
        "cached": False,
        "fetchedAtEpoch": time.time(),
        "updatedAt": datetime.now().astimezone().isoformat(),
    }
    write_cached_balance(path, result)
    return result


# ------------------------------------------------- token figures (not money)


def models_cache_path() -> Path:
    return cache_file().parent / "models.json"


def read_price_cache() -> dict:
    try:
        data = json.loads(models_cache_path().read_text())
    except Exception:
        return {}
    return data.get("prices", {}) if isinstance(data, dict) else {}


def write_price_cache(prices: dict) -> None:
    try:
        path = models_cache_path()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"prices": prices}))
        os.chmod(tmp, 0o600)
        tmp.replace(path)
    except OSError:
        pass


def model_blended_price(model_id: str, key: str) -> float | None:
    """Blended USD per token for a model: 0.0 = free, None = unknown."""
    if not model_id:
        return None
    if model_id.endswith(":free"):
        return 0.0  # OpenRouter free-tier variant: billed $0, never depletes
    wanted = {model_id, model_id.split(":")[0]}
    prices = read_price_cache()
    entry = next(
        (prices.get(mid) for mid in wanted if isinstance(prices.get(mid), dict)),
        None,
    )
    fresh = False
    if isinstance(entry, dict) and "at" in entry:
        try:
            fresh = (time.time() - float(entry["at"])) < MODELS_CACHE_TTL_SEC
        except Exception:
            pass
    if not fresh and key:
        try:
            payload = api_get(OPENROUTER_MODELS_URL, key)
            for item in payload.get("data", []):
                mid = item.get("id")
                pricing = item.get("pricing") or {}
                if isinstance(mid, str) and mid in wanted and isinstance(pricing, dict):
                    try:
                        prices[mid] = {
                            "p": float(pricing.get("prompt", 0) or 0),
                            "c": float(pricing.get("completion", 0) or 0),
                            "at": time.time(),
                        }
                    except Exception:
                        continue
            write_price_cache(prices)
            entry = next(
                (prices.get(mid) for mid in wanted if isinstance(prices.get(mid), dict)),
                None,
            )
        except Exception:
            pass  # offline: fall through to whatever is cached
    if not isinstance(entry, dict):
        return None
    try:
        return (float(entry.get("p", 0)) + float(entry.get("c", 0))) / 2
    except Exception:
        return None


def ensure_token_figures(result: dict, key: str, top_model: str) -> dict:
    """Attach token budget figures (or free/unknown mode) to a balance."""
    result["model"] = top_model  # always current, even on cache hits
    if "tokenMode" in result:
        return result
    price = model_blended_price(top_model, key)
    if price is None:
        result["tokenMode"] = "unknown-price"
        return result
    if price <= 0:
        result["tokenMode"] = "free-unlimited"
        return result
    total = float(result.get("total", 0))
    used = float(result.get("used", 0))
    remaining = float(result.get("remaining", 0))
    result["tokenMode"] = "converted"
    result["pricePer1M"] = round(price * 1_000_000, 4)
    result["budgetTokens"] = int(total / price) if total > 0 else 0
    result["usedTokens"] = int(max(0.0, used) / price)
    result["remainingTokens"] = int(max(0.0, remaining) / price)
    return result


def main() -> int:
    record = collect()
    json.dump(record, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
