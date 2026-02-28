"""
Finding model for storing security findings.
"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Finding(Base):
    """Security finding discovered during red team operations."""
    
    __tablename__ = "redteam_findings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium")  # critical, high, medium, low, info
    status: Mapped[str] = mapped_column(String(20), default="open")  # open, confirmed, fixed, false_positive
    category: Mapped[str] = mapped_column(String(100), nullable=True)  # BOLA, privilege_escalation, etc.
    endpoint: Mapped[str] = mapped_column(String(500), nullable=True)
    method: Mapped[str] = mapped_column(String(10), nullable=True)  # GET, POST, etc.
    evidence: Mapped[str] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=True)
    scan_id: Mapped[int] = mapped_column(Integer, nullable=True)  # Link to main Sentinel scan
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
