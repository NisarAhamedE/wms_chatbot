"""
Wave management agents (Category 9) - 5 specialized sub-category agents.
Handles all aspects of wave planning, release, optimization, and execution tracking.
"""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import WMSBaseAgent, WMSBaseTool, WMSContext
from ...database.models import (
    Wave, WaveDetail, WorkAssignment, Item, Location, Inventory, User
)


class WavePlanningTool(WMSBaseTool):
    """Tool for wave planning and optimization"""
    
    name = "wave_planning"
    description = "Plan and optimize waves for picking efficiency and resource allocation"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute wave planning analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Parse wave parameters
                wave_params = self._parse_wave_query(query)
                
                # Get wave planning data
                planning_query = """
                SELECT 
                    w.wave_id,
                    w.wave_name,
                    w.wave_type,
                    w.planned_start_time,
                    w.planned_end_time,
                    w.wave_status,
                    w.priority_level,
                    w.created_at,
                    COUNT(wd.detail_id) as total_lines,
                    COUNT(DISTINCT wd.item_id) as unique_items,
                    COUNT(DISTINCT wd.location_id) as unique_locations,
                    SUM(wd.quantity) as total_quantity,
                    COUNT(DISTINCT wa.assigned_user_id) as assigned_users,
                    AVG(wa.estimated_duration) as avg_estimated_duration,
                    COUNT(CASE WHEN wa.work_status = 'COMPLETED' THEN 1 END) as completed_tasks,
                    COUNT(wa.work_id) as total_tasks
                FROM waves w
                LEFT JOIN wave_details wd ON w.wave_id = wd.wave_id
                LEFT JOIN work_assignments wa ON w.wave_id = wa.wave_id
                WHERE w.created_at >= NOW() - INTERVAL '14 days'
                GROUP BY w.wave_id, w.wave_name, w.wave_type, w.planned_start_time, 
                         w.planned_end_time, w.wave_status, w.priority_level, w.created_at
                ORDER BY w.created_at DESC
                LIMIT 100;
                """
                
                result = await session.execute(planning_query)
                wave_data = result.fetchall()
                
                if not wave_data:
                    return "No wave data found for the last 14 days."
                
                response = "🌊 **Wave Planning Analysis (Last 14 days):**\n\n"
                
                # Overall wave statistics
                total_waves = len(wave_data)
                planned_waves = len([w for w in wave_data if w.wave_status == 'PLANNED'])
                released_waves = len([w for w in wave_data if w.wave_status == 'RELEASED'])
                in_progress_waves = len([w for w in wave_data if w.wave_status == 'IN_PROGRESS'])
                completed_waves = len([w for w in wave_data if w.wave_status == 'COMPLETED'])
                
                response += f"📊 **Wave Overview:**\n"
                response += f"   Total waves: {total_waves}\n"
                response += f"   Planned: {planned_waves} ({planned_waves/total_waves*100:.1f}%)\n"
                response += f"   Released: {released_waves} ({released_waves/total_waves*100:.1f}%)\n"
                response += f"   In Progress: {in_progress_waves} ({in_progress_waves/total_waves*100:.1f}%)\n"
                response += f"   Completed: {completed_waves} ({completed_waves/total_waves*100:.1f}%)\n\n"
                
                # Wave type breakdown
                wave_types = {}
                for wave in wave_data:
                    wtype = wave.wave_type or "STANDARD"
                    if wtype not in wave_types:
                        wave_types[wtype] = {"count": 0, "total_lines": 0, "total_quantity": 0, "completed": 0}
                    wave_types[wtype]["count"] += 1
                    wave_types[wtype]["total_lines"] += wave.total_lines or 0
                    wave_types[wtype]["total_quantity"] += float(wave.total_quantity or 0)
                    if wave.wave_status == "COMPLETED":
                        wave_types[wtype]["completed"] += 1
                
                response += f"📋 **Wave Type Analysis:**\n"
                for wtype, stats in sorted(wave_types.items(), key=lambda x: x[1]["count"], reverse=True):
                    completion_rate = (stats["completed"] / stats["count"]) * 100 if stats["count"] > 0 else 0
                    avg_lines = stats["total_lines"] / stats["count"] if stats["count"] > 0 else 0
                    
                    response += f"   {wtype}:\n"
                    response += f"      Waves: {stats['count']} ({completion_rate:.1f}% completed)\n"
                    response += f"      Avg lines per wave: {avg_lines:.1f}\n"
                    response += f"      Total quantity: {stats['total_quantity']:,.1f}\n"
                
                # Wave size analysis
                small_waves = len([w for w in wave_data if (w.total_lines or 0) <= 50])
                medium_waves = len([w for w in wave_data if 50 < (w.total_lines or 0) <= 200])
                large_waves = len([w for w in wave_data if (w.total_lines or 0) > 200])
                
                response += f"\n📏 **Wave Size Distribution:**\n"
                response += f"   Small waves (≤50 lines): {small_waves}\n"
                response += f"   Medium waves (51-200 lines): {medium_waves}\n"
                response += f"   Large waves (>200 lines): {large_waves}\n"
                
                # Resource utilization
                waves_with_users = [w for w in wave_data if w.assigned_users and w.assigned_users > 0]
                if waves_with_users:
                    avg_users_per_wave = sum(w.assigned_users for w in waves_with_users) / len(waves_with_users)
                    max_users = max(w.assigned_users for w in waves_with_users)
                    min_users = min(w.assigned_users for w in waves_with_users)
                    
                    response += f"\n👥 **Resource Allocation:**\n"
                    response += f"   Waves with assigned users: {len(waves_with_users)}\n"
                    response += f"   Avg users per wave: {avg_users_per_wave:.1f}\n"
                    response += f"   User range: {min_users}-{max_users} per wave\n"
                
                # Wave efficiency analysis
                completed_waves_with_tasks = [
                    w for w in wave_data 
                    if w.wave_status == 'COMPLETED' and w.total_tasks and w.total_tasks > 0
                ]
                
                if completed_waves_with_tasks:
                    response += f"\n⚡ **Wave Efficiency:**\n"
                    for wave in completed_waves_with_tasks[:5]:
                        completion_rate = (wave.completed_tasks / wave.total_tasks) * 100
                        efficiency_score = (wave.total_quantity or 0) / (wave.total_tasks or 1)
                        
                        response += f"   {wave.wave_name}:\n"
                        response += f"      Task completion: {completion_rate:.1f}%\n"
                        response += f"      Efficiency: {efficiency_score:.1f} units/task\n"
                        response += f"      Lines: {wave.total_lines}, Users: {wave.assigned_users or 0}\n"
                
                # Priority analysis
                high_priority_waves = [w for w in wave_data if w.priority_level and w.priority_level >= 8]
                if high_priority_waves:
                    response += f"\n🔴 **High Priority Waves:** {len(high_priority_waves)}\n"
                    pending_high_priority = [w for w in high_priority_waves if w.wave_status in ['PLANNED', 'RELEASED']]
                    if pending_high_priority:
                        response += f"   Pending high priority: {len(pending_high_priority)}\n"
                        for wave in pending_high_priority[:3]:
                            response += f"      {wave.wave_name}: Priority {wave.priority_level}, {wave.total_lines} lines\n"
                
                # Upcoming planned waves
                upcoming_waves = [
                    w for w in wave_data 
                    if w.wave_status in ['PLANNED', 'RELEASED'] and 
                       w.planned_start_time and w.planned_start_time >= datetime.utcnow()
                ]
                
                if upcoming_waves:
                    upcoming_waves.sort(key=lambda x: x.planned_start_time)
                    response += f"\n📅 **Upcoming Waves:**\n"
                    for wave in upcoming_waves[:5]:
                        hours_until = (wave.planned_start_time - datetime.utcnow()).total_seconds() / 3600
                        response += f"   {wave.wave_name}: {hours_until:.1f}h ({wave.total_lines} lines)\n"
                
                # Wave optimization recommendations
                response += f"\n💡 **Planning Recommendations:**\n"
                
                # Check for wave balance
                if wave_types and len(wave_types) > 1:
                    wave_counts = [stats["count"] for stats in wave_types.values()]
                    max_count = max(wave_counts)
                    min_count = min(wave_counts)
                    if max_count > min_count * 3:
                        response += f"   • Wave type imbalance detected - consider balancing workload\n"
                
                # Check for size optimization
                if large_waves > total_waves * 0.2:  # More than 20% are large
                    response += f"   • {large_waves} large waves may need splitting for better resource utilization\n"
                
                if small_waves > total_waves * 0.5:  # More than 50% are small
                    response += f"   • Consider consolidating {small_waves} small waves for efficiency\n"
                
                # Resource optimization
                if waves_with_users and max_users > avg_users_per_wave * 2:
                    response += f"   • Review resource allocation - some waves have 2x average user count\n"
                
                # Priority management
                if high_priority_waves and pending_high_priority:
                    response += f"   • Prioritize release of {len(pending_high_priority)} high-priority waves\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing wave planning: {str(e)}"
    
    def _parse_wave_query(self, query: str) -> Dict[str, Any]:
        """Parse wave query parameters"""
        query_lower = query.lower()
        params = {}
        
        import re
        
        # Extract wave type
        if "batch" in query_lower:
            params["wave_type"] = "BATCH"
        elif "single" in query_lower:
            params["wave_type"] = "SINGLE"
        elif "priority" in query_lower:
            params["wave_type"] = "PRIORITY"
        
        # Extract status
        if "planned" in query_lower:
            params["status"] = "PLANNED"
        elif "released" in query_lower:
            params["status"] = "RELEASED"
        elif "completed" in query_lower:
            params["status"] = "COMPLETED"
        
        return params


class WaveExecutionTool(WMSBaseTool):
    """Tool for wave execution monitoring and tracking"""
    
    name = "wave_execution"
    description = "Monitor wave execution progress, track performance, and identify bottlenecks"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute wave execution analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get wave execution data
                execution_query = """
                SELECT 
                    w.wave_id,
                    w.wave_name,
                    w.wave_type,
                    w.wave_status,
                    w.planned_start_time,
                    w.actual_start_time,
                    w.planned_end_time,
                    w.actual_end_time,
                    w.priority_level,
                    COUNT(wd.detail_id) as total_lines,
                    SUM(wd.quantity) as total_quantity,
                    COUNT(wa.work_id) as total_tasks,
                    COUNT(CASE WHEN wa.work_status = 'COMPLETED' THEN 1 END) as completed_tasks,
                    COUNT(CASE WHEN wa.work_status = 'IN_PROGRESS' THEN 1 END) as in_progress_tasks,
                    COUNT(DISTINCT wa.assigned_user_id) as assigned_users,
                    AVG(CASE 
                        WHEN wa.completed_at IS NOT NULL AND wa.started_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (wa.completed_at - wa.started_at)) / 60
                        ELSE NULL
                    END) as avg_task_duration_minutes,
                    MIN(wa.started_at) as first_task_start,
                    MAX(wa.completed_at) as last_task_completion
                FROM waves w
                LEFT JOIN wave_details wd ON w.wave_id = wd.wave_id
                LEFT JOIN work_assignments wa ON w.wave_id = wa.wave_id
                WHERE w.wave_status IN ('RELEASED', 'IN_PROGRESS', 'COMPLETED')
                    AND w.actual_start_time IS NOT NULL
                    AND w.created_at >= NOW() - INTERVAL '7 days'
                GROUP BY w.wave_id, w.wave_name, w.wave_type, w.wave_status, 
                         w.planned_start_time, w.actual_start_time, w.planned_end_time, 
                         w.actual_end_time, w.priority_level
                ORDER BY w.actual_start_time DESC
                LIMIT 50;
                """
                
                result = await session.execute(execution_query)
                execution_data = result.fetchall()
                
                if not execution_data:
                    return "No wave execution data found for the last 7 days."
                
                response = "🚀 **Wave Execution Analysis (Last 7 days):**\n\n"
                
                # Execution status overview
                total_executing_waves = len(execution_data)
                in_progress_waves = len([w for w in execution_data if w.wave_status == 'IN_PROGRESS'])
                completed_waves = len([w for w in execution_data if w.wave_status == 'COMPLETED'])
                
                response += f"📊 **Execution Status:**\n"
                response += f"   Total executing waves: {total_executing_waves}\n"
                response += f"   In Progress: {in_progress_waves}\n"
                response += f"   Completed: {completed_waves}\n\n"
                
                # Performance metrics for completed waves
                completed_waves_data = [w for w in execution_data if w.wave_status == 'COMPLETED']
                if completed_waves_data:
                    # Calculate execution times
                    execution_times = []
                    schedule_variances = []
                    
                    for wave in completed_waves_data:
                        if wave.actual_start_time and wave.actual_end_time:
                            exec_time = (wave.actual_end_time - wave.actual_start_time).total_seconds() / 3600
                            execution_times.append(exec_time)
                        
                        if wave.planned_end_time and wave.actual_end_time:
                            variance = (wave.actual_end_time - wave.planned_end_time).total_seconds() / 3600
                            schedule_variances.append(variance)
                    
                    if execution_times:
                        avg_execution_time = sum(execution_times) / len(execution_times)
                        response += f"⏱️ **Execution Performance:**\n"
                        response += f"   Completed waves: {len(completed_waves_data)}\n"
                        response += f"   Avg execution time: {avg_execution_time:.1f} hours\n"
                        response += f"   Fastest wave: {min(execution_times):.1f} hours\n"
                        response += f"   Slowest wave: {max(execution_times):.1f} hours\n"
                    
                    if schedule_variances:
                        avg_variance = sum(schedule_variances) / len(schedule_variances)
                        on_time_waves = len([v for v in schedule_variances if abs(v) <= 0.5])  # Within 30 min
                        early_waves = len([v for v in schedule_variances if v < -0.5])
                        late_waves = len([v for v in schedule_variances if v > 0.5])
                        
                        response += f"   Schedule variance: {avg_variance:+.1f} hours avg\n"
                        response += f"   On-time waves: {on_time_waves} ({on_time_waves/len(schedule_variances)*100:.1f}%)\n"
                        response += f"   Early completions: {early_waves}\n"
                        response += f"   Late completions: {late_waves}\n"
                
                # Current active waves
                active_waves = [w for w in execution_data if w.wave_status == 'IN_PROGRESS']
                if active_waves:
                    response += f"\n🔄 **Currently Active Waves:**\n"
                    for wave in active_waves:
                        completion_rate = (wave.completed_tasks / wave.total_tasks) * 100 if wave.total_tasks > 0 else 0
                        hours_running = (datetime.utcnow() - wave.actual_start_time).total_seconds() / 3600 if wave.actual_start_time else 0
                        
                        response += f"   {wave.wave_name}:\n"
                        response += f"      Progress: {completion_rate:.1f}% ({wave.completed_tasks}/{wave.total_tasks})\n"
                        response += f"      Running time: {hours_running:.1f} hours\n"
                        response += f"      Users: {wave.assigned_users or 0}\n"
                        response += f"      Lines: {wave.total_lines}\n"
                
                # Task completion analysis
                waves_with_tasks = [w for w in execution_data if w.total_tasks and w.total_tasks > 0]
                if waves_with_tasks:
                    total_tasks = sum(w.total_tasks for w in waves_with_tasks)
                    total_completed = sum(w.completed_tasks for w in waves_with_tasks)
                    total_in_progress = sum(w.in_progress_tasks for w in waves_with_tasks)
                    
                    overall_completion = (total_completed / total_tasks) * 100 if total_tasks > 0 else 0
                    
                    response += f"\n📈 **Task Completion:**\n"
                    response += f"   Total tasks: {total_tasks:,}\n"
                    response += f"   Completed: {total_completed:,} ({overall_completion:.1f}%)\n"
                    response += f"   In Progress: {total_in_progress:,}\n"
                    response += f"   Pending: {total_tasks - total_completed - total_in_progress:,}\n"
                
                # Productivity analysis
                productive_waves = [w for w in execution_data if w.avg_task_duration_minutes]
                if productive_waves:
                    avg_task_time = sum(w.avg_task_duration_minutes for w in productive_waves) / len(productive_waves)
                    
                    response += f"\n⚡ **Productivity Metrics:**\n"
                    response += f"   Average task duration: {avg_task_time:.1f} minutes\n"
                    
                    # Find most/least efficient waves
                    sorted_by_efficiency = sorted(productive_waves, key=lambda x: x.avg_task_duration_minutes)
                    if len(sorted_by_efficiency) >= 2:
                        most_efficient = sorted_by_efficiency[0]
                        least_efficient = sorted_by_efficiency[-1]
                        
                        response += f"   Most efficient: {most_efficient.wave_name} ({most_efficient.avg_task_duration_minutes:.1f} min/task)\n"
                        response += f"   Least efficient: {least_efficient.wave_name} ({least_efficient.avg_task_duration_minutes:.1f} min/task)\n"
                
                # Bottleneck identification
                stalled_waves = []
                slow_waves = []
                
                for wave in active_waves:
                    if wave.actual_start_time:
                        hours_running = (datetime.utcnow() - wave.actual_start_time).total_seconds() / 3600
                        completion_rate = (wave.completed_tasks / wave.total_tasks) * 100 if wave.total_tasks > 0 else 0
                        
                        # Stalled if running >4 hours with <10% completion
                        if hours_running > 4 and completion_rate < 10:
                            stalled_waves.append((wave, hours_running, completion_rate))
                        # Slow if completion rate is very low for time running
                        elif hours_running > 2 and completion_rate < hours_running * 10:  # Less than 10% per hour
                            slow_waves.append((wave, hours_running, completion_rate))
                
                if stalled_waves or slow_waves:
                    response += f"\n⚠️ **Performance Issues:**\n"
                    
                    if stalled_waves:
                        response += f"   Stalled waves: {len(stalled_waves)}\n"
                        for wave, hours, completion in stalled_waves:
                            response += f"      {wave.wave_name}: {hours:.1f}h running, {completion:.1f}% complete\n"
                    
                    if slow_waves:
                        response += f"   Slow-progressing waves: {len(slow_waves)}\n"
                        for wave, hours, completion in slow_waves[:3]:
                            response += f"      {wave.wave_name}: {hours:.1f}h running, {completion:.1f}% complete\n"
                
                # Recommendations
                response += f"\n💡 **Execution Recommendations:**\n"
                
                if schedule_variances and avg_variance > 1:
                    response += f"   • Average completion is {avg_variance:.1f}h behind schedule - review planning accuracy\n"
                
                if late_waves > len(schedule_variances) * 0.3:
                    response += f"   • {late_waves} waves completed late - investigate resource constraints\n"
                
                if stalled_waves:
                    response += f"   • {len(stalled_waves)} waves are stalled - immediate intervention required\n"
                
                if active_waves:
                    avg_progress = sum(
                        (w.completed_tasks / w.total_tasks) * 100 if w.total_tasks > 0 else 0 
                        for w in active_waves
                    ) / len(active_waves)
                    
                    if avg_progress < 50:
                        response += f"   • Active waves averaging {avg_progress:.1f}% completion - monitor resource allocation\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing wave execution: {str(e)}"


class WaveOptimizationTool(WMSBaseTool):
    """Tool for wave optimization and efficiency analysis"""
    
    name = "wave_optimization"
    description = "Analyze wave efficiency and provide optimization recommendations"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute wave optimization analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get wave optimization data
                optimization_query = """
                SELECT 
                    w.wave_id,
                    w.wave_name,
                    w.wave_type,
                    COUNT(DISTINCT wd.location_id) as unique_locations,
                    COUNT(DISTINCT wd.item_id) as unique_items,
                    COUNT(wd.detail_id) as total_lines,
                    SUM(wd.quantity) as total_quantity,
                    COUNT(DISTINCT wa.assigned_user_id) as total_users,
                    AVG(CASE 
                        WHEN wa.completed_at IS NOT NULL AND wa.started_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (wa.completed_at - wa.started_at)) / 60
                        ELSE NULL
                    END) as avg_task_minutes,
                    SUM(CASE 
                        WHEN wa.completed_at IS NOT NULL AND wa.started_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (wa.completed_at - wa.started_at)) / 60
                        ELSE 0
                    END) as total_work_minutes,
                    COUNT(CASE WHEN wa.work_status = 'COMPLETED' THEN 1 END) as completed_tasks,
                    COUNT(wa.work_id) as total_tasks,
                    STRING_AGG(DISTINCT l.zone_id, ',') as zones_involved
                FROM waves w
                JOIN wave_details wd ON w.wave_id = wd.wave_id
                LEFT JOIN work_assignments wa ON w.wave_id = wa.wave_id
                LEFT JOIN locations l ON wd.location_id = l.location_id
                WHERE w.wave_status = 'COMPLETED'
                    AND w.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY w.wave_id, w.wave_name, w.wave_type
                HAVING COUNT(wd.detail_id) > 0
                ORDER BY total_lines DESC
                LIMIT 100;
                """
                
                result = await session.execute(optimization_query)
                optimization_data = result.fetchall()
                
                if not optimization_data:
                    return "No completed wave optimization data found for the last 30 days."
                
                response = "🎯 **Wave Optimization Analysis (Last 30 days):**\n\n"
                
                # Overall optimization metrics
                total_waves = len(optimization_data)
                total_lines = sum(wave.total_lines for wave in optimization_data)
                total_quantity = sum(float(wave.total_quantity) for wave in optimization_data)
                total_work_time = sum(float(wave.total_work_minutes or 0) for wave in optimization_data)
                
                avg_lines_per_wave = total_lines / total_waves if total_waves > 0 else 0
                avg_quantity_per_wave = total_quantity / total_waves if total_waves > 0 else 0
                overall_productivity = total_quantity / (total_work_time / 60) if total_work_time > 0 else 0
                
                response += f"📊 **Optimization Overview:**\n"
                response += f"   Waves analyzed: {total_waves}\n"
                response += f"   Total lines: {total_lines:,}\n"
                response += f"   Total quantity: {total_quantity:,.1f}\n"
                response += f"   Total work time: {total_work_time/60:.1f} hours\n"
                response += f"   Avg lines per wave: {avg_lines_per_wave:.1f}\n"
                response += f"   Overall productivity: {overall_productivity:.1f} units/hour\n\n"
                
                # Wave efficiency analysis
                efficiency_metrics = []
                for wave in optimization_data:
                    if wave.total_work_minutes and wave.total_work_minutes > 0:
                        lines_per_hour = (wave.total_lines / (wave.total_work_minutes / 60))
                        quantity_per_hour = (float(wave.total_quantity) / (wave.total_work_minutes / 60))
                        locations_per_line = wave.unique_locations / wave.total_lines if wave.total_lines > 0 else 0
                        
                        efficiency_metrics.append({
                            "wave": wave,
                            "lines_per_hour": lines_per_hour,
                            "quantity_per_hour": quantity_per_hour,
                            "locations_per_line": locations_per_line,
                            "zone_count": len(wave.zones_involved.split(',') if wave.zones_involved else [])
                        })
                
                # Top performing waves
                if efficiency_metrics:
                    top_by_lines = sorted(efficiency_metrics, key=lambda x: x["lines_per_hour"], reverse=True)[:5]
                    top_by_quantity = sorted(efficiency_metrics, key=lambda x: x["quantity_per_hour"], reverse=True)[:5]
                    
                    response += f"🏆 **Top Performing Waves (by lines/hour):**\n"
                    for metric in top_by_lines:
                        wave = metric["wave"]
                        response += f"   {wave.wave_name}:\n"
                        response += f"      Lines/hour: {metric['lines_per_hour']:.1f}\n"
                        response += f"      Quantity/hour: {metric['quantity_per_hour']:.1f}\n"
                        response += f"      Users: {wave.total_users}, Zones: {metric['zone_count']}\n"
                
                # Wave complexity analysis
                simple_waves = [w for w in optimization_data if w.unique_locations <= 10]
                complex_waves = [w for w in optimization_data if w.unique_locations > 50]
                multi_zone_waves = [w for w in optimization_data if len((w.zones_involved or '').split(',')) > 3]
                
                response += f"\n📊 **Complexity Analysis:**\n"
                response += f"   Simple waves (≤10 locations): {len(simple_waves)}\n"
                response += f"   Complex waves (>50 locations): {len(complex_waves)}\n"
                response += f"   Multi-zone waves (>3 zones): {len(multi_zone_waves)}\n"
                
                # Efficiency by complexity
                if simple_waves and complex_waves:
                    simple_avg_productivity = sum(
                        float(w.total_quantity) / (float(w.total_work_minutes or 1) / 60) 
                        for w in simple_waves if w.total_work_minutes
                    ) / len([w for w in simple_waves if w.total_work_minutes])
                    
                    complex_avg_productivity = sum(
                        float(w.total_quantity) / (float(w.total_work_minutes or 1) / 60) 
                        for w in complex_waves if w.total_work_minutes
                    ) / len([w for w in complex_waves if w.total_work_minutes])
                    
                    response += f"\n   Simple wave productivity: {simple_avg_productivity:.1f} units/hour\n"
                    response += f"   Complex wave productivity: {complex_avg_productivity:.1f} units/hour\n"
                    
                    if simple_avg_productivity > complex_avg_productivity * 1.2:
                        response += f"   📈 Simple waves are {simple_avg_productivity/complex_avg_productivity:.1f}x more productive\n"
                
                # Resource utilization optimization
                user_efficiency = {}
                for wave in optimization_data:
                    if wave.total_users and wave.total_users > 0:
                        users_bucket = "1" if wave.total_users == 1 else "2-3" if wave.total_users <= 3 else "4-6" if wave.total_users <= 6 else "7+"
                        
                        if users_bucket not in user_efficiency:
                            user_efficiency[users_bucket] = {"waves": 0, "total_productivity": 0}
                        
                        user_efficiency[users_bucket]["waves"] += 1
                        if wave.total_work_minutes:
                            productivity = float(wave.total_quantity) / (float(wave.total_work_minutes) / 60)
                            user_efficiency[users_bucket]["total_productivity"] += productivity
                
                response += f"\n👥 **Resource Utilization:**\n"
                for users, stats in sorted(user_efficiency.items()):
                    if stats["waves"] > 0:
                        avg_productivity = stats["total_productivity"] / stats["waves"]
                        response += f"   {users} users: {stats['waves']} waves, {avg_productivity:.1f} avg units/hour\n"
                
                # Zone optimization analysis
                zone_performance = {}
                for wave in optimization_data:
                    if wave.zones_involved:
                        zone_count = len(wave.zones_involved.split(','))
                        zone_bucket = "Single" if zone_count == 1 else "2-3 zones" if zone_count <= 3 else "4+ zones"
                        
                        if zone_bucket not in zone_performance:
                            zone_performance[zone_bucket] = {"waves": 0, "total_lines": 0, "total_time": 0}
                        
                        zone_performance[zone_bucket]["waves"] += 1
                        zone_performance[zone_bucket]["total_lines"] += wave.total_lines
                        zone_performance[zone_bucket]["total_time"] += float(wave.total_work_minutes or 0)
                
                response += f"\n🗺️ **Zone Distribution Efficiency:**\n"
                for zone_type, stats in sorted(zone_performance.items()):
                    if stats["waves"] > 0 and stats["total_time"] > 0:
                        efficiency = (stats["total_lines"] / (stats["total_time"] / 60))
                        response += f"   {zone_type}: {stats['waves']} waves, {efficiency:.1f} lines/hour\n"
                
                # Optimization opportunities
                response += f"\n💡 **Optimization Opportunities:**\n"
                
                # Wave size optimization
                oversized_waves = [w for w in optimization_data if w.total_lines > avg_lines_per_wave * 2]
                undersized_waves = [w for w in optimization_data if w.total_lines < avg_lines_per_wave * 0.5]
                
                if oversized_waves:
                    response += f"   • {len(oversized_waves)} oversized waves could be split for better resource utilization\n"
                
                if undersized_waves:
                    response += f"   • {len(undersized_waves)} undersized waves could be consolidated\n"
                
                # Complexity optimization
                if complex_waves and simple_waves:
                    if simple_avg_productivity > complex_avg_productivity * 1.3:
                        response += f"   • Complex waves are {complex_avg_productivity/simple_avg_productivity:.2f}x less efficient - consider breaking down\n"
                
                # Resource optimization
                if user_efficiency:
                    efficiency_values = [
                        stats["total_productivity"] / stats["waves"] 
                        for stats in user_efficiency.values() if stats["waves"] > 0
                    ]
                    if efficiency_values:
                        best_efficiency = max(efficiency_values)
                        worst_efficiency = min(efficiency_values)
                        
                        if best_efficiency > worst_efficiency * 1.5:
                            response += f"   • Optimal user allocation shows {best_efficiency/worst_efficiency:.1f}x productivity difference\n"
                
                # Zone optimization
                if multi_zone_waves:
                    single_zone_waves = [w for w in optimization_data if len((w.zones_involved or '').split(',')) == 1]
                    if single_zone_waves and len(single_zone_waves) < len(multi_zone_waves):
                        response += f"   • Consider single-zone picking to reduce travel time ({len(multi_zone_waves)} multi-zone waves)\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing wave optimization: {str(e)}"


# Functional Agent - Business processes and workflows
class WaveManagementFunctionalAgent(WMSBaseAgent):
    """Handles functional aspects of wave management"""
    
    def __init__(self):
        tools = [
            WavePlanningTool("wave_management", "functional"),
            WaveExecutionTool("wave_management", "functional"),
            WaveOptimizationTool("wave_management", "functional")
        ]
        super().__init__("wave_management", "functional", tools)
    
    def _get_specialization(self) -> str:
        return "Wave planning workflows, execution monitoring, and picking optimization strategies"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "wave_planning",
            "execution_monitoring",
            "resource_optimization",
            "batch_coordination",
            "performance_tracking",
            "workflow_efficiency"
        ]


# Technical Agent - System specifications
class WaveManagementTechnicalAgent(WMSBaseAgent):
    """Handles technical aspects of wave management"""
    
    def __init__(self):
        tools = [WavePlanningTool("wave_management", "technical")]
        super().__init__("wave_management", "technical", tools)
    
    def _get_specialization(self) -> str:
        return "Wave optimization algorithms, batch processing systems, and automated wave release"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "optimization_algorithms",
            "batch_processing",
            "automated_release",
            "system_integration",
            "real_time_monitoring",
            "performance_analytics"
        ]


# Configuration Agent - Setup and parameters
class WaveManagementConfigurationAgent(WMSBaseAgent):
    """Handles wave management configuration"""
    
    def __init__(self):
        tools = [WaveOptimizationTool("wave_management", "configuration")]
        super().__init__("wave_management", "configuration", tools)
    
    def _get_specialization(self) -> str:
        return "Wave template configuration, optimization parameters, and release criteria setup"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "template_configuration",
            "parameter_optimization",
            "release_criteria",
            "rule_configuration",
            "policy_setup",
            "threshold_management"
        ]


# Relationships Agent - Integration with other modules
class WaveManagementRelationshipsAgent(WMSBaseAgent):
    """Handles wave management relationships with other WMS modules"""
    
    def __init__(self):
        tools = [WaveExecutionTool("wave_management", "relationships")]
        super().__init__("wave_management", "relationships", tools)
    
    def _get_specialization(self) -> str:
        return "Wave integration with picking, inventory allocation, and labor management systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "picking_integration",
            "allocation_coordination",
            "labor_planning",
            "inventory_reservation",
            "cross_module_sync",
            "workflow_orchestration"
        ]


# Notes Agent - Best practices and recommendations
class WaveManagementNotesAgent(WMSBaseAgent):
    """Provides wave management best practices and recommendations"""
    
    def __init__(self):
        tools = [WaveOptimizationTool("wave_management", "notes")]
        super().__init__("wave_management", "notes", tools)
    
    def _get_specialization(self) -> str:
        return "Wave efficiency best practices, optimization strategies, and performance improvement methods"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "efficiency_best_practices",
            "optimization_strategies",
            "performance_improvement",
            "resource_planning",
            "continuous_optimization",
            "industry_benchmarks"
        ]