"""The deployed frontend calls the API from another origin.

On Azure the static site and the API live on different hosts, so the API must
answer CORS requests from the origins listed in WEATHER_REPORT_ALLOWED_ORIGINS
and from no others. The setting is read when `api.main` is imported, so each
case runs in a fresh interpreter.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://site.example"

PROBE = """
import json
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)
simple = client.get("/api/health", headers={"Origin": ORIGIN})
preflight = client.options(
    "/api/discoveries/surprise",
    headers={
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    },
)
print(json.dumps({
    "simple": simple.headers.get("access-control-allow-origin"),
    "preflight_status": preflight.status_code,
    "preflight": preflight.headers.get("access-control-allow-origin"),
}))
"""


def probe(origin, allowed):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT), str(ROOT / "src")])}
    env.pop("WEATHER_REPORT_ALLOWED_ORIGINS", None)
    if allowed is not None:
        env["WEATHER_REPORT_ALLOWED_ORIGINS"] = allowed
    result = subprocess.run(
        [sys.executable, "-c", f"ORIGIN = {origin!r}\n{PROBE}"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_listed_origin_may_call_the_api():
    answer = probe(SITE, f"https://other.example, {SITE}/")
    assert answer == {"simple": SITE, "preflight_status": 200, "preflight": SITE}


def test_unlisted_origin_gets_no_cors_grant():
    answer = probe("https://elsewhere.example", SITE)
    assert answer["simple"] is None
    assert answer["preflight"] is None


def test_no_setting_means_no_cross_origin_access():
    answer = probe(SITE, None)
    assert answer["simple"] is None
    assert answer["preflight"] is None
