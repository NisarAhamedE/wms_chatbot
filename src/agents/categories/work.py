"""
Work management agents (Category 6) - 5 specialized sub-category agents.
Handles all aspects of work assignment, labor management, task tracking, and productivity optimization.
"""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import WMSBaseAgent, WMSBaseTool, WMSContext
from ...database.models import WorkAssignment, User, Location, Item, Inventory


class WorkAssignmentTool(WMSBaseTool):
    """Tool for managing work assignments and task allocation"""
    
    name = "work_assignment"
    description = "Manage work assignments, task allocation, and workforce distribution"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute work assignment analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Parse work parameters
                work_params = self._parse_work_query(query)
                
                # Get work assignments with user and performance data
                assignment_query = """
                SELECT 
                    wa.work_id,
                    wa.work_type,
                    wa.assigned_user_id,
                    u.full_name,
                    wa.item_id,
                    i.item_description,
                    wa.location_id,
                    wa.quantity,
                    wa.work_status,
                    wa.priority_level,
                    wa.created_at,
                    wa.started_at,
                    wa.completed_at,
                    wa.estimated_duration,
                    wa.actual_duration,
                    CASE 
                        WHEN wa.completed_at IS NOT NULL AND wa.started_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (wa.completed_at - wa.started_at)) / 60
                        ELSE NULL
                    END as actual_duration_minutes
                FROM work_assignments wa
                LEFT JOIN users u ON wa.assigned_user_id = u.user_id
                LEFT JOIN items i ON wa.item_id = i.item_id
                WHERE wa.created_at >= NOW() - INTERVAL '7 days'
                ORDER BY wa.created_at DESC
                LIMIT 200;
                """
                
                result = await session.execute(assignment_query)
                work_data = result.fetchall()
                
                if not work_data:
                    return "No work assignments found in the last 7 days."
                
                response = "👷 **Work Assignment Analysis (Last 7 days):**\n\n"
                
                # Overall statistics
                total_tasks = len(work_data)
                pending_tasks = len([w for w in work_data if w.work_status == 'PENDING'])
                in_progress_tasks = len([w for w in work_data if w.work_status == 'IN_PROGRESS'])
                completed_tasks = len([w for w in work_data if w.work_status == 'COMPLETED'])
                cancelled_tasks = len([w for w in work_data if w.work_status == 'CANCELLED'])
                
                response += f"📊 **Overall Statistics:**\n"
                response += f"   Total work assignments: {total_tasks}\n"
                response += f"   Pending: {pending_tasks} ({pending_tasks/total_tasks*100:.1f}%)\n"
                response += f"   In Progress: {in_progress_tasks} ({in_progress_tasks/total_tasks*100:.1f}%)\n"
                response += f"   Completed: {completed_tasks} ({completed_tasks/total_tasks*100:.1f}%)\n"
                response += f"   Cancelled: {cancelled_tasks} ({cancelled_tasks/total_tasks*100:.1f}%)\n\n"
                
                # Work type breakdown
                work_types = {}
                for work in work_data:
                    wtype = work.work_type
                    if wtype not in work_types:
                        work_types[wtype] = {"total": 0, "completed": 0, "pending": 0, "total_qty": 0}
                    work_types[wtype]["total"] += 1
                    work_types[wtype]["total_qty"] += float(work.quantity or 0)
                    if work.work_status == "COMPLETED":
                        work_types[wtype]["completed"] += 1
                    elif work.work_status == "PENDING":
                        work_types[wtype]["pending"] += 1
                
                response += f"📋 **Work Type Breakdown:**\n"
                for wtype, stats in sorted(work_types.items(), key=lambda x: x[1]["total"], reverse=True):
                    completion_rate = (stats["completed"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                    response += f"   {wtype}:\n"
                    response += f"      Total: {stats['total']} ({completion_rate:.1f}% completed)\n"
                    response += f"      Pending: {stats['pending']}\n"
                    response += f"      Total quantity: {stats['total_qty']:,.1f}\n"
                
                # User performance analysis
                user_stats = {}
                for work in work_data:
                    if work.assigned_user_id:
                        user_id = work.assigned_user_id
                        user_name = work.full_name or f"User {user_id}"
                        
                        if user_id not in user_stats:
                            user_stats[user_id] = {
                                "name": user_name,
                                "total": 0, "completed": 0, "pending": 0,
                                "total_duration": 0, "duration_count": 0,
                                "work_types": set()
                            }
                        
                        user_stats[user_id]["total"] += 1
                        user_stats[user_id]["work_types"].add(work.work_type)
                        
                        if work.work_status == "COMPLETED":
                            user_stats[user_id]["completed"] += 1
                            if work.actual_duration_minutes:
                                user_stats[user_id]["total_duration"] += work.actual_duration_minutes
                                user_stats[user_id]["duration_count"] += 1
                        elif work.work_status == "PENDING":
                            user_stats[user_id]["pending"] += 1
                
                # Top performers
                top_users = sorted(
                    user_stats.items(), 
                    key=lambda x: x[1]["completed"], 
                    reverse=True
                )[:5]
                
                response += f"\n🏆 **Top Performers (by completed tasks):**\n"
                for user_id, stats in top_users:
                    completion_rate = (stats["completed"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                    avg_duration = stats["total_duration"] / stats["duration_count"] if stats["duration_count"] > 0 else 0
                    
                    response += f"   {stats['name']}:\n"
                    response += f"      Completed: {stats['completed']}/{stats['total']} ({completion_rate:.0f}%)\n"
                    response += f"      Pending: {stats['pending']}\n"
                    response += f"      Work types: {len(stats['work_types'])}\n"
                    if avg_duration > 0:
                        response += f"      Avg duration: {avg_duration:.1f} minutes\n"
                
                # Priority analysis
                high_priority = [w for w in work_data if w.priority_level and w.priority_level >= 8]
                overdue_tasks = []
                
                current_time = datetime.utcnow()
                for work in work_data:
                    if work.work_status in ['PENDING', 'IN_PROGRESS']:
                        # Consider overdue if created more than 4 hours ago for high priority, 24 hours for normal
                        threshold_hours = 4 if (work.priority_level and work.priority_level >= 8) else 24
                        if (current_time - work.created_at).total_seconds() > threshold_hours * 3600:
                            overdue_tasks.append(work)
                
                if high_priority:
                    response += f"\n🔴 **High Priority Tasks:** {len(high_priority)}\n"
                    high_priority_pending = [w for w in high_priority if w.work_status == 'PENDING']
                    if high_priority_pending:
                        response += f"   Pending high priority: {len(high_priority_pending)}\n"
                        for work in high_priority_pending[:3]:
                            response += f"      {work.work_id}: {work.work_type} - Priority {work.priority_level}\n"
                
                if overdue_tasks:
                    response += f"\n⏰ **Overdue Tasks:** {len(overdue_tasks)}\n"
                    for work in overdue_tasks[:5]:
                        hours_overdue = (current_time - work.created_at).total_seconds() / 3600
                        response += f"   {work.work_id}: {work.work_type} ({hours_overdue:.1f}h overdue)\n"
                
                # Performance insights
                completed_with_duration = [w for w in work_data if w.actual_duration_minutes]
                if completed_with_duration:
                    avg_task_duration = sum(w.actual_duration_minutes for w in completed_with_duration) / len(completed_with_duration)
                    fast_tasks = len([w for w in completed_with_duration if w.actual_duration_minutes < avg_task_duration * 0.5])
                    slow_tasks = len([w for w in completed_with_duration if w.actual_duration_minutes > avg_task_duration * 2])
                    
                    response += f"\n⏱️ **Performance Insights:**\n"
                    response += f"   Average task duration: {avg_task_duration:.1f} minutes\n"
                    response += f"   Fast completions (<50% avg): {fast_tasks}\n"
                    response += f"   Slow completions (>200% avg): {slow_tasks}\n"
                
                # Recommendations
                response += f"\n💡 **Recommendations:**\n"
                
                if pending_tasks > total_tasks * 0.4:  # More than 40% pending
                    response += f"   • High pending task volume ({pending_tasks}) - consider workforce optimization\n"
                
                if overdue_tasks:
                    response += f"   • {len(overdue_tasks)} overdue tasks require immediate attention\n"
                
                if high_priority:
                    response += f"   • Prioritize {len([w for w in high_priority if w.work_status != 'COMPLETED'])} incomplete high-priority tasks\n"
                
                # Check for workload balance
                if user_stats:
                    max_tasks = max(stats["total"] for stats in user_stats.values())
                    min_tasks = min(stats["total"] for stats in user_stats.values())
                    if max_tasks > min_tasks * 2:  # Imbalanced if 2x difference
                        response += f"   • Workload imbalance detected - consider task redistribution\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing work assignments: {str(e)}"
    
    def _parse_work_query(self, query: str) -> Dict[str, Any]:
        """Parse work query parameters"""
        query_lower = query.lower()
        params = {}
        
        import re
        
        # Extract work type
        work_types = ["pick", "putaway", "move", "count", "pack", "load", "unload"]
        for wtype in work_types:
            if wtype in query_lower:
                params["work_type"] = wtype.upper()
                break
        
        # Extract status
        if "pending" in query_lower:
            params["status"] = "PENDING"
        elif "completed" in query_lower:
            params["status"] = "COMPLETED"
        elif "progress" in query_lower or "active" in query_lower:
            params["status"] = "IN_PROGRESS"
        
        # Extract user
        user_pattern = r'user[:\s]+([a-zA-Z0-9_]+)'
        user_match = re.search(user_pattern, query_lower)
        if user_match:
            params["user_id"] = user_match.group(1)
        
        # Extract priority
        if "high priority" in query_lower or "urgent" in query_lower:
            params["priority"] = "HIGH"
        
        return params


class LaborProductivityTool(WMSBaseTool):
    """Tool for analyzing labor productivity and performance metrics"""
    
    name = "labor_productivity"
    description = "Analyze workforce productivity, efficiency metrics, and performance trends"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute productivity analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get labor productivity metrics
                productivity_query = """
                SELECT 
                    wa.assigned_user_id,
                    u.full_name,
                    DATE(wa.created_at) as work_date,
                    wa.work_type,
                    COUNT(*) as tasks_assigned,
                    SUM(CASE WHEN wa.work_status = 'COMPLETED' THEN 1 ELSE 0 END) as tasks_completed,
                    SUM(wa.quantity) as total_quantity,
                    AVG(CASE 
                        WHEN wa.completed_at IS NOT NULL AND wa.started_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (wa.completed_at - wa.started_at)) / 60
                        ELSE NULL
                    END) as avg_duration_minutes,
                    SUM(CASE 
                        WHEN wa.completed_at IS NOT NULL AND wa.started_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (wa.completed_at - wa.started_at)) / 60
                        ELSE 0
                    END) as total_work_minutes,
                    MIN(wa.started_at) as first_start,
                    MAX(wa.completed_at) as last_completion
                FROM work_assignments wa
                LEFT JOIN users u ON wa.assigned_user_id = u.user_id
                WHERE wa.created_at >= NOW() - INTERVAL '14 days'
                    AND wa.assigned_user_id IS NOT NULL
                GROUP BY wa.assigned_user_id, u.full_name, DATE(wa.created_at), wa.work_type
                ORDER BY work_date DESC, tasks_completed DESC
                LIMIT 100;
                """
                
                result = await session.execute(productivity_query)
                productivity_data = result.fetchall()
                
                if not productivity_data:
                    return "No labor productivity data available for the last 14 days."
                
                response = "📊 **Labor Productivity Analysis (Last 14 days):**\n\n"
                
                # Aggregate user performance
                user_performance = {}
                for record in productivity_data:
                    user_id = record.assigned_user_id
                    user_name = record.full_name or f"User {user_id}"
                    
                    if user_id not in user_performance:
                        user_performance[user_id] = {
                            "name": user_name,
                            "total_tasks": 0,
                            "total_completed": 0,
                            "total_quantity": 0,
                            "total_work_time": 0,
                            "work_days": set(),
                            "work_types": set()
                        }
                    
                    user_performance[user_id]["total_tasks"] += record.tasks_assigned
                    user_performance[user_id]["total_completed"] += record.tasks_completed
                    user_performance[user_id]["total_quantity"] += float(record.total_quantity or 0)
                    user_performance[user_id]["total_work_time"] += float(record.total_work_minutes or 0)
                    user_performance[user_id]["work_days"].add(record.work_date)
                    user_performance[user_id]["work_types"].add(record.work_type)
                
                # Calculate key metrics
                total_users = len(user_performance)
                total_tasks = sum(user["total_tasks"] for user in user_performance.values())
                total_completed = sum(user["total_completed"] for user in user_performance.values())
                total_quantity = sum(user["total_quantity"] for user in user_performance.values())
                total_work_time = sum(user["total_work_time"] for user in user_performance.values())
                
                overall_completion_rate = (total_completed / total_tasks) * 100 if total_tasks > 0 else 0
                avg_productivity = total_quantity / (total_work_time / 60) if total_work_time > 0 else 0  # units per hour
                
                response += f"🎯 **Overall Metrics:**\n"
                response += f"   Active workers: {total_users}\n"
                response += f"   Total tasks assigned: {total_tasks:,}\n"
                response += f"   Tasks completed: {total_completed:,} ({overall_completion_rate:.1f}%)\n"
                response += f"   Total quantity processed: {total_quantity:,.1f}\n"
                response += f"   Total work time: {total_work_time/60:.1f} hours\n"
                response += f"   Average productivity: {avg_productivity:.1f} units/hour\n\n"
                
                # Top performers by different metrics
                # By completion rate
                users_by_completion = sorted(
                    user_performance.items(),
                    key=lambda x: x[1]["total_completed"] / x[1]["total_tasks"] if x[1]["total_tasks"] > 0 else 0,
                    reverse=True
                )[:5]
                
                response += f"🏆 **Top Performers (by completion rate):**\n"
                for user_id, stats in users_by_completion:
                    if stats["total_tasks"] > 0:
                        completion_rate = (stats["total_completed"] / stats["total_tasks"]) * 100
                        daily_avg = stats["total_completed"] / len(stats["work_days"]) if stats["work_days"] else 0
                        hourly_productivity = stats["total_quantity"] / (stats["total_work_time"] / 60) if stats["total_work_time"] > 0 else 0
                        
                        response += f"   {stats['name']}:\n"
                        response += f"      Completion rate: {completion_rate:.1f}%\n"
                        response += f"      Daily average: {daily_avg:.1f} tasks\n"
                        response += f"      Productivity: {hourly_productivity:.1f} units/hour\n"
                        response += f"      Work types: {len(stats['work_types'])}\n"
                
                # Work type productivity analysis
                work_type_stats = {}
                for record in productivity_data:
                    wtype = record.work_type
                    if wtype not in work_type_stats:
                        work_type_stats[wtype] = {
                            "total_tasks": 0, "completed_tasks": 0,
                            "total_quantity": 0, "total_time": 0, "workers": set()
                        }
                    
                    work_type_stats[wtype]["total_tasks"] += record.tasks_assigned
                    work_type_stats[wtype]["completed_tasks"] += record.tasks_completed
                    work_type_stats[wtype]["total_quantity"] += float(record.total_quantity or 0)
                    work_type_stats[wtype]["total_time"] += float(record.total_work_minutes or 0)
                    work_type_stats[wtype]["workers"].add(record.assigned_user_id)
                
                response += f"\n📋 **Productivity by Work Type:**\n"
                for wtype, stats in sorted(work_type_stats.items(), key=lambda x: x[1]["completed_tasks"], reverse=True):
                    completion_rate = (stats["completed_tasks"] / stats["total_tasks"]) * 100 if stats["total_tasks"] > 0 else 0
                    avg_time_per_task = stats["total_time"] / stats["completed_tasks"] if stats["completed_tasks"] > 0 else 0
                    productivity = stats["total_quantity"] / (stats["total_time"] / 60) if stats["total_time"] > 0 else 0
                    
                    response += f"   {wtype}:\n"
                    response += f"      Workers: {len(stats['workers'])}\n"
                    response += f"      Completion rate: {completion_rate:.1f}%\n"
                    response += f"      Avg time per task: {avg_time_per_task:.1f} minutes\n"
                    response += f"      Productivity: {productivity:.1f} units/hour\n"
                
                # Identify performance patterns
                high_performers = [
                    user_id for user_id, stats in user_performance.items()
                    if stats["total_tasks"] > 0 and (stats["total_completed"] / stats["total_tasks"]) > 0.9
                ]
                
                low_performers = [
                    user_id for user_id, stats in user_performance.items()
                    if stats["total_tasks"] > 0 and (stats["total_completed"] / stats["total_tasks"]) < 0.7
                ]
                
                versatile_workers = [
                    user_id for user_id, stats in user_performance.items()
                    if len(stats["work_types"]) >= 3
                ]
                
                response += f"\n📈 **Performance Insights:**\n"
                response += f"   High performers (>90% completion): {len(high_performers)}\n"
                response += f"   Low performers (<70% completion): {len(low_performers)}\n"
                response += f"   Versatile workers (3+ work types): {len(versatile_workers)}\n"
                
                # Daily productivity trends
                daily_totals = {}
                for record in productivity_data:
                    date = record.work_date
                    if date not in daily_totals:
                        daily_totals[date] = {"tasks": 0, "completed": 0, "workers": set()}
                    daily_totals[date]["tasks"] += record.tasks_assigned
                    daily_totals[date]["completed"] += record.tasks_completed
                    daily_totals[date]["workers"].add(record.assigned_user_id)
                
                if len(daily_totals) >= 2:
                    sorted_days = sorted(daily_totals.items(), key=lambda x: x[0], reverse=True)
                    response += f"\n📅 **Recent Daily Performance:**\n"
                    
                    for date, stats in sorted_days[:5]:
                        completion_rate = (stats["completed"] / stats["tasks"]) * 100 if stats["tasks"] > 0 else 0
                        response += f"   {date.strftime('%Y-%m-%d')}: {stats['completed']}/{stats['tasks']} tasks ({completion_rate:.0f}%), {len(stats['workers'])} workers\n"
                
                # Recommendations
                response += f"\n💡 **Productivity Recommendations:**\n"
                
                if overall_completion_rate < 85:
                    response += f"   • Overall completion rate is {overall_completion_rate:.1f}% - investigate workflow bottlenecks\n"
                
                if low_performers:
                    response += f"   • Provide additional training/support for {len(low_performers)} underperforming workers\n"
                
                if high_performers:
                    response += f"   • Leverage expertise of {len(high_performers)} top performers for mentoring\n"
                
                # Check for workload distribution
                task_counts = [stats["total_tasks"] for stats in user_performance.values()]
                if task_counts:
                    max_tasks = max(task_counts)
                    min_tasks = min(task_counts)
                    if max_tasks > min_tasks * 2 and min_tasks > 0:
                        response += f"   • Workload imbalance detected - consider redistributing tasks\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing labor productivity: {str(e)}"


class TaskEfficiencyTool(WMSBaseTool):
    """Tool for analyzing task efficiency and process optimization"""
    
    name = "task_efficiency"
    description = "Analyze task efficiency, cycle times, and process optimization opportunities"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute efficiency analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get task efficiency metrics
                efficiency_query = """
                SELECT 
                    wa.work_type,
                    wa.location_id,
                    l.zone_id,
                    wa.item_id,
                    i.item_category,
                    wa.quantity,
                    wa.estimated_duration,
                    CASE 
                        WHEN wa.completed_at IS NOT NULL AND wa.started_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (wa.completed_at - wa.started_at)) / 60
                        ELSE NULL
                    END as actual_duration_minutes,
                    CASE 
                        WHEN wa.estimated_duration IS NOT NULL AND wa.completed_at IS NOT NULL AND wa.started_at IS NOT NULL THEN
                            (EXTRACT(EPOCH FROM (wa.completed_at - wa.started_at)) / 60) / wa.estimated_duration
                        ELSE NULL
                    END as efficiency_ratio,
                    wa.created_at,
                    wa.priority_level
                FROM work_assignments wa
                LEFT JOIN locations l ON wa.location_id = l.location_id
                LEFT JOIN items i ON wa.item_id = i.item_id
                WHERE wa.work_status = 'COMPLETED'
                    AND wa.created_at >= NOW() - INTERVAL '30 days'
                    AND wa.started_at IS NOT NULL
                    AND wa.completed_at IS NOT NULL
                ORDER BY wa.completed_at DESC
                LIMIT 500;
                """
                
                result = await session.execute(efficiency_query)
                efficiency_data = result.fetchall()
                
                if not efficiency_data:
                    return "No completed task efficiency data available for the last 30 days."
                
                response = "⚡ **Task Efficiency Analysis (Last 30 days):**\n\n"
                
                # Overall efficiency metrics
                tasks_with_duration = [task for task in efficiency_data if task.actual_duration_minutes]
                tasks_with_estimates = [task for task in efficiency_data if task.efficiency_ratio]
                
                if not tasks_with_duration:
                    return "No tasks with duration data found."
                
                avg_duration = sum(task.actual_duration_minutes for task in tasks_with_duration) / len(tasks_with_duration)
                median_duration = sorted([task.actual_duration_minutes for task in tasks_with_duration])[len(tasks_with_duration)//2]
                
                response += f"⏱️ **Duration Analysis:**\n"
                response += f"   Tasks analyzed: {len(tasks_with_duration)}\n"
                response += f"   Average duration: {avg_duration:.1f} minutes\n"
                response += f"   Median duration: {median_duration:.1f} minutes\n"
                
                if tasks_with_estimates:
                    avg_efficiency = sum(task.efficiency_ratio for task in tasks_with_estimates) / len(tasks_with_estimates)
                    on_time_tasks = len([task for task in tasks_with_estimates if task.efficiency_ratio <= 1.1])  # Within 10%
                    early_tasks = len([task for task in tasks_with_estimates if task.efficiency_ratio < 0.9])  # 10%+ faster
                    late_tasks = len([task for task in tasks_with_estimates if task.efficiency_ratio > 1.1])  # 10%+ slower
                    
                    response += f"   Tasks with estimates: {len(tasks_with_estimates)}\n"
                    response += f"   Average efficiency ratio: {avg_efficiency:.2f}\n"
                    response += f"   On-time tasks (±10%): {on_time_tasks} ({on_time_tasks/len(tasks_with_estimates)*100:.1f}%)\n"
                    response += f"   Early completions: {early_tasks} ({early_tasks/len(tasks_with_estimates)*100:.1f}%)\n"
                    response += f"   Late completions: {late_tasks} ({late_tasks/len(tasks_with_estimates)*100:.1f}%)\n"
                
                response += "\n"
                
                # Work type efficiency analysis
                work_type_efficiency = {}
                for task in efficiency_data:
                    wtype = task.work_type
                    if wtype not in work_type_efficiency:
                        work_type_efficiency[wtype] = {
                            "durations": [], "efficiencies": [], "quantities": []
                        }
                    
                    if task.actual_duration_minutes:
                        work_type_efficiency[wtype]["durations"].append(task.actual_duration_minutes)
                    if task.efficiency_ratio:
                        work_type_efficiency[wtype]["efficiencies"].append(task.efficiency_ratio)
                    if task.quantity:
                        work_type_efficiency[wtype]["quantities"].append(float(task.quantity))
                
                response += f"📊 **Efficiency by Work Type:**\n"
                for wtype, data in sorted(work_type_efficiency.items(), key=lambda x: len(x[1]["durations"]), reverse=True):
                    if data["durations"]:
                        avg_duration = sum(data["durations"]) / len(data["durations"])
                        avg_quantity = sum(data["quantities"]) / len(data["quantities"]) if data["quantities"] else 0
                        
                        response += f"   {wtype}:\n"
                        response += f"      Tasks: {len(data['durations'])}\n"
                        response += f"      Avg duration: {avg_duration:.1f} minutes\n"
                        response += f"      Avg quantity: {avg_quantity:.1f}\n"
                        
                        if data["efficiencies"]:
                            avg_efficiency = sum(data["efficiencies"]) / len(data["efficiencies"])
                            response += f"      Avg efficiency ratio: {avg_efficiency:.2f}\n"
                            
                            if avg_efficiency > 1.2:
                                response += f"      ⚠️ Consistently over estimate\n"
                            elif avg_efficiency < 0.8:
                                response += f"      ✅ Consistently under estimate\n"
                
                # Zone efficiency analysis
                zone_efficiency = {}
                for task in efficiency_data:
                    if task.zone_id and task.actual_duration_minutes:
                        zone = task.zone_id
                        if zone not in zone_efficiency:
                            zone_efficiency[zone] = {"durations": [], "task_count": 0}
                        zone_efficiency[zone]["durations"].append(task.actual_duration_minutes)
                        zone_efficiency[zone]["task_count"] += 1
                
                if zone_efficiency:
                    response += f"\n📍 **Efficiency by Zone:**\n"
                    for zone, data in sorted(zone_efficiency.items(), key=lambda x: x[1]["task_count"], reverse=True):
                        avg_duration = sum(data["durations"]) / len(data["durations"])
                        response += f"   Zone {zone}: {data['task_count']} tasks, {avg_duration:.1f} min avg\n"
                
                # Item category efficiency
                category_efficiency = {}
                for task in efficiency_data:
                    if task.item_category and task.actual_duration_minutes:
                        category = task.item_category
                        if category not in category_efficiency:
                            category_efficiency[category] = {"durations": [], "quantities": []}
                        category_efficiency[category]["durations"].append(task.actual_duration_minutes)
                        if task.quantity:
                            category_efficiency[category]["quantities"].append(float(task.quantity))
                
                if category_efficiency:
                    response += f"\n📂 **Efficiency by Item Category:**\n"
                    for category, data in sorted(category_efficiency.items(), key=lambda x: len(x[1]["durations"]), reverse=True)[:5]:
                        avg_duration = sum(data["durations"]) / len(data["durations"])
                        avg_quantity = sum(data["quantities"]) / len(data["quantities"]) if data["quantities"] else 0
                        efficiency_score = avg_quantity / avg_duration if avg_duration > 0 else 0
                        
                        response += f"   {category}: {len(data['durations'])} tasks, {avg_duration:.1f} min avg, {efficiency_score:.2f} units/min\n"
                
                # Identify optimization opportunities
                slow_tasks = [task for task in tasks_with_duration if task.actual_duration_minutes > avg_duration * 2]
                fast_tasks = [task for task in tasks_with_duration if task.actual_duration_minutes < avg_duration * 0.5]
                
                response += f"\n🔍 **Optimization Opportunities:**\n"
                
                if slow_tasks:
                    response += f"   Slow tasks (>2x average): {len(slow_tasks)}\n"
                    # Group by work type
                    slow_by_type = {}
                    for task in slow_tasks:
                        wtype = task.work_type
                        slow_by_type[wtype] = slow_by_type.get(wtype, 0) + 1
                    
                    for wtype, count in sorted(slow_by_type.items(), key=lambda x: x[1], reverse=True)[:3]:
                        response += f"      {wtype}: {count} slow tasks\n"
                
                if fast_tasks:
                    response += f"   Fast tasks (<50% average): {len(fast_tasks)}\n"
                    response += f"   Analyze fast completions for best practices\n"
                
                # Priority efficiency
                if any(task.priority_level for task in efficiency_data):
                    high_priority_tasks = [task for task in efficiency_data if task.priority_level and task.priority_level >= 8]
                    if high_priority_tasks and tasks_with_duration:
                        avg_high_priority_duration = sum(
                            task.actual_duration_minutes for task in high_priority_tasks if task.actual_duration_minutes
                        ) / len([task for task in high_priority_tasks if task.actual_duration_minutes])
                        
                        response += f"\n🔴 **High Priority Task Performance:**\n"
                        response += f"   High priority tasks: {len(high_priority_tasks)}\n"
                        response += f"   Avg duration: {avg_high_priority_duration:.1f} minutes\n"
                        
                        if avg_high_priority_duration > avg_duration:
                            response += f"   ⚠️ High priority tasks taking longer than average\n"
                
                # Recommendations
                response += f"\n💡 **Efficiency Recommendations:**\n"
                
                if tasks_with_estimates and avg_efficiency > 1.1:
                    response += f"   • Review task estimates - actual times are {(avg_efficiency-1)*100:.0f}% higher than estimated\n"
                
                if slow_tasks:
                    response += f"   • Investigate {len(slow_tasks)} slow-performing tasks for process improvements\n"
                
                if zone_efficiency:
                    slowest_zone = max(zone_efficiency.items(), key=lambda x: sum(x[1]["durations"])/len(x[1]["durations"]))
                    fastest_zone = min(zone_efficiency.items(), key=lambda x: sum(x[1]["durations"])/len(x[1]["durations"]))
                    
                    if len(zone_efficiency) > 1:
                        response += f"   • Compare processes between Zone {fastest_zone[0]} (fastest) and Zone {slowest_zone[0]} (slowest)\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing task efficiency: {str(e)}"


# Functional Agent - Business processes and workflows
class WorkFunctionalAgent(WMSBaseAgent):
    """Handles functional aspects of work management"""
    
    def __init__(self):
        tools = [
            WorkAssignmentTool("work", "functional"),
            LaborProductivityTool("work", "functional"),
            TaskEfficiencyTool("work", "functional")
        ]
        super().__init__("work", "functional", tools)
    
    def _get_specialization(self) -> str:
        return "Work assignment workflows, task coordination, and labor management processes"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "task_assignment",
            "workflow_coordination",
            "priority_management",
            "resource_allocation",
            "performance_tracking",
            "workload_balancing"
        ]


# Technical Agent - System specifications
class WorkTechnicalAgent(WMSBaseAgent):
    """Handles technical aspects of work management"""
    
    def __init__(self):
        tools = [WorkAssignmentTool("work", "technical")]
        super().__init__("work", "technical", tools)
    
    def _get_specialization(self) -> str:
        return "Work management systems, task optimization algorithms, and mobile workforce integration"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "system_optimization",
            "algorithm_development",
            "mobile_integration",
            "real_time_tracking",
            "api_development",
            "data_synchronization"
        ]


# Configuration Agent - Setup and parameters
class WorkConfigurationAgent(WMSBaseAgent):
    """Handles work management configuration"""
    
    def __init__(self):
        tools = [LaborProductivityTool("work", "configuration")]
        super().__init__("work", "configuration", tools)
    
    def _get_specialization(self) -> str:
        return "Work rules configuration, priority settings, and performance standards setup"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "rule_configuration",
            "priority_setup",
            "performance_standards",
            "workflow_design",
            "policy_configuration",
            "system_parameters"
        ]


# Relationships Agent - Integration with other modules
class WorkRelationshipsAgent(WMSBaseAgent):
    """Handles work management relationships with other WMS modules"""
    
    def __init__(self):
        tools = [WorkAssignmentTool("work", "relationships")]
        super().__init__("work", "relationships", tools)
    
    def _get_specialization(self) -> str:
        return "Work integration with inventory, picking, putaway, and quality control processes"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "process_integration",
            "workflow_coordination",
            "cross_module_sync",
            "dependency_management",
            "resource_coordination",
            "system_orchestration"
        ]


# Notes Agent - Best practices and recommendations
class WorkNotesAgent(WMSBaseAgent):
    """Provides work management best practices and recommendations"""
    
    def __init__(self):
        tools = [TaskEfficiencyTool("work", "notes")]
        super().__init__("work", "notes", tools)
    
    def _get_specialization(self) -> str:
        return "Labor productivity best practices, efficiency optimization, and workforce management strategies"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "productivity_best_practices",
            "efficiency_optimization",
            "workforce_strategies",
            "performance_improvement",
            "training_guidelines",
            "continuous_improvement"
        ]