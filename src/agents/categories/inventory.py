"""
Inventory management agents (Category 7) - 5 specialized sub-category agents.
Handles all aspects of inventory tracking, accuracy, movements, and valuation.
"""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import WMSBaseAgent, WMSBaseTool, WMSContext
from ...database.models import Inventory, Item, Location, InventoryMovement


class InventoryQueryTool(WMSBaseTool):
    """Tool for querying inventory information"""
    
    name = "inventory_query"
    description = "Query inventory levels, stock status, and item availability"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute inventory query"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Parse query for inventory parameters
                inventory_params = self._parse_inventory_query(query)
                
                # Build complex query with joins
                stmt = (
                    select(
                        Inventory.inventory_id,
                        Inventory.item_id,
                        Item.item_description,
                        Inventory.location_id,
                        Inventory.lot_number,
                        Inventory.quantity_on_hand,
                        Inventory.quantity_allocated,
                        (Inventory.quantity_on_hand - Inventory.quantity_allocated).label('quantity_available'),
                        Inventory.expiration_date,
                        Inventory.last_movement_date
                    )
                    .join(Item, Inventory.item_id == Item.item_id)
                    .join(Location, Inventory.location_id == Location.location_id)
                )
                
                # Apply filters based on parsed parameters
                if inventory_params.get("item_id"):
                    stmt = stmt.where(Inventory.item_id.ilike(f"%{inventory_params['item_id']}%"))
                
                if inventory_params.get("location_id"):
                    stmt = stmt.where(Inventory.location_id.ilike(f"%{inventory_params['location_id']}%"))
                
                if inventory_params.get("lot_number"):
                    stmt = stmt.where(Inventory.lot_number.ilike(f"%{inventory_params['lot_number']}%"))
                
                if inventory_params.get("low_stock"):
                    # Show items with low available quantity
                    stmt = stmt.where((Inventory.quantity_on_hand - Inventory.quantity_allocated) < 10)
                
                if inventory_params.get("zero_stock"):
                    # Show items with zero or negative available quantity
                    stmt = stmt.where((Inventory.quantity_on_hand - Inventory.quantity_allocated) <= 0)
                
                # Execute query
                result = await session.execute(stmt.limit(50))
                inventory_records = result.fetchall()
                
                if not inventory_records:
                    return "No inventory records found matching the specified criteria."
                
                # Format results
                response = f"📦 **Found {len(inventory_records)} inventory record(s):**\n\n"
                
                total_value = Decimal('0')
                for record in inventory_records:
                    response += f"🏷️ **{record.item_id}** - {record.item_description[:50]}...\n"
                    response += f"   📍 Location: {record.location_id}\n"
                    response += f"   📊 On Hand: {record.quantity_on_hand}\n"
                    response += f"   🔒 Allocated: {record.quantity_allocated}\n"
                    response += f"   ✅ Available: {record.quantity_available}\n"
                    
                    if record.lot_number:
                        response += f"   🏷️ Lot: {record.lot_number}\n"
                    
                    if record.expiration_date:
                        response += f"   📅 Expires: {record.expiration_date.strftime('%Y-%m-%d')}\n"
                    
                    if record.last_movement_date:
                        response += f"   🔄 Last Movement: {record.last_movement_date.strftime('%Y-%m-%d %H:%M')}\n"
                    
                    response += "\n"
                
                return response
                
        except Exception as e:
            return f"Error querying inventory: {str(e)}"
    
    def _parse_inventory_query(self, query: str) -> Dict[str, Any]:
        """Parse natural language query for inventory parameters"""
        query_lower = query.lower()
        params = {}
        
        # Extract item ID/SKU
        import re
        item_patterns = [
            r'item[:\s]+([a-zA-Z0-9-]+)',
            r'sku[:\s]+([a-zA-Z0-9-]+)',
            r'part[:\s]+([a-zA-Z0-9-]+)'
        ]
        
        for pattern in item_patterns:
            match = re.search(pattern, query_lower)
            if match:
                params["item_id"] = match.group(1).upper()
                break
        
        # Extract location
        location_pattern = r'location[:\s]+([a-zA-Z0-9-]+)'
        location_match = re.search(location_pattern, query_lower)
        if location_match:
            params["location_id"] = location_match.group(1).upper()
        
        # Extract lot number
        lot_pattern = r'lot[:\s]+([a-zA-Z0-9-]+)'
        lot_match = re.search(lot_pattern, query_lower)
        if lot_match:
            params["lot_number"] = lot_match.group(1).upper()
        
        # Check for stock level queries
        if any(phrase in query_lower for phrase in ["low stock", "low inventory", "running low"]):
            params["low_stock"] = True
        
        if any(phrase in query_lower for phrase in ["zero stock", "out of stock", "no inventory"]):
            params["zero_stock"] = True
        
        return params


class InventoryMovementTool(WMSBaseTool):
    """Tool for analyzing inventory movements and history"""
    
    name = "inventory_movement"
    description = "Analyze inventory movements, transaction history, and flow patterns"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute movement analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Parse timeframe from query
                timeframe_days = self._parse_timeframe(query)
                start_date = datetime.utcnow() - timedelta(days=timeframe_days)
                
                # Get movement summary
                movement_query = """
                SELECT 
                    im.movement_type,
                    COUNT(*) as transaction_count,
                    SUM(ABS(im.movement_quantity)) as total_quantity,
                    AVG(ABS(im.movement_quantity)) as avg_quantity
                FROM inventory_movements im
                WHERE im.movement_date >= :start_date
                GROUP BY im.movement_type
                ORDER BY transaction_count DESC;
                """
                
                result = await session.execute(movement_query, {"start_date": start_date})
                movement_summary = result.fetchall()
                
                if not movement_summary:
                    return f"No inventory movements found in the last {timeframe_days} days."
                
                response = f"📊 **Inventory Movement Summary (Last {timeframe_days} days):**\n\n"
                
                total_transactions = sum(row.transaction_count for row in movement_summary)
                total_quantity = sum(row.total_quantity for row in movement_summary)
                
                response += f"📈 **Overall Statistics:**\n"
                response += f"   Total Transactions: {total_transactions:,}\n"
                response += f"   Total Quantity Moved: {total_quantity:,.2f}\n"
                response += f"   Average per Transaction: {total_quantity/total_transactions:.2f}\n\n"
                
                response += f"📋 **By Movement Type:**\n"
                for row in movement_summary:
                    percentage = (row.transaction_count / total_transactions) * 100
                    response += f"   🔄 **{row.movement_type}**\n"
                    response += f"      Transactions: {row.transaction_count:,} ({percentage:.1f}%)\n"
                    response += f"      Total Quantity: {row.total_quantity:,.2f}\n"
                    response += f"      Average Quantity: {row.avg_quantity:.2f}\n\n"
                
                # Get top active items
                active_items_query = """
                SELECT 
                    im.item_id,
                    i.item_description,
                    COUNT(*) as movement_count,
                    SUM(ABS(im.movement_quantity)) as total_moved
                FROM inventory_movements im
                JOIN items i ON im.item_id = i.item_id
                WHERE im.movement_date >= :start_date
                GROUP BY im.item_id, i.item_description
                ORDER BY movement_count DESC
                LIMIT 10;
                """
                
                result = await session.execute(active_items_query, {"start_date": start_date})
                active_items = result.fetchall()
                
                if active_items:
                    response += f"🏆 **Most Active Items:**\n"
                    for i, row in enumerate(active_items, 1):
                        response += f"   {i}. {row.item_id}: {row.movement_count} movements, {row.total_moved:.2f} total\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing movements: {str(e)}"
    
    def _parse_timeframe(self, query: str) -> int:
        """Parse timeframe from query, default to 30 days"""
        query_lower = query.lower()
        
        import re
        
        # Look for specific day mentions
        day_pattern = r'(\d+)\s*days?'
        day_match = re.search(day_pattern, query_lower)
        if day_match:
            return int(day_match.group(1))
        
        # Look for week mentions
        week_pattern = r'(\d+)\s*weeks?'
        week_match = re.search(week_pattern, query_lower)
        if week_match:
            return int(week_match.group(1)) * 7
        
        # Look for month mentions
        month_pattern = r'(\d+)\s*months?'
        month_match = re.search(month_pattern, query_lower)
        if month_match:
            return int(month_match.group(1)) * 30
        
        # Default timeframes
        if "today" in query_lower:
            return 1
        elif "week" in query_lower:
            return 7
        elif "month" in query_lower:
            return 30
        elif "quarter" in query_lower:
            return 90
        elif "year" in query_lower:
            return 365
        
        return 30  # Default to 30 days


class InventoryAccuracyTool(WMSBaseTool):
    """Tool for inventory accuracy analysis and reporting"""
    
    name = "inventory_accuracy"
    description = "Analyze inventory accuracy, discrepancies, and adjustment patterns"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute accuracy analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get adjustment movements (indicate accuracy issues)
                accuracy_query = """
                SELECT 
                    im.item_id,
                    i.item_description,
                    COUNT(*) as adjustment_count,
                    SUM(im.movement_quantity) as net_adjustment,
                    ABS(SUM(im.movement_quantity)) as total_abs_adjustment,
                    AVG(im.movement_quantity) as avg_adjustment
                FROM inventory_movements im
                JOIN items i ON im.item_id = i.item_id
                WHERE im.movement_type = 'ADJUSTMENT'
                    AND im.movement_date >= NOW() - INTERVAL '90 days'
                GROUP BY im.item_id, i.item_description
                HAVING COUNT(*) > 1  -- Items with multiple adjustments
                ORDER BY adjustment_count DESC, total_abs_adjustment DESC
                LIMIT 20;
                """
                
                result = await session.execute(accuracy_query)
                accuracy_data = result.fetchall()
                
                response = "🎯 **Inventory Accuracy Analysis (Last 90 days):**\n\n"
                
                if not accuracy_data:
                    response += "✅ No significant accuracy issues found. All items appear to have good inventory accuracy.\n"
                    return response
                
                # Overall statistics
                total_adjustments = sum(row.adjustment_count for row in accuracy_data)
                total_items_with_issues = len(accuracy_data)
                
                response += f"📊 **Summary:**\n"
                response += f"   Items with accuracy issues: {total_items_with_issues}\n"
                response += f"   Total adjustments: {total_adjustments}\n"
                response += f"   Average adjustments per item: {total_adjustments/total_items_with_issues:.1f}\n\n"
                
                # Items requiring attention
                response += f"⚠️ **Items Requiring Attention:**\n"
                high_priority = [row for row in accuracy_data if row.adjustment_count >= 5]
                medium_priority = [row for row in accuracy_data if 3 <= row.adjustment_count < 5]
                
                if high_priority:
                    response += f"\n🔴 **High Priority** (5+ adjustments):\n"
                    for row in high_priority[:5]:
                        response += f"   {row.item_id}: {row.adjustment_count} adjustments, net {row.net_adjustment:+.2f}\n"
                
                if medium_priority:
                    response += f"\n🟡 **Medium Priority** (3-4 adjustments):\n"
                    for row in medium_priority[:5]:
                        response += f"   {row.item_id}: {row.adjustment_count} adjustments, net {row.net_adjustment:+.2f}\n"
                
                # Get location-based accuracy issues
                location_accuracy_query = """
                SELECT 
                    im.to_location_id as location_id,
                    COUNT(*) as adjustment_count,
                    ABS(SUM(im.movement_quantity)) as total_abs_adjustment
                FROM inventory_movements im
                WHERE im.movement_type = 'ADJUSTMENT'
                    AND im.movement_date >= NOW() - INTERVAL '90 days'
                    AND im.to_location_id IS NOT NULL
                GROUP BY im.to_location_id
                HAVING COUNT(*) > 2
                ORDER BY adjustment_count DESC
                LIMIT 10;
                """
                
                result = await session.execute(location_accuracy_query)
                location_data = result.fetchall()
                
                if location_data:
                    response += f"\n📍 **Locations with Frequent Adjustments:**\n"
                    for row in location_data:
                        response += f"   {row.location_id}: {row.adjustment_count} adjustments\n"
                
                response += f"\n💡 **Recommendations:**\n"
                response += f"   • Investigate root causes for high-adjustment items\n"
                response += f"   • Review cycle counting frequency for problem items\n"
                response += f"   • Check for process issues in high-adjustment locations\n"
                response += f"   • Consider additional training for staff handling these items\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing accuracy: {str(e)}"


class InventoryValuationTool(WMSBaseTool):
    """Tool for inventory valuation and financial analysis"""
    
    name = "inventory_valuation"
    description = "Calculate inventory values, aging analysis, and financial metrics"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute valuation analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get inventory valuation data
                valuation_query = """
                SELECT 
                    inv.item_id,
                    i.item_description,
                    i.item_category,
                    i.standard_cost,
                    SUM(inv.quantity_on_hand) as total_on_hand,
                    SUM(inv.quantity_allocated) as total_allocated,
                    SUM(inv.quantity_on_hand - inv.quantity_allocated) as total_available,
                    SUM(inv.quantity_on_hand * COALESCE(i.standard_cost, 0)) as total_value,
                    COUNT(DISTINCT inv.location_id) as location_count,
                    MIN(inv.last_movement_date) as oldest_movement,
                    MAX(inv.last_movement_date) as newest_movement
                FROM inventory inv
                JOIN items i ON inv.item_id = i.item_id
                WHERE inv.quantity_on_hand > 0
                GROUP BY inv.item_id, i.item_description, i.item_category, i.standard_cost
                ORDER BY total_value DESC
                LIMIT 50;
                """
                
                result = await session.execute(valuation_query)
                valuation_data = result.fetchall()
                
                if not valuation_data:
                    return "No inventory data available for valuation."
                
                # Calculate summary statistics
                total_inventory_value = sum(float(row.total_value or 0) for row in valuation_data)
                total_quantity = sum(float(row.total_on_hand) for row in valuation_data)
                total_items = len(valuation_data)
                
                response = f"💰 **Inventory Valuation Analysis:**\n\n"
                response += f"📊 **Overall Summary:**\n"
                response += f"   Total Items: {total_items:,}\n"
                response += f"   Total Quantity: {total_quantity:,.2f}\n"
                response += f"   Total Value: ${total_inventory_value:,.2f}\n"
                response += f"   Average Value per Item: ${total_inventory_value/total_items:,.2f}\n\n"
                
                # Top value items
                high_value_items = [row for row in valuation_data[:10] if row.total_value and row.total_value > 0]
                if high_value_items:
                    response += f"💎 **Top Value Items:**\n"
                    for i, row in enumerate(high_value_items, 1):
                        value = float(row.total_value or 0)
                        percentage = (value / total_inventory_value) * 100
                        response += f"   {i}. {row.item_id}: ${value:,.2f} ({percentage:.1f}%)\n"
                        response += f"      Qty: {row.total_on_hand:.2f}, Cost: ${row.standard_cost or 0:.2f}\n"
                
                # Category analysis
                category_values = {}
                for row in valuation_data:
                    category = row.item_category or "Unknown"
                    if category not in category_values:
                        category_values[category] = {"value": 0, "quantity": 0, "items": 0}
                    category_values[category]["value"] += float(row.total_value or 0)
                    category_values[category]["quantity"] += float(row.total_on_hand)
                    category_values[category]["items"] += 1
                
                response += f"\n📂 **Value by Category:**\n"
                sorted_categories = sorted(category_values.items(), key=lambda x: x[1]["value"], reverse=True)
                for category, data in sorted_categories[:5]:
                    percentage = (data["value"] / total_inventory_value) * 100
                    response += f"   {category}: ${data['value']:,.2f} ({percentage:.1f}%)\n"
                    response += f"      Items: {data['items']}, Avg Value: ${data['value']/data['items']:,.2f}\n"
                
                # Aging analysis (based on last movement date)
                current_date = datetime.utcnow()
                aging_buckets = {
                    "0-30 days": {"count": 0, "value": 0},
                    "31-60 days": {"count": 0, "value": 0},
                    "61-90 days": {"count": 0, "value": 0},
                    "90+ days": {"count": 0, "value": 0},
                    "No movement": {"count": 0, "value": 0}
                }
                
                for row in valuation_data:
                    value = float(row.total_value or 0)
                    if row.newest_movement:
                        days_old = (current_date - row.newest_movement).days
                        if days_old <= 30:
                            aging_buckets["0-30 days"]["count"] += 1
                            aging_buckets["0-30 days"]["value"] += value
                        elif days_old <= 60:
                            aging_buckets["31-60 days"]["count"] += 1
                            aging_buckets["31-60 days"]["value"] += value
                        elif days_old <= 90:
                            aging_buckets["61-90 days"]["count"] += 1
                            aging_buckets["61-90 days"]["value"] += value
                        else:
                            aging_buckets["90+ days"]["count"] += 1
                            aging_buckets["90+ days"]["value"] += value
                    else:
                        aging_buckets["No movement"]["count"] += 1
                        aging_buckets["No movement"]["value"] += value
                
                response += f"\n📅 **Inventory Aging:**\n"
                for bucket, data in aging_buckets.items():
                    if data["count"] > 0:
                        percentage = (data["value"] / total_inventory_value) * 100
                        response += f"   {bucket}: {data['count']} items, ${data['value']:,.2f} ({percentage:.1f}%)\n"
                
                return response
                
        except Exception as e:
            return f"Error performing valuation analysis: {str(e)}"


# Functional Agent - Business processes and workflows
class InventoryFunctionalAgent(WMSBaseAgent):
    """Handles functional aspects of inventory management"""
    
    def __init__(self):
        tools = [
            InventoryQueryTool("inventory_management", "functional"),
            InventoryMovementTool("inventory_management", "functional"),
            InventoryAccuracyTool("inventory_management", "functional")
        ]
        super().__init__("inventory_management", "functional", tools)
    
    def _get_specialization(self) -> str:
        return "Inventory tracking workflows, stock management processes, and accuracy maintenance"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "stock_level_inquiry",
            "movement_tracking",
            "accuracy_analysis",
            "cycle_count_planning",
            "shortage_management",
            "stock_rotation"
        ]


# Technical Agent - System specifications
class InventoryTechnicalAgent(WMSBaseAgent):
    """Handles technical aspects of inventory management"""
    
    def __init__(self):
        tools = [InventoryQueryTool("inventory_management", "technical")]
        super().__init__("inventory_management", "technical", tools)
    
    def _get_specialization(self) -> str:
        return "Real-time inventory updates, serialization, lot control, and FIFO/LIFO processing"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "real_time_updates",
            "serial_tracking",
            "lot_control",
            "fifo_lifo_logic",
            "system_integration",
            "data_synchronization"
        ]


# Configuration Agent - Setup and parameters
class InventoryConfigurationAgent(WMSBaseAgent):
    """Handles inventory configuration and policies"""
    
    def __init__(self):
        tools = [InventoryQueryTool("inventory_management", "configuration")]
        super().__init__("inventory_management", "configuration", tools)
    
    def _get_specialization(self) -> str:
        return "Inventory policies, tolerance settings, audit trails, and approval workflows"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "policy_configuration",
            "tolerance_settings",
            "audit_trail_setup",
            "workflow_configuration",
            "validation_rules",
            "system_parameters"
        ]


# Relationships Agent - Integration with other modules
class InventoryRelationshipsAgent(WMSBaseAgent):
    """Handles inventory relationships with other WMS modules"""
    
    def __init__(self):
        tools = [InventoryMovementTool("inventory_management", "relationships")]
        super().__init__("inventory_management", "relationships", tools)
    
    def _get_specialization(self) -> str:
        return "Inventory integration with receiving, picking, shipping, and financial systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "receiving_integration",
            "picking_allocation",
            "shipping_deduction",
            "financial_integration",
            "cross_module_sync",
            "workflow_coordination"
        ]


# Notes Agent - Best practices and recommendations
class InventoryNotesAgent(WMSBaseAgent):
    """Provides inventory management best practices and recommendations"""
    
    def __init__(self):
        tools = [InventoryValuationTool("inventory_management", "notes")]
        super().__init__("inventory_management", "notes", tools)
    
    def _get_specialization(self) -> str:
        return "Inventory accuracy best practices, shrinkage control, and variance analysis strategies"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "accuracy_best_practices",
            "shrinkage_control",
            "variance_analysis",
            "process_improvement",
            "kpi_recommendations",
            "industry_benchmarks"
        ]