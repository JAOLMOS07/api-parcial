from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
import uvicorn

from models import *
from sales import SalesService
from inventory import InventoryService
from analytics import AnalyticsService

# Initialize FastAPI app
app = FastAPI(
    title="MegaMart Supermarket Sales System",
    description="RESTful API for supermarket sales, inventory, and analytics management",
    version="1.0.0"
)

# Initialize services
sales_service = SalesService()
inventory_service = InventoryService(sales_service)
analytics_service = AnalyticsService(sales_service)


# Error handler for custom exceptions
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)}
    )


# Sales Endpoints
@app.post("/api/ventas/iniciar-transaccion", response_model=StartTransactionResponse)
async def start_transaction(request: StartTransactionRequest):
    """Start a new sales transaction"""
    try:
        transaction = await sales_service.start_transaction(
            customer_id=request.customer_id,
            branch_id=request.branch_id
        )
        return StartTransactionResponse(
            transaction_id=transaction.id,
            created_at=transaction.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/ventas/agregar-producto", response_model=AddProductResponse)
async def add_product_to_transaction(request: AddProductRequest):
    """Add a product to an existing transaction with real-time stock validation"""
    try:
        transaction = await sales_service.add_product_to_transaction(
            transaction_id=request.transaction_id,
            product_id=request.product_id,
            quantity=request.quantity
        )
        return AddProductResponse(transaction=transaction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/ventas/aplicar-promocion", response_model=ApplyPromotionResponse)
async def apply_promotion(request: ApplyPromotionRequest):
    """Apply a promotion to a transaction"""
    try:
        transaction, discount = await sales_service.apply_promotion(
            transaction_id=request.transaction_id,
            promotion_code=request.promotion_code
        )
        return ApplyPromotionResponse(
            transaction=transaction,
            discount_applied=discount
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/ventas/finalizar", response_model=FinalizeTransactionResponse)
async def finalize_transaction(request: FinalizeTransactionRequest):
    """Finalize a transaction and generate receipt"""
    try:
        receipt = await sales_service.finalize_transaction(
            transaction_id=request.transaction_id,
            payment_method=request.payment_method,
            amount_paid=request.amount_paid
        )

        payment_confirmation = f"Payment of €{request.amount_paid} processed successfully via {request.payment_method.value}"

        return FinalizeTransactionResponse(
            receipt=receipt,
            payment_confirmation=payment_confirmation
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Inventory Endpoints
@app.get("/api/inventario/disponibilidad/{codigo}", response_model=StockAvailabilityResponse)
async def get_stock_availability(codigo: str):
    """Get stock availability for a product"""
    try:
        product = await inventory_service.get_stock_availability(codigo)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {codigo} not found")

        return StockAvailabilityResponse(
            product_id=product.id,
            stock_quantity=product.stock,
            branch_id=product.branch_id,
            product_name=product.name,
            price=product.price
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/inventario/transferir", response_model=TransferInventoryResponse)
async def transfer_inventory(request: TransferInventoryRequest):
    """Transfer inventory between branches"""
    try:
        transfer_record = await inventory_service.transfer_inventory(
            product_id=request.product_id,
            from_branch_id=request.from_branch_id,
            to_branch_id=request.to_branch_id,
            quantity=request.quantity
        )

        return TransferInventoryResponse(
            transfer_id=transfer_record["id"],
            status=transfer_record["status"],
            message=f"Successfully transferred {request.quantity} units from {request.from_branch_id} to {request.to_branch_id}",
            transferred_at=transfer_record["transferred_at"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/inventario/perecederos/vencimientos", response_model=ExpiringProductsResponse)
async def get_expiring_products(hours: int = 48):
    """Get products expiring within specified hours (default: 48 hours)"""
    try:
        expiring_products = await inventory_service.get_expiring_products(hours=hours)

        return ExpiringProductsResponse(
            expiring_products=expiring_products,
            total_count=len(expiring_products)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/inventario/ajuste-stock", response_model=StockAdjustmentResponse)
async def adjust_stock(request: StockAdjustmentRequest):
    """Adjust stock levels for a product"""
    try:
        adjustment = await inventory_service.adjust_stock(
            product_id=request.product_id,
            branch_id=request.branch_id,
            adjustment_quantity=request.adjustment_quantity,
            reason=request.reason
        )

        return StockAdjustmentResponse(adjustment=adjustment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Analytics Endpoints
@app.get("/api/analytics/ventas/tiempo-real", response_model=RealTimeSalesResponse)
async def get_real_time_sales():
    """Get real-time sales data"""
    try:
        sales_data = await analytics_service.get_real_time_sales()

        return RealTimeSalesResponse(
            total_sales=sales_data["total_sales"],
            total_transactions=sales_data["total_transactions"],
            timestamp=sales_data["timestamp"]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/analytics/productos/trending", response_model=TrendingProductsResponse)
async def get_trending_products():
    """Get top 10 trending products sold today"""
    try:
        trending_products = await analytics_service.get_trending_products()

        return TrendingProductsResponse(
            trending_products=trending_products,
            date=datetime.now().strftime("%Y-%m-%d")
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/analytics/prediccion-demanda/{producto}", response_model=DemandPrediction)
async def predict_demand(producto: str):
    """Get demand prediction for a product for the next 7 days"""
    try:
        prediction = await analytics_service.predict_demand(producto)
        return prediction
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/cliente/{customer_id}/recomendaciones", response_model=CustomerRecommendationsResponse)
async def get_customer_recommendations(customer_id: str):
    """Get product recommendations for a customer based on purchase history"""
    try:
        recommendations = await analytics_service.get_customer_recommendations(customer_id)

        return CustomerRecommendationsResponse(
            customer_id=customer_id,
            recommendations=recommendations,
            generated_at=datetime.now()
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Additional utility endpoints
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "service": "MegaMart Sales System"
    }


@app.get("/api/customers")
async def list_customers():
    """List all customers (for testing purposes)"""
    return {"customers": list(sales_service.customers.values())}


@app.get("/api/products")
async def list_products():
    """List all products (for testing purposes)"""
    return {"products": list(sales_service.products.values())}


@app.get("/api/promotions")
async def list_promotions():
    """List all available promotions (for testing purposes)"""
    return {"promotions": sales_service.promotions}


@app.get("/api/transactions")
async def list_transactions():
    """List all transactions (for testing purposes)"""
    return {"transactions": list(sales_service.transactions.values())}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)