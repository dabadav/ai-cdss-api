from fastapi import FastAPI, Depends, HTTPException, Request
from contextlib import asynccontextmanager

from ai_cdss_api.config import Settings
from ai_cdss_api.dependencies import get_settings
from ai_cdss_api.schemas import RecommendationRequest, RGSMode

from ai_cdss.cdss import CDSS
from ai_cdss.data_loader import DataLoader
from ai_cdss.data_processor import DataProcessor

from rgs_interface.data.schemas import PrescriptionStagingRow, RecsysMetricsRow

import uuid
import pandas as pd
import datetime

import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared resources
    app.state.loader = DataLoader(rgs_mode='plus')
    app.state.processor = DataProcessor(weights=[1, 1, 1], alpha=0.5)

    yield  # Startup is complete

    # Shutdown logic
    app.state.loader.interface.close()  # Close the database connection

app = FastAPI(
    title="AI-CDSS API",
    description="Clinical Decision Support System (CDSS) for personalized rehabilitation protocol recommendations.",
    version="1.0.0",
    lifespan=lifespan,
    contact={
        "name": "Eodyne Systems",
        "email": "contact@eodyne.com"
    },
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
    tags=["Recommendations"]
    )
def recommend(
    request: Request, 
    payload: RecommendationRequest,
    settings: Settings = Depends(get_settings),
):
    # from lifespan 
    loader: DataLoader = request.app.state.loader
    processor: DataProcessor = request.app.state.processor
    
    # params
    study_id = payload.study_id
    n = payload.n or settings.N
    days = payload.days or settings.DAYS
    protocols_per_day = payload.protocols_per_day or settings.PROTOCOLS_PER_DAY

    # study_id -> patient_list
    patient_data = loader.interface.fetch_patients_by_study(study_ids = study_id)
    if patient_data.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No patients found for study ID: {study_id}"
        )
    else:
        patient_list = patient_data["PATIENT_ID"].tolist()
    logger.info(f"Fetched {len(patient_list)} patients for study ID {study_id}")

    # ** LOADING DATA ** #
    session = loader.load_session_data(patient_list=patient_list)
    timeseries = loader.load_timeseries_data(patient_list=patient_list)
    ppf = loader.load_ppf_data(patient_list=patient_list)
    protocol_similarity = loader.load_protocol_similarity()
    
    # ** PROCESSING DATA ** #
    scores = processor.process_data(session_data=session, timeseries_data=timeseries, ppf_data=ppf, init_data=None) # SessionSchema, TimeseriesSchema, PPFSchema -> ScoringSchema
    #  TODO: Add whole scoring to db

    # ** BUSINESS LOGIC ** #
    cdss = CDSS(scoring=scores, n=n, days=days, protocols_per_day=protocols_per_day)
    unique_id = uuid.uuid4()

    for patient in session.PATIENT_ID.unique():

        recommendations = cdss.recommend(patient, protocol_similarity)
        prescription_df = (
            recommendations
            .explode("DAYS")
            .rename(columns={"DAYS": "WEEKDAY"})
        )
        metrics_df = pd.melt(
            recommendations,
            id_vars=["PATIENT_ID", "PROTOCOL_ID"],
            value_vars=["DELTA_DM", "ADHERENCE_RECENT", "PPF"],
            var_name="KEY",
            value_name="VALUE"
        )

        # ** DB WRITING ** #
        for _, row in prescription_df.iterrows():
            loader.interface.add_prescription_staging_entry(
                PrescriptionStagingRow.from_row(
                    row,
                    recommendation_id=unique_id,
                    start=datetime.datetime.now(),
                )
            )

        for _, row in metrics_df.iterrows():
            loader.interface.add_recsys_metrics_entry(
                RecsysMetricsRow.from_row(
                    row, 
                    recommendation_id=unique_id,
                    metric_date=datetime.datetime.now(),
                )
            )

###
### Chron -> patient info / study -> fetch_data -> process data -> write data
###