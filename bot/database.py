from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    BigInteger,
    Text,
    Index,
    func,
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    relationship,
    Session as SQLAlchemySession,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import config

Base = declarative_base()


class UserRole(PyEnum):
    USER = "user"
    ADMIN = "admin"


class ProxyType(PyEnum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


class ProxyStatus(PyEnum):
    AVAILABLE = "available"
    SOLD = "sold"
    EXPIRED = "expired"
    PENDING = "pending"


class OrderStatus(PyEnum):
    PENDING = "pending"
    PAID = "paid"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class TransactionType(PyEnum):
    DEPOSIT = "deposit"
    PURCHASE = "purchase"
    REFUND = "refund"
    REFERRAL = "referral"
    WITHDRAWAL = "withdrawal"


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)  # Telegram user ID
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    language_code = Column(String(10), default="ru")
    role = Column(SQLEnum(UserRole), default=UserRole.USER)
    balance = Column(Float, default=0.0)
    referral_code = Column(String(20), unique=True, nullable=True)
    referred_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    referrals = relationship("User", backref="referrer", remote_side=[id])
    orders = relationship("Order", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    proxies = relationship("Proxy", back_populates="user")

    def __repr__(self):
        return f"<User {self.id} (@{self.username})>"


class Proxy(Base):
    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proxy6_id = Column(String(50), unique=True, nullable=True)  # ID from proxy6.net
    ip = Column(String(45), nullable=False)
    port = Column(Integer, nullable=False)
    login = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)
    type = Column(SQLEnum(ProxyType), nullable=False)
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    isp = Column(String(255), nullable=True)
    status = Column(SQLEnum(ProxyStatus), default=ProxyStatus.AVAILABLE)
    price_per_month = Column(Float, nullable=False)  # Cost from provider
    sale_price = Column(Float, nullable=False)  # Price for user (with markup)
    expires_at = Column(DateTime, nullable=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="proxies")
    order = relationship("Order", back_populates="proxies")

    # Indexes
    __table_args__ = (
        Index("ix_proxies_status_type", "status", "type"),
        Index("ix_proxies_user_status", "user_id", "status"),
    )

    def __repr__(self):
        return f"<Proxy {self.ip}:{self.port} ({self.type.value})>"

    @property
    def connection_string(self) -> str:
        if self.login and self.password:
            return f"{self.type.value}://{self.login}:{self.password}@{self.ip}:{self.port}"
        return f"{self.type.value}://{self.ip}:{self.port}"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    proxy_type = Column(SQLEnum(ProxyType), nullable=False)
    country = Column(String(100), nullable=True)
    count = Column(Integer, default=1)
    period_days = Column(Integer, default=30)
    total_price = Column(Float, nullable=False)
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING)
    yookassa_payment_id = Column(String(100), nullable=True)
    yookassa_payment_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="orders")
    proxies = relationship("Proxy", back_populates="order")

    def __repr__(self):
        return f"<Order {self.id} user={self.user_id} {self.proxy_type.value} x{self.count}>"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    type = Column(SQLEnum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)  # Positive for income, negative for expense
    balance_before = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    yookassa_payment_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="transactions")
    order = relationship("Order")

    def __repr__(self):
        return f"<Transaction {self.id} user={self.user_id} {self.type.value} {self.amount}>"


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Setting {self.key}={self.value}>"


# Async engine and session
async_engine = create_async_engine(config.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine for migrations/admin
sync_engine = create_engine(config.DATABASE_URL.replace("+aiosqlite", ""), echo=False)
SessionLocal = sessionmaker(bind=sync_engine)


async def init_db():
    """Create all tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_session() -> SQLAlchemySession:
    with SessionLocal() as session:
        yield session