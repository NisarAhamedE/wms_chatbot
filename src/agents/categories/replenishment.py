"""
Replenishment management agents (Category 11) - 5 specialized sub-category agents.
Handles all aspects of inventory replenishment including min/max planning, demand forecasting, and automated replenishment.
"""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import WMSBaseAgent, WMSBaseTool, WMSContext
from ...database.models import (
    ReplenishmentTask, Item, Location, Inventory, InventoryMovement, PutawayTask
)


class ReplenishmentPlanningTool(WMSBaseTool):
    """Tool for replenishment planning and demand analysis"""
    
    name = "replenishment_planning"
    description = "Plan replenishment activities, analyze demand patterns, and optimize stock levels"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute replenishment planning analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Parse replenishment parameters
                replen_params = self._parse_replen_query(query)
                
                # Get replenishment planning data
                planning_query = """
                SELECT 
                    rt.task_id,
                    rt.item_id,
                    i.item_description,
                    i.item_category,
                    rt.from_location_id,
                    rt.to_location_id,
                    l_from.zone_id as from_zone,
                    l_to.zone_id as to_zone,
                    rt.requested_quantity,
                    rt.actual_quantity,
                    rt.replenishment_type,
                    rt.task_status,
                    rt.priority_level,
                    rt.trigger_reason,
                    rt.created_at,
                    rt.completed_at,
                    inv_to.quantity_on_hand as current_pick_qty,
                    inv_to.min_quantity,
                    inv_to.max_quantity,
                    inv_from.quantity_on_hand as reserve_qty,
                    CASE 
                        WHEN rt.completed_at IS NOT NULL AND rt.started_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (rt.completed_at - rt.started_at)) / 60
                        ELSE NULL
                    END as completion_time_minutes
                FROM replenishment_tasks rt
                JOIN items i ON rt.item_id = i.item_id
                LEFT JOIN locations l_from ON rt.from_location_id = l_from.location_id
                LEFT JOIN locations l_to ON rt.to_location_id = l_to.location_id
                LEFT JOIN inventory inv_to ON rt.item_id = inv_to.item_id AND rt.to_location_id = inv_to.location_id
                LEFT JOIN inventory inv_from ON rt.item_id = inv_from.item_id AND rt.from_location_id = inv_from.location_id
                WHERE rt.created_at >= NOW() - INTERVAL '14 days'
                ORDER BY rt.created_at DESC
                LIMIT 200;
                """
                
                result = await session.execute(planning_query)
                replen_data = result.fetchall()
                
                if not replen_data:
                    return "No replenishment data found for the last 14 days."
                
                response = "🔄 **Replenishment Planning Analysis (Last 14 days):**\n\n"
                
                # Overall replenishment statistics
                total_tasks = len(replen_data)
                pending_tasks = len([r for r in replen_data if r.task_status == 'PENDING'])
                in_progress_tasks = len([r for r in replen_data if r.task_status == 'IN_PROGRESS'])
                completed_tasks = len([r for r in replen_data if r.task_status == 'COMPLETED'])
                cancelled_tasks = len([r for r in replen_data if r.task_status == 'CANCELLED'])
                
                total_requested = sum(float(r.requested_quantity) for r in replen_data)
                total_completed_qty = sum(float(r.actual_quantity or 0) for r in replen_data if r.task_status == 'COMPLETED')
                completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
                
                response += f"📊 **Replenishment Overview:**\n"
                response += f"   Total tasks: {total_tasks:,}\n"
                response += f"   Pending: {pending_tasks:,} ({pending_tasks/total_tasks*100:.1f}%)\n"
                response += f"   In Progress: {in_progress_tasks:,} ({in_progress_tasks/total_tasks*100:.1f}%)\n"
                response += f"   Completed: {completed_tasks:,} ({completion_rate:.1f}%)\n"
                response += f"   Cancelled: {cancelled_tasks:,}\n"
                response += f"   Total quantity requested: {total_requested:,.1f}\n\n"
                
                # Replenishment type analysis
                replen_types = {}
                for task in replen_data:
                    rtype = task.replenishment_type or "STANDARD"
                    if rtype not in replen_types:
                        replen_types[rtype] = {
                            "count": 0, "requested_qty": 0, "completed": 0, "avg_completion_time": []
                        }
                    
                    replen_types[rtype]["count"] += 1
                    replen_types[rtype]["requested_qty"] += float(task.requested_quantity)
                    
                    if task.task_status == "COMPLETED":
                        replen_types[rtype]["completed"] += 1
                        if task.completion_time_minutes:
                            replen_types[rtype]["avg_completion_time"].append(task.completion_time_minutes)
                
                response += f"🔄 **Replenishment Type Analysis:**\n"
                for rtype, stats in sorted(replen_types.items(), key=lambda x: x[1]["count"], reverse=True):
                    completion_pct = (stats["completed"] / stats["count"]) * 100 if stats["count"] > 0 else 0
                    avg_time = sum(stats["avg_completion_time"]) / len(stats["avg_completion_time"]) if stats["avg_completion_time"] else 0
                    
                    response += f"   {rtype}:\n"
                    response += f"      Tasks: {stats['count']:,} ({completion_pct:.1f}% completed)\n"
                    response += f"      Quantity: {stats['requested_qty']:,.1f}\n"
                    if avg_time > 0:
                        response += f"      Avg completion time: {avg_time:.1f} minutes\n"
                
                # Trigger reason analysis
                trigger_reasons = {}
                for task in replen_data:
                    reason = task.trigger_reason or "UNKNOWN"
                    trigger_reasons[reason] = trigger_reasons.get(reason, 0) + 1
                
                response += f"\n📋 **Trigger Reasons:**\n"
                for reason, count in sorted(trigger_reasons.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_tasks) * 100
                    response += f"   {reason}: {count:,} ({percentage:.1f}%)\n"
                
                # Zone flow analysis
                zone_flows = {}
                for task in replen_data:
                    if task.from_zone and task.to_zone:
                        flow = f"{task.from_zone} → {task.to_zone}"
                        if flow not in zone_flows:
                            zone_flows[flow] = {"count": 0, "quantity": 0, "completed": 0}
                        zone_flows[flow]["count"] += 1
                        zone_flows[flow]["quantity"] += float(task.requested_quantity)
                        if task.task_status == "COMPLETED":
                            zone_flows[flow]["completed"] += 1
                
                if zone_flows:
                    response += f"\n🗺️ **Zone Flow Analysis:**\n"
                    for flow, stats in sorted(zone_flows.items(), key=lambda x: x[1]["count"], reverse=True)[:10]:
                        completion_rate = (stats["completed"] / stats["count"]) * 100 if stats["count"] > 0 else 0
                        response += f"   {flow}:\n"
                        response += f"      Tasks: {stats['count']:,} ({completion_rate:.1f}% completed)\n"
                        response += f"      Quantity: {stats['quantity']:,.1f}\n"
                
                # Min/Max analysis for items with defined thresholds
                min_max_items = [task for task in replen_data if task.min_quantity and task.max_quantity]
                if min_max_items:
                    response += f"\n📏 **Min/Max Threshold Analysis:**\n"
                    
                    below_min = len([task for task in min_max_items if task.current_pick_qty and task.current_pick_qty < task.min_quantity])
                    above_max = len([task for task in min_max_items if task.current_pick_qty and task.current_pick_qty > task.max_quantity])
                    in_range = len(min_max_items) - below_min - above_max
                    
                    response += f"   Items with thresholds: {len(min_max_items):,}\n"
                    response += f"   Below minimum: {below_min:,}\n"
                    response += f"   Above maximum: {above_max:,}\n"
                    response += f"   In range: {in_range:,}\n"
                    
                    # Items needing urgent replenishment
                    urgent_replen = [
                        task for task in min_max_items 
                        if task.current_pick_qty and task.min_quantity and 
                           task.current_pick_qty < task.min_quantity * 0.5  # Below 50% of minimum
                    ]
                    
                    if urgent_replen:
                        response += f"\n🚨 **Urgent Replenishment Needed:** {len(urgent_replen)} items\n"
                        for task in urgent_replen[:5]:
                            shortage_pct = (1 - (task.current_pick_qty / task.min_quantity)) * 100 if task.min_quantity > 0 else 0
                            response += f"      {task.item_id}: {task.current_pick_qty:,.1f} (Min: {task.min_quantity:,.1f}, {shortage_pct:.0f}% below)\n"
                
                # Priority analysis
                high_priority = [task for task in replen_data if task.priority_level and task.priority_level >= 8]
                overdue_tasks = []
                
                current_time = datetime.utcnow()
                for task in replen_data:
                    if task.task_status in ['PENDING', 'IN_PROGRESS']:
                        hours_old = (current_time - task.created_at).total_seconds() / 3600
                        threshold_hours = 4 if (task.priority_level and task.priority_level >= 8) else 24
                        if hours_old > threshold_hours:
                            overdue_tasks.append((task, hours_old))
                
                if high_priority:
                    response += f"\n🔴 **High Priority Tasks:** {len(high_priority)}\n"
                    pending_high_priority = [task for task in high_priority if task.task_status == 'PENDING']
                    if pending_high_priority:
                        response += f"   Pending high priority: {len(pending_high_priority)}\n"
                        for task in pending_high_priority[:3]:
                            response += f"      {task.item_id}: {task.requested_quantity:,.1f} units\n"
                
                if overdue_tasks:
                    response += f"\n⏰ **Overdue Tasks:** {len(overdue_tasks)}\n"
                    for task, hours_old in overdue_tasks[:5]:
                        response += f"   {task.item_id}: {hours_old:.1f} hours overdue\n"
                
                # Performance analysis
                completed_with_time = [task for task in replen_data if task.completion_time_minutes and task.task_status == 'COMPLETED']
                if completed_with_time:
                    avg_completion_time = sum(task.completion_time_minutes for task in completed_with_time) / len(completed_with_time)
                    fast_tasks = len([task for task in completed_with_time if task.completion_time_minutes < avg_completion_time * 0.5])
                    slow_tasks = len([task for task in completed_with_time if task.completion_time_minutes > avg_completion_time * 2])
                    
                    response += f"\n⚡ **Performance Insights:**\n"
                    response += f"   Avg completion time: {avg_completion_time:.1f} minutes\n"
                    response += f"   Fast completions: {fast_tasks}\n"
                    response += f"   Slow completions: {slow_tasks}\n"
                
                # Recommendations
                response += f"\n💡 **Replenishment Recommendations:**\n"
                
                if completion_rate < 85:
                    response += f"   • Completion rate is {completion_rate:.1f}% - investigate resource constraints\n"
                
                if pending_tasks > total_tasks * 0.4:
                    response += f"   • High pending task volume ({pending_tasks}) - consider workforce optimization\n"
                
                if overdue_tasks:
                    response += f"   • {len(overdue_tasks)} overdue tasks require immediate attention\n"
                
                if urgent_replen:
                    response += f"   • {len(urgent_replen)} items critically below minimum - expedite replenishment\n"
                
                # Check for replenishment frequency issues
                frequent_replen_items = {}
                for task in replen_data:
                    if task.task_status == 'COMPLETED':
                        item_id = task.item_id
                        frequent_replen_items[item_id] = frequent_replen_items.get(item_id, 0) + 1
                
                high_frequency_items = {item: count for item, count in frequent_replen_items.items() if count > 5}
                if high_frequency_items:
                    response += f"   • {len(high_frequency_items)} items replenished >5 times - review min/max settings\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing replenishment planning: {str(e)}"
    
    def _parse_replen_query(self, query: str) -> Dict[str, Any]:
        """Parse replenishment query parameters"""
        query_lower = query.lower()
        params = {}
        
        import re
        
        # Extract replenishment type
        if "min max" in query_lower or "min/max" in query_lower:
            params["type"] = "MIN_MAX"
        elif "demand" in query_lower:
            params["type"] = "DEMAND"
        elif "emergency" in query_lower:
            params["type"] = "EMERGENCY"
        
        # Extract status
        if "pending" in query_lower:
            params["status"] = "PENDING"
        elif "completed" in query_lower:
            params["status"] = "COMPLETED"
        elif "overdue" in query_lower:
            params["overdue"] = True
        
        return params


class DemandForecastingTool(WMSBaseTool):
    """Tool for demand forecasting and consumption analysis"""
    
    name = "demand_forecasting"
    description = "Analyze demand patterns, forecast future needs, and optimize replenishment timing"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute demand forecasting analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get consumption data for demand analysis
                demand_query = """
                SELECT 
                    im.item_id,
                    i.item_description,
                    i.item_category,
                    DATE(im.movement_date) as consumption_date,
                    SUM(ABS(im.movement_quantity)) as daily_consumption,
                    COUNT(*) as transaction_count,
                    im.movement_type
                FROM inventory_movements im
                JOIN items i ON im.item_id = i.item_id
                WHERE im.movement_type IN ('PICK', 'SHIP', 'ADJUSTMENT')
                    AND im.movement_quantity < 0  -- Outbound movements
                    AND im.movement_date >= NOW() - INTERVAL '90 days'
                GROUP BY im.item_id, i.item_description, i.item_category, 
                         DATE(im.movement_date), im.movement_type
                ORDER BY im.item_id, consumption_date DESC
                LIMIT 1000;
                """
                
                result = await session.execute(demand_query)
                demand_data = result.fetchall()
                
                if not demand_data:
                    return "No consumption data found for demand forecasting analysis."
                
                response = "📈 **Demand Forecasting Analysis (Last 90 days):**\n\n"
                
                # Aggregate demand by item
                item_demand = {}
                for record in demand_data:
                    item_id = record.item_id
                    if item_id not in item_demand:
                        item_demand[item_id] = {
                            "description": record.item_description,
                            "category": record.item_category,
                            "daily_consumption": [],
                            "total_consumption": 0,
                            "active_days": set(),
                            "transaction_count": 0
                        }
                    
                    item_demand[item_id]["daily_consumption"].append(record.daily_consumption)
                    item_demand[item_id]["total_consumption"] += record.daily_consumption
                    item_demand[item_id]["active_days"].add(record.consumption_date)
                    item_demand[item_id]["transaction_count"] += record.transaction_count
                
                # Calculate demand statistics
                total_items = len(item_demand)
                total_consumption = sum(data["total_consumption"] for data in item_demand.values())
                
                response += f"📊 **Demand Overview:**\n"
                response += f"   Items analyzed: {total_items:,}\n"
                response += f"   Total consumption: {total_consumption:,.1f} units\n"
                response += f"   Average per item: {total_consumption/total_items:.1f} units\n\n"
                
                # High demand items
                high_demand_items = sorted(
                    item_demand.items(), 
                    key=lambda x: x[1]["total_consumption"], 
                    reverse=True
                )[:10]
                
                response += f"🔥 **High Demand Items:**\n"
                for item_id, data in high_demand_items:
                    daily_avg = data["total_consumption"] / len(data["active_days"]) if data["active_days"] else 0
                    velocity = len(data["active_days"]) / 90  # Active days ratio
                    
                    # Calculate demand variability
                    if len(data["daily_consumption"]) > 1:
                        avg_daily = sum(data["daily_consumption"]) / len(data["daily_consumption"])
                        variance = sum((x - avg_daily) ** 2 for x in data["daily_consumption"]) / len(data["daily_consumption"])
                        std_dev = variance ** 0.5
                        cv = (std_dev / avg_daily) if avg_daily > 0 else 0  # Coefficient of variation
                    else:
                        cv = 0
                    
                    response += f"   {item_id}:\n"
                    response += f"      Total consumed: {data['total_consumption']:,.1f}\n"
                    response += f"      Daily average: {daily_avg:.1f}\n"
                    response += f"      Velocity: {velocity:.1%} (active {len(data['active_days'])} days)\n"
                    response += f"      Variability: {cv:.2f} CV\n"
                
                # Demand pattern analysis
                steady_demand = [
                    (item_id, data) for item_id, data in item_demand.items()
                    if len(data["active_days"]) >= 30  # Active at least 30 days
                ]
                
                intermittent_demand = [
                    (item_id, data) for item_id, data in item_demand.items()
                    if 5 <= len(data["active_days"]) < 30
                ]
                
                sporadic_demand = [
                    (item_id, data) for item_id, data in item_demand.items()
                    if len(data["active_days"]) < 5
                ]
                
                response += f"\n📊 **Demand Patterns:**\n"
                response += f"   Steady demand (30+ active days): {len(steady_demand)} items\n"
                response += f"   Intermittent demand (5-29 days): {len(intermittent_demand)} items\n"
                response += f"   Sporadic demand (<5 days): {len(sporadic_demand)} items\n\n"
                
                # Category demand analysis
                category_demand = {}
                for item_id, data in item_demand.items():
                    category = data["category"] or "Unknown"
                    if category not in category_demand:
                        category_demand[category] = {
                            "items": 0, "total_consumption": 0, "avg_velocity": 0
                        }
                    
                    category_demand[category]["items"] += 1
                    category_demand[category]["total_consumption"] += data["total_consumption"]
                    velocity = len(data["active_days"]) / 90
                    category_demand[category]["avg_velocity"] += velocity
                
                response += f"📂 **Category Demand Analysis:**\n"
                sorted_categories = sorted(category_demand.items(), key=lambda x: x[1]["total_consumption"], reverse=True)
                for category, stats in sorted_categories[:5]:
                    avg_velocity = stats["avg_velocity"] / stats["items"] if stats["items"] > 0 else 0
                    response += f"   {category}:\n"
                    response += f"      Items: {stats['items']}\n"
                    response += f"      Total consumption: {stats['total_consumption']:,.1f}\n"
                    response += f"      Avg velocity: {avg_velocity:.1%}\n"
                
                # Forecast high-demand items for next 30 days
                if steady_demand:
                    response += f"\n🔮 **30-Day Demand Forecast (Top Steady Items):**\n"
                    for item_id, data in steady_demand[:5]:
                        daily_avg = data["total_consumption"] / len(data["active_days"])
                        forecast_30_day = daily_avg * 30
                        
                        # Simple trend analysis (last 30 days vs previous 60)
                        recent_consumption = sum(
                            consumption for i, consumption in enumerate(data["daily_consumption"][:30])
                        )
                        older_consumption = sum(
                            consumption for i, consumption in enumerate(data["daily_consumption"][30:60])
                        )
                        
                        trend = "↗" if recent_consumption > older_consumption else "↘" if recent_consumption < older_consumption else "→"
                        
                        response += f"   {item_id}: {forecast_30_day:.1f} units {trend}\n"
                        response += f"      Based on {daily_avg:.1f} daily avg from {len(data['active_days'])} active days\n"
                
                # Replenishment urgency analysis
                urgent_items = []
                for item_id, data in item_demand.items():
                    if len(data["active_days"]) >= 7:  # At least a week of activity
                        daily_avg = data["total_consumption"] / len(data["active_days"])
                        # Items consuming more than 10 units per day on average
                        if daily_avg > 10:
                            urgent_items.append((item_id, daily_avg, data))
                
                if urgent_items:
                    urgent_items.sort(key=lambda x: x[1], reverse=True)
                    response += f"\n🚨 **High Consumption Items (>10/day avg):** {len(urgent_items)}\n"
                    for item_id, daily_avg, data in urgent_items[:5]:
                        days_supply_at_current_rate = 100 / daily_avg if daily_avg > 0 else float('inf')  # Assuming 100 units on hand
                        response += f"   {item_id}: {daily_avg:.1f} units/day\n"
                        response += f"      Est. {days_supply_at_current_rate:.1f} days supply at current rate\n"
                
                # Demand variability insights
                high_variability_items = []
                for item_id, data in item_demand.items():
                    if len(data["daily_consumption"]) > 5:
                        avg_daily = sum(data["daily_consumption"]) / len(data["daily_consumption"])
                        variance = sum((x - avg_daily) ** 2 for x in data["daily_consumption"]) / len(data["daily_consumption"])
                        std_dev = variance ** 0.5
                        cv = (std_dev / avg_daily) if avg_daily > 0 else 0
                        
                        if cv > 1.0:  # High variability
                            high_variability_items.append((item_id, cv, avg_daily))
                
                if high_variability_items:
                    high_variability_items.sort(key=lambda x: x[1], reverse=True)
                    response += f"\n📊 **High Variability Items (CV>1.0):** {len(high_variability_items)}\n"
                    for item_id, cv, avg_daily in high_variability_items[:5]:
                        response += f"   {item_id}: CV={cv:.2f}, avg={avg_daily:.1f}/day\n"
                        response += f"      Consider safety stock due to demand unpredictability\n"
                
                # Recommendations
                response += f"\n💡 **Forecasting Recommendations:**\n"
                
                if steady_demand:
                    response += f"   • {len(steady_demand)} items have steady demand - suitable for automated replenishment\n"
                
                if intermittent_demand:
                    response += f"   • {len(intermittent_demand)} items have intermittent demand - use statistical forecasting\n"
                
                if sporadic_demand:
                    response += f"   • {len(sporadic_demand)} items have sporadic demand - consider event-driven replenishment\n"
                
                if urgent_items:
                    response += f"   • {len(urgent_items)} high-consumption items need frequent monitoring\n"
                
                if high_variability_items:
                    response += f"   • {len(high_variability_items)} items have high demand variability - increase safety stock\n"
                
                # Seasonal or trend analysis recommendation
                if len(demand_data) > 60:  # Enough data points
                    response += f"   • Consider seasonal analysis with {len(set(r.consumption_date for r in demand_data))} days of data\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing demand forecasting: {str(e)}"


class ReplenishmentEfficiencyTool(WMSBaseTool):
    """Tool for replenishment efficiency analysis and optimization"""
    
    name = "replenishment_efficiency"
    description = "Analyze replenishment efficiency, cycle times, and optimization opportunities"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute efficiency analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get replenishment efficiency data
                efficiency_query = """
                SELECT 
                    rt.task_id,
                    rt.item_id,
                    i.item_description,
                    rt.replenishment_type,
                    rt.from_location_id,
                    rt.to_location_id,
                    l_from.zone_id as from_zone,
                    l_to.zone_id as to_zone,
                    rt.requested_quantity,
                    rt.actual_quantity,
                    rt.created_at,
                    rt.started_at,
                    rt.completed_at,
                    rt.assigned_user_id,
                    CASE 
                        WHEN rt.started_at IS NOT NULL AND rt.created_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (rt.started_at - rt.created_at)) / 60
                        ELSE NULL
                    END as time_to_start_minutes,
                    CASE 
                        WHEN rt.completed_at IS NOT NULL AND rt.started_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (rt.completed_at - rt.started_at)) / 60
                        ELSE NULL
                    END as execution_time_minutes,
                    CASE 
                        WHEN rt.completed_at IS NOT NULL AND rt.created_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (rt.completed_at - rt.created_at)) / 60
                        ELSE NULL
                    END as total_cycle_time_minutes
                FROM replenishment_tasks rt
                JOIN items i ON rt.item_id = i.item_id
                LEFT JOIN locations l_from ON rt.from_location_id = l_from.location_id
                LEFT JOIN locations l_to ON rt.to_location_id = l_to.location_id
                WHERE rt.task_status = 'COMPLETED'
                    AND rt.created_at >= NOW() - INTERVAL '30 days'
                ORDER BY rt.completed_at DESC
                LIMIT 500;
                """
                
                result = await session.execute(efficiency_query)
                efficiency_data = result.fetchall()
                
                if not efficiency_data:
                    return "No completed replenishment efficiency data found for the last 30 days."
                
                response = "⚡ **Replenishment Efficiency Analysis (Last 30 days):**\n\n"
                
                # Overall efficiency metrics
                total_completed = len(efficiency_data)
                total_quantity = sum(float(task.actual_quantity or 0) for task in efficiency_data)
                
                # Timing analysis
                tasks_with_timing = [task for task in efficiency_data if task.total_cycle_time_minutes]
                if tasks_with_timing:
                    avg_cycle_time = sum(task.total_cycle_time_minutes for task in tasks_with_timing) / len(tasks_with_timing)
                    
                    tasks_with_start_time = [task for task in efficiency_data if task.time_to_start_minutes]
                    avg_time_to_start = sum(task.time_to_start_minutes for task in tasks_with_start_time) / len(tasks_with_start_time) if tasks_with_start_time else 0
                    
                    tasks_with_exec_time = [task for task in efficiency_data if task.execution_time_minutes]
                    avg_execution_time = sum(task.execution_time_minutes for task in tasks_with_exec_time) / len(tasks_with_exec_time) if tasks_with_exec_time else 0
                    
                    response += f"⏱️ **Timing Analysis:**\n"
                    response += f"   Completed tasks: {total_completed:,}\n"
                    response += f"   Total quantity: {total_quantity:,.1f}\n"
                    response += f"   Avg cycle time: {avg_cycle_time:.1f} minutes\n"
                    response += f"   Avg time to start: {avg_time_to_start:.1f} minutes\n"
                    response += f"   Avg execution time: {avg_execution_time:.1f} minutes\n\n"
                
                # Efficiency by replenishment type
                type_efficiency = {}
                for task in efficiency_data:
                    rtype = task.replenishment_type or "STANDARD"
                    if rtype not in type_efficiency:
                        type_efficiency[rtype] = {
                            "tasks": 0, "total_quantity": 0, "cycle_times": [], "execution_times": []
                        }
                    
                    type_efficiency[rtype]["tasks"] += 1
                    type_efficiency[rtype]["total_quantity"] += float(task.actual_quantity or 0)
                    
                    if task.total_cycle_time_minutes:
                        type_efficiency[rtype]["cycle_times"].append(task.total_cycle_time_minutes)
                    if task.execution_time_minutes:
                        type_efficiency[rtype]["execution_times"].append(task.execution_time_minutes)
                
                response += f"📊 **Efficiency by Type:**\n"
                for rtype, stats in sorted(type_efficiency.items(), key=lambda x: x[1]["tasks"], reverse=True):
                    avg_cycle = sum(stats["cycle_times"]) / len(stats["cycle_times"]) if stats["cycle_times"] else 0
                    avg_exec = sum(stats["execution_times"]) / len(stats["execution_times"]) if stats["execution_times"] else 0
                    productivity = stats["total_quantity"] / (sum(stats["execution_times"]) / 60) if stats["execution_times"] and sum(stats["execution_times"]) > 0 else 0
                    
                    response += f"   {rtype}:\n"
                    response += f"      Tasks: {stats['tasks']:,}\n"
                    response += f"      Avg cycle time: {avg_cycle:.1f} min\n"
                    response += f"      Avg execution: {avg_exec:.1f} min\n"
                    response += f"      Productivity: {productivity:.1f} units/hour\n"
                
                # Zone efficiency analysis
                zone_efficiency = {}
                for task in efficiency_data:
                    if task.from_zone and task.to_zone:
                        zone_pair = f"{task.from_zone}→{task.to_zone}"
                        if zone_pair not in zone_efficiency:
                            zone_efficiency[zone_pair] = {
                                "tasks": 0, "total_quantity": 0, "execution_times": []
                            }
                        
                        zone_efficiency[zone_pair]["tasks"] += 1
                        zone_efficiency[zone_pair]["total_quantity"] += float(task.actual_quantity or 0)
                        
                        if task.execution_time_minutes:
                            zone_efficiency[zone_pair]["execution_times"].append(task.execution_time_minutes)
                
                if zone_efficiency:
                    response += f"\n🗺️ **Zone Efficiency:**\n"
                    sorted_zones = sorted(zone_efficiency.items(), key=lambda x: x[1]["tasks"], reverse=True)[:10]
                    
                    for zone_pair, stats in sorted_zones:
                        avg_exec_time = sum(stats["execution_times"]) / len(stats["execution_times"]) if stats["execution_times"] else 0
                        avg_quantity = stats["total_quantity"] / stats["tasks"] if stats["tasks"] > 0 else 0
                        
                        response += f"   {zone_pair}:\n"
                        response += f"      Tasks: {stats['tasks']:,}\n"
                        response += f"      Avg execution: {avg_exec_time:.1f} min\n"
                        response += f"      Avg quantity: {avg_quantity:.1f} units\n"
                
                # User performance analysis
                user_performance = {}
                for task in efficiency_data:
                    if task.assigned_user_id:
                        user_id = task.assigned_user_id
                        if user_id not in user_performance:
                            user_performance[user_id] = {
                                "tasks": 0, "total_quantity": 0, "execution_times": [], "cycle_times": []
                            }
                        
                        user_performance[user_id]["tasks"] += 1
                        user_performance[user_id]["total_quantity"] += float(task.actual_quantity or 0)
                        
                        if task.execution_time_minutes:
                            user_performance[user_id]["execution_times"].append(task.execution_time_minutes)
                        if task.total_cycle_time_minutes:
                            user_performance[user_id]["cycle_times"].append(task.total_cycle_time_minutes)
                
                # Top performers
                if user_performance:
                    top_performers = sorted(
                        user_performance.items(),
                        key=lambda x: x[1]["tasks"],
                        reverse=True
                    )[:5]
                    
                    response += f"\n🏆 **Top Performers (by volume):**\n"
                    for user_id, stats in top_performers:
                        avg_exec = sum(stats["execution_times"]) / len(stats["execution_times"]) if stats["execution_times"] else 0
                        productivity = stats["total_quantity"] / (sum(stats["execution_times"]) / 60) if stats["execution_times"] and sum(stats["execution_times"]) > 0 else 0
                        
                        response += f"   User {user_id}:\n"
                        response += f"      Tasks: {stats['tasks']:,}\n"
                        response += f"      Quantity: {stats['total_quantity']:,.1f}\n"
                        response += f"      Avg execution: {avg_exec:.1f} min\n"
                        response += f"      Productivity: {productivity:.1f} units/hour\n"
                
                # Efficiency distribution analysis
                if tasks_with_timing:
                    cycle_times = [task.total_cycle_time_minutes for task in tasks_with_timing]
                    
                    # Percentile analysis
                    sorted_times = sorted(cycle_times)
                    p25 = sorted_times[len(sorted_times) // 4]
                    p50 = sorted_times[len(sorted_times) // 2]
                    p75 = sorted_times[3 * len(sorted_times) // 4]
                    p95 = sorted_times[19 * len(sorted_times) // 20]
                    
                    fast_tasks = len([t for t in cycle_times if t <= p25])
                    slow_tasks = len([t for t in cycle_times if t >= p95])
                    
                    response += f"\n📊 **Performance Distribution:**\n"
                    response += f"   25th percentile: {p25:.1f} min\n"
                    response += f"   Median: {p50:.1f} min\n"
                    response += f"   75th percentile: {p75:.1f} min\n"
                    response += f"   95th percentile: {p95:.1f} min\n"
                    response += f"   Fast tasks (≤25%ile): {fast_tasks}\n"
                    response += f"   Slow tasks (≥95%ile): {slow_tasks}\n"
                
                # Quantity efficiency analysis
                small_tasks = [task for task in efficiency_data if task.actual_quantity and task.actual_quantity <= 10]
                large_tasks = [task for task in efficiency_data if task.actual_quantity and task.actual_quantity > 50]
                
                if small_tasks and large_tasks:
                    small_avg_time = sum(
                        task.execution_time_minutes for task in small_tasks if task.execution_time_minutes
                    ) / len([task for task in small_tasks if task.execution_time_minutes])
                    
                    large_avg_time = sum(
                        task.execution_time_minutes for task in large_tasks if task.execution_time_minutes
                    ) / len([task for task in large_tasks if task.execution_time_minutes])
                    
                    response += f"\n📦 **Quantity Impact:**\n"
                    response += f"   Small tasks (≤10 units): {len(small_tasks)}, avg {small_avg_time:.1f} min\n"
                    response += f"   Large tasks (>50 units): {len(large_tasks)}, avg {large_avg_time:.1f} min\n"
                    
                    if large_avg_time > 0 and small_avg_time > 0:
                        efficiency_ratio = large_avg_time / small_avg_time
                        response += f"   Large tasks take {efficiency_ratio:.1f}x longer than small tasks\n"
                
                # Recommendations
                response += f"\n💡 **Efficiency Recommendations:**\n"
                
                if tasks_with_timing and avg_cycle_time > 60:
                    response += f"   • Average cycle time is {avg_cycle_time:.1f} minutes - investigate delays\n"
                
                if avg_time_to_start > 30:
                    response += f"   • Tasks take {avg_time_to_start:.1f} min to start - improve task assignment\n"
                
                # Check for zone inefficiencies
                if zone_efficiency:
                    zone_times = [(zone, sum(stats["execution_times"])/len(stats["execution_times"]) if stats["execution_times"] else 0) 
                                  for zone, stats in zone_efficiency.items()]
                    zone_times = [(z, t) for z, t in zone_times if t > 0]
                    
                    if zone_times:
                        zone_times.sort(key=lambda x: x[1])
                        if len(zone_times) > 1 and zone_times[-1][1] > zone_times[0][1] * 1.5:
                            response += f"   • Zone {zone_times[-1][0]} is {zone_times[-1][1]/zone_times[0][1]:.1f}x slower - investigate path optimization\n"
                
                # Performance consistency
                if tasks_with_timing and len(cycle_times) > 10:
                    cv = (p75 - p25) / p50 if p50 > 0 else 0
                    if cv > 0.5:
                        response += f"   • High timing variability (IQR/median = {cv:.2f}) - standardize processes\n"
                
                if slow_tasks > total_completed * 0.05:  # More than 5% slow tasks
                    response += f"   • {slow_tasks} tasks in 95th percentile - investigate bottlenecks\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing replenishment efficiency: {str(e)}"


# Functional Agent - Business processes and workflows
class ReplenishmentFunctionalAgent(WMSBaseAgent):
    """Handles functional aspects of replenishment management"""
    
    def __init__(self):
        tools = [
            ReplenishmentPlanningTool("replenishment", "functional"),
            DemandForecastingTool("replenishment", "functional"),
            ReplenishmentEfficiencyTool("replenishment", "functional")
        ]
        super().__init__("replenishment", "functional", tools)
    
    def _get_specialization(self) -> str:
        return "Replenishment workflows, min/max planning, demand forecasting, and automated replenishment processes"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "replenishment_planning",
            "demand_forecasting",
            "min_max_optimization",
            "automated_triggering",
            "shortage_prevention",
            "inventory_optimization"
        ]


# Technical Agent - System specifications
class ReplenishmentTechnicalAgent(WMSBaseAgent):
    """Handles technical aspects of replenishment management"""
    
    def __init__(self):
        tools = [ReplenishmentPlanningTool("replenishment", "technical")]
        super().__init__("replenishment", "technical", tools)
    
    def _get_specialization(self) -> str:
        return "Replenishment algorithms, automated forecasting systems, and real-time optimization engines"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "forecasting_algorithms",
            "optimization_engines",
            "automated_systems",
            "real_time_monitoring",
            "system_integration",
            "performance_analytics"
        ]


# Configuration Agent - Setup and parameters
class ReplenishmentConfigurationAgent(WMSBaseAgent):
    """Handles replenishment configuration"""
    
    def __init__(self):
        tools = [DemandForecastingTool("replenishment", "configuration")]
        super().__init__("replenishment", "configuration", tools)
    
    def _get_specialization(self) -> str:
        return "Min/max threshold setup, replenishment rule configuration, and forecasting parameter tuning"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "threshold_configuration",
            "rule_setup",
            "parameter_tuning",
            "policy_configuration",
            "trigger_management",
            "algorithm_calibration"
        ]


# Relationships Agent - Integration with other modules
class ReplenishmentRelationshipsAgent(WMSBaseAgent):
    """Handles replenishment relationships with other WMS modules"""
    
    def __init__(self):
        tools = [ReplenishmentPlanningTool("replenishment", "relationships")]
        super().__init__("replenishment", "relationships", tools)
    
    def _get_specialization(self) -> str:
        return "Replenishment integration with inventory, putaway, picking, and purchasing systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "inventory_coordination",
            "putaway_integration",
            "picking_optimization",
            "purchase_triggering",
            "cross_module_sync",
            "workflow_orchestration"
        ]


# Notes Agent - Best practices and recommendations
class ReplenishmentNotesAgent(WMSBaseAgent):
    """Provides replenishment management best practices and recommendations"""
    
    def __init__(self):
        tools = [ReplenishmentEfficiencyTool("replenishment", "notes")]
        super().__init__("replenishment", "notes", tools)
    
    def _get_specialization(self) -> str:
        return "Replenishment optimization best practices, demand forecasting strategies, and inventory efficiency methods"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "optimization_best_practices",
            "forecasting_strategies",
            "efficiency_improvement",
            "inventory_optimization",
            "performance_benchmarking",
            "continuous_improvement"
        ]