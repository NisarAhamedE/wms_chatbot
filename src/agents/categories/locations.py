"""
Location management agents (Category 2) - 5 specialized sub-category agents.
Handles all aspects of warehouse location management including layout, optimization, and capacity planning.
"""

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import WMSBaseAgent, WMSBaseTool, WMSContext
from ...database.models import Location, Inventory, WorkAssignment


class LocationQueryTool(WMSBaseTool):
    """Tool for querying location information"""
    
    name = "location_query"
    description = "Query warehouse location information including capacity, status, and inventory"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute location query"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Parse query for location parameters
                location_params = self._parse_location_query(query)
                
                # Build SQL query based on parameters
                stmt = select(Location)
                
                if location_params.get("location_id"):
                    stmt = stmt.where(Location.location_id == location_params["location_id"])
                if location_params.get("zone_id"):
                    stmt = stmt.where(Location.zone_id == location_params["zone_id"])
                if location_params.get("location_type"):
                    stmt = stmt.where(Location.location_type == location_params["location_type"])
                if location_params.get("is_pickable") is not None:
                    stmt = stmt.where(Location.is_pickable == location_params["is_pickable"])
                
                # Execute query
                result = await session.execute(stmt.limit(50))
                locations = result.scalars().all()
                
                if not locations:
                    return "No locations found matching the specified criteria."
                
                # Format results
                response = f"Found {len(locations)} location(s):\n\n"
                for loc in locations:
                    response += f"📍 **{loc.location_id}**\n"
                    response += f"   Zone: {loc.zone_id}\n"
                    response += f"   Type: {loc.location_type}\n"
                    response += f"   Capacity: {loc.capacity_qty or 'N/A'}\n"
                    response += f"   Pickable: {'Yes' if loc.is_pickable else 'No'}\n"
                    response += f"   Receivable: {'Yes' if loc.is_receivable else 'No'}\n\n"
                
                return response
                
        except Exception as e:
            return f"Error querying locations: {str(e)}"
    
    def _parse_location_query(self, query: str) -> Dict[str, Any]:
        """Parse natural language query for location parameters"""
        query_lower = query.lower()
        params = {}
        
        # Extract location ID
        import re
        location_pattern = r'location[:\s]+([a-zA-Z0-9-]+)'
        location_match = re.search(location_pattern, query_lower)
        if location_match:
            params["location_id"] = location_match.group(1).upper()
        
        # Extract zone
        zone_pattern = r'zone[:\s]+([a-zA-Z0-9-]+)'
        zone_match = re.search(zone_pattern, query_lower)
        if zone_match:
            params["zone_id"] = zone_match.group(1).upper()
        
        # Extract location type
        if "pick" in query_lower:
            params["location_type"] = "PICK"
        elif "reserve" in query_lower:
            params["location_type"] = "RESERVE"
        elif "staging" in query_lower:
            params["location_type"] = "STAGING"
        
        # Extract pickable status
        if "pickable" in query_lower and "not" not in query_lower:
            params["is_pickable"] = True
        elif "not pickable" in query_lower:
            params["is_pickable"] = False
        
        return params


class LocationCapacityTool(WMSBaseTool):
    """Tool for analyzing location capacity and utilization"""
    
    name = "location_capacity"
    description = "Analyze location capacity, utilization, and space optimization"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute capacity analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get location capacity data with current inventory
                capacity_query = """
                SELECT 
                    l.location_id,
                    l.zone_id,
                    l.location_type,
                    l.capacity_qty,
                    l.capacity_volume,
                    COALESCE(SUM(i.quantity_on_hand), 0) as current_qty,
                    CASE 
                        WHEN l.capacity_qty > 0 THEN 
                            (COALESCE(SUM(i.quantity_on_hand), 0) / l.capacity_qty) * 100
                        ELSE 0 
                    END as utilization_pct
                FROM locations l
                LEFT JOIN inventory i ON l.location_id = i.location_id
                WHERE l.is_active = true
                GROUP BY l.location_id, l.zone_id, l.location_type, l.capacity_qty, l.capacity_volume
                ORDER BY utilization_pct DESC
                LIMIT 20;
                """
                
                result = await session.execute(capacity_query)
                capacity_data = result.fetchall()
                
                if not capacity_data:
                    return "No capacity data available."
                
                # Format capacity analysis
                response = "📊 **Location Capacity Analysis**\n\n"
                
                high_utilization = []
                low_utilization = []
                
                for row in capacity_data:
                    utilization = float(row.utilization_pct)
                    
                    if utilization > 90:
                        high_utilization.append(row)
                    elif utilization < 20:
                        low_utilization.append(row)
                
                # High utilization locations
                if high_utilization:
                    response += "🔴 **High Utilization Locations (>90%):**\n"
                    for row in high_utilization[:5]:
                        response += f"   {row.location_id}: {row.utilization_pct:.1f}% ({row.current_qty}/{row.capacity_qty})\n"
                    response += "\n"
                
                # Low utilization locations
                if low_utilization:
                    response += "🟢 **Low Utilization Locations (<20%):**\n"
                    for row in low_utilization[:5]:
                        response += f"   {row.location_id}: {row.utilization_pct:.1f}% ({row.current_qty}/{row.capacity_qty})\n"
                    response += "\n"
                
                # Overall statistics
                total_locations = len(capacity_data)
                avg_utilization = sum(float(row.utilization_pct) for row in capacity_data) / total_locations
                
                response += f"📈 **Summary:**\n"
                response += f"   Total Locations: {total_locations}\n"
                response += f"   Average Utilization: {avg_utilization:.1f}%\n"
                response += f"   High Utilization: {len(high_utilization)} locations\n"
                response += f"   Low Utilization: {len(low_utilization)} locations\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing capacity: {str(e)}"


class LocationOptimizationTool(WMSBaseTool):
    """Tool for location optimization recommendations"""
    
    name = "location_optimization"
    description = "Provide location optimization recommendations and slotting analysis"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute optimization analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Analyze pick frequency and location efficiency
                optimization_query = """
                SELECT 
                    l.location_id,
                    l.zone_id,
                    l.location_type,
                    l.aisle,
                    l.bay,
                    l.level,
                    COUNT(w.work_id) as pick_frequency,
                    AVG(w.actual_duration) as avg_pick_time
                FROM locations l
                LEFT JOIN work_assignments w ON l.location_id = w.location_id 
                    AND w.work_type = 'PICK' 
                    AND w.completed_at > NOW() - INTERVAL '30 days'
                WHERE l.is_active = true AND l.is_pickable = true
                GROUP BY l.location_id, l.zone_id, l.location_type, l.aisle, l.bay, l.level
                ORDER BY pick_frequency DESC
                LIMIT 30;
                """
                
                result = await session.execute(optimization_query)
                optimization_data = result.fetchall()
                
                if not optimization_data:
                    return "No optimization data available."
                
                # Analyze data for recommendations
                high_frequency = [row for row in optimization_data if row.pick_frequency > 10]
                slow_movers = [row for row in optimization_data if row.pick_frequency < 2]
                
                response = "🎯 **Location Optimization Recommendations**\n\n"
                
                # High frequency locations
                if high_frequency:
                    response += "⚡ **High Frequency Pick Locations:**\n"
                    response += "   Consider placing fast-moving items here:\n"
                    for row in high_frequency[:5]:
                        avg_time = row.avg_pick_time or 0
                        response += f"   {row.location_id}: {row.pick_frequency} picks/month, avg {avg_time:.1f}min\n"
                    response += "\n"
                
                # Slow moving locations
                if slow_movers:
                    response += "🐌 **Low Activity Locations:**\n"
                    response += "   Consider relocating items to optimize space:\n"
                    for row in slow_movers[:5]:
                        response += f"   {row.location_id}: {row.pick_frequency} picks/month\n"
                    response += "\n"
                
                # Zone analysis
                zone_stats = {}
                for row in optimization_data:
                    zone = row.zone_id
                    if zone not in zone_stats:
                        zone_stats[zone] = {"picks": 0, "locations": 0, "total_time": 0}
                    zone_stats[zone]["picks"] += row.pick_frequency
                    zone_stats[zone]["locations"] += 1
                    zone_stats[zone]["total_time"] += row.avg_pick_time or 0
                
                response += "📊 **Zone Performance:**\n"
                for zone, stats in sorted(zone_stats.items(), key=lambda x: x[1]["picks"], reverse=True):
                    avg_time_per_zone = stats["total_time"] / stats["locations"] if stats["locations"] > 0 else 0
                    response += f"   {zone}: {stats['picks']} picks, {stats['locations']} locations, {avg_time_per_zone:.1f}min avg\n"
                
                response += "\n💡 **Recommendations:**\n"
                response += "   • Move fast-moving items to easily accessible locations\n"
                response += "   • Consolidate slow-moving items to free up prime space\n"
                response += "   • Review zone layout for pick path optimization\n"
                response += "   • Consider velocity-based slotting strategy\n"
                
                return response
                
        except Exception as e:
            return f"Error performing optimization analysis: {str(e)}"


# Functional Agent - Business processes and workflows
class LocationsFunctionalAgent(WMSBaseAgent):
    """Handles functional aspects of location management"""
    
    def __init__(self):
        tools = [
            LocationQueryTool("locations", "functional"),
            LocationCapacityTool("locations", "functional"),
            LocationOptimizationTool("locations", "functional")
        ]
        super().__init__("locations", "functional", tools)
    
    def _get_specialization(self) -> str:
        return "Warehouse location management workflows, capacity planning, and space optimization"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "location_lookup",
            "capacity_analysis", 
            "space_optimization",
            "zone_management",
            "slotting_recommendations",
            "layout_planning"
        ]
    
    async def _validate_category_specific(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Validate location-specific queries"""
        query_lower = query.lower()
        
        # Check for location-related keywords
        location_keywords = ["location", "bin", "aisle", "zone", "capacity", "space", "layout"]
        if not any(keyword in query_lower for keyword in location_keywords):
            return {
                "valid": False,
                "reason": "Query does not appear to be location-related. Try including terms like 'location', 'zone', 'capacity', or 'layout'."
            }
        
        return {"valid": True}
    
    async def _extract_action_parameters(self, query: str, context: WMSContext) -> Dict[str, Any]:
        """Extract location action parameters"""
        query_lower = query.lower()
        
        if "create location" in query_lower or "add location" in query_lower:
            return {
                "action_type": "create_location",
                "required_permission": "write",
                "parameters": self._parse_location_creation(query)
            }
        elif "update location" in query_lower or "modify location" in query_lower:
            return {
                "action_type": "update_location", 
                "required_permission": "write",
                "parameters": self._parse_location_update(query)
            }
        elif "optimize" in query_lower:
            return {
                "action_type": "optimize_locations",
                "required_permission": "analyze",
                "parameters": {"optimization_type": "space_utilization"}
            }
        
        return {"action_type": "unknown", "parameters": {}}
    
    def _parse_location_creation(self, query: str) -> Dict[str, Any]:
        """Parse location creation parameters from query"""
        # This would use NLP to extract location details
        # For now, return basic structure
        return {
            "zone_id": "A",
            "location_type": "PICK",
            "is_pickable": True,
            "is_receivable": True
        }
    
    def _parse_location_update(self, query: str) -> Dict[str, Any]:
        """Parse location update parameters from query"""
        return {
            "update_fields": ["capacity_qty", "location_type"]
        }


# Technical Agent - System specifications and integrations
class LocationsTechnicalAgent(WMSBaseAgent):
    """Handles technical aspects of location management"""
    
    def __init__(self):
        tools = [LocationQueryTool("locations", "technical")]
        super().__init__("locations", "technical", tools)
    
    def _get_specialization(self) -> str:
        return "Location system architecture, coordinate systems, barcode generation, and RFID integration"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "coordinate_mapping",
            "barcode_generation", 
            "rfid_integration",
            "system_architecture",
            "api_integration",
            "database_schema"
        ]


# Configuration Agent - Setup and parameters
class LocationsConfigurationAgent(WMSBaseAgent):
    """Handles location configuration and setup"""
    
    def __init__(self):
        tools = [LocationQueryTool("locations", "configuration")]
        super().__init__("locations", "configuration", tools)
    
    def _get_specialization(self) -> str:
        return "Location setup, attribute configuration, zone restrictions, and access controls"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "location_setup",
            "zone_configuration",
            "capacity_settings",
            "access_controls",
            "validation_rules",
            "system_parameters"
        ]


# Relationships Agent - Integration with other modules
class LocationsRelationshipsAgent(WMSBaseAgent):
    """Handles location relationships with other WMS modules"""
    
    def __init__(self):
        tools = [LocationQueryTool("locations", "relationships")]
        super().__init__("locations", "relationships", tools)
    
    def _get_specialization(self) -> str:
        return "Location relationships with inventory, picking, putaway, and equipment assignments"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "inventory_placement",
            "picking_integration",
            "putaway_strategies", 
            "equipment_assignments",
            "workflow_integration",
            "cross_module_analysis"
        ]


# Notes Agent - Best practices and recommendations
class LocationsNotesAgent(WMSBaseAgent):
    """Provides location management best practices and recommendations"""
    
    def __init__(self):
        tools = [LocationOptimizationTool("locations", "notes")]
        super().__init__("locations", "notes", tools)
    
    def _get_specialization(self) -> str:
        return "Location optimization best practices, naming conventions, and scalability considerations"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "best_practices",
            "naming_conventions",
            "optimization_strategies",
            "scalability_planning",
            "industry_standards",
            "recommendations"
        ]