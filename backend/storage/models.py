"""
storage/models.py
SQLAlchemy ORM models: Employee, SyncLog, KPISnapshot
"""

import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, Date, Text, Enum, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


class SourceSystem(str, enum.Enum):
    GREENHOUSE = "greenhouse"
    WORKDAY = "workday"


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "active"
    TERMINATED = "terminated"
    ON_LEAVE = "on_leave"


class SyncStatus(str, enum.Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class Employee(Base):
    """
    Unified employee record — source of truth after normalization.
    Records from both Greenhouse and Workday are merged here.
    HRIS (Workday) wins on conflict.
    """
    __tablename__ = "employees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(String(64), nullable=False)        # Business key from source
    source_system = Column(String(32), nullable=False)      # Which system last wrote this
    full_name = Column(String(256), nullable=False)
    email = Column(String(256))
    department = Column(String(128))
    job_title = Column(String(256))
    location = Column(String(128))
    status = Column(String(32), default=EmployeeStatus.ACTIVE)
    gender = Column(String(32))
    ethnicity = Column(String(64))
    hire_date = Column(Date)
    termination_date = Column(Date, nullable=True)
    manager_id = Column(String(64), nullable=True)
    salary_band = Column(String(16), nullable=True)         # Band label only, no raw figure
    last_synced_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("employee_id", "source_system", name="uq_employee_source"),
        Index("ix_employees_department", "department"),
        Index("ix_employees_status", "status"),
        Index("ix_employees_hire_date", "hire_date"),
    )

    def __repr__(self):
        return f"<Employee {self.employee_id} | {self.full_name} | {self.source_system}>"


class SyncLog(Base):
    """
    One row per sync cycle per source system.
    Tracks every API pull for auditing and debugging.
    """
    __tablename__ = "sync_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    synced_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    source_system = Column(String(32), nullable=False)
    records_pulled = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)
    conflicts_detected = Column(Integer, default=0)
    conflicts_resolved = Column(Integer, default=0)
    status = Column(String(16), default=SyncStatus.SUCCESS)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    cursor_used = Column(String(64), nullable=True)         # Last-modified timestamp used
    cursor_next = Column(String(64), nullable=True)         # Cursor to use in next sync

    __table_args__ = (
        Index("ix_sync_log_synced_at", "synced_at"),
        Index("ix_sync_log_source", "source_system"),
    )

    def __repr__(self):
        return f"<SyncLog {self.source_system} @ {self.synced_at} | {self.status}>"


class KPISnapshot(Base):
    """
    Pre-computed KPI values written by the analytics engine after each sync.
    Dimension allows slicing (e.g. kpi_name='attrition_rate', dimension='Engineering').
    """
    __tablename__ = "kpi_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_date = Column(Date, nullable=False)
    kpi_name = Column(String(128), nullable=False)          # e.g. 'attrition_rate'
    dimension = Column(String(128), default="all")          # e.g. 'Engineering', 'all'
    value = Column(Float, nullable=False)
    unit = Column(String(32), nullable=True)                # e.g. 'percent', 'count'
    computed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("snapshot_date", "kpi_name", "dimension", name="uq_kpi_snapshot"),
        Index("ix_kpi_snapshots_date", "snapshot_date"),
        Index("ix_kpi_snapshots_name", "kpi_name"),
    )

    def __repr__(self):
        return f"<KPI {self.kpi_name} [{self.dimension}] = {self.value} on {self.snapshot_date}>"
