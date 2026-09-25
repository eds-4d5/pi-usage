#!/usr/bin/env python3
"""Smoke test for scripts/pi-usage.py using tests/fixture.jsonl."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pi-usage.py"
FIXTURE = ROOT / "tests" / "fixture.jsonl"

out = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=True).stdout
record = json.loads(out)
assert record["id"] == "pi", record
assert record["schemaVersion"] == 1

# Fixture parse check (independent of ~/.pi sessions on disk):
# m1: 4000+1200+8000+500=13700, m2: 1500+800+8500+100=10900, m4: 2900 fallback
# m3 is user role -> ignored
lines = FIXTURE.read_text().splitlines()
total = 0
for line in lines:
    e = json.loads(line)
    if e.get("type") == "message" and e["message"].get("role") == "assistant":
        u = e["message"]["usage"]
        t = u.get("input", 0) + u.get("output", 0) + u.get("cacheRead", 0) + u.get("cacheWrite", 0)
        if t <= 0:
            t = u.get("totalTokens", 0)
        total += t
assert total == 13700 + 10900 + 2900 == 27500, total
print(f"fixture total ok: {total}")
print(f"local record: today={record['todayTotalTokens']} totalPrompts={record['totalPrompts']} ready={record['ready']}")
print(f"local balance: {record['balance']}")
assert "balance" in record and isinstance(record["balance"], dict)

# Balance from a fresh seeded cache (no network): remaining = total - used.
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    fake_home = Path(tmp)
    (fake_home / ".pi" / "agent").mkdir(parents=True)
    (fake_home / ".pi" / "agent" / "auth.json").write_text('{"openrouter": "sk-test-fake"}')
    cache_dir = fake_home / ".cache" / "omarchy" / "pi-usage"
    cache_dir.mkdir(parents=True)
    import time as _time

    (cache_dir / "openrouter.json").write_text(
        json.dumps(
            {
                "available": True,
                "currency": "USD",
                "total": 10.0,
                "used": 2.5,
                "remaining": 7.5,
                "cached": False,
                "fetchedAtEpoch": _time.time(),
            }
        )
    )
    env = dict(os.environ, HOME=str(fake_home), XDG_CACHE_HOME=str(fake_home / ".cache"))
    out2 = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=True, env=env
    ).stdout
    rec2 = json.loads(out2)
    assert rec2["balance"]["available"] is True, rec2["balance"]
    assert rec2["balance"]["remaining"] == 7.5, rec2["balance"]
    assert "sk-test" not in out2, "key leaked into output!"
print("balance cache ok: remaining=7.5, no key in output")

# responseModel wins over the "openrouter/free" placeholder.
with tempfile.TemporaryDirectory() as tmp:
    fake_home = Path(tmp)
    sess = fake_home / ".pi" / "agent" / "sessions" / "proj"
    sess.mkdir(parents=True)
    (sess / "s.jsonl").write_text(
        '{"type":"message","id":"a1","timestamp":1795732800000,'
        '"message":{"role":"assistant","provider":"openrouter",'
        '"model":"openrouter/free","responseModel":"qwen/qwen3-8b:free",'
        '"usage":{"input":100,"output":50,"totalTokens":150}}}\n'
    )
    env = dict(os.environ, HOME=str(fake_home))
    env.pop("OPENROUTER_API_KEY", None)
    rec3 = json.loads(
        subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=True, env=env
        ).stdout
    )
    assert rec3["topModel"] == "qwen/qwen3-8b:free", rec3["topModel"]
    assert rec3["totalPrompts"] == 1, rec3["totalPrompts"]
print("responseModel ok")

# Active model = most recent assistant message, across models.
with tempfile.TemporaryDirectory() as tmp:
    fake_home = Path(tmp)
    sess = fake_home / ".pi" / "agent" / "sessions" / "proj"
    sess.mkdir(parents=True)
    (sess / "s.jsonl").write_text(
        '{"type":"message","id":"old","timestamp":1000,'
        '"message":{"role":"assistant","provider":"openrouter",'
        '"model":"openrouter/free","responseModel":"aaa/old:free",'
        '"usage":{"input":10,"output":5,"totalTokens":15}}}\n'
        '{"type":"message","id":"new","timestamp":2000,'
        '"message":{"role":"assistant","provider":"openrouter",'
        '"model":"openrouter/free","responseModel":"bbb/new:free",'
        '"usage":{"input":20,"output":5,"totalTokens":25}}}\n'
    )
    env = dict(os.environ, HOME=str(fake_home))
    env.pop("OPENROUTER_API_KEY", None)
    rec4 = json.loads(
        subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=True, env=env
        ).stdout
    )
    assert rec4["activeModel"] == "bbb/new:free", rec4["activeModel"]
    assert rec4["topModel"] == "bbb/new:free", rec4["topModel"]
print("activeModel ok")
print("OK")
