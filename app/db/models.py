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

    # НОВОЕ: связь с мастером
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

    location_type = Column(String(32), nullable=False)
    address = Column(Text, nullable=True)
    address_details = Column(Text, nullable=True)

    date_iso = Column(Date, nullable=True)
    time_slot = Column(String(32), nullable=True)
    datetime_from = Column(DateTime(timezone=True), nullable=True)
    datetime_to = Column(DateTime(timezone=True), nullable=True)

    total_amount = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(8), default="RUB", nullable=False)
    payment_status = Column(String(32), default="unpaid", nullable=False)
    paid_amount = Column(Numeric(10, 2), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    yandex_url = Column(Text, nullable=True)
    google_url = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)

    client = relationship("Client", back_populates="requests")
    time_slots = relationship("TimeSlotBooking", back_populates="request")

    # НОВОЕ: обратная связь к мастеру
    master = relationship("Master", back_populates="requests")

class Master(Base):
    __tablename__ = "master"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Привязка к MAX / ботам
    max_user_id = Column(BigInteger, nullable=False, unique=True)
    max_chat_id = Column(BigInteger, nullable=True)

    # Новые поля
    master_id = Column(String(12), unique=True, nullable=True)      # МСТР + 7 цифр
    lastname = Column(Text, nullable=True)                          # фамилия
    service_name = Column(Text, nullable=True)                      # название сервиса (для админа)
    is_admin = Column(Integer, nullable=False, default=0)           # 1 - админ, 0 - мастер

    name = Column(Text, nullable=True)
    phone = Column(String(32), nullable=True)
    email = Column(String(255), nullable=True)

    avatar_url = Column(Text, nullable=True)

    plan = Column(String(32), nullable=False, default="free")
    is_active = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    login_code = Column(String(16), nullable=True)
    login_code_expires_at = Column(DateTime(timezone=True), nullable=True)

    requests = relationship("ServiceRequest", back_populates="master")


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
    status = Column(String(32), default="active", nullable=False)  # active / cancelled

    request = relationship("ServiceRequest", back_populates="time_slots")


class DeviceCategory(Base):
    __tablename__ = "device_category"

    code = Column(String(64), primary_key=True)
    name = Column(Text, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)


class DeviceSubtype(Base):
    __tablename__ = "device_subtype"

    code = Column(String(64), primary_key=True)
    category_code = Column(String(64), ForeignKey("device_category.code"), nullable=False)
    name = Column(Text, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)