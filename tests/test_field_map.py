"""#82 / BS-012: Field maps through the agreed HTTP contract seam."""

from tests.fake_acquisition import NativeGridSource
from tests.test_explore_time_steps import job_of

pytest_plugins = ["tests.test_explore_time_steps"]


def field(client, **changes):
    return client.get(
        "/api/explore/field-map",
        params={
            "rectangle": "-1,14,4,16",
            "variable_id": "temperature",
            "time_step": "daily",
            "period_start": "2010-01",
            "period_end": "2010-01",
            **changes,
        },
    )


def test_bs012_one_value_per_cell_and_cached_background_result(api, validator_for):
    client, use = api
    source = use(
        NativeGridSource(lambda stamp, cell: float(cell + 2), longitudes=[0, 1, 2, 3])
    )
    result = job_of(client, field(client), validator_for)
    assert result["status"] == "succeeded", result
    data = result["result"]
    assert data["frames"][0] == [2, 3, 4, 5]
    assert len(data["cells"]) == 4
    assert data["cells"][0]["bbox"] == [-0.5, 14.5, 0.5, 15.5]
    assert data["timestamps"][:2] == ["2010-01-01", "2010-01-02"]
    again = field(client)
    assert again.status_code == 200
    validator_for("responses.schema.json", "#/$defs/fieldMapResponse").validate(
        again.json()
    )
    assert again.json()["data"] == data
    assert source.calls == 1


def test_bs012_colour_range_spans_the_period(api, validator_for):
    client, use = api
    use(NativeGridSource(lambda stamp, cell: -3.0 if stamp.month == 1 else 12.0))
    job = job_of(client, field(client, period_end="2010-12"), validator_for)
    assert job["status"] == "succeeded", job
    assert (job["result"]["minimum"], job["result"]["maximum"]) == (-3, 12)


def test_bs012_3_hourly_thirteen_months_names_the_one_year_limit(api, validator_for):
    client, use = api
    source = use(NativeGridSource(lambda stamp, cell: 1.0))
    response = field(client, time_step="3-hourly", period_end="2011-01")
    assert response.status_code == 422
    validator_for("responses.schema.json", "#/$defs/errorResponse").validate(
        response.json()
    )
    assert "1 year" in response.json()["error"]["message"]
    assert source.calls == 0


def test_bs006_catalog_region_uses_native_cell_bounds(api, validator_for):
    client, use = api
    use(NativeGridSource(lambda stamp, cell: float(cell + 6), longitudes=[0, 1]))
    response = client.get(
        "/api/explore/field-map",
        params={
            "region_id": "sahel",
            "variable_id": "temperature",
            "time_step": "daily",
            "period_start": "2010-01",
            "period_end": "2010-01",
        },
    )
    job = job_of(client, response, validator_for)
    assert job["status"] == "succeeded", job
    assert job["result"]["region_id"] == "sahel"
    assert job["result"]["frames"][0] == [6, 7]
    assert job["result"]["cells"][1]["bbox"] == [0.5, 14.5, 1.5, 15.5]


def test_bs014_land_mask_and_missing_cells_are_null(api, validator_for):
    from tests.fake_acquisition import FakeGridAcquisitionSource

    client, use = api
    use(
        FakeGridAcquisitionSource(
            timestamps=["2010-01-01", "2010-01-02"],
            latitudes=[15],
            longitudes=[0, 1, 2, 3],
            values=[[[2, None, 100, 200]], [[8, None, 100, 200]]],
            units="mm",
            land_mask=[[1, 1, 0, 0]],
        )
    )
    job = job_of(client, field(client, variable_id="soil-moisture"), validator_for)
    assert job["status"] == "succeeded", job
    assert job["result"]["frames"][:3] == [
        [2, None, None, None],
        [8, None, None, None],
        [None] * 4,
    ]
    assert (job["result"]["minimum"], job["result"]["maximum"]) == (2, 8)


def test_joined_rectangles_keep_only_their_cells_once(api, validator_for):
    from tests.fake_acquisition import FakeGridAcquisitionSource

    client, use = api
    use(
        FakeGridAcquisitionSource(
            timestamps=["2010-01-01"],
            latitudes=[14, 15],
            longitudes=[0, 1],
            values=[[[1, 2], [3, 4]]],
            units="°C",
        )
    )
    job = job_of(
        client,
        field(client, rectangle=["-0.5,13.5,1.5,14.5", "-0.5,14,0.5,15.5"]),
        validator_for,
    )
    assert job["status"] == "succeeded", job
    assert job["result"]["frames"][0] == [1, 2, 3]


def test_antimeridian_cells_keep_native_bounds(api, validator_for):
    client, use = api
    use(NativeGridSource(lambda stamp, cell: float(cell), longitudes=[175, 185, 0]))
    job = job_of(client, field(client, rectangle="170,14,-170,16"), validator_for)
    assert job["status"] == "succeeded", job
    assert job["result"]["frames"][0] == [0, 1]
    assert job["result"]["cells"][1]["bbox"] == [-175.5, 14.5, -174.5, 15.5]
