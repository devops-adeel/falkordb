#!/usr/bin/env python3
"""
Islamic Finance Entity Models for Graphiti
Defines custom Pydantic models for Islamic finance concepts
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum


class AccountType(str, Enum):
    """Types of Islamic finance accounts"""
    WADIAH = "wadiah"  # Safekeeping/Current account
    MUDARABAH = "mudarabah"  # Profit-sharing savings
    MUSHARAKAH = "musharakah"  # Joint venture
    QARD = "qard"  # Interest-free loan account
    WAQF = "waqf"  # Endowment account


class TransactionType(str, Enum):
    """Types of Shariah-compliant transactions"""
    MURABAHAH = "murabahah"  # Cost-plus financing
    IJARAH = "ijarah"  # Leasing
    SALAM = "salam"  # Forward sale
    ISTISNA = "istisna"  # Manufacturing finance
    TAWARRUQ = "tawarruq"  # Monetization
    SADAQAH = "sadaqah"  # Charity
    ZAKAT = "zakat"  # Obligatory alms
    GENERAL = "general"  # General transaction


class InvestmentType(str, Enum):
    """Types of Shariah-compliant investments"""
    SUKUK = "sukuk"  # Islamic bonds
    EQUITY = "equity"  # Shariah-compliant stocks
    REITS = "reits"  # Islamic REITs
    COMMODITY = "commodity"  # Commodity murabahah
    GOLD = "gold"  # Physical gold
    PROPERTY = "property"  # Real estate


class Account(BaseModel):
    """Represents an Islamic finance account"""
    account_name: str = Field(..., description="Account name or identifier")
    account_type: AccountType = Field(..., description="Type of Islamic account")
    institution: str = Field(..., description="Financial institution name")
    balance: float = Field(0.0, description="Current balance")
    currency: str = Field("USD", description="Account currency")
    opened_date: str = Field(..., description="Account opening date (ISO format)")
    profit_rate: Optional[float] = Field(None, description="Expected profit rate (percentage)")
    is_zakat_eligible: bool = Field(True, description="Whether zakatable")
    shariah_board: Optional[str] = Field(None, description="Shariah supervisory board")
    notes: Optional[str] = Field(None, description="Additional notes")


class Transaction(BaseModel):
    """Represents a Shariah-compliant transaction"""
    transaction_id: str = Field(..., description="Unique transaction identifier")
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    amount: float = Field(..., description="Transaction amount")
    currency: str = Field("USD", description="Transaction currency")
    from_account: str = Field(..., description="Source account")
    to_account: Optional[str] = Field(None, description="Destination account")
    date: str = Field(..., description="Transaction date (ISO format)")
    description: str = Field(..., description="Transaction description")
    is_zakat_deductible: bool = Field(False, description="Whether zakat deductible")
    shariah_compliant: bool = Field(True, description="Shariah compliance status")
    contract_type: Optional[str] = Field(None, description="Islamic contract type used")
    fees: Optional[float] = Field(None, description="Transaction fees")


class ZakatCalculation(BaseModel):
    """Represents a Zakat calculation"""
    calculation_date: str = Field(..., description="Calculation date (ISO format)")
    lunar_year: str = Field(..., description="Islamic lunar year")
    total_wealth: float = Field(..., description="Total zakatable wealth")
    nisab_threshold: float = Field(..., description="Nisab threshold amount")
    eligible_wealth: float = Field(..., description="Wealth above nisab")
    zakat_rate: float = Field(0.025, description="Zakat rate (usually 2.5%)")
    zakat_due: float = Field(..., description="Total zakat amount due")
    gold_value: Optional[float] = Field(None, description="Value of gold holdings")
    silver_value: Optional[float] = Field(None, description="Value of silver holdings")
    cash_value: Optional[float] = Field(None, description="Cash and bank balances")
    investment_value: Optional[float] = Field(None, description="Zakatable investments")
    deductions: Optional[float] = Field(None, description="Debts and liabilities")
    paid_amount: float = Field(0.0, description="Amount already paid")
    remaining_due: float = Field(..., description="Remaining zakat to pay")


class Investment(BaseModel):
    """Represents a Shariah-compliant investment"""
    investment_name: str = Field(..., description="Investment name or ticker")
    investment_type: InvestmentType = Field(..., description="Type of investment")
    amount_invested: float = Field(..., description="Initial investment amount")
    current_value: float = Field(..., description="Current market value")
    purchase_date: str = Field(..., description="Purchase date (ISO format)")
    shariah_screening: bool = Field(True, description="Passed Shariah screening")
    screening_criteria: List[str] = Field(default_factory=list, description="Screening criteria used")
    profit_distribution: Optional[str] = Field(None, description="How profits are distributed")
    maturity_date: Optional[str] = Field(None, description="Maturity date if applicable")
    expected_return: Optional[float] = Field(None, description="Expected return percentage")
    risk_level: Literal["low", "medium", "high"] = Field("medium", description="Risk assessment")


class Contract(BaseModel):
    """Represents an Islamic finance contract"""
    contract_id: str = Field(..., description="Unique contract identifier")
    contract_type: str = Field(..., description="Islamic contract type (Mudarabah, Musharakah, etc.)")
    parties: List[str] = Field(..., description="Parties involved in contract")
    amount: float = Field(..., description="Contract amount")
    start_date: str = Field(..., description="Contract start date (ISO format)")
    end_date: Optional[str] = Field(None, description="Contract end date (ISO format)")
    profit_sharing_ratio: Optional[str] = Field(None, description="Profit sharing ratio (e.g., 70:30)")
    terms: List[str] = Field(default_factory=list, description="Key contract terms")
    shariah_compliant: bool = Field(True, description="Shariah compliance certification")
    status: Literal["active", "completed", "terminated"] = Field("active", description="Contract status")


class Beneficiary(BaseModel):
    """Represents a beneficiary for zakat or sadaqah"""
    beneficiary_name: str = Field(..., description="Beneficiary name or organization")
    category: Literal["fakir", "miskin", "amil", "muallaf", "riqab", "gharim", "fisabilillah", "ibnus_sabil"] = Field(
        ..., description="Zakat beneficiary category"
    )
    description: Optional[str] = Field(None, description="Description of need")
    location: Optional[str] = Field(None, description="Beneficiary location")
    verified: bool = Field(False, description="Whether verified as eligible")
    regular_recipient: bool = Field(False, description="Whether regular recipient")


# Edge type definitions for Islamic finance relationships

class Owns(BaseModel):
    """Relationship: Person/Entity owns an account or investment"""
    ownership_percentage: float = Field(100.0, description="Percentage of ownership")
    acquisition_date: str = Field(..., description="When ownership began (ISO format)")
    is_primary_owner: bool = Field(True, description="Whether primary owner")


class PaidZakat(BaseModel):
    """Relationship: Zakat payment from account to beneficiary"""
    payment_date: str = Field(..., description="Payment date (ISO format)")
    amount: float = Field(..., description="Zakat amount paid")
    payment_method: str = Field(..., description="Payment method used")
    receipt_number: Optional[str] = Field(None, description="Receipt or reference number")
    lunar_year: str = Field(..., description="Islamic year for which zakat was paid")


class InvestedIn(BaseModel):
    """Relationship: Account invested in an investment"""
    investment_date: str = Field(..., description="Investment date (ISO format)")
    amount: float = Field(..., description="Amount invested")
    expected_profit_share: Optional[float] = Field(None, description="Expected profit percentage")
    lock_in_period: Optional[int] = Field(None, description="Lock-in period in months")


class ExecutedTransaction(BaseModel):
    """Relationship: Account executed a transaction"""
    execution_date: str = Field(..., description="Execution date (ISO format)")
    status: Literal["pending", "completed", "failed", "cancelled"] = Field(
        "completed", description="Transaction status"
    )
    confirmation_number: Optional[str] = Field(None, description="Confirmation number")


class CalculatedFor(BaseModel):
    """Relationship: Zakat calculation was done for an account"""
    calculation_method: str = Field(..., description="Method used for calculation")
    includes_investments: bool = Field(True, description="Whether investments included")
    verified_by: Optional[str] = Field(None, description="Who verified the calculation")


class BoundByContract(BaseModel):
    """Relationship: Parties bound by Islamic contract"""
    role: str = Field(..., description="Role in contract (e.g., investor, entrepreneur)")
    obligations: List[str] = Field(default_factory=list, description="Contract obligations")
    profit_share: Optional[float] = Field(None, description="Profit share percentage")


# Edge type mapping for Graphiti
ISLAMIC_FINANCE_EDGE_TYPE_MAP = {
    ("Account", "Investment"): ["InvestedIn"],
    ("Account", "Transaction"): ["ExecutedTransaction"],
    ("ZakatCalculation", "Account"): ["CalculatedFor"],
    ("ZakatCalculation", "Beneficiary"): ["PaidZakat"],
    ("Account", "Beneficiary"): ["PaidZakat"],
    ("Contract", "Account"): ["BoundByContract"],
    ("Contract", "Investment"): ["BoundByContract"],
    # Note: "Owns" relationship would typically be from a Person entity to Account/Investment
}


# Entity and edge type dictionaries for Graphiti
ISLAMIC_FINANCE_ENTITY_TYPES = {
    "Account": Account,
    "Transaction": Transaction,
    "ZakatCalculation": ZakatCalculation,
    "Investment": Investment,
    "Contract": Contract,
    "Beneficiary": Beneficiary,
}


ISLAMIC_FINANCE_EDGE_TYPES = {
    "Owns": Owns,
    "PaidZakat": PaidZakat,
    "InvestedIn": InvestedIn,
    "ExecutedTransaction": ExecutedTransaction,
    "CalculatedFor": CalculatedFor,
    "BoundByContract": BoundByContract,
}