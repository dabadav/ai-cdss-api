import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from ai_cdss import DataLoader, DataProcessor
from ai_cdss.constants import (
    DEFAULT_DATA_DIR,
    DEFAULT_OUTPUT_DIR,
    PROTOCOL_ATTRIBUTES_CSV,
    PROTOCOL_SIMILARITY_CSV,
)
from ai_cdss.interface import CDSSInterface
from ai_cdss_api.config import Settings
from ai_cdss_api.dependencies import get_settings
from ai_cdss_api.schemas import RecommendationRequest
from fastapi import Depends, FastAPI, HTTPException, Request, status

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared resources
    app.state.loader = DataLoader(rgs_mode="plus")
    app.state.processor = DataProcessor(weights=[1, 1, 1], alpha=0.5)

    yield  # Startup is complete

    # Shutdown logic
    app.state.loader.interface.close()  # Close the database connection


app = FastAPI(
    title="AI-CDSS API",
    description="Clinical Decision Support System (CDSS) for personalized rehabilitation protocol recommendations.",
    version="1.0.0",
    lifespan=lifespan,
    contact={"name": "Eodyne Systems", "email": "contact@eodyne.com"},
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)


@app.post(
    "/recommend",
    summary="Get personalized rehabilitation recommendations",
    description="""
    Generate a list of protocol recommendations for each patient in the request.
    Recommendations are based on patient profiles, time series data, and computed protocol suitability.
    Each recommendation includes a computed PPF score, adherence values, usage history,
    and an explanation field identifying the top contributing clinical subscales.
    """,
    tags=["Recommendations"],
)
def recommend(
    request: Request,
    payload: RecommendationRequest,
    settings: Settings = Depends(get_settings),
):
    try:
        cdss = CDSSInterface(
            loader=request.app.state.loader, processor=request.app.state.processor
        )
        return cdss.recommend_for_study(
            study_id=payload.study_id,
            n=payload.n or settings.N,
            days=payload.days or settings.DAYS,
            protocols_per_day=payload.protocols_per_day or settings.PROTOCOLS_PER_DAY,
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve)) from ve
    except Exception as e:
        logger.exception("Unhandled error in /recommend")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.post(
    "/compute_metrics/{patient_id}",
    summary="Compute Patient-Protocol Fit",
    tags=["Recommendations"],
)
async def compute_metrics(
    patient_id: int,
    request: Request,
):
    """
    Computes Patient-Protocol Fit (PPF) and Protocol Similarity based on loaded data.
    Returns the computed PPF with contributions and the protocol similarity matrix.
    """
    try:
        cdss = CDSSInterface(
            loader=request.app.state.loader, processor=request.app.state.processor
        )
        return cdss.compute_patient_fit([patient_id])

    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve)) from ve
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re)) from re
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Unexpected error: {str(e)}"
        ) from e


@app.get("/", include_in_schema=False)
def root():
    return {"status": "ok"}


@app.get(
    "/health", summary="Health check for service and dependencies", tags=["Health"]
)
def health(request: Request):
    # Optionally check DB, cache, etc.
    loader = getattr(request.app.state, "loader", None)
    db_ok = False
    if loader and hasattr(loader, "interface") and hasattr(loader.interface, "engine"):
        try:
            with loader.interface.engine.connect() as conn:
                db_ok = True
        except Exception:
            db_ok = False

    # File checks
    files_to_check = {
        "protocol_attributes": str(DEFAULT_DATA_DIR / PROTOCOL_ATTRIBUTES_CSV),
        "protocol_similarity": str(DEFAULT_OUTPUT_DIR / PROTOCOL_SIMILARITY_CSV),
    }
    files_status = {name: Path(path).exists() for name, path in files_to_check.items()}

    return {
        "status": "ok" if db_ok and all(files_status.values()) else "degraded",
        "checks": {
            "database": "ok" if db_ok else "error",
            "files": {
                name: {"path": path, "exists": files_status[name]}
                for name, path in files_to_check.items()
            },
        },
    }
