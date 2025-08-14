"""
Item management agents (Category 3) - 5 specialized sub-category agents.
Handles all aspects of item master data, attributes, specifications, and lifecycle management.
"""

import json
import hashlib
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import WMSBaseAgent, WMSBaseTool, WMSContext
from ...database.models import Item, Inventory, InventoryMovement


class ItemQueryTool(WMSBaseTool):
    """Tool for querying item master data"""
    
    name = "item_query"
    description = "Query item information including specifications, attributes, and relationships"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute item query"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Parse query for item parameters
                item_params = self._parse_item_query(query)
                
                # Build SQL query
                stmt = select(Item)
                
                if item_params.get("item_id"):
                    stmt = stmt.where(Item.item_id.ilike(f"%{item_params['item_id']}%"))
                if item_params.get("description"):
                    stmt = stmt.where(Item.item_description.ilike(f"%{item_params['description']}%"))
                if item_params.get("category"):
                    stmt = stmt.where(Item.item_category == item_params["category"])
                if item_params.get("uom"):
                    stmt = stmt.where(Item.unit_of_measure == item_params["uom"])
                if item_params.get("active_only"):
                    stmt = stmt.where(Item.is_active == True)
                
                # Execute query
                result = await session.execute(stmt.limit(50))
                items = result.scalars().all()
                
                if not items:
                    return "No items found matching the specified criteria."
                
                # Format results
                response = f"🏷️ **Found {len(items)} item(s):**\n\n"
                
                for item in items:
                    response += f"📦 **{item.item_id}** - {item.item_description}\n"
                    response += f"   📂 Category: {item.item_category or 'N/A'}\n"
                    response += f"   📏 UOM: {item.unit_of_measure}\n"
                    response += f"   💰 Standard Cost: ${item.standard_cost or 0:.2f}\n"
                    
                    if item.weight:
                        response += f"   ⚖️ Weight: {item.weight} {item.weight_uom or 'units'}\n"
                    if item.dimensions_length and item.dimensions_width and item.dimensions_height:
                        response += f"   📐 Dimensions: {item.dimensions_length}x{item.dimensions_width}x{item.dimensions_height} {item.dimension_uom or 'units'}\n"
                    
                    response += f"   🔄 Active: {'Yes' if item.is_active else 'No'}\n"
                    
                    if item.hazmat_class:
                        response += f"   ⚠️ Hazmat Class: {item.hazmat_class}\n"
                    if item.lot_controlled:
                        response += f"   🏷️ Lot Controlled: Yes\n"
                    if item.serial_controlled:
                        response += f"   🔢 Serial Controlled: Yes\n"
                    
                    response += "\n"
                
                return response
                
        except Exception as e:
            return f"Error querying items: {str(e)}"
    
    def _parse_item_query(self, query: str) -> Dict[str, Any]:
        """Parse natural language query for item parameters"""
        query_lower = query.lower()
        params = {}
        
        # Extract item ID/SKU
        import re
        item_patterns = [
            r'item[:\s]+([a-zA-Z0-9-]+)',
            r'sku[:\s]+([a-zA-Z0-9-]+)',
            r'part[:\s]+([a-zA-Z0-9-]+)',
            r'product[:\s]+([a-zA-Z0-9-]+)'
        ]
        
        for pattern in item_patterns:
            match = re.search(pattern, query_lower)
            if match:
                params["item_id"] = match.group(1).upper()
                break
        
        # Extract description
        if "description" in query_lower:
            desc_pattern = r'description[:\s]+([a-zA-Z0-9\s]+)'
            desc_match = re.search(desc_pattern, query_lower)
            if desc_match:
                params["description"] = desc_match.group(1).strip()
        
        # Extract category
        if "category" in query_lower:
            cat_pattern = r'category[:\s]+([a-zA-Z0-9\s]+)'
            cat_match = re.search(cat_pattern, query_lower)
            if cat_match:
                params["category"] = cat_match.group(1).strip().upper()
        
        # Extract UOM
        if any(uom in query_lower for uom in ["each", "box", "case", "pallet", "kg", "lb"]):
            for uom in ["each", "box", "case", "pallet", "kg", "lb"]:
                if uom in query_lower:
                    params["uom"] = uom.upper()
                    break
        
        # Check for active filter
        if any(phrase in query_lower for phrase in ["active only", "active items", "not inactive"]):
            params["active_only"] = True
        
        return params


class ItemSpecificationTool(WMSBaseTool):
    """Tool for managing item specifications and attributes"""
    
    name = "item_specification"
    description = "Analyze item specifications, dimensions, weight, and special attributes"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute specification analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get items with complete specification data
                spec_query = """
                SELECT 
                    i.item_id,
                    i.item_description,
                    i.item_category,
                    i.weight,
                    i.weight_uom,
                    i.dimensions_length,
                    i.dimensions_width,
                    i.dimensions_height,
                    i.dimension_uom,
                    i.volume,
                    i.hazmat_class,
                    i.lot_controlled,
                    i.serial_controlled,
                    i.expiration_tracking,
                    i.standard_cost
                FROM items i
                WHERE i.is_active = true
                ORDER BY i.item_category, i.item_id
                LIMIT 100;
                """
                
                result = await session.execute(spec_query)
                items = result.fetchall()
                
                if not items:
                    return "No item specification data available."
                
                # Analyze specifications
                response = "📋 **Item Specification Analysis:**\n\n"
                
                # Categorize by specifications
                hazmat_items = [item for item in items if item.hazmat_class]
                lot_controlled = [item for item in items if item.lot_controlled]
                serial_controlled = [item for item in items if item.serial_controlled]
                expiry_tracking = [item for item in items if item.expiration_tracking]
                
                # Weight analysis
                weighted_items = [item for item in items if item.weight and item.weight > 0]
                if weighted_items:
                    avg_weight = sum(float(item.weight) for item in weighted_items) / len(weighted_items)
                    max_weight = max(float(item.weight) for item in weighted_items)
                    min_weight = min(float(item.weight) for item in weighted_items)
                    
                    response += f"⚖️ **Weight Analysis:**\n"
                    response += f"   Items with weight data: {len(weighted_items)}\n"
                    response += f"   Average weight: {avg_weight:.2f}\n"
                    response += f"   Weight range: {min_weight:.2f} - {max_weight:.2f}\n\n"
                
                # Dimension analysis
                dimensional_items = [item for item in items if all([
                    item.dimensions_length, item.dimensions_width, item.dimensions_height
                ])]
                
                if dimensional_items:
                    response += f"📐 **Dimension Analysis:**\n"
                    response += f"   Items with complete dimensions: {len(dimensional_items)}\n"
                    
                    # Calculate volumes for items without volume data
                    calculated_volumes = []
                    for item in dimensional_items:
                        if not item.volume:
                            calc_volume = float(item.dimensions_length) * float(item.dimensions_width) * float(item.dimensions_height)
                            calculated_volumes.append((item.item_id, calc_volume))
                    
                    if calculated_volumes:
                        response += f"   Items missing volume data: {len(calculated_volumes)}\n"
                        # Show top 3 largest by calculated volume
                        calculated_volumes.sort(key=lambda x: x[1], reverse=True)
                        response += f"   Largest by calculated volume:\n"
                        for item_id, volume in calculated_volumes[:3]:
                            response += f"     • {item_id}: {volume:.2f} cubic units\n"
                    response += "\n"
                
                # Special handling requirements
                if hazmat_items:
                    response += f"⚠️ **Hazmat Items:** {len(hazmat_items)}\n"
                    hazmat_classes = {}
                    for item in hazmat_items:
                        hclass = item.hazmat_class
                        hazmat_classes[hclass] = hazmat_classes.get(hclass, 0) + 1
                    
                    for hclass, count in sorted(hazmat_classes.items()):
                        response += f"   Class {hclass}: {count} items\n"
                    response += "\n"
                
                if lot_controlled:
                    response += f"🏷️ **Lot Controlled Items:** {len(lot_controlled)}\n"
                
                if serial_controlled:
                    response += f"🔢 **Serial Controlled Items:** {len(serial_controlled)}\n"
                
                if expiry_tracking:
                    response += f"📅 **Expiration Tracking Items:** {len(expiry_tracking)}\n"
                
                # Category breakdown
                categories = {}
                for item in items:
                    cat = item.item_category or "Unknown"
                    categories[cat] = categories.get(cat, 0) + 1
                
                response += f"\n📂 **Category Breakdown:**\n"
                sorted_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)
                for category, count in sorted_categories[:10]:
                    response += f"   {category}: {count} items\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing specifications: {str(e)}"


class ItemLifecycleTool(WMSBaseTool):
    """Tool for item lifecycle management and history"""
    
    name = "item_lifecycle"
    description = "Track item lifecycle, creation dates, modifications, and activity patterns"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute lifecycle analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get item lifecycle data
                lifecycle_query = """
                SELECT 
                    i.item_id,
                    i.item_description,
                    i.created_at,
                    i.updated_at,
                    i.is_active,
                    COUNT(DISTINCT inv.inventory_id) as location_count,
                    SUM(inv.quantity_on_hand) as total_quantity,
                    COUNT(DISTINCT im.movement_id) as movement_count,
                    MAX(im.movement_date) as last_movement,
                    MIN(im.movement_date) as first_movement
                FROM items i
                LEFT JOIN inventory inv ON i.item_id = inv.item_id
                LEFT JOIN inventory_movements im ON i.item_id = im.item_id
                WHERE i.created_at >= NOW() - INTERVAL '2 years'
                GROUP BY i.item_id, i.item_description, i.created_at, i.updated_at, i.is_active
                ORDER BY i.created_at DESC
                LIMIT 50;
                """
                
                result = await session.execute(lifecycle_query)
                lifecycle_data = result.fetchall()
                
                if not lifecycle_data:
                    return "No item lifecycle data available."
                
                response = "🔄 **Item Lifecycle Analysis:**\n\n"
                
                # Recent items
                recent_items = [item for item in lifecycle_data[:10]]
                response += f"🆕 **Recently Created Items:**\n"
                for item in recent_items:
                    days_old = (datetime.utcnow() - item.created_at).days
                    response += f"   {item.item_id}: {days_old} days old"
                    if item.movement_count:
                        response += f" ({item.movement_count} movements)"
                    response += "\n"
                response += "\n"
                
                # Activity analysis
                active_items = [item for item in lifecycle_data if item.movement_count and item.movement_count > 0]
                inactive_items = [item for item in lifecycle_data if not item.movement_count or item.movement_count == 0]
                
                response += f"📊 **Activity Summary:**\n"
                response += f"   Total items analyzed: {len(lifecycle_data)}\n"
                response += f"   Items with movement activity: {len(active_items)}\n"
                response += f"   Items with no movement: {len(inactive_items)}\n\n"
                
                if active_items:
                    # Most active items
                    most_active = sorted(active_items, key=lambda x: x.movement_count, reverse=True)[:5]
                    response += f"⚡ **Most Active Items:**\n"
                    for item in most_active:
                        response += f"   {item.item_id}: {item.movement_count} movements\n"
                        if item.last_movement:
                            days_since = (datetime.utcnow() - item.last_movement).days
                            response += f"      Last activity: {days_since} days ago\n"
                    response += "\n"
                
                if inactive_items:
                    response += f"😴 **Inactive Items (No Movements):**\n"
                    for item in inactive_items[:5]:
                        days_old = (datetime.utcnow() - item.created_at).days
                        response += f"   {item.item_id}: Created {days_old} days ago\n"
                        if item.total_quantity:
                            response += f"      Has inventory: {item.total_quantity:.2f}\n"
                    
                    if len(inactive_items) > 5:
                        response += f"   ... and {len(inactive_items) - 5} more inactive items\n"
                    response += "\n"
                
                # Lifecycle patterns
                current_date = datetime.utcnow()
                new_items = len([i for i in lifecycle_data if (current_date - i.created_at).days <= 30])
                old_items = len([i for i in lifecycle_data if (current_date - i.created_at).days > 365])
                
                response += f"📈 **Lifecycle Patterns:**\n"
                response += f"   New items (last 30 days): {new_items}\n"
                response += f"   Established items (1+ years): {old_items}\n"
                
                # Items needing attention
                stale_items = [item for item in lifecycle_data 
                              if item.last_movement and (current_date - item.last_movement).days > 90]
                
                if stale_items:
                    response += f"\n⚠️ **Items Needing Attention (90+ days no movement):**\n"
                    for item in stale_items[:5]:
                        days_stale = (current_date - item.last_movement).days
                        response += f"   {item.item_id}: {days_stale} days since last movement\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing lifecycle: {str(e)}"


# Functional Agent - Business processes and workflows
class ItemsFunctionalAgent(WMSBaseAgent):
    """Handles functional aspects of item management"""
    
    def __init__(self):
        tools = [
            ItemQueryTool("items", "functional"),
            ItemSpecificationTool("items", "functional"),
            ItemLifecycleTool("items", "functional")
        ]
        super().__init__("items", "functional", tools)
    
    def _get_specialization(self) -> str:
        return "Item master data management, product catalog workflows, and item lifecycle processes"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "item_lookup",
            "catalog_management",
            "specification_analysis",
            "lifecycle_tracking",
            "item_creation_workflows",
            "attribute_management"
        ]


# Technical Agent - System specifications
class ItemsTechnicalAgent(WMSBaseAgent):
    """Handles technical aspects of item management"""
    
    def __init__(self):
        tools = [ItemQueryTool("items", "technical")]
        super().__init__("items", "technical", tools)
    
    def _get_specialization(self) -> str:
        return "Item data structure, barcode generation, API integrations, and data validation systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "data_validation",
            "barcode_generation",
            "api_integration",
            "data_import_export",
            "system_integration",
            "performance_optimization"
        ]


# Configuration Agent - Setup and parameters
class ItemsConfigurationAgent(WMSBaseAgent):
    """Handles item configuration and setup"""
    
    def __init__(self):
        tools = [ItemSpecificationTool("items", "configuration")]
        super().__init__("items", "configuration", tools)
    
    def _get_specialization(self) -> str:
        return "Item attribute configuration, validation rules, category setup, and data governance"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "attribute_configuration",
            "validation_rules",
            "category_management",
            "data_governance",
            "field_configuration",
            "business_rules"
        ]


# Relationships Agent - Integration with other modules
class ItemsRelationshipsAgent(WMSBaseAgent):
    """Handles item relationships with other WMS modules"""
    
    def __init__(self):
        tools = [ItemQueryTool("items", "relationships")]
        super().__init__("items", "relationships", tools)
    
    def _get_specialization(self) -> str:
        return "Item relationships with inventory, orders, locations, and external systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "inventory_integration",
            "order_item_linking",
            "supplier_relationships",
            "location_assignments",
            "cross_reference_management",
            "system_mappings"
        ]


# Notes Agent - Best practices and recommendations
class ItemsNotesAgent(WMSBaseAgent):
    """Provides item management best practices and recommendations"""
    
    def __init__(self):
        tools = [ItemLifecycleTool("items", "notes")]
        super().__init__("items", "notes", tools)
    
    def _get_specialization(self) -> str:
        return "Item master data best practices, naming conventions, and data quality standards"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "data_quality_standards",
            "naming_conventions",
            "best_practices",
            "maintenance_strategies",
            "performance_optimization",
            "governance_guidelines"
        ]