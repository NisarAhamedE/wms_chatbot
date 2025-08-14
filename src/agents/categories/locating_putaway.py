"""
Locating/Putaway management agents (Category 5) - 5 specialized sub-category agents.
Handles all aspects of putaway strategies, location assignment, and storage optimization.
"""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import WMSBaseAgent, WMSBaseTool, WMSContext
from ...database.models import (
    PutawayTask, Location, Item, Inventory, InventoryMovement,
    ReceivingTransaction, WorkAssignment
)


class PutawayStrategyTool(WMSBaseTool):
    """Tool for managing putaway strategies and location assignment"""
    
    name = "putaway_strategy"
    description = "Analyze putaway strategies, location assignments, and storage optimization"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute putaway strategy analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Parse putaway parameters
                putaway_params = self._parse_putaway_query(query)
                
                # Get putaway tasks with location analysis
                strategy_query = """
                SELECT 
                    pt.task_id,
                    pt.item_id,
                    i.item_description,
                    i.item_category,
                    pt.quantity,
                    pt.from_location_id,
                    pt.to_location_id,
                    l.location_type,
                    l.zone_id,
                    l.capacity_qty,
                    pt.putaway_strategy,
                    pt.task_status,
                    pt.priority_level,
                    pt.created_at,
                    pt.assigned_user_id,
                    pt.completed_at,
                    COALESCE(inv.quantity_on_hand, 0) as current_inventory
                FROM putaway_tasks pt
                JOIN items i ON pt.item_id = i.item_id
                LEFT JOIN locations l ON pt.to_location_id = l.location_id
                LEFT JOIN inventory inv ON pt.to_location_id = inv.location_id AND pt.item_id = inv.item_id
                WHERE pt.created_at >= NOW() - INTERVAL '7 days'
                ORDER BY pt.created_at DESC
                LIMIT 100;
                """
                
                result = await session.execute(strategy_query)
                putaway_data = result.fetchall()
                
                if not putaway_data:
                    return "No putaway tasks found in the last 7 days."
                
                response = "📦 **Putaway Strategy Analysis:**\n\n"
                
                # Task statistics
                total_tasks = len(putaway_data)
                pending_tasks = len([t for t in putaway_data if t.task_status == 'PENDING'])
                in_progress_tasks = len([t for t in putaway_data if t.task_status == 'IN_PROGRESS'])
                completed_tasks = len([t for t in putaway_data if t.task_status == 'COMPLETED'])
                
                response += f"📊 **Task Summary:**\n"
                response += f"   Total tasks (7 days): {total_tasks}\n"
                response += f"   Pending: {pending_tasks}\n"
                response += f"   In Progress: {in_progress_tasks}\n"
                response += f"   Completed: {completed_tasks}\n"
                
                if completed_tasks > 0:
                    completion_rate = (completed_tasks / total_tasks) * 100
                    response += f"   Completion rate: {completion_rate:.1f}%\n"
                
                response += "\n"
                
                # Strategy breakdown
                strategies = {}
                for task in putaway_data:
                    strategy = task.putaway_strategy or "DEFAULT"
                    if strategy not in strategies:
                        strategies[strategy] = {"count": 0, "completed": 0, "total_qty": 0}
                    strategies[strategy]["count"] += 1
                    strategies[strategy]["total_qty"] += float(task.quantity)
                    if task.task_status == "COMPLETED":
                        strategies[strategy]["completed"] += 1
                
                response += f"🎯 **Strategy Performance:**\n"
                for strategy, stats in sorted(strategies.items(), key=lambda x: x[1]["count"], reverse=True):
                    completion_pct = (stats["completed"] / stats["count"]) * 100 if stats["count"] > 0 else 0
                    response += f"   {strategy}:\n"
                    response += f"      Tasks: {stats['count']} ({completion_pct:.0f}% completed)\n"
                    response += f"      Total quantity: {stats['total_qty']:,.1f}\n"
                
                # Zone analysis
                zones = {}
                for task in putaway_data:
                    if task.zone_id:
                        zone = task.zone_id
                        if zone not in zones:
                            zones[zone] = {"tasks": 0, "completed": 0, "capacity_used": 0}
                        zones[zone]["tasks"] += 1
                        if task.task_status == "COMPLETED":
                            zones[zone]["completed"] += 1
                            zones[zone]["capacity_used"] += float(task.quantity)
                
                if zones:
                    response += f"\n📍 **Zone Utilization:**\n"
                    for zone, stats in sorted(zones.items(), key=lambda x: x[1]["tasks"], reverse=True):
                        completion_pct = (stats["completed"] / stats["tasks"]) * 100 if stats["tasks"] > 0 else 0
                        response += f"   Zone {zone}: {stats['tasks']} tasks ({completion_pct:.0f}% completed)\n"
                        response += f"      Capacity used: {stats['capacity_used']:,.1f}\n"
                
                # Priority analysis
                high_priority = [t for t in putaway_data if t.priority_level and t.priority_level >= 8]
                overdue_tasks = [
                    t for t in putaway_data 
                    if t.task_status != 'COMPLETED' and 
                       (datetime.utcnow() - t.created_at).total_seconds() > 86400  # 24 hours
                ]
                
                if high_priority:
                    response += f"\n🔴 **High Priority Tasks:** {len(high_priority)}\n"
                    for task in high_priority[:5]:
                        response += f"   {task.task_id}: {task.item_id} (Priority {task.priority_level})\n"
                
                if overdue_tasks:
                    response += f"\n⏰ **Overdue Tasks:** {len(overdue_tasks)}\n"
                    for task in overdue_tasks[:5]:
                        hours_old = (datetime.utcnow() - task.created_at).total_seconds() / 3600
                        response += f"   {task.task_id}: {hours_old:.1f} hours old\n"
                
                # Recommendations
                response += f"\n💡 **Strategy Recommendations:**\n"
                
                # Check for capacity issues
                capacity_issues = [
                    t for t in putaway_data 
                    if t.capacity_qty and t.current_inventory and 
                       (t.current_inventory + t.quantity) > t.capacity_qty
                ]
                
                if capacity_issues:
                    response += f"   • {len(capacity_issues)} tasks may exceed location capacity\n"
                    response += f"   • Review location assignments for optimal space utilization\n"
                
                # Check for velocity-based optimization
                if any(task.putaway_strategy == "DEFAULT" for task in putaway_data):
                    response += f"   • Consider velocity-based putaway for frequently picked items\n"
                
                if pending_tasks > total_tasks * 0.3:  # More than 30% pending
                    response += f"   • High pending task volume - consider workforce optimization\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing putaway strategy: {str(e)}"
    
    def _parse_putaway_query(self, query: str) -> Dict[str, Any]:
        """Parse putaway query parameters"""
        query_lower = query.lower()
        params = {}
        
        import re
        
        # Extract strategy type
        if "fifo" in query_lower:
            params["strategy"] = "FIFO"
        elif "lifo" in query_lower:
            params["strategy"] = "LIFO"
        elif "velocity" in query_lower:
            params["strategy"] = "VELOCITY_BASED"
        elif "random" in query_lower:
            params["strategy"] = "RANDOM"
        
        # Extract status
        if "pending" in query_lower:
            params["status"] = "PENDING"
        elif "completed" in query_lower:
            params["status"] = "COMPLETED"
        elif "progress" in query_lower:
            params["status"] = "IN_PROGRESS"
        
        # Extract priority
        if "high priority" in query_lower or "urgent" in query_lower:
            params["priority"] = "HIGH"
        
        return params


class LocationOptimizationTool(WMSBaseTool):
    """Tool for location optimization and space utilization"""
    
    name = "location_optimization"
    description = "Optimize location assignments and analyze space utilization efficiency"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute location optimization analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get location utilization data
                optimization_query = """
                SELECT 
                    l.location_id,
                    l.zone_id,
                    l.location_type,
                    l.capacity_qty,
                    l.capacity_volume,
                    COALESCE(SUM(inv.quantity_on_hand), 0) as current_quantity,
                    COUNT(DISTINCT inv.item_id) as item_count,
                    COUNT(pt.task_id) as recent_putaway_tasks,
                    COUNT(wa.work_id) as recent_pick_tasks,
                    CASE 
                        WHEN l.capacity_qty > 0 THEN 
                            (COALESCE(SUM(inv.quantity_on_hand), 0) / l.capacity_qty) * 100
                        ELSE 0 
                    END as utilization_pct,
                    MAX(pt.created_at) as last_putaway,
                    MAX(wa.created_at) as last_pick
                FROM locations l
                LEFT JOIN inventory inv ON l.location_id = inv.location_id
                LEFT JOIN putaway_tasks pt ON l.location_id = pt.to_location_id 
                    AND pt.created_at >= NOW() - INTERVAL '30 days'
                LEFT JOIN work_assignments wa ON l.location_id = wa.location_id 
                    AND wa.work_type = 'PICK' 
                    AND wa.created_at >= NOW() - INTERVAL '30 days'
                WHERE l.is_active = true
                GROUP BY l.location_id, l.zone_id, l.location_type, l.capacity_qty, l.capacity_volume
                ORDER BY utilization_pct DESC
                LIMIT 100;
                """
                
                result = await session.execute(optimization_query)
                location_data = result.fetchall()
                
                if not location_data:
                    return "No location optimization data available."
                
                response = "🎯 **Location Optimization Analysis:**\n\n"
                
                # Utilization categories
                over_utilized = [loc for loc in location_data if loc.utilization_pct > 95]
                under_utilized = [loc for loc in location_data if loc.utilization_pct < 20 and loc.utilization_pct > 0]
                empty_locations = [loc for loc in location_data if loc.utilization_pct == 0]
                optimal_range = [loc for loc in location_data if 70 <= loc.utilization_pct <= 95]
                
                response += f"📊 **Utilization Summary:**\n"
                response += f"   Total locations: {len(location_data)}\n"
                response += f"   Over-utilized (>95%): {len(over_utilized)}\n"
                response += f"   Optimal range (70-95%): {len(optimal_range)}\n"
                response += f"   Under-utilized (<20%): {len(under_utilized)}\n"
                response += f"   Empty locations: {len(empty_locations)}\n\n"
                
                # Over-utilized locations (capacity issues)
                if over_utilized:
                    response += f"🔴 **Over-Utilized Locations (>95%):**\n"
                    for loc in over_utilized[:10]:
                        response += f"   {loc.location_id} ({loc.zone_id}): {loc.utilization_pct:.1f}%\n"
                        response += f"      Current: {loc.current_quantity}/{loc.capacity_qty}\n"
                        response += f"      Items: {loc.item_count}, Recent putaways: {loc.recent_putaway_tasks}\n"
                    response += "\n"
                
                # Under-utilized locations (opportunity)
                if under_utilized:
                    response += f"🟡 **Under-Utilized Locations (<20%):**\n"
                    for loc in under_utilized[:10]:
                        response += f"   {loc.location_id} ({loc.zone_id}): {loc.utilization_pct:.1f}%\n"
                        response += f"      Capacity available: {loc.capacity_qty - loc.current_quantity:.0f}\n"
                        response += f"      Recent activity: {loc.recent_putaway_tasks + loc.recent_pick_tasks} tasks\n"
                    response += "\n"
                
                # Zone-level analysis
                zone_stats = {}
                for loc in location_data:
                    zone = loc.zone_id
                    if zone not in zone_stats:
                        zone_stats[zone] = {
                            "locations": 0, "total_capacity": 0, "used_capacity": 0,
                            "putaway_tasks": 0, "pick_tasks": 0
                        }
                    zone_stats[zone]["locations"] += 1
                    zone_stats[zone]["total_capacity"] += loc.capacity_qty or 0
                    zone_stats[zone]["used_capacity"] += loc.current_quantity or 0
                    zone_stats[zone]["putaway_tasks"] += loc.recent_putaway_tasks or 0
                    zone_stats[zone]["pick_tasks"] += loc.recent_pick_tasks or 0
                
                response += f"📍 **Zone Performance:**\n"
                for zone, stats in sorted(zone_stats.items(), key=lambda x: x[1]["used_capacity"], reverse=True):
                    if stats["total_capacity"] > 0:
                        zone_utilization = (stats["used_capacity"] / stats["total_capacity"]) * 100
                        response += f"   Zone {zone}:\n"
                        response += f"      Utilization: {zone_utilization:.1f}%\n"
                        response += f"      Locations: {stats['locations']}\n"
                        response += f"      Activity: {stats['putaway_tasks']} putaways, {stats['pick_tasks']} picks\n"
                
                # Velocity-based recommendations
                high_activity_locations = [
                    loc for loc in location_data 
                    if (loc.recent_pick_tasks or 0) > 10  # More than 10 picks in 30 days
                ]
                
                low_activity_locations = [
                    loc for loc in location_data 
                    if (loc.recent_pick_tasks or 0) == 0 and loc.current_quantity > 0
                ]
                
                response += f"\n🔄 **Activity Analysis:**\n"
                response += f"   High activity locations: {len(high_activity_locations)}\n"
                response += f"   Slow-moving inventory locations: {len(low_activity_locations)}\n\n"
                
                # Optimization recommendations
                response += f"💡 **Optimization Recommendations:**\n"
                
                if over_utilized:
                    response += f"   • {len(over_utilized)} locations need capacity expansion or redistribution\n"
                
                if under_utilized:
                    response += f"   • {len(under_utilized)} locations available for consolidation\n"
                
                if high_activity_locations:
                    response += f"   • Move {len(high_activity_locations)} high-velocity items to easily accessible locations\n"
                
                if low_activity_locations:
                    response += f"   • Consider moving {len(low_activity_locations)} slow-moving items to reserve areas\n"
                
                # Calculate potential space savings
                total_under_used_capacity = sum(
                    (loc.capacity_qty or 0) - (loc.current_quantity or 0) 
                    for loc in under_utilized
                )
                
                if total_under_used_capacity > 0:
                    response += f"   • Potential space savings: {total_under_used_capacity:,.0f} units through consolidation\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing location optimization: {str(e)}"


class PutawayPerformanceTool(WMSBaseTool):
    """Tool for putaway performance analysis and metrics"""
    
    name = "putaway_performance"
    description = "Analyze putaway performance, completion times, and productivity metrics"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute performance analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get putaway performance data
                performance_query = """
                SELECT 
                    pt.assigned_user_id,
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN pt.task_status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_tasks,
                    AVG(CASE 
                        WHEN pt.completed_at IS NOT NULL AND pt.started_at IS NOT NULL THEN 
                            EXTRACT(EPOCH FROM (pt.completed_at - pt.started_at)) / 60
                        ELSE NULL 
                    END) as avg_completion_time_minutes,
                    SUM(pt.quantity) as total_quantity,
                    COUNT(DISTINCT pt.item_id) as unique_items,
                    COUNT(DISTINCT DATE(pt.created_at)) as active_days,
                    MIN(pt.created_at) as first_task,
                    MAX(pt.completed_at) as last_completed
                FROM putaway_tasks pt
                WHERE pt.created_at >= NOW() - INTERVAL '30 days'
                    AND pt.assigned_user_id IS NOT NULL
                GROUP BY pt.assigned_user_id
                ORDER BY completed_tasks DESC
                LIMIT 20;
                """
                
                result = await session.execute(performance_query)
                performance_data = result.fetchall()
                
                if not performance_data:
                    return "No putaway performance data available for the last 30 days."
                
                response = "📈 **Putaway Performance Analysis (Last 30 days):**\n\n"
                
                # Overall metrics
                total_users = len(performance_data)
                total_tasks = sum(user.total_tasks for user in performance_data)
                total_completed = sum(user.completed_tasks for user in performance_data)
                total_quantity = sum(float(user.total_quantity) for user in performance_data)
                
                overall_completion_rate = (total_completed / total_tasks) * 100 if total_tasks > 0 else 0
                avg_completion_time = sum(
                    float(user.avg_completion_time_minutes or 0) for user in performance_data
                ) / len([u for u in performance_data if u.avg_completion_time_minutes])
                
                response += f"🎯 **Overall Performance:**\n"
                response += f"   Active users: {total_users}\n"
                response += f"   Total tasks: {total_tasks:,}\n"
                response += f"   Completed: {total_completed:,} ({overall_completion_rate:.1f}%)\n"
                response += f"   Total quantity: {total_quantity:,.1f}\n"
                response += f"   Average completion time: {avg_completion_time:.1f} minutes\n\n"
                
                # Top performers
                top_performers = sorted(performance_data, key=lambda x: x.completed_tasks, reverse=True)[:5]
                response += f"🏆 **Top Performers (by tasks completed):**\n"
                for i, user in enumerate(top_performers, 1):
                    completion_rate = (user.completed_tasks / user.total_tasks) * 100 if user.total_tasks > 0 else 0
                    daily_avg = user.completed_tasks / user.active_days if user.active_days > 0 else 0
                    
                    response += f"   {i}. User {user.assigned_user_id}:\n"
                    response += f"      Completed: {user.completed_tasks}/{user.total_tasks} ({completion_rate:.0f}%)\n"
                    response += f"      Daily average: {daily_avg:.1f} tasks\n"
                    response += f"      Quantity handled: {user.total_quantity:,.1f}\n"
                    if user.avg_completion_time_minutes:
                        response += f"      Avg time per task: {user.avg_completion_time_minutes:.1f} min\n"
                
                # Performance insights
                fastest_users = [
                    user for user in performance_data 
                    if user.avg_completion_time_minutes and user.avg_completion_time_minutes < avg_completion_time * 0.8
                ]
                
                slowest_users = [
                    user for user in performance_data 
                    if user.avg_completion_time_minutes and user.avg_completion_time_minutes > avg_completion_time * 1.2
                ]
                
                response += f"\n⚡ **Performance Insights:**\n"
                if fastest_users:
                    response += f"   Fast performers: {len(fastest_users)} users averaging <{avg_completion_time * 0.8:.1f} min/task\n"
                
                if slowest_users:
                    response += f"   Slower performers: {len(slowest_users)} users averaging >{avg_completion_time * 1.2:.1f} min/task\n"
                
                # Productivity trends
                high_volume_users = [user for user in performance_data if user.completed_tasks > total_completed / total_users * 1.5]
                consistent_users = [user for user in performance_data if user.active_days >= 20]  # 20+ days active
                
                response += f"   High volume users: {len(high_volume_users)} (>150% of average)\n"
                response += f"   Consistent workers: {len(consistent_users)} (20+ active days)\n"
                
                # Time analysis
                if performance_data:
                    completion_times = [
                        user.avg_completion_time_minutes for user in performance_data 
                        if user.avg_completion_time_minutes
                    ]
                    
                    if completion_times:
                        min_time = min(completion_times)
                        max_time = max(completion_times)
                        median_time = sorted(completion_times)[len(completion_times)//2]
                        
                        response += f"\n⏱️ **Time Analysis:**\n"
                        response += f"   Fastest completion: {min_time:.1f} minutes\n"
                        response += f"   Slowest completion: {max_time:.1f} minutes\n"
                        response += f"   Median time: {median_time:.1f} minutes\n"
                        response += f"   Time variation: {max_time - min_time:.1f} minutes\n"
                
                # Recommendations
                response += f"\n💡 **Performance Recommendations:**\n"
                
                if overall_completion_rate < 90:
                    response += f"   • Overall completion rate is {overall_completion_rate:.1f}% - investigate incomplete tasks\n"
                
                if slowest_users:
                    response += f"   • Provide additional training for {len(slowest_users)} slower performers\n"
                
                if fastest_users:
                    response += f"   • Share best practices from {len(fastest_users)} top performers\n"
                
                if len(completion_times) > 1 and (max(completion_times) - min(completion_times)) > avg_completion_time:
                    response += f"   • High time variation suggests process standardization opportunities\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing putaway performance: {str(e)}"


# Functional Agent - Business processes and workflows
class LocatingPutawayFunctionalAgent(WMSBaseAgent):
    """Handles functional aspects of locating and putaway management"""
    
    def __init__(self):
        tools = [
            PutawayStrategyTool("locating_putaway", "functional"),
            LocationOptimizationTool("locating_putaway", "functional"),
            PutawayPerformanceTool("locating_putaway", "functional")
        ]
        super().__init__("locating_putaway", "functional", tools)
    
    def _get_specialization(self) -> str:
        return "Putaway strategy execution, location assignment workflows, and storage optimization processes"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "putaway_strategy_execution",
            "location_assignment",
            "storage_optimization",
            "capacity_management",
            "velocity_analysis",
            "workflow_coordination"
        ]


# Technical Agent - System specifications
class LocatingPutawayTechnicalAgent(WMSBaseAgent):
    """Handles technical aspects of locating and putaway management"""
    
    def __init__(self):
        tools = [PutawayStrategyTool("locating_putaway", "technical")]
        super().__init__("locating_putaway", "technical", tools)
    
    def _get_specialization(self) -> str:
        return "Putaway algorithms, location optimization engines, and automated assignment systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "algorithm_optimization",
            "automated_assignment",
            "system_integration",
            "real_time_processing",
            "performance_monitoring",
            "api_development"
        ]


# Configuration Agent - Setup and parameters
class LocatingPutawayConfigurationAgent(WMSBaseAgent):
    """Handles locating and putaway configuration"""
    
    def __init__(self):
        tools = [LocationOptimizationTool("locating_putaway", "configuration")]
        super().__init__("locating_putaway", "configuration", tools)
    
    def _get_specialization(self) -> str:
        return "Putaway strategy configuration, location rules setup, and optimization parameter tuning"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "strategy_configuration",
            "rule_definition",
            "parameter_tuning",
            "policy_setup",
            "constraint_management",
            "workflow_configuration"
        ]


# Relationships Agent - Integration with other modules
class LocatingPutawayRelationshipsAgent(WMSBaseAgent):
    """Handles locating/putaway relationships with other WMS modules"""
    
    def __init__(self):
        tools = [PutawayStrategyTool("locating_putaway", "relationships")]
        super().__init__("locating_putaway", "relationships", tools)
    
    def _get_specialization(self) -> str:
        return "Putaway integration with receiving, inventory, picking, and labor management systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "receiving_integration",
            "inventory_coordination",
            "picking_optimization",
            "labor_planning",
            "cross_module_workflows",
            "system_synchronization"
        ]


# Notes Agent - Best practices and recommendations
class LocatingPutawayNotesAgent(WMSBaseAgent):
    """Provides locating and putaway best practices and recommendations"""
    
    def __init__(self):
        tools = [PutawayPerformanceTool("locating_putaway", "notes")]
        super().__init__("locating_putaway", "notes", tools)
    
    def _get_specialization(self) -> str:
        return "Putaway efficiency best practices, storage optimization strategies, and performance improvement methods"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "efficiency_best_practices",
            "optimization_strategies",
            "performance_improvement",
            "training_guidelines",
            "process_standardization",
            "continuous_improvement"
        ]