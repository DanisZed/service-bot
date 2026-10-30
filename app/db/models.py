from datetime import datetime, timezone
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
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import declarative_base, relationship



Base = declarative_base()



class ServiceCenter(Base):
    __tablename__ = "service_center"


    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(String(10), unique=True, nullable=False, index=True)
    service_name = Column(Text, nullable=False)
    address = Column(Text, nullable=True)
    website = Column(String(255), nullable=True)
    phone = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


    masters = relationship("Master", back_populates="service_center")



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


    visit_reminder_sent_at = Column(DateTime(timezone=True), nullable=True)


    # Владелец заявки: сервисный центр или мастер-одиночка.
    # Для заявки сервиса это обычно диспетчер, создавший заявку.
    master_id = Column(BigInteger, ForeignKey("master.id"), nullable=True)

    # Исполнитель заявки.
    assigned_master_id = Column(BigInteger, ForeignKey("master.id"), nullable=True)

    # Единый отображаемый номер заявки.
    # Для сервиса номер выдаётся в рамках сервисного центра,
    # для мастера-одиночки — в рамках его личного списка.
    master_seq = Column(Integer, nullable=True)


    # Владелец-сервисный центр.
    service_center_id = Column(
        Integer,
        ForeignKey("service_center.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )


    # Заявка была создана диспетчером и передана мастеру-исполнителю.
    is_from_dispatcher = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Процент диспетчера, зафиксированный на момент назначения.
    dispatcher_commission_percent = Column(
        Numeric(5, 2),
        nullable=True,
    )

    # Рассчитанное вознаграждение диспетчера.
    dispatcher_fee_amount = Column(
        Numeric(12, 2),
        nullable=True,
    )


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
    repair_description = Column(Text, nullable=True)
    what_was_done = Column(Text, nullable=True)
    warranty_period = Column(Integer, nullable=True)


    location_type = Column(String(32), nullable=False)
    address = Column(Text, nullable=True)
    address_details = Column(Text, nullable=True)


    date_iso = Column(Date, nullable=True)
    time_slot = Column(String(32), nullable=True)
    datetime_from = Column(DateTime(timezone=True), nullable=True)
    datetime_to = Column(DateTime(timezone=True), nullable=True)


    total_amount = Column(Numeric(10, 2), nullable=True)
    parts_cost = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(8), default="RUB", nullable=False)
    payment_status = Column(String(32), default="unpaid", nullable=False)
    paid_amount = Column(Numeric(10, 2), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)


    yandex_url = Column(Text, nullable=True)
    google_url = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)


    client = relationship("Client", back_populates="requests")
    time_slots = relationship("TimeSlotBooking", back_populates="request")

    master = relationship(
        "Master",
        primaryjoin="ServiceRequest.master_id == Master.id",
        back_populates="requests",
    )

    assigned_master = relationship(
        "Master",
        primaryjoin="ServiceRequest.assigned_master_id == Master.id",
        lazy="selectin",
    )

    service_center = relationship("ServiceCenter")


    lead_source_id = Column(
        Integer,
        ForeignKey("lead_source.id", ondelete="SET NULL"),
        nullable=True,
    )


    lead_source = relationship(
        "LeadSource",
        back_populates="requests",
        lazy="selectin",
    )


    @property
    def lead_source_name(self):
        return self.lead_source.name if self.lead_source else None

    @property
    def assigned_master_name(self):
        if not self.assigned_master:
            return None

        return " ".join(
            part
            for part in [
                self.assigned_master.lastname,
                self.assigned_master.name,
            ]
            if part
        ) or None



class Master(Base):
    __tablename__ = "master"


    id = Column(BigInteger, primary_key=True, autoincrement=True)


    max_user_id = Column(BigInteger, nullable=False, unique=True)
    max_chat_id = Column(BigInteger, nullable=True)


    master_id = Column(String(12), unique=True, nullable=True)
    lastname = Column(Text, nullable=True)


    is_admin = Column(Integer, nullable=False, default=0)


    service_center_id = Column(
        Integer,
        ForeignKey("service_center.id", ondelete="SET NULL"),
        nullable=True,
    )


    # Процент диспетчера от закрытой заявки,
    # переданной этому мастеру.
    dispatcher_commission_percent = Column(
        Numeric(5, 2),
        nullable=True,
    )


    name = Column(Text, nullable=True)
    phone = Column(String(32), nullable=True)
    email = Column(String(255), nullable=True)


    avatar_url = Column(Text, nullable=True)


    plan = Column(String(32), nullable=False, default="free")
    is_active = Column(Integer, nullable=False, default=1)


    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


    login_code = Column(String(16), nullable=True)
    login_code_expires_at = Column(DateTime(timezone=True), nullable=True)


    requests = relationship(
        "ServiceRequest",
        primaryjoin="Master.id == ServiceRequest.master_id",
        back_populates="master",
    )

    service_center = relationship("ServiceCenter", back_populates="masters")


    device_categories = relationship(
        "DeviceCategory",
        back_populates="master",
        foreign_keys="DeviceCategory.master_id",
    )


    device_subtypes = relationship(
        "DeviceSubtype",
        back_populates="master",
        foreign_keys="DeviceSubtype.master_id",
    )


    lead_sources = relationship(
        "LeadSource",
        back_populates="master",
        foreign_keys="LeadSource.master_id",
    )


    webpush_subscriptions = relationship(
        "WebPushSubscription",
        back_populates="master",
        cascade="all, delete-orphan",
    )


    social_links = relationship(
        "MasterSocialLink",
        back_populates="master",
        cascade="all, delete-orphan",
    )


    parts = relationship(
        "Part",
        back_populates="master",
        cascade="all, delete-orphan",
    )



class MasterSocialLink(Base):
    __tablename__ = "master_social_link"


    id = Column(Integer, primary_key=True, autoincrement=True)
    master_id = Column(BigInteger, ForeignKey("master.id", ondelete="CASCADE"), nullable=False)


    type = Column(String(32), nullable=False)
    url = Column(Text, nullable=False)


    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


    master = relationship("Master", back_populates="social_links")



class TimeSlotBooking(Base):
    __tablename__ = "time_slot_booking"


    id = Column(BigInteger, primary_key=True, autoincrement=True)
    service_request_id = Column(
        BigInteger,
        ForeignKey("service_request.id", ondelete="CASCADE"),
        nullable=False,
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

    # Владелец: либо сервисный центр, либо мастер-одиночка.
    service_center_id = Column(
        Integer,
        ForeignKey("service_center.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    master_id = Column(
        BigInteger,
        ForeignKey("master.id", ondelete="CASCADE"),
        nullable=True,
    )

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


    master = relationship(
        "Master",
        back_populates="device_categories",
        foreign_keys=[master_id],
    )

    service_center = relationship("ServiceCenter")

    subtypes = relationship("DeviceSubtype", back_populates="category")


    __table_args__ = (
        UniqueConstraint("master_id", "name"),
    )



class DeviceSubtype(Base):
    __tablename__ = "device_subtype"


    id = Column(Integer, primary_key=True, autoincrement=True)

    # Владелец: либо сервисный центр, либо мастер-одиночка.
    service_center_id = Column(
        Integer,
        ForeignKey("service_center.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    master_id = Column(
        BigInteger,
        ForeignKey("master.id", ondelete="CASCADE"),
        nullable=True,
    )

    category_id = Column(Integer, ForeignKey("device_category.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(12, 2), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


    master = relationship(
        "Master",
        back_populates="device_subtypes",
        foreign_keys=[master_id],
    )

    service_center = relationship("ServiceCenter")

    category = relationship("DeviceCategory", back_populates="subtypes")


    __table_args__ = (
        UniqueConstraint("master_id", "category_id", "name"),
    )



class LeadSource(Base):
    __tablename__ = "lead_source"


    id = Column(Integer, primary_key=True, autoincrement=True)

    # Владелец: либо сервисный центр, либо мастер-одиночка.
    service_center_id = Column(
        Integer,
        ForeignKey("service_center.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    master_id = Column(
        BigInteger,
        ForeignKey("master.id", ondelete="CASCADE"),
        nullable=True,
    )

    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_advertisable = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


    master = relationship(
        "Master",
        back_populates="lead_sources",
        foreign_keys=[master_id],
    )

    service_center = relationship("ServiceCenter")

    budgets = relationship("AdBudget", back_populates="source")
    requests = relationship("ServiceRequest", back_populates="lead_source")


    __table_args__ = (
        UniqueConstraint("master_id", "name"),
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


    source = relationship("LeadSource", back_populates="budgets")


    __table_args__ = (
        UniqueConstraint("source_id", "budget_date"),
    )



class WebPushSubscription(Base):
    __tablename__ = "webpush_subscription"


    id = Column(Integer, primary_key=True, autoincrement=True)
    master_id = Column(
        BigInteger,
        ForeignKey("master.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )


    endpoint = Column(Text, unique=True, nullable=False)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)


    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


    master = relationship("Master", back_populates="webpush_subscriptions")



class Notification(Base):
    __tablename__ = "notification"


    id = Column(BigInteger, primary_key=True, autoincrement=True)
    master_id = Column(
        BigInteger,
        ForeignKey("master.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    request_id = Column(
        BigInteger,
        ForeignKey("service_request.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )


    type = Column(String(32), nullable=False, default="visit_reminder")
    channel = Column(String(32), nullable=False, default="webpush")


    remind_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)


    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


    master = relationship("Master")
    request = relationship("ServiceRequest")



# Модели склада запчастей: поставщики, запчасти, партии закупки и списания в заявки.



class Supplier(Base):
    __tablename__ = "supplier"


    id = Column(Integer, primary_key=True, autoincrement=True)
    master_id = Column(
        Integer,
        ForeignKey("master.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    comment = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)


    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


    master = relationship("Master")
    batches = relationship("PartBatch", back_populates="supplier_rel")



class Part(Base):
    __tablename__ = "part"




    id = Column(BigInteger, primary_key=True, autoincrement=True)
    master_id = Column(
        BigInteger,
        ForeignKey("master.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )




    category = Column(String(100), nullable=False)
    name = Column(Text, nullable=False)
    item_type = Column(String(32), nullable=False, default="part")




    is_active = Column(Boolean, default=True, nullable=False)


    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )




    master = relationship("Master", back_populates="parts")
    batches = relationship(
        "PartBatch",
        back_populates="part",
        order_by="PartBatch.purchased_at",
    )



class PartBatch(Base):
    __tablename__ = "part_batch"


    id = Column(BigInteger, primary_key=True, autoincrement=True)
    part_id = Column(
        BigInteger,
        ForeignKey("part.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


    quantity_initial = Column(Integer, nullable=False)
    quantity_remaining = Column(Integer, nullable=False)


    purchase_price = Column(Numeric(12, 2), nullable=False)
    purchased_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


    supplier = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    supplier_id = Column(
        Integer,
        ForeignKey("supplier.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


    part = relationship("Part", back_populates="batches")
    supplier_rel = relationship("Supplier", back_populates="batches")
    request_parts = relationship("RequestPart", back_populates="batch")



class RequestPart(Base):
    __tablename__ = "request_part"


    id = Column(BigInteger, primary_key=True, autoincrement=True)
    request_id = Column(
        BigInteger,
        ForeignKey("service_request.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    part_id = Column(
        BigInteger,
        ForeignKey("part.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    batch_id = Column(
        BigInteger,
        ForeignKey("part_batch.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


    quantity = Column(Integer, nullable=False)
    unit_cost = Column(Numeric(12, 2), nullable=False)
    total_cost = Column(Numeric(12, 2), nullable=False)


    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


    request = relationship("ServiceRequest")
    part = relationship("Part")
    batch = relationship("PartBatch")



class PartCategory(Base):
    __tablename__ = "part_categories"



    id = Column(Integer, primary_key=True, autoincrement=True)



    master_id = Column(
        BigInteger,
        ForeignKey("master.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )



    parent_id = Column(
        Integer,
        ForeignKey("part_categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )



    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)



    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )



    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )



    master = relationship("Master")



    parent = relationship(
        "PartCategory",
        remote_side=[id],
        backref="children",
    )



    __table_args__ = (
        UniqueConstraint("master_id", "parent_id", "name"),
    )



# ========== Финансы: расходы, категории расходов и сделки перепродажи ==========



class ExpenseCategory(Base):
    __tablename__ = "expense_categories"



    id = Column(Integer, primary_key=True, autoincrement=True)



    master_id = Column(
        BigInteger,
        ForeignKey("master.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )



    parent_id = Column(
        Integer,
        ForeignKey("expense_categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )



    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)



    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )



    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )



    master = relationship("Master")



    parent = relationship(
        "ExpenseCategory",
        remote_side=[id],
        backref="children",
    )



    __table_args__ = (
        UniqueConstraint("master_id", "parent_id", "name"),
    )




class Expense(Base):
    __tablename__ = "expenses"



    id = Column(BigInteger, primary_key=True, autoincrement=True)



    master_id = Column(
        BigInteger,
        ForeignKey("master.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )



    category_id = Column(
        Integer,
        ForeignKey("expense_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )



    resale_deal_id = Column(
        BigInteger,
        ForeignKey("resale_deals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )



    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(Text, nullable=True)
    spent_at = Column(DateTime(timezone=True), nullable=False)



    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )



    category = relationship("ExpenseCategory")
    resale_deal = relationship("ResaleDeal")




class ResaleDeal(Base):
    __tablename__ = "resale_deals"



    id = Column(BigInteger, primary_key=True, autoincrement=True)



    master_id = Column(
        BigInteger,
        ForeignKey("master.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )



    title = Column(String(255), nullable=False)
    status = Column(String(32), default="purchased", nullable=False)



    purchase_amount = Column(Numeric(12, 2), default=0, nullable=False)
    sale_amount = Column(Numeric(12, 2), default=0, nullable=False)



    purchased_at = Column(DateTime(timezone=True), nullable=True)
    sold_at = Column(DateTime(timezone=True), nullable=True)



    notes = Column(Text, nullable=True)



    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )



    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )



    parts = relationship(
        "ResaleDealPart",
        back_populates="deal",
        cascade="all, delete-orphan",
    )


    resale_item_id = Column(
        BigInteger,
        ForeignKey("part.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )



    resale_item = relationship("Part")



class ResaleDealPart(Base):
    __tablename__ = "resale_deal_parts"



    id = Column(BigInteger, primary_key=True, autoincrement=True)



    deal_id = Column(
        BigInteger,
        ForeignKey("resale_deals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )



    part_id = Column(
        BigInteger,
        ForeignKey("part.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )



    batch_id = Column(
        BigInteger,
        ForeignKey("part_batch.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )



    quantity = Column(Integer, nullable=False)
    unit_cost = Column(Numeric(12, 2), nullable=False)
    total_cost = Column(Numeric(12, 2), nullable=False)



    deal = relationship("ResaleDeal", back_populates="parts")
    part = relationship("Part")
    batch = relationship("PartBatch")