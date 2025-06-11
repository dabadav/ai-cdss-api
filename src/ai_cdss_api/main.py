from fastapi import FastAPI, Depends, HTTPException, status, Request
from contextlib import asynccontextmanager

from ai_cdss_api.config import Settings
from ai_cdss_api.dependencies import get_settings
from ai_cdss_api.schemas import RecommendationRequest

from ai_cdss.cdss import CDSS
from ai_cdss.data_loader import DataLoader, DataLoaderLocal
from ai_cdss.data_processor import DataProcessor, ClinicalSubscales, ProtocolToClinicalMapper, compute_ppf
from ai_cdss.constants import PPF_PARQUET_FILEPATH

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
    try:
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
        # SessionSchema, TimeseriesSchema, PPFSchema -> ScoringSchema
        scores = processor.process_data(session_data=session, timeseries_data=timeseries, ppf_data=ppf, init_data=None)
        #  TODO: Add whole scoring to db

        # ** BUSINESS LOGIC ** #
        cdss = CDSS(scoring=scores, n=n, days=days, protocols_per_day=protocols_per_day)
        unique_id = uuid.uuid4()
        datetime_now = datetime.datetime.now()

        for patient in patient_list:

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
                        start=datetime_now,
                    )
                )

            for _, row in metrics_df.iterrows():
                loader.interface.add_recsys_metric_entry(
                    RecsysMetricsRow.from_row(
                        row, 
                        recommendation_id=unique_id,
                        metric_date=datetime_now,
                    )
                )

            return {"message": "Recommendations generated and processed successfully."}

    except HTTPException:
        # Re-raise HTTPExceptions that were intentionally raised by previous try-except blocks
        raise
    except Exception as e:
        # This catches any unhandled exceptions that slip through the more specific blocks
        logger.critical(f"An unexpected and unhandled error in the recommend endpoint for study ID {study_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected internal server error during recommendation generation. {e}"
        )

@app.post(
    "/compute_metrics/{patient_id}", 
    summary="Compute Patient-Protocol Fit",
    tags=["Recommendations"]
    )
async def compute_metrics(
    patient_id: int,
    request: Request,
):
    """
    Computes Patient-Protocol Fit (PPF) and Protocol Similarity based on loaded data.
    Returns the computed PPF with contributions and the protocol similarity matrix.
    """

    # Load Patient Subscale Scores, and Protocol Attributes
    try:
        loader: DataLoaderLocal = request.app.state.loader

        patient = loader.load_patient_subscales([patient_id])
        if patient.empty:
            logger.critical(f"Patient data not found for ID: {patient_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient data not found for ID: {patient_id}"
            )

        protocol = loader.load_protocol_attributes()
        if protocol.empty:
            logger.critical("Protocol data could not be loaded.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Protocol data could not be loaded."
            )

        patient_deficiency = ClinicalSubscales().compute_deficit_matrix(patient)
        protocol_mapped = ProtocolToClinicalMapper().map_protocol_features(protocol)

        ppf, contrib = compute_ppf(patient_deficiency, protocol_mapped)
        ppf_contrib = pd.merge(ppf, contrib, on=["PATIENT_ID", "PROTOCOL_ID"], how="left")
        ppf_contrib.attrs = {"SUBSCALES": list(protocol_mapped.columns)}

        # Append to PPF parquet
        if not ppf_contrib.empty:
            try:
                # Check if the file already exists to decide initial write mode
                if not PPF_PARQUET_FILEPATH.exists():
                    # If file doesn't exist, create it (write mode)
                    logger.debug(f"Creating new file {PPF_PARQUET_FILEPATH}")
                    ppf_contrib.to_parquet(PPF_PARQUET_FILEPATH, index=False)
                
                # Perform upsert operation, appending new record or updating on previous patient, protocol.
                else:
                    # Read existing data
                    existing_ppf = pd.read_parquet(PPF_PARQUET_FILEPATH)

                    # Identify rows in existing_ppf that are NOT being updated by ppf_contrib
                    new_or_updated_keys = ppf_contrib[['PATIENT_ID', 'PROTOCOL_ID']]
                    # Anti-join to keep only old rows that DON'T have a match in new_or_updated_keys
                    merged = existing_ppf.merge(new_or_updated_keys, on=['PATIENT_ID', 'PROTOCOL_ID'], how='left', indicator=True)
                    filtered_existing_ppf = existing_ppf[merged['_merge'] == 'left_only']
                    updated_ppf = pd.concat([filtered_existing_ppf, ppf_contrib], ignore_index=True)

                    # Propagate metadata
                    updated_ppf.attrs = {"SUBSCALES": list(protocol_mapped.columns)}

                    # Overwrite the file with combined data
                    updated_ppf.to_parquet(PPF_PARQUET_FILEPATH)

                saved_path = str(PPF_PARQUET_FILEPATH.absolute())
                logger.debug(f"Appended results for patient {patient_id} to single Parquet file: {saved_path}")

            except Exception as parquet_err:
                logger.error(f"Error appending to single Parquet file for patient {patient_id}: {parquet_err}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail=f"Failed to save results to Parquet: {parquet_err}")
    
        else:
            print(f"No PPF data to save for patient {patient_id}. Skipping Parquet write.")

        return {
            "message": f"Computation successful for patient {patient_id}, updated file {saved_path}",
            "patient_id": patient_id,
            "subscales_used": list(protocol_mapped.columns) # Include metadata here
        }
    
    except HTTPException as e:
        raise e
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )

###
### Chron -> patient info / study -> fetch_data -> process data -> write data
###