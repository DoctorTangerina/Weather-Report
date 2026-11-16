"""BS-009 (#13): live acquisition and fallback at the agreed HTTP seam."""

import pytest
from fastapi.testclient import TestClient

from api import main


def test_bs009_failed_live_fetch_returns_preloaded_example_with_notice(validator_for):
    with TestClient(main.app) as client:
        response = client.get(
            "/api/series",
            params={
                "region_id": "sahel",
                "variable_id": "temperature",
                "period_start": "2025-01",
                "period_end": "2025-12",
            },
        )
    assert response.status_code == 200
    body = response.json()
    validator_for("responses.schema.json", "#/$defs/seriesResponse").validate(body)
    assert body["data"]["region_id"] == "sahel"
    assert body["data"]["period"] == {"start": "2000-01", "end": "2024-12"}
    assert body["notice"]["code"] == "live_data_unavailable"
    assert "different" in body["notice"]["message"]
    assert body["provenance"] == "preloaded"


def test_bs009_live_success_is_reused_after_api_store_restart(
    tmp_path, stub_dir, monkeypatch, validator_for
):
    import json

    from engine import ENGINE_VERSION, JsonResultStore

    payload = json.loads((stub_dir / "series/sahel__temperature.json").read_text())
    payload.update(
        period={"start": "2025-01", "end": "2025-03"}, values=[29.1, 31.7, 28.4]
    )
    payload["quality"]["missing_fraction"] = 0.0

    async def acquire(region, variable, period, *, token):
        assert region.region_id == "sahel"
        assert variable.variable_id == "temperature"
        assert period.start == "2025-01"
        assert token == "server-only-test-token"
        return payload

    monkeypatch.setenv("EARTHDATA_TOKEN", "server-only-test-token")
    monkeypatch.setattr(main, "acquire_series", acquire, raising=False)
    monkeypatch.setattr(
        main, "live_store", JsonResultStore(tmp_path, ENGINE_VERSION), raising=False
    )
    params = {
        "region_id": "sahel",
        "variable_id": "temperature",
        "period_start": "2025-01",
        "period_end": "2025-03",
    }
    with TestClient(main.app) as client:
        first = client.get("/api/series", params=params)
    assert first.status_code == 200
    validator_for("responses.schema.json", "#/$defs/seriesResponse").validate(
        first.json()
    )
    assert first.json() == {"data": payload, "notice": None, "provenance": "live"}

    async def no_network(*args, **kwargs):
        raise AssertionError("A persisted cache hit must not acquire again")

    monkeypatch.setattr(main, "acquire_series", no_network)
    monkeypatch.setattr(main, "live_store", JsonResultStore(tmp_path, ENGINE_VERSION))
    with TestClient(main.app) as client:
        second = client.get("/api/series", params=params)
    assert second.json() == {"data": payload, "notice": None, "provenance": "cache"}
    assert "server-only-test-token" not in second.text


@pytest.mark.parametrize(
    "start,end",
    [
        ("bad", "2020-01"),
        ("2020-13", "2021-01"),
        ("2021-02", "2021-01"),
        ("0000-01", "2020-01"),
    ],
)
def test_invalid_period_is_rejected_before_acquisition(
    start, end, monkeypatch, validator_for
):
    async def unexpected(*args, **kwargs):
        raise AssertionError("Invalid periods must not reach acquisition")

    monkeypatch.setattr(main, "acquire_series", unexpected)
    with TestClient(main.app) as client:
        response = client.get(
            "/api/series",
            params={
                "region_id": "sahel",
                "variable_id": "temperature",
                "period_start": start,
                "period_end": end,
            },
        )
    assert response.status_code == 422
    validator_for("responses.schema.json", "#/$defs/errorResponse").validate(
        response.json()
    )
    assert response.json()["error"]["code"] == "invalid_period"


@pytest.fixture(autouse=True)
def isolated_live_cache(tmp_path, monkeypatch):
    from engine import ENGINE_VERSION, JsonResultStore

    monkeypatch.setattr(
        main, "live_store", JsonResultStore(tmp_path / "cache", ENGINE_VERSION)
    )
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)


def test_timeout_returns_fallback_and_cancels_acquisition(monkeypatch):
    import asyncio
    import threading

    cancelled = threading.Event()

    async def stalled(*args, **kwargs):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    monkeypatch.setenv("EARTHDATA_TOKEN", "not-for-the-client")
    monkeypatch.setattr(main, "acquire_series", stalled)
    monkeypatch.setattr(main, "LIVE_TIMEOUT_SECONDS", 0.01)
    with TestClient(main.app) as client:
        response = client.get(
            "/api/series",
            params={
                "region_id": "sahel",
                "variable_id": "temperature",
                "period_start": "2025-01",
                "period_end": "2025-03",
            },
        )
    assert response.status_code == 200
    assert response.json()["notice"]["code"] == "live_data_unavailable"
    assert cancelled.is_set()


@pytest.mark.parametrize(
    "failure",
    ["auth", "upstream", "quality", "invalid-payload", "wrong-key", "programming"],
)
def test_acquisition_failures_are_classified_without_leaking_credentials(
    failure, monkeypatch, caplog
):
    import copy

    from api.acquisition import AcquisitionUnavailable

    token = "must-stay-server-side"

    async def acquire(*args, **kwargs):
        if failure == "programming":
            raise RuntimeError("bug")
        if failure == "invalid-payload":
            return {"values": [1]}
        if failure == "wrong-key":
            return copy.deepcopy(main.store.all_series()[0])
        raise AcquisitionUnavailable(f"{failure}: secret={token}")

    monkeypatch.setenv("EARTHDATA_TOKEN", token)
    monkeypatch.setattr(main, "acquire_series", acquire)
    with TestClient(main.app) as client:
        if failure == "programming":
            with pytest.raises(RuntimeError, match="bug"):
                client.get(
                    "/api/series",
                    params={
                        "region_id": "sahel",
                        "variable_id": "temperature",
                        "period_start": "2025-01",
                        "period_end": "2025-03",
                    },
                )
            return
        response = client.get(
            "/api/series",
            params={
                "region_id": "sahel",
                "variable_id": "temperature",
                "period_start": "2025-01",
                "period_end": "2025-03",
            },
        )
    assert response.status_code == 200
    assert response.json()["notice"]["code"] == "live_data_unavailable"
    assert token not in response.text + caplog.text


def test_no_usable_examples_returns_503(tmp_path, monkeypatch, validator_for):
    from engine import ENGINE_VERSION, JsonResultStore

    monkeypatch.setattr(
        main, "store", JsonResultStore(tmp_path / "empty", ENGINE_VERSION)
    )
    with TestClient(main.app) as client:
        response = client.get(
            "/api/series", params={"region_id": "sahel", "variable_id": "temperature"}
        )
    assert response.status_code == 503
    validator_for("responses.schema.json", "#/$defs/errorResponse").validate(
        response.json()
    )
    assert response.json()["error"]["code"] == "live_data_unavailable"


@pytest.mark.parametrize("tier", ["same-pair", "same-variable", "other-variable"])
def test_examples_are_selected_by_priority_with_their_real_identity(
    tier, tmp_path, stub_dir, monkeypatch
):
    import json

    from engine import ENGINE_VERSION, JsonResultStore

    names = [
        "central-india__precipitation",
        "amazon-basin__temperature",
        "sahel__temperature",
    ]
    if tier == "same-variable":
        names.pop()
    elif tier == "other-variable":
        names = names[:1]
    directory = tmp_path / "examples" / "series"
    directory.mkdir(parents=True)
    for index, name in enumerate(names):
        (directory / f"{index}.json").write_text(
            (stub_dir / f"series/{name}.json").read_text()
        )
    monkeypatch.setattr(
        main, "store", JsonResultStore(directory.parent, ENGINE_VERSION)
    )
    expected = json.loads((stub_dir / f"series/{names[-1]}.json").read_text())
    with TestClient(main.app) as client:
        response = client.get(
            "/api/series",
            params={
                "region_id": "sahel",
                "variable_id": "temperature",
                "period_start": "2025-01",
                "period_end": "2025-03",
            },
        )
    assert response.json()["data"] == expected
    assert response.json()["provenance"] == "preloaded"


def test_exact_preloaded_example_has_provenance_without_claiming_live_failure(
    monkeypatch,
):
    async def no_network(*args, **kwargs):
        raise AssertionError("Exact preloaded examples may be served directly")

    monkeypatch.setattr(main, "acquire_series", no_network)
    with TestClient(main.app) as client:
        response = client.get(
            "/api/series", params={"region_id": "sahel", "variable_id": "temperature"}
        )
    assert response.json()["provenance"] == "preloaded"
    assert response.json()["notice"] is None


def test_storage_failure_still_returns_live_data(
    monkeypatch, stub_dir, tmp_path, caplog
):
    import json

    from engine import ENGINE_VERSION, JsonResultStore

    payload = json.loads((stub_dir / "series/sahel__temperature.json").read_text())
    payload.update(
        period={"start": "2025-01", "end": "2025-03"}, values=[27.3, 28.6, 30.1]
    )
    payload["quality"]["missing_fraction"] = 0.0

    async def acquire(*args, **kwargs):
        return payload

    # A file cannot contain a series/ directory: a real filesystem failure.
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("blocked")
    monkeypatch.setattr(main, "live_store", JsonResultStore(blocked, ENGINE_VERSION))
    monkeypatch.setenv("EARTHDATA_TOKEN", "server-only")
    monkeypatch.setattr(main, "acquire_series", acquire)
    with TestClient(main.app) as client:
        response = client.get(
            "/api/series",
            params={
                "region_id": "sahel",
                "variable_id": "temperature",
                "period_start": "2025-01",
                "period_end": "2025-03",
            },
        )
    assert response.status_code == 200
    assert response.json() == {"data": payload, "notice": None, "provenance": "live"}
    assert "could not be persisted" in caplog.text


@pytest.mark.parametrize(
    "invalid",
    [
        "schema",
        "version",
        "catalog",
        "excluded",
        "malformed-json",
        "nonfinite",
        "month-count",
    ],
)
def test_incompatible_examples_are_skipped(invalid, tmp_path, stub_dir, monkeypatch):
    import json

    from engine import ENGINE_VERSION, JsonResultStore

    directory = tmp_path / "examples" / "series"
    directory.mkdir(parents=True)
    payload = json.loads((stub_dir / "series/sahel__temperature.json").read_text())
    if invalid == "schema":
        del payload["units"]
    elif invalid == "version":
        payload["engine_version"] = "obsolete"
    elif invalid == "catalog":
        payload["region_id"] = "not-in-catalog"
    elif invalid == "excluded":
        payload["quality"]["included"] = False
    elif invalid == "nonfinite":
        payload["values"][0] = float("inf")
    elif invalid == "month-count":
        payload["values"] = [1.3, 4.9]
    text = "{broken-json" if invalid == "malformed-json" else json.dumps(payload)
    (directory / "invalid.json").write_text(text)
    monkeypatch.setattr(
        main, "store", JsonResultStore(directory.parent, ENGINE_VERSION)
    )
    with TestClient(main.app) as client:
        response = client.get(
            "/api/series", params={"region_id": "sahel", "variable_id": "temperature"}
        )
    assert response.status_code == 503
