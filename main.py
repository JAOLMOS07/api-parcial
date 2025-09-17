import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="MegaMart Sales System",
    description="Complete supermarket sales and inventory management system",
    version="1.0.0"
)

origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URL = "mongodb+srv://mena27:12345678me@megamart.iqhvvyx.mongodb.net/"
client = AsyncIOMotorClient(MONGO_URL)
db = client.megamart

# Collections
products_collection = db.products
customers_collection = db.customers
transactions_collection = db.transactions
inventory_collection = db.inventory
branches_collection = db.branches


# Enums
class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    POINTS = "points"
    MIXED = "mixed"


# Pydantic Models
class ProductModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    category: str
    price: float
    stock: int
    expiration_date: Optional[datetime] = None
    branch_id: str

    class Config:
        populate_by_name = True


class CustomerModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    email: str
    cedula:str
    points: int = 0

    class Config:
        populate_by_name = True


class TransactionItem(BaseModel):
    product_id: str
    quantity: int
    unit_price: float
    subtotal: float


class Discount(BaseModel):
    type: str  # "3x2", "percentage", "fixed"
    amount: float
    promotion_code: str


class TransactionModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    customer_id: str
    branch_id: str
    items: List[TransactionItem] = []
    total: float = 0.0
    discounts: List[Discount] = []
    status: TransactionStatus = TransactionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    payment_method: Optional[PaymentMethod] = None
    amount_paid: float = 0.0

    class Config:
        populate_by_name = True


class BranchModel(BaseModel):
    """
    Modelo para la colección de sucursales/tiendas
    """
    id: Optional[str] = Field(alias="_id", default=None)
    branch_id: str = Field(..., description="ID único de la sucursal (ej: branch_001)")
    name: str = Field(..., description="Nombre de la sucursal")
    address: str = Field(..., description="Dirección completa de la sucursal")
    city: str = Field(..., description="Ciudad donde está ubicada")
    state: str = Field(..., description="Estado/Provincia")
    postal_code: str = Field(..., description="Código postal")
    phone: str = Field(..., description="Teléfono de contacto")
    email: str = Field(..., description="Email de la sucursal")
    manager_name: str = Field(..., description="Nombre del gerente")
    opening_hours: str = Field(..., description="Horarios de atención")
    is_active: bool = Field(default=True, description="Si la sucursal está activa")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default=None)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}



class InventoryAdjustment(BaseModel):
    product_id: str
    branch_id: str
    adjustment_quantity: int
    reason: str
    created_at: datetime = Field(default_factory=datetime.now)


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
    quantity: int


class ApplyPromotionRequest(BaseModel):
    transaction_id: str
    promotion_code: str


class FinalizeTransactionRequest(BaseModel):
    transaction_id: str
    payment_method: PaymentMethod
    amount_paid: float


class TransferInventoryRequest(BaseModel):
    product_id: str
    from_branch_id: str
    to_branch_id: str
    quantity: int


class StockAdjustmentRequest(BaseModel):
    product_id: str
    branch_id: str
    adjustment_quantity: int
    reason: str


class StockResponse(BaseModel):
    stock_quantity: int
    branch_id: str


class TransferResponse(BaseModel):
    status: str
    message: str


class ExpiringProduct(BaseModel):
    product_id: str
    name: str
    expiration_date: datetime
    stock: int
    branch_id: str


class RealTimeSales(BaseModel):
    total_sales: float
    total_transactions: int
    timestamp: datetime


class TrendingProduct(BaseModel):
    product_id: str
    name: str
    count: int


class DemandPrediction(BaseModel):
    product_id: str
    estimated_sales_next_7_days: int


class ProductRecommendation(BaseModel):
    product_id: str
    name: str
    category: str
    score: float


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


# Helper Functions
def object_id_to_str(obj):
    """Convert ObjectId to string for JSON serialization"""
    if isinstance(obj, dict):
        return {k: object_id_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [object_id_to_str(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    return obj


async def get_product_by_id(product_id: str, branch_id: str) -> Optional[dict]:
    """Get product by ID and branch"""
    try:
        product = await products_collection.find_one({
            "_id": ObjectId(product_id),
            "branch_id": branch_id
        })
        return object_id_to_str(product) if product else None
    except:
        return None


async def get_transaction_by_id(transaction_id: str) -> Optional[dict]:
    """Get transaction by ID"""
    try:
        transaction = await transactions_collection.find_one({
            "_id": ObjectId(transaction_id)
        })
        return object_id_to_str(transaction) if transaction else None
    except:
        return None


async def update_product_stock(product_id: str, branch_id: str, quantity_change: int):
    """Update product stock"""
    await products_collection.update_one(
        {"_id": ObjectId(product_id), "branch_id": branch_id},
        {"$inc": {"stock": quantity_change}}
    )


def apply_promotion_logic(items: List[TransactionItem], promotion_code: str) -> Discount:
    """Apply promotion logic based on code"""
    if promotion_code == "3X2":
        # Simple 3x2 logic - get cheapest item free for every 3 items
        if len(items) >= 3:
            cheapest_price = min(item.unit_price for item in items)
            discount_amount = cheapest_price
            return Discount(type="3x2", amount=discount_amount, promotion_code=promotion_code)

    elif promotion_code.startswith("DESC"):
        # Percentage discount
        percentage = int(promotion_code.replace("DESC", ""))
        subtotal = sum(item.subtotal for item in items)
        discount_amount = subtotal * (percentage / 100)
        return Discount(type="percentage", amount=discount_amount, promotion_code=promotion_code)

    return Discount(type="none", amount=0.0, promotion_code=promotion_code)


# API Endpoints

# Sales Endpoints
@app.post("/api/ventas/iniciar-transaccion", response_model=StartTransactionResponse)
async def start_transaction(request: StartTransactionRequest):
    """Start a new transaction"""
    try:
        # Verify customer exists
        customer = await customers_collection.find_one({"cedula": request.customer_id})
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

        # Create new transaction
        transaction_data = {
            "customer_id": request.customer_id,
            "branch_id": request.branch_id,
            "items": [],
            "total": 0.0,
            "discounts": [],
            "status": TransactionStatus.PENDING,
            "created_at": datetime.now(),
            "amount_paid": 0.0
        }

        result = await transactions_collection.insert_one(transaction_data)

        return StartTransactionResponse(
            transaction_id=str(result.inserted_id),
            created_at=transaction_data["created_at"]
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting transaction: {str(e)}"
        )


@app.post("/api/ventas/agregar-productos")
async def add_product_to_transaction(request: AddProductRequest):
    """Add product to transaction"""
    try:
        # Get transaction
        transaction = await get_transaction_by_id(request.transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )

        if transaction["status"] != TransactionStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add products to completed transaction"
            )

        # Get product and validate stock
        product = await get_product_by_id(request.product_id, transaction["branch_id"])
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found in this branch"
            )

        if product["stock"] < request.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock. Available: {product['stock']}"
            )

        # Create transaction item
        subtotal = product["price"] * request.quantity
        new_item = {
            "product_id": request.product_id,
            "quantity": request.quantity,
            "unit_price": product["price"],
            "subtotal": subtotal
        }

        # Update transaction
        await transactions_collection.update_one(
            {"_id": ObjectId(request.transaction_id)},
            {
                "$push": {"items": new_item},
                "$inc": {"total": subtotal}
            }
        )

        # Reserve stock (reduce available stock)
        await update_product_stock(request.product_id, transaction["branch_id"], -request.quantity)

        # Get updated transaction
        updated_transaction = await get_transaction_by_id(request.transaction_id)
        return updated_transaction

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding product: {str(e)}"
        )


@app.post("/api/ventas/aplicar-promocion")
async def apply_promotion(request: ApplyPromotionRequest):
    """Apply promotion to transaction"""
    try:
        # Get transaction
        transaction = await get_transaction_by_id(request.transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )

        if transaction["status"] != TransactionStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot apply promotion to completed transaction"
            )

        # Apply promotion logic
        items = [TransactionItem(**item) for item in transaction["items"]]
        discount = apply_promotion_logic(items, request.promotion_code)

        if discount.amount > 0 and (transaction['total'] - discount.amount) >= 0 :
            # Update transaction with discount
            await transactions_collection.update_one(
                {"_id": ObjectId(request.transaction_id)},
                {
                    "$push": {"discounts": discount.dict()},
                    "$inc": {"total": -discount.amount}
                }
            )

        # Get updated transaction
        updated_transaction = await get_transaction_by_id(request.transaction_id)
        return updated_transaction

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error applying promotion: {str(e)}"
        )


@app.post("/api/ventas/finalizar", response_model=Receipt)
async def finalize_transaction(request: FinalizeTransactionRequest):
    """Finalize transaction and generate receipt"""
    try:
        # Get transaction
        transaction = await get_transaction_by_id(request.transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )

        if transaction["status"] != TransactionStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction already completed"
            )

        total = transaction["total"]

        # Validate payment
        if request.amount_paid < total and request.payment_method != PaymentMethod.POINTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient payment amount"
            )

        # Handle points payment
        if request.payment_method == PaymentMethod.POINTS:
            customer = await customers_collection.find_one({"cedula": transaction["customer_id"]})
            if customer["points"] < total:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient points"
                )

            # Deduct points
            await customers_collection.update_one(
                {"cedula": transaction["customer_id"]},
                {"$inc": {"points": -int(total)}}
            )
        else:
            # Add points (1 point per dollar spent)
            await customers_collection.update_one(
                {"cedula": transaction["customer_id"]},
                {"$inc": {"points": int(total)}}
            )

        # Complete transaction
        completed_at = datetime.now()
        await transactions_collection.update_one(
            {"_id": ObjectId(request.transaction_id)},
            {
                "$set": {
                    "status": TransactionStatus.COMPLETED,
                    "payment_method": request.payment_method,
                    "amount_paid": request.amount_paid,
                    "completed_at": completed_at
                }
            }
        )

        # Calculate change
        change = max(0, request.amount_paid - total) if request.payment_method != PaymentMethod.POINTS else 0

        # Calculate subtotal (before discounts)
        subtotal = sum(item["subtotal"] for item in transaction["items"])

        # Generate receipt
        receipt = Receipt(
            transaction_id=request.transaction_id,
            customer_id=transaction["customer_id"],
            branch_id=transaction["branch_id"],
            items=[TransactionItem(**item) for item in transaction["items"]],
            subtotal=subtotal,
            discounts=[Discount(**discount) for discount in transaction["discounts"]],
            total=total,
            payment_method=request.payment_method,
            amount_paid=request.amount_paid,
            change=change,
            completed_at=completed_at
        )

        return receipt

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error finalizing transaction: {str(e)}"
        )


# Inventory Endpoints
@app.get("/api/inventario/disponibilidad/{codigo}", response_model=StockResponse)
async def check_stock_availability(codigo: str, branch_id: str):
    """Check product stock availability"""
    try:
        product = await get_product_by_id(codigo, branch_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found in this branch"
            )

        return StockResponse(
            stock_quantity=product["stock"],
            branch_id=product["branch_id"]
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking stock: {str(e)}"
        )


@app.post("/api/inventario/transferir", response_model=TransferResponse)
async def transfer_inventory(request: TransferInventoryRequest):
    """Transfer inventory between branches"""
    try:
        # Check source product stock
        source_product = await get_product_by_id(request.product_id, request.from_branch_id)
        if not source_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found in source branch"
            )

        if source_product["stock"] < request.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient stock in source branch"
            )

        # Check if product exists in destination branch
        dest_product = await get_product_by_id(request.product_id, request.to_branch_id)

        # Update source branch stock
        await update_product_stock(request.product_id, request.from_branch_id, -request.quantity)

        if dest_product:
            # Update destination branch stock
            await update_product_stock(request.product_id, request.to_branch_id, request.quantity)
        else:
            # Create product in destination branch
            new_product = source_product.copy()
            new_product["branch_id"] = request.to_branch_id
            new_product["stock"] = request.quantity
            del new_product["_id"]
            await products_collection.insert_one(new_product)

        return TransferResponse(
            status="success",
            message=f"Transferred {request.quantity} units successfully"
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error transferring inventory: {str(e)}"
        )


@app.get("/api/inventario/perecederos/vencimientos", response_model=List[ExpiringProduct])
async def get_expiring_products():
    """Get products expiring within 48 hours"""
    try:
        expiration_threshold = datetime.now() + timedelta(hours=48)

        cursor = products_collection.find({
            "expiration_date": {
                "$lte": expiration_threshold,
                "$ne": None
            }
        })

        expiring_products = []
        async for product in cursor:
            expiring_products.append(ExpiringProduct(
                product_id=str(product["_id"]),
                name=product["name"],
                expiration_date=product["expiration_date"],
                stock=product["stock"],
                branch_id=product["branch_id"]
            ))

        return expiring_products

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting expiring products: {str(e)}"
        )


@app.put("/api/inventario/ajuste-stock")
async def adjust_stock(request: StockAdjustmentRequest):
    """Adjust product stock"""
    try:
        # Verify product exists
        product = await get_product_by_id(request.product_id, request.branch_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found in this branch"
            )

        # Update stock
        await update_product_stock(request.product_id, request.branch_id, request.adjustment_quantity)

        # Record adjustment
        adjustment = InventoryAdjustment(
            product_id=request.product_id,
            branch_id=request.branch_id,
            adjustment_quantity=request.adjustment_quantity,
            reason=request.reason
        )

        await inventory_collection.insert_one(adjustment.dict())

        # Get updated stock
        updated_product = await get_product_by_id(request.product_id, request.branch_id)

        return {
            "status": "success",
            "new_stock_level": updated_product["stock"],
            "adjustment": request.adjustment_quantity,
            "reason": request.reason
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adjusting stock: {str(e)}"
        )


# Analytics Endpoints
@app.get("/api/analytics/ventas/tiempo-real", response_model=RealTimeSales)
async def get_real_time_sales():
    """Get real-time sales data for today"""
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Aggregate today's sales
        pipeline = [
            {
                "$match": {
                    "status": TransactionStatus.COMPLETED,
                    "completed_at": {"$gte": today_start, "$lt": today_end}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_sales": {"$sum": "$total"},
                    "total_transactions": {"$sum": 1}
                }
            }
        ]

        result = await transactions_collection.aggregate(pipeline).to_list(1)

        if result:
            return RealTimeSales(
                total_sales=result[0]["total_sales"],
                total_transactions=result[0]["total_transactions"],
                timestamp=datetime.now()
            )
        else:
            return RealTimeSales(
                total_sales=0.0,
                total_transactions=0,
                timestamp=datetime.now()
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting real-time sales: {str(e)}"
        )


@app.get("/api/analytics/productos/trending", response_model=List[TrendingProduct])
async def get_trending_products():
    """Get top 10 trending products for today"""
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Aggregate product sales
        pipeline = [
            {
                "$match": {
                    "status": TransactionStatus.COMPLETED,
                    "completed_at": {"$gte": today_start, "$lt": today_end}
                }
            },
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": "$items.product_id",
                    "count": {"$sum": "$items.quantity"}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]

        results = await transactions_collection.aggregate(pipeline).to_list(10)

        trending_products = []
        for result in results:
            # Get product name
            product = await products_collection.find_one({"_id": ObjectId(result["_id"])})
            product_name = product["name"] if product else "Unknown Product"

            trending_products.append(TrendingProduct(
                product_id=result["_id"],
                name=product_name,
                count=result["count"]
            ))

        return trending_products

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting trending products: {str(e)}"
        )


@app.get("/api/analytics/prediccion-demanda/{producto}", response_model=DemandPrediction)
async def predict_demand(producto: str):
    """Basic demand prediction for next 7 days"""
    try:
        # Get last 30 days of sales for this product
        thirty_days_ago = datetime.now() - timedelta(days=30)

        pipeline = [
            {
                "$match": {
                    "status": TransactionStatus.COMPLETED,
                    "completed_at": {"$gte": thirty_days_ago}
                }
            },
            {"$unwind": "$items"},
            {
                "$match": {"items.product_id": producto}
            },
            {
                "$group": {
                    "_id": None,
                    "total_quantity": {"$sum": "$items.quantity"},
                    "days_count": {"$sum": 1}
                }
            }
        ]

        result = await transactions_collection.aggregate(pipeline).to_list(1)

        if result:
            # Simple prediction: average daily sales * 7
            total_quantity = result[0]["total_quantity"]
            days_with_sales = result[0]["days_count"]
            daily_average = total_quantity / max(days_with_sales, 1)
            predicted_7_days = int(daily_average * 7)
        else:
            predicted_7_days = 0

        return DemandPrediction(
            product_id=producto,
            estimated_sales_next_7_days=predicted_7_days
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error predicting demand: {str(e)}"
        )


@app.get("/api/cliente/{id}/recomendaciones", response_model=List[ProductRecommendation])
async def get_customer_recommendations(id: str):
    """Get product recommendations for customer"""
    try:
        # Get customer's purchase history
        customer_transactions = await transactions_collection.find({
            "customer_id": id,
            "status": TransactionStatus.COMPLETED
        }).to_list(None)

        # Extract categories from purchased products
        purchased_categories = set()
        purchased_products = set()

        for transaction in customer_transactions:
            for item in transaction.get("items", []):
                purchased_products.add(item["product_id"])

                # Get product category
                product = await products_collection.find_one({"_id": ObjectId(item["product_id"])})
                if product:
                    purchased_categories.add(product["category"])

        # Find products in same categories that customer hasn't bought
        recommendations = []
        for category in purchased_categories:
            products_cursor = products_collection.find({
                "category": category,
                "stock": {"$gt": 0}
            }).limit(5)

            async for product in products_cursor:
                product_id = str(product["_id"])
                if product_id not in purchased_products:
                    recommendations.append(ProductRecommendation(
                        product_id=product_id,
                        name=product["name"],
                        category=product["category"],
                        score=0.8  # Simple static score
                    ))

        return recommendations[:10]  # Return top 10

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting recommendations: {str(e)}"
        )


# CRUD Endpoints for Entities

# Products Endpoints
@app.get("/api/productos", response_model=List[ProductModel])
async def list_products(branch_id: Optional[str] = None, category: Optional[str] = None, skip: int = 0,
                        limit: int = 100):
    """List all products with optional filtering"""
    try:
        query = {}
        if branch_id:
            query["branch_id"] = branch_id
        if category:
            query["category"] = category

        cursor = products_collection.find(query).skip(skip).limit(limit)
        products = []

        async for product in cursor:
            product_data = object_id_to_str(product)
            products.append(ProductModel(**product_data))

        return products

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing products: {str(e)}"
        )


@app.get("/api/productos/{product_id}", response_model=ProductModel)
async def get_product(product_id: str):
    """Get product by ID"""
    try:
        product = await products_collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )

        product_data = object_id_to_str(product)
        return ProductModel(**product_data)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting product: {str(e)}"
        )


# Customers Endpoints
@app.get("/api/clientes", response_model=List[CustomerModel])
async def list_customers(skip: int = 0, limit: int = 100):
    """List all customers"""
    try:
        cursor = customers_collection.find({}).skip(skip).limit(limit)
        customers = []

        async for customer in cursor:
            customer_data = object_id_to_str(customer)
            customers.append(CustomerModel(**customer_data))

        return customers

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing customers: {str(e)}"
        )


@app.get("/api/clientes/{customer_id}", response_model=CustomerModel)
async def get_customer(customer_id: str):
    """Get customer by ID"""
    try:
        customer = await customers_collection.find_one({"_id": ObjectId(customer_id)})
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

        customer_data = object_id_to_str(customer)
        return CustomerModel(**customer_data)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting customer: {str(e)}"
        )


# Transactions Endpoints
@app.get("/api/transacciones", response_model=List[TransactionModel])
async def list_transactions(
        customer_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        status_filter: Optional[TransactionStatus] = None,
        skip: int = 0,
        limit: int = 100
):
    """List all transactions with optional filtering"""
    try:
        query = {}
        if customer_id:
            query["customer_id"] = customer_id
        if branch_id:
            query["branch_id"] = branch_id
        if status_filter:
            query["status"] = status_filter

        cursor = transactions_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        transactions = []

        async for transaction in cursor:
            transaction_data = object_id_to_str(transaction)
            transactions.append(TransactionModel(**transaction_data))

        return transactions

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing transactions: {str(e)}"
        )


@app.get("/api/transacciones/{transaction_id}", response_model=TransactionModel)
async def get_transaction(transaction_id: str):
    """Get transaction by ID"""
    try:
        transaction = await get_transaction_by_id(transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )

        return TransactionModel(**transaction)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting transaction: {str(e)}"
        )


# Inventory Adjustments Endpoints
@app.get("/api/ajustes-inventario", response_model=List[InventoryAdjustment])
async def list_inventory_adjustments(
        product_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
):
    """List all inventory adjustments with optional filtering"""
    try:
        query = {}
        if product_id:
            query["product_id"] = product_id
        if branch_id:
            query["branch_id"] = branch_id

        cursor = inventory_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        adjustments = []

        async for adjustment in cursor:
            adjustment_data = object_id_to_str(adjustment)
            adjustments.append(InventoryAdjustment(**adjustment_data))

        return adjustments

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing inventory adjustments: {str(e)}"
        )

@app.get("/api/sedes", response_model=List[BranchModel])
async def list_branches(skip: int = 0, limit: int = 100):
    """List all branches"""
    try:
        cursor = branches_collection.find({}).skip(skip).limit(limit)
        branches = []

        async for branch in cursor:
            branch_data = object_id_to_str(branch)
            branches.append(BranchModel(**branch_data))

        return branches

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing customers: {str(e)}"
        )


@app.get("/api/sedes/{branch_id}", response_model=BranchModel)
async def get_branch(branch_id: str):
    """Get branch by ID"""
    try:
        branch = await branches_collection.find_one({"branch_id": branch_id})
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="branch not found"
            )

        branch_data = object_id_to_str(branch)
        return BranchModel(**branch_data)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting customer: {str(e)}"
        )

# Summary Endpoints
@app.get("/api/resumen/productos")
async def get_products_summary():
    """Get products summary statistics"""
    try:
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_products": {"$sum": 1},
                    "total_stock": {"$sum": "$stock"},
                    "categories": {"$addToSet": "$category"},
                    "branches": {"$addToSet": "$branch_id"}
                }
            }
        ]

        result = await products_collection.aggregate(pipeline).to_list(1)

        if result:
            summary = result[0]
            return {
                "total_products": summary["total_products"],
                "total_stock": summary["total_stock"],
                "total_categories": len(summary["categories"]),
                "total_branches": len(summary["branches"]),
                "categories": summary["categories"],
                "branches": summary["branches"]
            }
        else:
            return {
                "total_products": 0,
                "total_stock": 0,
                "total_categories": 0,
                "total_branches": 0,
                "categories": [],
                "branches": []
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting products summary: {str(e)}"
        )


@app.get("/api/resumen/clientes")
async def get_customers_summary():
    """Get customers summary statistics"""
    try:
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_customers": {"$sum": 1},
                    "total_points": {"$sum": "$points"},
                    "avg_points": {"$avg": "$points"}
                }
            }
        ]

        result = await customers_collection.aggregate(pipeline).to_list(1)

        if result:
            summary = result[0]
            return {
                "total_customers": summary["total_customers"],
                "total_points": summary["total_points"],
                "average_points": round(summary["avg_points"], 2) if summary["avg_points"] else 0
            }
        else:
            return {
                "total_customers": 0,
                "total_points": 0,
                "average_points": 0
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting customers summary: {str(e)}"
        )


@app.get("/api/resumen/transacciones")
async def get_transactions_summary():
    """Get transactions summary statistics"""
    try:
        pipeline = [
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "total_amount": {"$sum": "$total"}
                }
            }
        ]

        results = await transactions_collection.aggregate(pipeline).to_list(None)

        summary = {
            "total_transactions": 0,
            "total_sales": 0.0,
            "by_status": {}
        }

        for result in results:
            status = result["_id"]
            count = result["count"]
            amount = result["total_amount"]

            summary["total_transactions"] += count
            summary["total_sales"] += amount
            summary["by_status"][status] = {
                "count": count,
                "total_amount": amount
            }

        return summary

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting transactions summary: {str(e)}"
        )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        await client.admin.command('ping')
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )