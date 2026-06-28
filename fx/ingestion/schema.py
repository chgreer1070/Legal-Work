"""
Pydantic models for FX clause extraction validation.
"""

from pydantic import BaseModel, Field


class FXClauseSchema(BaseModel):
    """Schema for a single extracted FX clause."""
    currency_pair: str = Field(..., description="Currency pair, e.g. USD/BRL")
    base_rate: float = Field(..., description="Contractual base exchange rate")
    threshold_pct: float = Field(..., description="Deviation percentage threshold, e.g. 3.0 for 3%")
    review_frequency: str = Field(default="monthly", description="monthly, quarterly, or annual")
    adjustment_method: str = Field(default="full_passthrough", description="full_passthrough, shared, or capped")
    notification_period_days: int = Field(default=30, description="Days notice required")
    clause_text: str = Field(default="", description="Verbatim clause text from contract")
    formula_type: str = Field(default="full_passthrough", description="full_passthrough, shared, capped, corridor, or custom")
    formula_expression: str = Field(default="", description="Arithmetic expression computing the USD adjustment amount, or empty if the clause defines none")
    formula_description: str = Field(default="", description="Plain-English description of the contract's calculation")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Extraction confidence")


class ExtractionResult(BaseModel):
    """Result of clause extraction from a contract."""
    clauses: list[FXClauseSchema] = Field(default_factory=list)
    raw_response: str = Field(default="", description="Raw LLM response for audit")
