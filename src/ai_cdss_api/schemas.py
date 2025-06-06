# schemas.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum

class RGSMode(str, Enum):
    app = "app"
    plus = "plus"

class RecommendationRequest(BaseModel):
    # input
    study_id: List[int] = Field(..., example=[1])
    
    # optional params
    weights: Optional[List[int]] = Field(None, example=[1, 1, 1])
    alpha: Optional[float] = Field(None, example=0.5)
    n: Optional[int] = Field(None, example=12) # Diversity
    days: Optional[int] = Field(None, example=7) # Num days
    protocols_per_day: Optional[int] = Field(None, example=5) # Intensity

    @field_validator("study_id")
    @classmethod
    def validate_study_id(cls, v):
        if not isinstance(v, list):
            raise ValueError("study_id must be a list of integers")
        if not v:
            raise ValueError("study_id must be a non-empty list")
        if not all(isinstance(i, int) for i in v):
            raise ValueError("All study_id values must be integers")
        return v
    
    @field_validator("weights")
    @classmethod
    def validate_weights(cls, v):
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("weights must be a list of integers")
            if not all(isinstance(i, int) and i > 0 for i in v):
                raise ValueError("All weights must be positive integers")
        return v
    
    @field_validator("alpha")
    @classmethod
    def validate_alpha(cls, v):
        if v is not None:
            if not isinstance(v, (float, int)) or not (0 <= v <= 1):
                raise ValueError("alpha must be a number between 0 and 1")
        return v
    
    @field_validator("n", "days", "protocols_per_day")
    @classmethod
    def validate_positive_integers(cls, v, field):
        if v is not None:
            if not isinstance(v, int) or v <= 0:
                raise ValueError(f"{field.name} must be a positive integer")
        return v
