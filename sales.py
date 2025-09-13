from datetime import datetime
from typing import Dict, List, Optional
import uuid
from models import (
    Transaction, TransactionItem, Discount, Product, Customer,
    TransactionStatus, PaymentMethod, Receipt
)


class SalesService:
    def __init__(self):
        # In-memory storage
        self.transactions: Dict[str, Transaction] = {}
        self.products: Dict[str, Product] = {}
        self.customers: Dict[str, Customer] = {}
        self.promotions: Dict[str, dict] = {}
        self._init_sample_data()

    def _init_sample_data(self):
        """Initialize sample data for testing"""
        # Sample products
        sample_products = [
            Product(id="P001", name="Milk", category="Dairy", price=2.50, stock=100, branch_id="B001",
                    expiration_date=datetime(2025, 9, 15)),
            Product(id="P002", name="Bread", category="Bakery", price=1.50, stock=50, branch_id="B001",
                    expiration_date=datetime(2025, 9, 14)),
            Product(id="P003", name="Apples", category="Fruits", price=3.00, stock=75, branch_id="B001"),
            Product(id="P004", name="Chicken", category="Meat", price=8.50, stock=30, branch_id="B001",
                    expiration_date=datetime(2025, 9, 16)),
            Product(id="P005", name="Rice", category="Grains", price=4.20, stock=200, branch_id="B001"),
        ]

        for product in sample_products:
            self.products[product.id] = product

        # Sample customers
        sample_customers = [
            Customer(id="C001", name="John Doe", email="john@example.com", points=150),
            Customer(id="C002", name="Jane Smith", email="jane@example.com", points=300),
            Customer(id="C003", name="Bob Wilson", email="bob@example.com", points=75),
        ]

        for customer in sample_customers:
            self.customers[customer.id] = customer

        # Sample promotions
        self.promotions = {
            "3X2MILK": {"type": "3x2", "product_id": "P001", "description": "3x2 on Milk"},
            "BREAD50": {"type": "percentage", "value": 50, "product_id": "P002", "description": "50% off Bread"},
            "CASHBACK10": {"type": "cashback", "value": 10, "min_purchase": 20,
                           "description": "€10 cashback on purchases over €20"},
            "FRUITS20": {"type": "percentage", "value": 20, "category": "Fruits", "description": "20% off all fruits"},
        }

    async def start_transaction(self, customer_id: str, branch_id: str) -> Transaction:
        """Start a new transaction"""
        if customer_id not in self.customers:
            raise ValueError(f"Customer {customer_id} not found")

        transaction_id = f"T{uuid.uuid4().hex[:8].upper()}"
        transaction = Transaction(
            id=transaction_id,
            customer_id=customer_id,
            branch_id=branch_id,
            created_at=datetime.now()
        )

        self.transactions[transaction_id] = transaction
        return transaction

    async def add_product_to_transaction(self, transaction_id: str, product_id: str, quantity: int) -> Transaction:
        """Add a product to an existing transaction"""
        if transaction_id not in self.transactions:
            raise ValueError(f"Transaction {transaction_id} not found")

        transaction = self.transactions[transaction_id]

        if transaction.status != TransactionStatus.ACTIVE:
            raise ValueError(f"Transaction {transaction_id} is not active")

        if product_id not in self.products:
            raise ValueError(f"Product {product_id} not found")

        product = self.products[product_id]

        # Check stock availability
        if product.stock < quantity:
            raise ValueError(
                f"Insufficient stock for product {product_id}. Available: {product.stock}, Requested: {quantity}")

        # Check if product is from the same branch
        if product.branch_id != transaction.branch_id:
            raise ValueError(f"Product {product_id} is not available in branch {transaction.branch_id}")

        # Update stock (simulate real-time stock validation)
        product.stock -= quantity

        # Check if product already exists in transaction
        existing_item = None
        for item in transaction.items:
            if item.product_id == product_id:
                existing_item = item
                break

        if existing_item:
            existing_item.quantity += quantity
            existing_item.total_price = existing_item.quantity * existing_item.unit_price
        else:
            new_item = TransactionItem(
                product_id=product_id,
                quantity=quantity,
                unit_price=product.price,
                total_price=product.price * quantity
            )
            transaction.items.append(new_item)

        # Recalculate totals
        self._recalculate_transaction_totals(transaction)

        return transaction

    async def apply_promotion(self, transaction_id: str, promotion_code: str) -> tuple[Transaction, Discount]:
        """Apply a promotion to a transaction"""
        if transaction_id not in self.transactions:
            raise ValueError(f"Transaction {transaction_id} not found")

        transaction = self.transactions[transaction_id]

        if transaction.status != TransactionStatus.ACTIVE:
            raise ValueError(f"Transaction {transaction_id} is not active")

        if promotion_code not in self.promotions:
            raise ValueError(f"Promotion code {promotion_code} is not valid")

        promotion = self.promotions[promotion_code]

        # Check if promotion is already applied
        for discount in transaction.discounts:
            if discount.promotion_code == promotion_code:
                raise ValueError(f"Promotion {promotion_code} already applied to this transaction")

        discount = self._calculate_discount(transaction, promotion, promotion_code)

        if discount.discount_value > 0:
            transaction.discounts.append(discount)
            self._recalculate_transaction_totals(transaction)

        return transaction, discount

    def _calculate_discount(self, transaction: Transaction, promotion: dict, promotion_code: str) -> Discount:
        """Calculate discount based on promotion type"""
        discount_value = 0.0
        applied_to = "total"

        if promotion["type"] == "3x2":
            # Find items with the promotion product
            for item in transaction.items:
                if item.product_id == promotion["product_id"]:
                    # For every 3 items, give 1 free
                    free_items = item.quantity // 3
                    discount_value += free_items * item.unit_price
                    applied_to = item.product_id
                    break

        elif promotion["type"] == "percentage":
            if "product_id" in promotion:
                # Discount on specific product
                for item in transaction.items:
                    if item.product_id == promotion["product_id"]:
                        discount_value = item.total_price * (promotion["value"] / 100)
                        applied_to = item.product_id
                        break
            elif "category" in promotion:
                # Discount on category
                for item in transaction.items:
                    product = self.products[item.product_id]
                    if product.category == promotion["category"]:
                        discount_value += item.total_price * (promotion["value"] / 100)
                        applied_to = promotion["category"]

        elif promotion["type"] == "cashback":
            subtotal = sum(item.total_price for item in transaction.items)
            if subtotal >= promotion["min_purchase"]:
                discount_value = promotion["value"]

        return Discount(
            promotion_code=promotion_code,
            discount_type=promotion["type"],
            discount_value=discount_value,
            applied_to=applied_to
        )

    async def finalize_transaction(self, transaction_id: str, payment_method: PaymentMethod,
                                   amount_paid: float) -> Receipt:
        """Finalize a transaction and generate receipt"""
        if transaction_id not in self.transactions:
            raise ValueError(f"Transaction {transaction_id} not found")

        transaction = self.transactions[transaction_id]

        if transaction.status != TransactionStatus.ACTIVE:
            raise ValueError(f"Transaction {transaction_id} is not active")

        if amount_paid < transaction.total:
            raise ValueError(f"Insufficient payment. Required: {transaction.total}, Paid: {amount_paid}")

        # Update transaction status
        transaction.status = TransactionStatus.COMPLETED
        transaction.completed_at = datetime.now()

        # Update customer points (1 point per euro spent)
        customer = self.customers[transaction.customer_id]
        points_earned = int(transaction.total)
        customer.points += points_earned

        # Generate receipt
        receipt = Receipt(
            transaction_id=transaction.id,
            customer_id=transaction.customer_id,
            branch_id=transaction.branch_id,
            items=transaction.items,
            subtotal=transaction.subtotal,
            discounts=transaction.discounts,
            total=transaction.total,
            payment_method=payment_method,
            amount_paid=amount_paid,
            change=amount_paid - transaction.total,
            completed_at=transaction.completed_at
        )

        return receipt

    def _recalculate_transaction_totals(self, transaction: Transaction):
        """Recalculate transaction subtotal and total"""
        transaction.subtotal = sum(item.total_price for item in transaction.items)
        total_discounts = sum(discount.discount_value for discount in transaction.discounts)
        transaction.total = max(0, transaction.subtotal - total_discounts)

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction by ID"""
        return self.transactions.get(transaction_id)

    def get_product(self, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        return self.products.get(product_id)

    def get_customer(self, customer_id: str) -> Optional[Customer]:
        """Get customer by ID"""
        return self.customers.get(customer_id)