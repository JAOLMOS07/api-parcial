from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    POINTS = "points"
    MIXED = "mixed"


class TransactionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Product(BaseModel):
    id: str
    name: str
    category: str
    price: float = Field(..., gt=0)
    stock: int = Field(..., ge=0)
    branch_id: str
    expiration_date: Optional[datetime] = None


class Customer(BaseModel):
    id: str
    name: str
    email: str
    points: int = Field(default=0, ge=0)


class TransactionItem(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)
    unit_price: float
    total_price: float


class Discount(BaseModel):
    promotion_code: str
    discount_type: str  # "percentage", "3x2", "cashback"
    discount_value: float
    applied_to: str  # "total" or product_id


class Transaction(BaseModel):
    id: str
    customer_id: str
    branch_id: str
    items: List[TransactionItem] = []
    subtotal: float = 0.0
    discounts: List[Discount] = []
    total: float = 0.0
    status: TransactionStatus = TransactionStatus.ACTIVE
    created_at: datetime
    completed_at: Optional[datetime] = None


class InventoryAdjustment(BaseModel):
    product_id: str
    branch_id: str
    adjustment_quantity: int
    reason: str
    adjusted_at: datetime = Field(default_factory=datetime.now)
    new_stock_level: int


# Request/Response Models
class StartTransactionRequest(BaseModel):
    customer_id: str
    branch_id: str


class StartTransactionResponse(BaseModel):
    transaction_id: str
    created_at: datetime


class AddProductRequest(BaseModel):
    transaction_id: str
    product_id: str
    quantity: int = Field(..., gt=0)


class AddProductResponse(BaseModel):
    transaction: Transaction
    message: str = "Product added successfully"


class ApplyPromotionRequest(BaseModel):
    transaction_id: str
    promotion_code: str


class ApplyPromotionResponse(BaseModel):
    transaction: Transaction
    discount_applied: Discount
    message: str = "Promotion applied successfully"


class FinalizeTransactionRequest(BaseModel):
    transaction_id: str
    payment_method: PaymentMethod
    amount_paid: float = Field(..., gt=0)


class Receipt(BaseModel):
    transaction_id: str
    customer_id: str
    branch_id: str
    items: List[TransactionItem]
    subtotal: float
    discounts: List[Discount]
    total: float
    payment_method: PaymentMethod
    amount_paid: float
    change: float
    completed_at: datetime


class FinalizeTransactionResponse(BaseModel):
    receipt: Receipt
    payment_confirmation: str
    message: str = "Transaction completed successfully"


class StockAvailabilityResponse(BaseModel):
    product_id: str
    stock_quantity: int
    branch_id: str
    product_name: str
    price: float


class TransferInventoryRequest(BaseModel):
    product_id: str
    from_branch_id: str
    to_branch_id: str
    quantity: int = Field(..., gt=0)


class TransferInventoryResponse(BaseModel):
    transfer_id: str
    status: str
    message: str
    transferred_at: datetime


class ExpiringProduct(BaseModel):
    product_id: str
    name: str
    branch_id: str
    stock: int
    expiration_date: datetime
    hours_until_expiration: int


class ExpiringProductsResponse(BaseModel):
    expiring_products: List[ExpiringProduct]
    total_count: int


class StockAdjustmentRequest(BaseModel):
    product_id: str
    branch_id: str
    adjustment_quantity: int
    reason: str


class StockAdjustmentResponse(BaseModel):
    adjustment: InventoryAdjustment
    message: str = "Stock adjusted successfully"


class RealTimeSalesResponse(BaseModel):
    total_sales: float
    total_transactions: int
    timestamp: datetime


class TrendingProduct(BaseModel):
    product_id: str
    name: str
    category: str
    sales_count: int
    revenue: float


class TrendingProductsResponse(BaseModel):
    trending_products: List[TrendingProduct]
    date: str


class DemandPrediction(BaseModel):
    product_id: str
    predictions: Dict[str, int]  # date -> predicted quantity
    confidence_score: float


class CustomerRecommendation(BaseModel):
    product_id: str
    name: str
    category: str
    price: float
    confidence_score: float
    reason: str


class CustomerRecommendationsResponse(BaseModel):
    customer_id: str
    recommendations: List[CustomerRecommendation]
    generated_at: datetime