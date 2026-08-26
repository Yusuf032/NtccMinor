from pydantic import BaseModel, Field
from typing import List, Optional


class CustomerData(BaseModel):
    """
    Customer profile data for banking.
    customer_id is mapped to CIN (Customer Identification Number) — 
    the same pattern used in healthcare for unique identification.
    """
    customer_id: str = Field(..., description="Customer Identification Number (CIN) — unique ID of the customer")
    name: str = Field(..., description="Full name of the customer")
    mobile: str = Field(..., description="Mobile phone number of the customer")
    email: str = Field(..., description="Email address of the customer")
    dob: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    pan_number: str = Field(..., description="PAN card number (masked/encrypted at rest)")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "CIN123456",
                "name": "Rajesh Kumar",
                "mobile": "+91-9876543210",
                "email": "rajesh.kumar@example.com",
                "dob": "1990-05-15",
                "pan_number": "ABCDE1234F"
            }
        }


class AccountData(BaseModel):
    """
    Bank account details linked to a customer.
    """
    account_id: str = Field(..., description="Unique account identifier")
    customer_id: str = Field(..., description="Customer Identification Number (CIN) — links to CustomerData")
    account_type: str = Field(..., description="Type of account (e.g., Savings, Current, FD)")
    balance: float = Field(..., description="Current account balance")
    branch_code: str = Field(..., description="Branch code of the account")
    account_status: str = Field(..., description="Status of the account (e.g., Active, Dormant, Closed)")
    last_updated: str = Field(..., description="Last updated timestamp in ISO format")

    class Config:
        json_schema_extra = {
            "example": {
                "account_id": "ACC-20250001",
                "customer_id": "CIN123456",
                "account_type": "Savings",
                "balance": 150000.50,
                "branch_code": "BR-MUM-001",
                "account_status": "Active",
                "last_updated": "2025-04-20T10:30:00Z"
            }
        }


class TransactionData(BaseModel):
    """
    Individual banking transaction record.
    """
    txn_id: str = Field(..., description="Unique transaction identifier")
    account_id: str = Field(..., description="Account ID this transaction belongs to")
    date: str = Field(..., description="Transaction date in YYYY-MM-DD format")
    amount: float = Field(..., description="Transaction amount")
    txn_type: str = Field(..., description="Transaction type (e.g., Credit, Debit, Transfer)")

    class Config:
        json_schema_extra = {
            "example": {
                "txn_id": "TXN-2025042001",
                "account_id": "ACC-20250001",
                "date": "2025-04-20",
                "amount": 25000.00,
                "txn_type": "Credit"
            }
        }


class BankingRecord(BaseModel):
    """
    Composite banking record combining customer, account, and transaction data.
    This is the top-level model for creating a complete banking record.
    
    customer_id (CIN) is the primary identifier — same pattern as healthcare CIN_1.
    """
    customer_id: str = Field(..., description="Customer Identification Number (CIN) — primary lookup key")
    customer_data: CustomerData = Field(..., description="Customer profile details")
    account_data: AccountData = Field(..., description="Account details")
    transaction_data: TransactionData = Field(..., description="Transaction details")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "CIN123456",
                "customer_data": {
                    "customer_id": "CIN123456",
                    "name": "Rajesh Kumar",
                    "mobile": "+91-9876543210",
                    "email": "rajesh.kumar@example.com",
                    "dob": "1990-05-15",
                    "pan_number": "ABCDE1234F"
                },
                "account_data": {
                    "account_id": "ACC-20250001",
                    "customer_id": "CIN123456",
                    "account_type": "Savings",
                    "balance": 150000.50,
                    "branch_code": "BR-MUM-001",
                    "account_status": "Active",
                    "last_updated": "2025-04-20T10:30:00Z"
                },
                "transaction_data": {
                    "txn_id": "TXN-2025042001",
                    "account_id": "ACC-20250001",
                    "date": "2025-04-20",
                    "amount": 25000.00,
                    "txn_type": "Credit"
                }
            }
        }


class LoadBankingEmbeddingsRequest(BaseModel):
    """Request model for loading banking embeddings. customer_id maps to CIN."""
    customer_id: str = Field(..., description="Customer Identification Number (CIN) of the customer")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "CIN123456"
            }
        }


class SearchBankingEmbeddingsRequest(BaseModel):
    """Request model for searching banking embeddings. customer_id maps to CIN."""
    customer_id: str = Field(..., description="Customer Identification Number (CIN) of the customer")
    query: str = Field(..., description="Natural language query to search for similar records")
    limit: Optional[int] = Field(10, description="Maximum number of records to return (default: 10)")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "CIN123456",
                "query": "large credit transactions last month",
                "limit": 5
            }
        }


class BankingQueryRequest(BaseModel):
    """Request model for LLM-powered banking queries. customer_id maps to CIN."""
    customer_id: str = Field(..., description="Customer Identification Number (CIN) of the customer")
    query: str = Field(..., description="Question to ask about the customer's banking history")
    limit: Optional[int] = Field(10, description="Maximum number of context records to use (default: 10)")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "CIN123456",
                "query": "What is the customer's average monthly transaction volume?",
                "limit": 10
            }
        }
