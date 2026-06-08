"""
SQLAlchemy data models for the FX Recovery System.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fx.db import Base


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_reference: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending_extraction")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    clauses: Mapped[list["FXClause"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="contract", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "contract_reference": self.contract_reference,
            "file_path": self.file_path,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "clause_count": len(self.clauses) if self.clauses else 0,
        }


class FXClause(Base):
    __tablename__ = "fx_clauses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(Integer, ForeignKey("contracts.id"), nullable=False)
    currency_pair: Mapped[str] = mapped_column(String(10), nullable=False)
    base_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    threshold_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    review_frequency: Mapped[str] = mapped_column(String(50), default="monthly")
    adjustment_method: Mapped[str] = mapped_column(String(50), default="full_passthrough")
    notification_period_days: Mapped[int] = mapped_column(Integer, default=30)
    clause_text: Mapped[str] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    contract: Mapped["Contract"] = relationship(back_populates="clauses")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="clause", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "currency_pair": self.currency_pair,
            "base_rate": float(self.base_rate),
            "threshold_pct": float(self.threshold_pct),
            "review_frequency": self.review_frequency,
            "adjustment_method": self.adjustment_method,
            "notification_period_days": self.notification_period_days,
            "clause_text": self.clause_text,
            "confidence_score": self.confidence_score,
            "extracted_at": self.extracted_at.isoformat() if self.extracted_at else None,
        }


class FXRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (Index("ix_fx_rates_pair_time", "currency_pair", "fetched_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    currency_pair: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="mock")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "currency_pair": self.currency_pair,
            "rate": float(self.rate),
            "source": self.source,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clause_id: Mapped[int] = mapped_column(Integer, ForeignKey("fx_clauses.id"), nullable=False)
    contract_id: Mapped[int] = mapped_column(Integer, ForeignKey("contracts.id"), nullable=False)
    currency_pair: Mapped[str] = mapped_column(String(10), nullable=False)
    base_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    current_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    deviation_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    exposure_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(50), default="triggered")
    notification_text: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    approved_by: Mapped[str] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    clause: Mapped["FXClause"] = relationship(back_populates="alerts")
    contract: Mapped["Contract"] = relationship(back_populates="alerts")

    def to_dict(self):
        # Access relationship data safely — may be detached from session
        try:
            customer_name = self.contract.customer_name if self.contract else None
            contract_ref = self.contract.contract_reference if self.contract else None
        except Exception:
            customer_name = None
            contract_ref = None

        return {
            "id": self.id,
            "clause_id": self.clause_id,
            "contract_id": self.contract_id,
            "currency_pair": self.currency_pair,
            "base_rate": float(self.base_rate),
            "current_rate": float(self.current_rate),
            "deviation_pct": float(self.deviation_pct),
            "exposure_amount": float(self.exposure_amount or 0),
            "status": self.status,
            "notification_text": self.notification_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "customer_name": customer_name,
            "contract_reference": contract_ref,
        }


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    currency_pair: Mapped[str] = mapped_column(String(10), nullable=False)
    prediction_date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, default=30)
    crossing_probability: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_direction: Mapped[str] = mapped_column(String(20), default="depreciation")
    confidence_lower: Mapped[float] = mapped_column(Float, nullable=True)
    confidence_upper: Mapped[float] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String(50), default="mavg_vol_v1")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "currency_pair": self.currency_pair,
            "prediction_date": self.prediction_date.isoformat() if self.prediction_date else None,
            "horizon_days": self.horizon_days,
            "crossing_probability": self.crossing_probability,
            "predicted_direction": self.predicted_direction,
            "confidence_lower": self.confidence_lower,
            "confidence_upper": self.confidence_upper,
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(Integer, ForeignKey("contracts.id"), nullable=False)
    currency_pair: Mapped[str] = mapped_column(String(10), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    transaction_count: Mapped[int] = mapped_column(Integer, default=0)

    contract: Mapped["Contract"] = relationship(back_populates="transactions")

    def to_dict(self):
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "currency_pair": self.currency_pair,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "volume": float(self.volume),
            "transaction_count": self.transaction_count,
        }


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=True)
    actor: Mapped[str] = mapped_column(String(255), default="system")
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=True)
    ai_model_used: Mapped[str] = mapped_column(String(100), nullable=True)
    ai_prompt_hash: Mapped[str] = mapped_column(String(64), nullable=True)
    ai_response_hash: Mapped[str] = mapped_column(String(64), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "actor": self.actor,
            "action": self.action,
            "details": self.details,
            "ai_model_used": self.ai_model_used,
        }
