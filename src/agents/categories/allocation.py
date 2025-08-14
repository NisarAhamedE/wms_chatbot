"""
Allocation management agents (Category 10) - 5 specialized sub-category agents.
Handles all aspects of inventory allocation including order prioritization, availability checks, and allocation optimization.
"""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import WMSBaseAgent, WMSBaseTool, WMSContext
from ...database.models import (
    Allocation, Order, OrderLine, Item, Location, Inventory, InventoryMovement
)


class AllocationStrategyTool(WMSBaseTool):
    """Tool for allocation strategy management and optimization"""
    
    name = "allocation_strategy"
    description = "Manage allocation strategies, prioritization rules, and availability optimization"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute allocation strategy analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Parse allocation parameters
                allocation_params = self._parse_allocation_query(query)
                
                # Get allocation strategy data
                strategy_query = """
                SELECT 
                    a.allocation_id,
                    a.order_number,
                    a.order_line_number,
                    a.item_id,
                    i.item_description,
                    a.requested_quantity,
                    a.allocated_quantity,
                    a.allocation_status,
                    a.priority_level,
                    a.allocation_rule,
                    a.from_location_id,
                    l.zone_id,
                    a.created_at,
                    a.allocated_at,
                    o.order_priority,
                    o.customer_id,
                    o.required_date,
                    inv.quantity_available,
                    (a.requested_quantity - a.allocated_quantity) as shortage_quantity
                FROM allocations a
                JOIN items i ON a.item_id = i.item_id
                LEFT JOIN orders o ON a.order_number = o.order_number
                LEFT JOIN locations l ON a.from_location_id = l.location_id
                LEFT JOIN inventory inv ON a.item_id = inv.item_id AND a.from_location_id = inv.location_id
                WHERE a.created_at >= NOW() - INTERVAL '14 days'
                ORDER BY a.created_at DESC
                LIMIT 200;
                """
                
                result = await session.execute(strategy_query)
                allocation_data = result.fetchall()
                
                if not allocation_data:
                    return "No allocation data found for the last 14 days."
                
                response = "🎯 **Allocation Strategy Analysis (Last 14 days):**\n\n"
                
                # Overall allocation statistics
                total_allocations = len(allocation_data)
                full_allocations = len([a for a in allocation_data if a.allocated_quantity >= a.requested_quantity])
                partial_allocations = len([a for a in allocation_data if 0 < a.allocated_quantity < a.requested_quantity])
                failed_allocations = len([a for a in allocation_data if a.allocated_quantity == 0])
                
                total_requested = sum(float(a.requested_quantity) for a in allocation_data)
                total_allocated = sum(float(a.allocated_quantity) for a in allocation_data)
                fill_rate = (total_allocated / total_requested) * 100 if total_requested > 0 else 0
                
                response += f"📊 **Allocation Overview:**\n"
                response += f"   Total allocations: {total_allocations:,}\n"
                response += f"   Full allocations: {full_allocations:,} ({full_allocations/total_allocations*100:.1f}%)\n"
                response += f"   Partial allocations: {partial_allocations:,} ({partial_allocations/total_allocations*100:.1f}%)\n"
                response += f"   Failed allocations: {failed_allocations:,} ({failed_allocations/total_allocations*100:.1f}%)\n"
                response += f"   Overall fill rate: {fill_rate:.1f}%\n\n"
                
                # Allocation rule performance
                rule_performance = {}
                for allocation in allocation_data:
                    rule = allocation.allocation_rule or "DEFAULT"
                    if rule not in rule_performance:
                        rule_performance[rule] = {
                            "count": 0, "requested": 0, "allocated": 0, "full_fills": 0
                        }
                    
                    rule_performance[rule]["count"] += 1
                    rule_performance[rule]["requested"] += float(allocation.requested_quantity)
                    rule_performance[rule]["allocated"] += float(allocation.allocated_quantity)
                    if allocation.allocated_quantity >= allocation.requested_quantity:
                        rule_performance[rule]["full_fills"] += 1
                
                response += f"📋 **Allocation Rule Performance:**\n"
                for rule, stats in sorted(rule_performance.items(), key=lambda x: x[1]["count"], reverse=True):
                    fill_rate = (stats["allocated"] / stats["requested"]) * 100 if stats["requested"] > 0 else 0
                    full_fill_rate = (stats["full_fills"] / stats["count"]) * 100 if stats["count"] > 0 else 0
                    
                    response += f"   {rule}:\n"
                    response += f"      Allocations: {stats['count']:,}\n"
                    response += f"      Fill rate: {fill_rate:.1f}%\n"
                    response += f"      Full fill rate: {full_fill_rate:.1f}%\n"
                
                # Priority analysis
                priority_performance = {}
                for allocation in allocation_data:
                    priority = allocation.priority_level or 5  # Default priority
                    priority_bucket = "High (8-10)" if priority >= 8 else "Medium (5-7)" if priority >= 5 else "Low (1-4)"
                    
                    if priority_bucket not in priority_performance:
                        priority_performance[priority_bucket] = {
                            "count": 0, "requested": 0, "allocated": 0, "avg_time_to_allocate": []
                        }
                    
                    priority_performance[priority_bucket]["count"] += 1
                    priority_performance[priority_bucket]["requested"] += float(allocation.requested_quantity)
                    priority_performance[priority_bucket]["allocated"] += float(allocation.allocated_quantity)
                    
                    if allocation.created_at and allocation.allocated_at:
                        time_diff = (allocation.allocated_at - allocation.created_at).total_seconds() / 60
                        priority_performance[priority_bucket]["avg_time_to_allocate"].append(time_diff)
                
                response += f"\n🔴 **Priority Performance:**\n"
                for priority, stats in sorted(priority_performance.items()):
                    fill_rate = (stats["allocated"] / stats["requested"]) * 100 if stats["requested"] > 0 else 0
                    avg_time = sum(stats["avg_time_to_allocate"]) / len(stats["avg_time_to_allocate"]) if stats["avg_time_to_allocate"] else 0
                    
                    response += f"   {priority}:\n"
                    response += f"      Fill rate: {fill_rate:.1f}%\n"
                    response += f"      Avg allocation time: {avg_time:.1f} minutes\n"
                    response += f"      Allocations: {stats['count']:,}\n"
                
                # Shortage analysis
                shortages = [a for a in allocation_data if a.shortage_quantity > 0]
                if shortages:
                    total_shortage = sum(float(a.shortage_quantity) for a in shortages)
                    
                    # Group shortages by item
                    item_shortages = {}
                    for allocation in shortages:
                        item_id = allocation.item_id
                        if item_id not in item_shortages:
                            item_shortages[item_id] = {"shortage": 0, "count": 0, "description": allocation.item_description}
                        item_shortages[item_id]["shortage"] += float(allocation.shortage_quantity)
                        item_shortages[item_id]["count"] += 1
                    
                    response += f"\n⚠️ **Shortage Analysis:**\n"
                    response += f"   Orders with shortages: {len(shortages)}\n"
                    response += f"   Total shortage quantity: {total_shortage:,.1f}\n"
                    response += f"   Items affected: {len(item_shortages)}\n\n"
                    
                    # Top shortage items
                    top_shortages = sorted(item_shortages.items(), key=lambda x: x[1]["shortage"], reverse=True)[:5]
                    response += f"   Top shortage items:\n"
                    for item_id, data in top_shortages:
                        response += f"      {item_id}: {data['shortage']:,.1f} units short ({data['count']} orders)\n"
                
                # Location performance
                location_performance = {}
                for allocation in allocation_data:
                    if allocation.from_location_id:
                        loc_id = allocation.from_location_id
                        zone = allocation.zone_id or "Unknown"
                        
                        if zone not in location_performance:
                            location_performance[zone] = {
                                "allocations": 0, "requested": 0, "allocated": 0, "locations": set()
                            }
                        
                        location_performance[zone]["allocations"] += 1
                        location_performance[zone]["requested"] += float(allocation.requested_quantity)
                        location_performance[zone]["allocated"] += float(allocation.allocated_quantity)
                        location_performance[zone]["locations"].add(loc_id)
                
                if location_performance:
                    response += f"\n📍 **Zone Allocation Performance:**\n"
                    for zone, stats in sorted(location_performance.items(), key=lambda x: x[1]["allocations"], reverse=True):
                        fill_rate = (stats["allocated"] / stats["requested"]) * 100 if stats["requested"] > 0 else 0
                        response += f"   Zone {zone}:\n"
                        response += f"      Allocations: {stats['allocations']:,}\n"
                        response += f"      Fill rate: {fill_rate:.1f}%\n"
                        response += f"      Active locations: {len(stats['locations'])}\n"
                
                # Customer impact analysis
                customer_impact = {}
                for allocation in allocation_data:
                    if allocation.customer_id:
                        customer = allocation.customer_id
                        if customer not in customer_impact:
                            customer_impact[customer] = {
                                "orders": set(), "total_requested": 0, "total_allocated": 0, "shortages": 0
                            }
                        
                        customer_impact[customer]["orders"].add(allocation.order_number)
                        customer_impact[customer]["total_requested"] += float(allocation.requested_quantity)
                        customer_impact[customer]["total_allocated"] += float(allocation.allocated_quantity)
                        if allocation.shortage_quantity > 0:
                            customer_impact[customer]["shortages"] += 1
                
                if customer_impact:
                    # Customers with highest shortage impact
                    shortage_impact = [
                        (cust, data) for cust, data in customer_impact.items() 
                        if data["shortages"] > 0
                    ]
                    
                    if shortage_impact:
                        shortage_impact.sort(key=lambda x: x[1]["shortages"], reverse=True)
                        response += f"\n👥 **Customer Impact:**\n"
                        response += f"   Customers affected by shortages: {len(shortage_impact)}\n"
                        
                        response += f"   Top impacted customers:\n"
                        for customer, data in shortage_impact[:5]:
                            fill_rate = (data["total_allocated"] / data["total_requested"]) * 100 if data["total_requested"] > 0 else 0
                            response += f"      {customer}: {data['shortages']} shortages, {fill_rate:.1f}% fill rate\n"
                
                # Recommendations
                response += f"\n💡 **Allocation Recommendations:**\n"
                
                if fill_rate < 90:
                    response += f"   • Overall fill rate is {fill_rate:.1f}% - investigate inventory availability\n"
                
                if failed_allocations > total_allocations * 0.1:
                    response += f"   • {failed_allocations} failed allocations - review allocation rules and inventory\n"
                
                # Check rule effectiveness
                if rule_performance:
                    rule_fill_rates = [
                        (rule, (stats["allocated"] / stats["requested"]) * 100 if stats["requested"] > 0 else 0)
                        for rule, stats in rule_performance.items()
                    ]
                    rule_fill_rates.sort(key=lambda x: x[1])
                    
                    if rule_fill_rates and rule_fill_rates[0][1] < rule_fill_rates[-1][1] * 0.8:
                        response += f"   • Rule '{rule_fill_rates[0][0]}' has {rule_fill_rates[0][1]:.1f}% fill rate - review effectiveness\n"
                
                # Priority optimization
                if priority_performance:
                    high_priority_fill = priority_performance.get("High (8-10)", {}).get("allocated", 0) / priority_performance.get("High (8-10)", {}).get("requested", 1) * 100
                    low_priority_fill = priority_performance.get("Low (1-4)", {}).get("allocated", 0) / priority_performance.get("Low (1-4)", {}).get("requested", 1) * 100
                    
                    if high_priority_fill < low_priority_fill:
                        response += f"   • High priority orders have lower fill rate - review allocation sequencing\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing allocation strategy: {str(e)}"
    
    def _parse_allocation_query(self, query: str) -> Dict[str, Any]:
        """Parse allocation query parameters"""
        query_lower = query.lower()
        params = {}
        
        import re
        
        # Extract allocation status
        if "allocated" in query_lower:
            params["status"] = "ALLOCATED"
        elif "failed" in query_lower or "shortage" in query_lower:
            params["status"] = "FAILED"
        elif "partial" in query_lower:
            params["status"] = "PARTIAL"
        
        # Extract priority
        if "high priority" in query_lower:
            params["priority"] = "HIGH"
        elif "low priority" in query_lower:
            params["priority"] = "LOW"
        
        return params


class AvailabilityCheckTool(WMSBaseTool):
    """Tool for inventory availability analysis and checks"""
    
    name = "availability_check"
    description = "Check inventory availability, analyze stock levels, and identify allocation constraints"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute availability analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get availability data
                availability_query = """
                SELECT 
                    inv.item_id,
                    i.item_description,
                    i.item_category,
                    SUM(inv.quantity_on_hand) as total_on_hand,
                    SUM(inv.quantity_allocated) as total_allocated,
                    SUM(inv.quantity_on_hand - inv.quantity_allocated) as total_available,
                    COUNT(inv.location_id) as location_count,
                    STRING_AGG(DISTINCT l.zone_id, ',') as zones,
                    SUM(CASE WHEN inv.quantity_on_hand - inv.quantity_allocated > 0 THEN 1 ELSE 0 END) as locations_with_availability,
                    AVG(inv.quantity_on_hand) as avg_per_location,
                    MAX(inv.quantity_on_hand) as max_in_location,
                    COUNT(CASE WHEN inv.quantity_on_hand - inv.quantity_allocated <= 0 THEN 1 END) as depleted_locations
                FROM inventory inv
                JOIN items i ON inv.item_id = i.item_id
                LEFT JOIN locations l ON inv.location_id = l.location_id
                WHERE inv.quantity_on_hand > 0 OR inv.quantity_allocated > 0
                GROUP BY inv.item_id, i.item_description, i.item_category
                ORDER BY total_available DESC
                LIMIT 100;
                """
                
                result = await session.execute(availability_query)
                availability_data = result.fetchall()
                
                if not availability_data:
                    return "No inventory availability data found."
                
                response = "📦 **Inventory Availability Analysis:**\n\n"
                
                # Overall availability metrics
                total_items = len(availability_data)
                items_with_availability = len([item for item in availability_data if item.total_available > 0])
                items_fully_allocated = len([item for item in availability_data if item.total_available <= 0 and item.total_on_hand > 0])
                items_out_of_stock = len([item for item in availability_data if item.total_on_hand <= 0])
                
                total_inventory_value = sum(float(item.total_on_hand) for item in availability_data)
                total_available_value = sum(float(item.total_available) for item in availability_data if item.total_available > 0)
                availability_rate = (total_available_value / total_inventory_value) * 100 if total_inventory_value > 0 else 0
                
                response += f"📊 **Availability Overview:**\n"
                response += f"   Items analyzed: {total_items:,}\n"
                response += f"   Items with availability: {items_with_availability:,} ({items_with_availability/total_items*100:.1f}%)\n"
                response += f"   Fully allocated items: {items_fully_allocated:,} ({items_fully_allocated/total_items*100:.1f}%)\n"
                response += f"   Out of stock items: {items_out_of_stock:,} ({items_out_of_stock/total_items*100:.1f}%)\n"
                response += f"   Overall availability rate: {availability_rate:.1f}%\n\n"
                
                # High availability items
                high_availability = sorted(availability_data, key=lambda x: x.total_available, reverse=True)[:10]
                response += f"✅ **High Availability Items:**\n"
                for item in high_availability:
                    if item.total_available > 0:
                        allocation_rate = (item.total_allocated / item.total_on_hand) * 100 if item.total_on_hand > 0 else 0
                        response += f"   {item.item_id}:\n"
                        response += f"      Available: {item.total_available:,.1f}\n"
                        response += f"      Locations: {item.locations_with_availability}/{item.location_count}\n"
                        response += f"      Allocation rate: {allocation_rate:.1f}%\n"
                
                # Low availability items (potential allocation issues)
                low_availability = [item for item in availability_data if 0 < item.total_available <= 10]
                if low_availability:
                    low_availability.sort(key=lambda x: x.total_available)
                    response += f"\n⚠️ **Low Availability Items:**\n"
                    for item in low_availability[:10]:
                        response += f"   {item.item_id}: {item.total_available:,.1f} available\n"
                        response += f"      On hand: {item.total_on_hand:,.1f}, Allocated: {item.total_allocated:,.1f}\n"
                        response += f"      Locations: {item.location_count} ({item.depleted_locations} depleted)\n"
                
                # Fully allocated items
                if items_fully_allocated > 0:
                    fully_allocated = [item for item in availability_data if item.total_available <= 0 and item.total_on_hand > 0]
                    response += f"\n🔴 **Fully Allocated Items:** {len(fully_allocated)}\n"
                    for item in fully_allocated[:5]:
                        response += f"   {item.item_id}: {item.total_on_hand:,.1f} on hand (100% allocated)\n"
                        response += f"      Locations: {item.location_count}\n"
                
                # Category availability analysis
                category_availability = {}
                for item in availability_data:
                    category = item.item_category or "Unknown"
                    if category not in category_availability:
                        category_availability[category] = {
                            "items": 0, "total_on_hand": 0, "total_available": 0, "items_available": 0
                        }
                    
                    category_availability[category]["items"] += 1
                    category_availability[category]["total_on_hand"] += float(item.total_on_hand)
                    category_availability[category]["total_available"] += float(item.total_available) if item.total_available > 0 else 0
                    if item.total_available > 0:
                        category_availability[category]["items_available"] += 1
                
                response += f"\n📂 **Category Availability:**\n"
                for category, stats in sorted(category_availability.items(), key=lambda x: x[1]["total_available"], reverse=True)[:5]:
                    availability_pct = (stats["items_available"] / stats["items"]) * 100 if stats["items"] > 0 else 0
                    utilization_pct = ((stats["total_on_hand"] - stats["total_available"]) / stats["total_on_hand"]) * 100 if stats["total_on_hand"] > 0 else 0
                    
                    response += f"   {category}:\n"
                    response += f"      Items available: {stats['items_available']}/{stats['items']} ({availability_pct:.1f}%)\n"
                    response += f"      Total available: {stats['total_available']:,.1f}\n"
                    response += f"      Utilization: {utilization_pct:.1f}%\n"
                
                # Zone distribution analysis
                zone_distribution = {}
                for item in availability_data:
                    if item.zones:
                        zones = item.zones.split(',')
                        zone_count = len(zones)
                        distribution_key = "Single zone" if zone_count == 1 else "2-3 zones" if zone_count <= 3 else "4+ zones"
                        
                        if distribution_key not in zone_distribution:
                            zone_distribution[distribution_key] = {"items": 0, "total_available": 0}
                        
                        zone_distribution[distribution_key]["items"] += 1
                        zone_distribution[distribution_key]["total_available"] += float(item.total_available) if item.total_available > 0 else 0
                
                if zone_distribution:
                    response += f"\n🗺️ **Zone Distribution:**\n"
                    for distribution, stats in sorted(zone_distribution.items()):
                        avg_availability = stats["total_available"] / stats["items"] if stats["items"] > 0 else 0
                        response += f"   {distribution}: {stats['items']} items, {avg_availability:.1f} avg available\n"
                
                # Allocation pressure analysis
                high_pressure_items = [
                    item for item in availability_data 
                    if item.total_on_hand > 0 and (item.total_allocated / item.total_on_hand) > 0.8
                ]
                
                if high_pressure_items:
                    response += f"\n🔥 **High Allocation Pressure:** {len(high_pressure_items)} items\n"
                    high_pressure_items.sort(key=lambda x: x.total_allocated / x.total_on_hand, reverse=True)
                    
                    for item in high_pressure_items[:5]:
                        pressure_pct = (item.total_allocated / item.total_on_hand) * 100
                        response += f"   {item.item_id}: {pressure_pct:.1f}% allocated\n"
                        response += f"      Remaining: {item.total_available:,.1f} of {item.total_on_hand:,.1f}\n"
                
                # Recommendations
                response += f"\n💡 **Availability Recommendations:**\n"
                
                if availability_rate < 70:
                    response += f"   • Low availability rate ({availability_rate:.1f}%) - review allocation strategies\n"
                
                if items_fully_allocated > total_items * 0.2:
                    response += f"   • {items_fully_allocated} fully allocated items - consider replenishment priorities\n"
                
                if low_availability:
                    response += f"   • {len(low_availability)} items have critical low availability - urgent replenishment needed\n"
                
                # Check for concentration risk
                if zone_distribution:
                    single_zone_items = zone_distribution.get("Single zone", {}).get("items", 0)
                    if single_zone_items > total_items * 0.7:
                        response += f"   • {single_zone_items} items in single zones - consider distribution for allocation flexibility\n"
                
                if high_pressure_items:
                    response += f"   • {len(high_pressure_items)} items under high allocation pressure - monitor closely\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing availability: {str(e)}"


class AllocationPerformanceTool(WMSBaseTool):
    """Tool for allocation performance analysis and metrics"""
    
    name = "allocation_performance"
    description = "Analyze allocation performance, timing, and efficiency metrics"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute performance analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get allocation performance data
                performance_query = """
                SELECT 
                    DATE(a.created_at) as allocation_date,
                    COUNT(*) as total_allocations,
                    SUM(a.requested_quantity) as total_requested,
                    SUM(a.allocated_quantity) as total_allocated,
                    COUNT(CASE WHEN a.allocated_quantity >= a.requested_quantity THEN 1 END) as full_allocations,
                    COUNT(CASE WHEN a.allocated_quantity = 0 THEN 1 END) as failed_allocations,
                    AVG(CASE 
                        WHEN a.allocated_at IS NOT NULL AND a.created_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (a.allocated_at - a.created_at)) / 60
                        ELSE NULL
                    END) as avg_allocation_time_minutes,
                    COUNT(DISTINCT a.item_id) as unique_items,
                    COUNT(DISTINCT a.order_number) as unique_orders,
                    AVG(a.priority_level) as avg_priority
                FROM allocations a
                WHERE a.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY DATE(a.created_at)
                ORDER BY allocation_date DESC
                LIMIT 30;
                """
                
                result = await session.execute(performance_query)
                performance_data = result.fetchall()
                
                if not performance_data:
                    return "No allocation performance data found for the last 30 days."
                
                response = "📈 **Allocation Performance Analysis (Last 30 days):**\n\n"
                
                # Overall performance metrics
                total_days = len(performance_data)
                total_allocations = sum(day.total_allocations for day in performance_data)
                total_requested = sum(float(day.total_requested) for day in performance_data)
                total_allocated = sum(float(day.total_allocated) for day in performance_data)
                total_full = sum(day.full_allocations for day in performance_data)
                total_failed = sum(day.failed_allocations for day in performance_data)
                
                overall_fill_rate = (total_allocated / total_requested) * 100 if total_requested > 0 else 0
                overall_success_rate = (total_full / total_allocations) * 100 if total_allocations > 0 else 0
                daily_avg = total_allocations / total_days if total_days > 0 else 0
                
                response += f"🎯 **Overall Performance:**\n"
                response += f"   Total allocations: {total_allocations:,}\n"
                response += f"   Fill rate: {overall_fill_rate:.1f}%\n"
                response += f"   Success rate: {overall_success_rate:.1f}%\n"
                response += f"   Daily average: {daily_avg:.1f} allocations\n"
                response += f"   Failed allocations: {total_failed:,} ({total_failed/total_allocations*100:.1f}%)\n\n"
                
                # Daily performance breakdown
                response += f"📅 **Daily Performance (Last 7 days):**\n"
                for day in performance_data[:7]:
                    fill_rate = (day.total_allocated / day.total_requested) * 100 if day.total_requested > 0 else 0
                    success_rate = (day.full_allocations / day.total_allocations) * 100 if day.total_allocations > 0 else 0
                    
                    response += f"   {day.allocation_date.strftime('%Y-%m-%d')}:\n"
                    response += f"      Allocations: {day.total_allocations:,}\n"
                    response += f"      Fill rate: {fill_rate:.1f}%\n"
                    response += f"      Success rate: {success_rate:.1f}%\n"
                    response += f"      Orders: {day.unique_orders}, Items: {day.unique_items}\n"
                    if day.avg_allocation_time_minutes:
                        response += f"      Avg time: {day.avg_allocation_time_minutes:.1f} minutes\n"
                
                # Performance trends
                if len(performance_data) >= 7:
                    recent_week = performance_data[:7]
                    previous_week = performance_data[7:14] if len(performance_data) >= 14 else performance_data[7:]
                    
                    if previous_week:
                        recent_avg_fill = sum(
                            (day.total_allocated / day.total_requested) * 100 if day.total_requested > 0 else 0 
                            for day in recent_week
                        ) / len(recent_week)
                        
                        previous_avg_fill = sum(
                            (day.total_allocated / day.total_requested) * 100 if day.total_requested > 0 else 0 
                            for day in previous_week
                        ) / len(previous_week)
                        
                        trend = recent_avg_fill - previous_avg_fill
                        trend_direction = "📈" if trend > 0 else "📉" if trend < 0 else "➡️"
                        
                        response += f"\n{trend_direction} **Weekly Trend:**\n"
                        response += f"   Fill rate change: {trend:+.1f}%\n"
                        response += f"   Recent week: {recent_avg_fill:.1f}%\n"
                        response += f"   Previous week: {previous_avg_fill:.1f}%\n"
                
                # Performance timing analysis
                timing_data = [day for day in performance_data if day.avg_allocation_time_minutes]
                if timing_data:
                    avg_timing = sum(day.avg_allocation_time_minutes for day in timing_data) / len(timing_data)
                    fastest_day = min(timing_data, key=lambda x: x.avg_allocation_time_minutes)
                    slowest_day = max(timing_data, key=lambda x: x.avg_allocation_time_minutes)
                    
                    response += f"\n⏱️ **Timing Analysis:**\n"
                    response += f"   Average allocation time: {avg_timing:.1f} minutes\n"
                    response += f"   Fastest day: {fastest_day.allocation_date.strftime('%Y-%m-%d')} ({fastest_day.avg_allocation_time_minutes:.1f} min)\n"
                    response += f"   Slowest day: {slowest_day.allocation_date.strftime('%Y-%m-%d')} ({slowest_day.avg_allocation_time_minutes:.1f} min)\n"
                
                # Volume vs performance correlation
                high_volume_days = [day for day in performance_data if day.total_allocations > daily_avg * 1.2]
                low_volume_days = [day for day in performance_data if day.total_allocations < daily_avg * 0.8]
                
                if high_volume_days and low_volume_days:
                    high_vol_fill_rate = sum(
                        (day.total_allocated / day.total_requested) * 100 if day.total_requested > 0 else 0 
                        for day in high_volume_days
                    ) / len(high_volume_days)
                    
                    low_vol_fill_rate = sum(
                        (day.total_allocated / day.total_requested) * 100 if day.total_requested > 0 else 0 
                        for day in low_volume_days
                    ) / len(low_volume_days)
                    
                    response += f"\n📊 **Volume Impact:**\n"
                    response += f"   High volume days ({len(high_volume_days)}): {high_vol_fill_rate:.1f}% avg fill rate\n"
                    response += f"   Low volume days ({len(low_volume_days)}): {low_vol_fill_rate:.1f}% avg fill rate\n"
                    
                    if abs(high_vol_fill_rate - low_vol_fill_rate) > 5:
                        impact = "positive" if high_vol_fill_rate > low_vol_fill_rate else "negative"
                        response += f"   Volume has {impact} impact on performance\n"
                
                # Best and worst performing days
                sorted_by_fill_rate = sorted(
                    [(day, (day.total_allocated / day.total_requested) * 100 if day.total_requested > 0 else 0) 
                     for day in performance_data],
                    key=lambda x: x[1]
                )
                
                if len(sorted_by_fill_rate) >= 2:
                    worst_day, worst_rate = sorted_by_fill_rate[0]
                    best_day, best_rate = sorted_by_fill_rate[-1]
                    
                    response += f"\n🏆 **Performance Extremes:**\n"
                    response += f"   Best day: {best_day.allocation_date.strftime('%Y-%m-%d')} ({best_rate:.1f}% fill rate)\n"
                    response += f"   Worst day: {worst_day.allocation_date.strftime('%Y-%m-%d')} ({worst_rate:.1f}% fill rate)\n"
                    
                    if best_rate - worst_rate > 20:
                        response += f"   High variability ({best_rate - worst_rate:.1f}% range) suggests process inconsistency\n"
                
                # Recommendations
                response += f"\n💡 **Performance Recommendations:**\n"
                
                if overall_fill_rate < 85:
                    response += f"   • Fill rate is {overall_fill_rate:.1f}% - investigate inventory and allocation strategies\n"
                
                if total_failed > total_allocations * 0.1:
                    response += f"   • {total_failed/total_allocations*100:.1f}% allocation failure rate - review availability checks\n"
                
                if timing_data and avg_timing > 10:
                    response += f"   • Average allocation time is {avg_timing:.1f} minutes - consider automation improvements\n"
                
                # Check for consistency
                fill_rates = [
                    (day.total_allocated / day.total_requested) * 100 if day.total_requested > 0 else 0 
                    for day in performance_data
                ]
                
                if fill_rates:
                    std_dev = (sum((rate - overall_fill_rate) ** 2 for rate in fill_rates) / len(fill_rates)) ** 0.5
                    if std_dev > 10:
                        response += f"   • High performance variability (σ={std_dev:.1f}%) - investigate consistency issues\n"
                
                if high_volume_days and timing_data:
                    high_vol_timing = sum(
                        day.avg_allocation_time_minutes for day in high_volume_days if day.avg_allocation_time_minutes
                    ) / len([day for day in high_volume_days if day.avg_allocation_time_minutes])
                    
                    if high_vol_timing > avg_timing * 1.5:
                        response += f"   • High volume days have {high_vol_timing/avg_timing:.1f}x longer allocation times - review scalability\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing allocation performance: {str(e)}"


# Functional Agent - Business processes and workflows
class AllocationFunctionalAgent(WMSBaseAgent):
    """Handles functional aspects of allocation management"""
    
    def __init__(self):
        tools = [
            AllocationStrategyTool("allocation", "functional"),
            AvailabilityCheckTool("allocation", "functional"),
            AllocationPerformanceTool("allocation", "functional")
        ]
        super().__init__("allocation", "functional", tools)
    
    def _get_specialization(self) -> str:
        return "Allocation workflows, availability checking, order prioritization, and shortage management"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "allocation_processing",
            "availability_checking",
            "order_prioritization",
            "shortage_management",
            "reservation_handling",
            "customer_allocation"
        ]


# Technical Agent - System specifications
class AllocationTechnicalAgent(WMSBaseAgent):
    """Handles technical aspects of allocation management"""
    
    def __init__(self):
        tools = [AllocationStrategyTool("allocation", "technical")]
        super().__init__("allocation", "technical", tools)
    
    def _get_specialization(self) -> str:
        return "Allocation algorithms, real-time availability engines, and automated reservation systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "allocation_algorithms",
            "real_time_availability",
            "automated_reservation",
            "system_integration",
            "performance_optimization",
            "concurrent_processing"
        ]


# Configuration Agent - Setup and parameters
class AllocationConfigurationAgent(WMSBaseAgent):
    """Handles allocation configuration"""
    
    def __init__(self):
        tools = [AvailabilityCheckTool("allocation", "configuration")]
        super().__init__("allocation", "configuration", tools)
    
    def _get_specialization(self) -> str:
        return "Allocation rule configuration, priority settings, and availability threshold management"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "rule_configuration",
            "priority_setup",
            "threshold_management",
            "policy_configuration",
            "customer_rules",
            "exception_handling"
        ]


# Relationships Agent - Integration with other modules
class AllocationRelationshipsAgent(WMSBaseAgent):
    """Handles allocation relationships with other WMS modules"""
    
    def __init__(self):
        tools = [AllocationStrategyTool("allocation", "relationships")]
        super().__init__("allocation", "relationships", tools)
    
    def _get_specialization(self) -> str:
        return "Allocation integration with inventory, orders, picking, and replenishment systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "inventory_integration",
            "order_coordination",
            "picking_allocation",
            "replenishment_triggers",
            "cross_module_sync",
            "workflow_orchestration"
        ]


# Notes Agent - Best practices and recommendations
class AllocationNotesAgent(WMSBaseAgent):
    """Provides allocation management best practices and recommendations"""
    
    def __init__(self):
        tools = [AllocationPerformanceTool("allocation", "notes")]
        super().__init__("allocation", "notes", tools)
    
    def _get_specialization(self) -> str:
        return "Allocation efficiency best practices, strategy optimization, and performance improvement methods"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "efficiency_best_practices",
            "strategy_optimization",
            "performance_improvement",
            "customer_satisfaction",
            "shortage_mitigation",
            "continuous_improvement"
        ]