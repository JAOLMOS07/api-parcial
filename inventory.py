from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid
from models import Product, InventoryAdjustment, ExpiringProduct


class InventoryService:
    def __init__(self, sales_service):
        self.sales_service = sales_service
        self.inventory_adjustments: List[InventoryAdjustment] = []
        self.transfers: Dict[str, dict] = {}

    async def get_stock_availability(self, product_code: str) -> Optional[Product]:
        """Get stock availability for a product"""
        return self.sales_service.get_product(product_code)

    async def transfer_inventory(self, product_id: str, from_branch_id: str, to_branch_id: str, quantity: int) -> dict:
        """Transfer inventory between branches"""
        # Find source product
        source_product = None
        for product in self.sales_service.products.values():
            if product.id == product_id and product.branch_id == from_branch_id:
                source_product = product
                break

        if not source_product:
            raise ValueError(f"Product {product_id} not found in branch {from_branch_id}")

        if source_product.stock < quantity:
            raise ValueError(
                f"Insufficient stock in source branch. Available: {source_product.stock}, Requested: {quantity}")

        # Find or create destination product
        destination_product = None
        for product in self.sales_service.products.values():
            if product.id == product_id and product.branch_id == to_branch_id:
                destination_product = product
                break

        if not destination_product:
            # Create new product entry for destination branch
            new_product_key = f"{product_id}_{to_branch_id}"
            destination_product = Product(
                id=product_id,
                name=source_product.name,
                category=source_product.category,
                price=source_product.price,
                stock=0,
                branch_id=to_branch_id,
                expiration_date=source_product.expiration_date
            )
            self.sales_service.products[new_product_key] = destination_product

        # Perform transfer
        source_product.stock -= quantity
        destination_product.stock += quantity

        # Record transfer
        transfer_id = f"TR{uuid.uuid4().hex[:8].upper()}"
        transfer_record = {
            "id": transfer_id,
            "product_id": product_id,
            "from_branch_id": from_branch_id,
            "to_branch_id": to_branch_id,
            "quantity": quantity,
            "status": "completed",
            "transferred_at": datetime.now()
        }

        self.transfers[transfer_id] = transfer_record

        return transfer_record

    async def get_expiring_products(self, hours: int = 48) -> List[ExpiringProduct]:
        """Get products expiring within specified hours"""
        expiring_products = []
        cutoff_time = datetime.now() + timedelta(hours=hours)

        for product in self.sales_service.products.values():
            if product.expiration_date and product.expiration_date <= cutoff_time:
                hours_until_expiration = int((product.expiration_date - datetime.now()).total_seconds() / 3600)

                if hours_until_expiration >= 0:  # Not already expired
                    expiring_product = ExpiringProduct(
                        product_id=product.id,
                        name=product.name,
                        branch_id=product.branch_id,
                        stock=product.stock,
                        expiration_date=product.expiration_date,
                        hours_until_expiration=max(0, hours_until_expiration)
                    )
                    expiring_products.append(expiring_product)

        # Sort by expiration time (soonest first)
        expiring_products.sort(key=lambda x: x.hours_until_expiration)

        return expiring_products

    async def adjust_stock(self, product_id: str, branch_id: str, adjustment_quantity: int,
                           reason: str) -> InventoryAdjustment:
        """Adjust stock levels for a product"""
        # Find the product
        target_product = None
        for product in self.sales_service.products.values():
            if product.id == product_id and product.branch_id == branch_id:
                target_product = product
                break

        if not target_product:
            raise ValueError(f"Product {product_id} not found in branch {branch_id}")

        # Check if adjustment would result in negative stock
        new_stock_level = target_product.stock + adjustment_quantity
        if new_stock_level < 0:
            raise ValueError(
                f"Stock adjustment would result in negative stock. Current: {target_product.stock}, Adjustment: {adjustment_quantity}")

        # Apply adjustment
        target_product.stock = new_stock_level

        # Record adjustment
        adjustment = InventoryAdjustment(
            product_id=product_id,
            branch_id=branch_id,
            adjustment_quantity=adjustment_quantity,
            reason=reason,
            adjusted_at=datetime.now(),
            new_stock_level=new_stock_level
        )

        self.inventory_adjustments.append(adjustment)

        return adjustment

    def get_transfer_history(self, branch_id: Optional[str] = None) -> List[dict]:
        """Get transfer history, optionally filtered by branch"""
        if branch_id:
            return [
                transfer for transfer in self.transfers.values()
                if transfer["from_branch_id"] == branch_id or transfer["to_branch_id"] == branch_id
            ]
        return list(self.transfers.values())

    def get_adjustment_history(self, product_id: Optional[str] = None, branch_id: Optional[str] = None) -> List[
        InventoryAdjustment]:
        """Get adjustment history with optional filters"""
        adjustments = self.inventory_adjustments

        if product_id:
            adjustments = [adj for adj in adjustments if adj.product_id == product_id]

        if branch_id:
            adjustments = [adj for adj in adjustments if adj.branch_id == branch_id]

        return adjustments