from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Numeric,
    ForeignKey,
    JSON,
    Boolean,
    UniqueConstraint,  # ← ДОБАВИТЬ
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Client(Base):
    __tablename__ = "client"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=True)
    phone = Column(String(32), nullable=True, unique=True)
    primary_source = Column(String(32), nullable=True)
    max_user_id = Column(BigInteger, nullable=True)
    max_chat_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    requests = relationship("ServiceRequest", back_populates="client")


class ServiceRequest(Base):
    __tablename__ = "service_request"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    master_id = Column(BigInteger, ForeignKey("master.id"), nullable=True)
    master_seq = Column(Integer, nullable=True)

    status = Column(String(32), default="new", nullable=False)
    opened_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    in_work_at = Column(DateTime(timezone=True), nullable=True)
    done_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancel_reason = Column(Text, nullable=True)

    source = Column(String(32), nullable=False)
    user_external_id = Column(BigInteger, nullable=True)
    chat_external_id = Column(BigInteger, nullable=True)

    client_id = Column(BigInteger, ForeignKey("client.id"), nullable=True)
    client_name = Column(Text, nullable=True)
    client_phone = Column(String(32), nullable=True)

    main_category = Column(String(64), nullable=False)
    subtype = Column(String(64), nullable=False)
    custom_device = Column(Text, nullable=True)

    service_title = Column(Text, nullable=True)
    problem_description = Column(Text, nullable=False)
    what_was_done = Column(Text, nullable=True)  # nullable=True, так как может быть пустым

    location_type = Column(String(32), nullable=False)
    address = Column(Text, nullable=True)
    address_details = Column(Text, nullable=True)

    date_iso = Column(Date, nullable=True)
    time_slot = Column(String(32), nullable=True)
    datetime_from = Column(DateTime(timezone=True), nullable=True)
    datetime_to = Column(DateTime(timezone=True), nullable=True)

    total_amount = Column(Numeric(10, 2), nullable=True)
    parts_cost = Column(Numeric(12, 2), nullable=True)  # стоимость запчастей
    currency = Column(String(8), default="RUB", nullable=False)
    payment_status = Column(String(32), default="unpaid", nullable=False)
    paid_amount = Column(Numeric(10, 2), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    yandex_url = Column(Text, nullable=True)
    google_url = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)

    # Связи
    client = relationship("Client", back_populates="requests")
    time_slots = relationship("TimeSlotBooking", back_populates="request")
    master = relationship("Master", back_populates="requests")
    
    # Новая связь с источником заявок
    lead_source_id = Column(Integer, ForeignKey("lead_source.id", ondelete="SET NULL"), nullable=True)
    lead_source = relationship("LeadSource", back_populates="requests")


class Master(Base):
    __tablename__ = "master"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    max_user_id = Column(BigInteger, nullable=False, unique=True)
    max_chat_id = Column(BigInteger, nullable=True)

    master_id = Column(String(12), unique=True, nullable=True)
    lastname = Column(Text, nullable=True)
    service_name = Column(Text, nullable=True)
    service_id = Column(String(10), unique=True, nullable=True)
    is_admin = Column(Integer, nullable=False, default=0)

    name = Column(Text, nullable=True)
    phone = Column(String(32), nullable=True)
    email = Column(String(255), nullable=True)

    avatar_url = Column(Text, nullable=True)

    plan = Column(String(32), nullable=False, default="free")
    is_active = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    login_code = Column(String(16), nullable=True)
    login_code_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Связи
    requests = relationship("ServiceRequest", back_populates="master")
    device_categories = relationship("DeviceCategory", back_populates="master")
    device_subtypes = relationship("DeviceSubtype", back_populates="master")
    lead_sources = relationship("LeadSource", back_populates="master")


class TimeSlotBooking(Base):
    __tablename__ = "time_slot_booking"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    service_request_id = Column(
        BigInteger, ForeignKey("service_request.id", ondelete="CASCADE"), nullable=False
    )
    date_iso = Column(Date, nullable=False)
    time_slot = Column(String(32), nullable=False)
    datetime_from = Column(DateTime(timezone=True), nullable=False)
    datetime_to = Column(DateTime(timezone=True), nullable=False)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    status = Column(String(32), default="active", nullable=False)

    request = relationship("ServiceRequest", back_populates="time_slots")


class DeviceCategory(Base):
    __tablename__ = "device_category"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(String(10), ForeignKey("master.service_id", ondelete="CASCADE"), nullable=True)
    master_id = Column(BigInteger, ForeignKey("master.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Связи
    master = relationship("Master", back_populates="device_categories")
    subtypes = relationship("DeviceSubtype", back_populates="category")

    __table_args__ = (
        UniqueConstraint('service_id', 'master_id', 'name'),
    )


class DeviceSubtype(Base):
    __tablename__ = "device_subtype"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(String(10), ForeignKey("master.service_id", ondelete="CASCADE"), nullable=True)
    master_id = Column(BigInteger, ForeignKey("master.id", ondelete="CASCADE"), nullable=True)
    category_id = Column(Integer, ForeignKey("device_category.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(12, 2), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Связи
    master = relationship("Master", back_populates="device_subtypes")
    category = relationship("DeviceCategory", back_populates="subtypes")

    __table_args__ = (
        UniqueConstraint('service_id', 'master_id', 'category_id', 'name'),
    )


class LeadSource(Base):
    __tablename__ = "lead_source"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(String(10), ForeignKey("master.service_id", ondelete="CASCADE"), nullable=True)
    master_id = Column(BigInteger, ForeignKey("master.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Связи
    master = relationship("Master", back_populates="lead_sources")
    budgets = relationship("AdBudget", back_populates="source")
    requests = relationship("ServiceRequest", back_populates="lead_source")

    __table_args__ = (
        UniqueConstraint('service_id', 'master_id', 'name'),
    )


class AdBudget(Base):
    __tablename__ = "ad_budget"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("lead_source.id", ondelete="CASCADE"), nullable=False)
    budget_date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(8), default="RUB", nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Связи
    source = relationship("LeadSource", back_populates="budgets")

    __table_args__ = (
        UniqueConstraint('source_id', 'budget_date'),
    )