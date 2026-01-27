from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(Text, nullable=False, default="user")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class Proposal(Base):
    __tablename__ = "proposals"

    proposal_id = Column(Text, primary_key=True)
    tenant_id = Column(Text, nullable=False)
    base_graph_version = Column(BigInteger, nullable=False)
    proposal_checksum = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    operations_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_proposals_tenant_status", "tenant_id", "status"),
        Index("idx_proposals_created_at", created_at.desc()),
    )

class AuditLog(Base):
    __tablename__ = "audit_log"

    tx_id = Column(Text, primary_key=True)
    tenant_id = Column(Text, nullable=False)
    proposal_id = Column(Text, nullable=False)
    operations_applied = Column(JSONB, nullable=False)
    revert_operations = Column(JSONB, nullable=False)
    correlation_id = Column(Text, server_default="")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_audit_log_proposal_id", "proposal_id"),
    )

class TenantGraphVersion(Base):
    __tablename__ = "tenant_graph_version"

    tenant_id = Column(Text, primary_key=True)
    graph_version = Column(BigInteger, nullable=False, server_default="0")

class GraphChange(Base):
    __tablename__ = "graph_changes"

    tenant_id = Column(Text, primary_key=True)
    graph_version = Column(BigInteger, primary_key=True)
    target_id = Column(Text, primary_key=True)
    change_type = Column(Text, server_default="")

class EventsOutbox(Base):
    __tablename__ = "events_outbox"

    event_id = Column(Text, primary_key=True)
    tenant_id = Column(Text, nullable=False)
    event_type = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False)
    published = Column(Boolean, nullable=False, server_default="false")
    attempts = Column(Integer, nullable=False, server_default="0")
    last_error = Column(Text, server_default="")
    created_at = Column(DateTime, server_default=func.now())

class Curriculum(Base):
    __tablename__ = "curricula"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    standard = Column(String(64), nullable=False)
    language = Column(String(2), nullable=False)
    status = Column(String(16), nullable=False)

class CurriculumNode(Base):
    __tablename__ = "curriculum_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    curriculum_id = Column(Integer, ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False)
    canonical_uid = Column(String(128), nullable=False)
    kind = Column(String(16), nullable=False)
    order_index = Column(Integer, nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
