"""Thin transport adapter for the reusable data correlation method."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from data.data_processing import ProcessingError
from data.data_processing.correlation_service import correlate_acquired_series
from engine import ENGINE_VERSION
from engine.contracts import as_dict

router = APIRouter()


@router.post("/api/correlation-map")
def correlation_map(request: dict):
    # Import the application-owned inventories when called, so the route follows
    # the same configured store/cache and test injection as /api/series.
    from . import main

    try:
        inventory = [
            item
            for store in (main.live_store, main.store)
            for item in store.all_series()
            if item.get("engine_version") == ENGINE_VERSION
        ]
        result = correlate_acquired_series(
            request, series=inventory, catalog=as_dict(main.catalog)
        )
    except ProcessingError as exc:
        return JSONResponse(
            status_code=503 if exc.code == "resource_exhausted" else 422,
            content={"error": exc.as_dict()},
        )
    except MemoryError:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "resource_exhausted",
                    "message": "Not enough resources. Reduce the number of inputs and try again.",
                    "details": {},
                }
            },
        )
    return main.ok(result)
