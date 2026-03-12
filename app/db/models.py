from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    Integer,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AccrualTransaction(Base):
    """
    Stores preprocessed SAP accrual account line items.

    Source: "Data Dump - Accrual Accounts" export.
    Each row represents a single accounting document line item with its
    posting details, clearing status, and monetary value.
    """

    __tablename__ = "accrual_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # -- Organisational / categorical --
    authorization_group: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    business_transaction_type: Mapped[str] = mapped_column(
        String(4), nullable=False, index=True, comment="RFBU | RFAD | RFIV"
    )
    country_key: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, index=True, comment="USD | CAD"
    )

    # -- Flags --
    calculate_tax: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cash_flow_relevant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    document_is_back_posted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # -- Clearing info --
    is_cleared: Mapped[bool] = mapped_column(
        Boolean, nullable=False, index=True, comment="Derived from Cleared Item"
    )
    clearing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    clearing_entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    clearing_fiscal_year: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )

    # -- Monetary --
    debit_credit_indicator: Mapped[str] = mapped_column(
        String(1), nullable=False, index=True, comment="S=Debit, H=Credit"
    )
    transaction_value: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Signed amount (negative for credits)"
    )
    abs_transaction_value: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Absolute value of transaction_value"
    )
    is_credit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, index=True, comment="True when indicator is H"
    )
    is_debit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, index=True, comment="True when indicator is S"
    )
    exchange_rate: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="FX rate, populated for non-USD"
    )

    # -- Posting periods --
    original_fiscal_year: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="Fiscal Year.1 — year of original posting"
    )
    fiscal_year: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, index=True, comment="Fiscal Year.2"
    )
    posting_period: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, index=True, comment="1-12 (month)"
    )
    fiscal_period_key: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="Derived YYYYPP key"
    )
    ref_doc_line_item: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="Reference document line item"
    )

    def __repr__(self) -> str:
        return (
            f"<AccrualTransaction(id={self.id}, "
            f"type={self.business_transaction_type}, "
            f"value={self.transaction_value}, "
            f"fy={self.fiscal_year}, period={self.posting_period})>"
        )
