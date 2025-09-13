from datetime import datetime, timedelta
from typing import Dict, List
from collections import defaultdict, Counter
import random
from models import (
    TransactionStatus, TrendingProduct, DemandPrediction,
    CustomerRecommendation, Transaction
)


class AnalyticsService:
    def __init__(self, sales_service):
        self.sales_service = sales_service
        # Simulate purchase history for recommendations
        self.purchase_history: Dict[str, List[str]] = {
            "C001": ["P001", "P002", "P003", "P001", "P005"],
            "C002": ["P002", "P004", "P003", "P005", "P001"],
            "C003": ["P001", "P003", "P004", "P002", "P005"],
        }

    async def get_real_time_sales(self) -> dict:
        """Get real-time sales data for today"""
        today = datetime.now().date()
        today_transactions = [
            t for t in self.sales_service.transactions.values()
            if t.created_at.date() == today and t.status == TransactionStatus.COMPLETED
        ]

        total_sales = sum(t.total for t in today_transactions)
        total_transactions = len(today_transactions)

        return {
            "total_sales": round(total_sales, 2),
            "total_transactions": total_transactions,
            "timestamp": datetime.now()
        }

    async def get_trending_products(self) -> List[TrendingProduct]:
        """Get top 10 trending products for today"""
        today = datetime.now().date()

        # Get completed transactions from today
        today_transactions = [
            t for t in self.sales_service.transactions.values()
            if t.created_at.date() == today and t.status == TransactionStatus.COMPLETED
        ]

        # Count product sales
        product_sales = defaultdict(lambda: {"count": 0, "revenue": 0.0})

        for transaction in today_transactions:
            for item in transaction.items:
                product_sales[item.product_id]["count"] += item.quantity
                product_sales[item.product_id]["revenue"] += item.total_price

        # Create trending products list
        trending_products = []

        # If no real sales today, simulate some data for demonstration
        if not product_sales:
            sample_sales = {
                "P001": {"count": 25, "revenue": 62.5},
                "P002": {"count": 18, "revenue": 27.0},
                "P003": {"count": 15, "revenue": 45.0},
                "P004": {"count": 12, "revenue": 102.0},
                "P005": {"count": 30, "revenue": 126.0},
            }
            product_sales.update(sample_sales)

        for product_id, sales_data in product_sales.items():
            product = self.sales_service.get_product(product_id)
            if product:
                trending_product = TrendingProduct(
                    product_id=product_id,
                    name=product.name,
                    category=product.category,
                    sales_count=sales_data["count"],
                    revenue=round(sales_data["revenue"], 2)
                )
                trending_products.append(trending_product)

        # Sort by sales count (descending) and take top 10
        trending_products.sort(key=lambda x: x.sales_count, reverse=True)
        return trending_products[:10]

    async def predict_demand(self, product_id: str) -> DemandPrediction:
        """Predict demand for a product for the next 7 days"""
        product = self.sales_service.get_product(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Simulate demand prediction based on historical patterns
        base_demand = self._calculate_base_demand(product_id)
        predictions = {}

        # Generate predictions for next 7 days
        for i in range(1, 8):
            future_date = datetime.now() + timedelta(days=i)
            date_str = future_date.strftime("%Y-%m-%d")

            # Simulate seasonal variations and trends
            day_of_week = future_date.weekday()
            weekend_multiplier = 1.3 if day_of_week >= 5 else 1.0
            random_variation = random.uniform(0.8, 1.2)

            predicted_quantity = int(base_demand * weekend_multiplier * random_variation)
            predictions[date_str] = max(1, predicted_quantity)

        # Calculate confidence score based on historical data availability
        confidence_score = random.uniform(0.75, 0.95)  # Simulate varying confidence

        return DemandPrediction(
            product_id=product_id,
            predictions=predictions,
            confidence_score=round(confidence_score, 2)
        )

    def _calculate_base_demand(self, product_id: str) -> int:
        """Calculate base daily demand for a product"""
        # Simulate historical sales analysis
        product_demand_map = {
            "P001": 8,  # Milk - high daily demand
            "P002": 12,  # Bread - very high daily demand
            "P003": 6,  # Apples - moderate demand
            "P004": 4,  # Chicken - lower demand
            "P005": 5,  # Rice - stable demand
        }

        return product_demand_map.get(product_id, 3)  # Default to 3 if not found

    async def get_customer_recommendations(self, customer_id: str) -> List[CustomerRecommendation]:
        """Get product recommendations for a customer based on purchase history"""
        if customer_id not in self.sales_service.customers:
            raise ValueError(f"Customer {customer_id} not found")

        # Get customer's purchase history
        customer_purchases = self.purchase_history.get(customer_id, [])

        if not customer_purchases:
            # Return popular products for new customers
            return await self._get_popular_product_recommendations()

        # Analyze purchase patterns
        purchase_counter = Counter(customer_purchases)
        favorite_categories = self._get_favorite_categories(customer_purchases)

        recommendations = []

        # Recommend products from favorite categories that customer hasn't bought much
        all_products = list(self.sales_service.products.values())

        for product in all_products:
            if product.category in favorite_categories:
                purchase_count = purchase_counter.get(product.id, 0)

                # Calculate confidence score based on category preference and purchase frequency
                category_preference = favorite_categories[product.category] / len(customer_purchases)
                recency_factor = 1.0 - (purchase_count / max(len(customer_purchases), 1))

                confidence_score = (category_preference + recency_factor) / 2

                if confidence_score > 0.3:  # Minimum threshold for recommendations
                    reason = f"Based on your preference for {product.category} products"
                    if purchase_count == 0:
                        reason += " (new item you might like)"

                    recommendation = CustomerRecommendation(
                        product_id=product.id,
                        name=product.name,
                        category=product.category,
                        price=product.price,
                        confidence_score=round(confidence_score, 2),
                        reason=reason
                    )
                    recommendations.append(recommendation)

        # Sort by confidence score (descending) and return top 5
        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        return recommendations[:5]

    def _get_favorite_categories(self, purchases: List[str]) -> Dict[str, int]:
        """Get customer's favorite categories based on purchase history"""
        category_counts = defaultdict(int)

        for product_id in purchases:
            product = self.sales_service.get_product(product_id)
            if product:
                category_counts[product.category] += 1

        return dict(category_counts)

    async def _get_popular_product_recommendations(self) -> List[CustomerRecommendation]:
        """Get popular product recommendations for new customers"""
        # Return top products based on general popularity
        popular_products = [
            ("P001", "Popular daily essential", 0.9),
            ("P002", "Customer favorite", 0.85),
            ("P003", "Healthy choice", 0.8),
            ("P005", "Pantry staple", 0.75),
            ("P004", "Quality protein source", 0.7),
        ]

        recommendations = []
        for product_id, reason, confidence in popular_products:
            product = self.sales_service.get_product(product_id)
            if product:
                recommendation = CustomerRecommendation(
                    product_id=product_id,
                    name=product.name,
                    category=product.category,
                    price=product.price,
                    confidence_score=confidence,
                    reason=reason
                )
                recommendations.append(recommendation)

        return recommendations

    async def get_branch_performance(self, branch_id: str) -> dict:
        """Get performance metrics for a specific branch"""
        branch_transactions = [
            t for t in self.sales_service.transactions.values()
            if t.branch_id == branch_id and t.status == TransactionStatus.COMPLETED
        ]

        if not branch_transactions:
            return {
                "branch_id": branch_id,
                "total_revenue": 0.0,
                "transaction_count": 0,
                "average_transaction_value": 0.0,
                "top_categories": []
            }

        total_revenue = sum(t.total for t in branch_transactions)
        transaction_count = len(branch_transactions)
        average_transaction_value = total_revenue / transaction_count if transaction_count > 0 else 0

        # Calculate top categories
        category_sales = defaultdict(float)
        for transaction in branch_transactions:
            for item in transaction.items:
                product = self.sales_service.get_product(item.product_id)
                if product:
                    category_sales[product.category] += item.total_price

        top_categories = sorted(category_sales.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "branch_id": branch_id,
            "total_revenue": round(total_revenue, 2),
            "transaction_count": transaction_count,
            "average_transaction_value": round(average_transaction_value, 2),
            "top_categories": [{"category": cat, "revenue": round(rev, 2)} for cat, rev in top_categories]
        }