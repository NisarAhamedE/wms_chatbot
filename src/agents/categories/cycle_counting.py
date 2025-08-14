"""
Cycle counting agents (Category 8) - 5 specialized sub-category agents.
Handles all aspects of cycle counting including count scheduling, accuracy tracking, and variance analysis.
"""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import WMSBaseAgent, WMSBaseTool, WMSContext
from ...database.models import (
    CycleCount, Item, Location, Inventory, InventoryMovement, User
)


class CycleCountSchedulingTool(WMSBaseTool):
    """Tool for managing cycle count scheduling and planning"""
    
    name = "cycle_count_scheduling"
    description = "Schedule cycle counts, manage count frequency, and optimize counting workflows"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute cycle count scheduling analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Parse scheduling parameters
                schedule_params = self._parse_schedule_query(query)
                
                # Get cycle count scheduling data
                scheduling_query = """
                SELECT 
                    cc.count_id,
                    cc.item_id,
                    i.item_description,
                    i.item_category,
                    cc.location_id,
                    l.zone_id,
                    cc.count_type,
                    cc.scheduled_date,
                    cc.count_status,
                    cc.assigned_user_id,
                    cc.priority_level,
                    cc.count_reason,
                    cc.created_at,
                    inv.quantity_on_hand as system_quantity,
                    cc.counted_quantity,
                    ABS(COALESCE(cc.counted_quantity, 0) - COALESCE(inv.quantity_on_hand, 0)) as variance,
                    CASE 
                        WHEN inv.quantity_on_hand > 0 THEN
                            ABS(COALESCE(cc.counted_quantity, 0) - COALESCE(inv.quantity_on_hand, 0)) / inv.quantity_on_hand * 100
                        ELSE 0
                    END as variance_percentage
                FROM cycle_counts cc
                JOIN items i ON cc.item_id = i.item_id
                LEFT JOIN locations l ON cc.location_id = l.location_id
                LEFT JOIN inventory inv ON cc.item_id = inv.item_id AND cc.location_id = inv.location_id
                WHERE cc.created_at >= NOW() - INTERVAL '30 days'
                ORDER BY cc.scheduled_date DESC, cc.priority_level DESC
                LIMIT 200;
                """
                
                result = await session.execute(scheduling_query)
                count_data = result.fetchall()
                
                if not count_data:
                    return "No cycle count data found for the last 30 days."
                
                response = "📊 **Cycle Count Scheduling Analysis (Last 30 days):**\n\n"
                
                # Overall statistics
                total_counts = len(count_data)
                scheduled_counts = len([c for c in count_data if c.count_status == 'SCHEDULED'])
                in_progress_counts = len([c for c in count_data if c.count_status == 'IN_PROGRESS'])
                completed_counts = len([c for c in count_data if c.count_status == 'COMPLETED'])
                cancelled_counts = len([c for c in count_data if c.count_status == 'CANCELLED'])
                
                response += f"📈 **Scheduling Overview:**\n"
                response += f"   Total cycle counts: {total_counts}\n"
                response += f"   Scheduled: {scheduled_counts} ({scheduled_counts/total_counts*100:.1f}%)\n"
                response += f"   In Progress: {in_progress_counts} ({in_progress_counts/total_counts*100:.1f}%)\n"
                response += f"   Completed: {completed_counts} ({completed_counts/total_counts*100:.1f}%)\n"
                response += f"   Cancelled: {cancelled_counts} ({cancelled_counts/total_counts*100:.1f}%)\n\n"
                
                # Count type breakdown
                count_types = {}
                for count in count_data:
                    ctype = count.count_type or "STANDARD"
                    if ctype not in count_types:
                        count_types[ctype] = {"total": 0, "completed": 0, "scheduled": 0}
                    count_types[ctype]["total"] += 1
                    if count.count_status == "COMPLETED":
                        count_types[ctype]["completed"] += 1
                    elif count.count_status == "SCHEDULED":
                        count_types[ctype]["scheduled"] += 1
                
                response += f"🔄 **Count Type Distribution:**\n"
                for ctype, stats in sorted(count_types.items(), key=lambda x: x[1]["total"], reverse=True):
                    completion_rate = (stats["completed"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                    response += f"   {ctype}:\n"
                    response += f"      Total: {stats['total']} ({completion_rate:.1f}% completed)\n"
                    response += f"      Scheduled: {stats['scheduled']}\n"
                    response += f"      Completed: {stats['completed']}\n"
                
                # Count reason analysis
                count_reasons = {}
                for count in count_data:
                    reason = count.count_reason or "ROUTINE"
                    count_reasons[reason] = count_reasons.get(reason, 0) + 1
                
                response += f"\n📋 **Count Reasons:**\n"
                for reason, count in sorted(count_reasons.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_counts) * 100
                    response += f"   {reason}: {count} ({percentage:.1f}%)\n"
                
                # Upcoming scheduled counts
                upcoming_counts = [
                    c for c in count_data 
                    if c.count_status == 'SCHEDULED' and c.scheduled_date >= datetime.utcnow().date()
                ]
                
                if upcoming_counts:
                    # Sort by date
                    upcoming_counts.sort(key=lambda x: x.scheduled_date)
                    
                    response += f"\n📅 **Upcoming Scheduled Counts:**\n"
                    for count in upcoming_counts[:10]:
                        days_until = (count.scheduled_date - datetime.utcnow().date()).days
                        priority_indicator = "🔴" if count.priority_level and count.priority_level >= 8 else "🟡" if count.priority_level and count.priority_level >= 5 else "🟢"
                        
                        response += f"   {priority_indicator} {count.scheduled_date.strftime('%Y-%m-%d')} ({days_until} days):\n"
                        response += f"      {count.item_id} @ {count.location_id}\n"
                        response += f"      Type: {count.count_type}, Reason: {count.count_reason}\n"
                        if count.assigned_user_id:
                            response += f"      Assigned: {count.assigned_user_id}\n"
                
                # Overdue counts
                overdue_counts = [
                    c for c in count_data 
                    if c.count_status in ['SCHEDULED', 'IN_PROGRESS'] and 
                       c.scheduled_date < datetime.utcnow().date()
                ]
                
                if overdue_counts:
                    response += f"\n🚨 **Overdue Counts:** {len(overdue_counts)}\n"
                    for count in overdue_counts[:5]:
                        days_overdue = (datetime.utcnow().date() - count.scheduled_date).days
                        response += f"   {count.count_id}: {days_overdue} days overdue\n"
                        response += f"      {count.item_id} @ {count.location_id}\n"
                
                # Zone distribution
                zone_counts = {}
                for count in count_data:
                    if count.zone_id:
                        zone = count.zone_id
                        if zone not in zone_counts:
                            zone_counts[zone] = {"total": 0, "completed": 0, "scheduled": 0}
                        zone_counts[zone]["total"] += 1
                        if count.count_status == "COMPLETED":
                            zone_counts[zone]["completed"] += 1
                        elif count.count_status == "SCHEDULED":
                            zone_counts[zone]["scheduled"] += 1
                
                if zone_counts:
                    response += f"\n📍 **Zone Distribution:**\n"
                    for zone, stats in sorted(zone_counts.items(), key=lambda x: x[1]["total"], reverse=True):
                        completion_rate = (stats["completed"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                        response += f"   Zone {zone}: {stats['total']} counts ({completion_rate:.0f}% completed)\n"
                        response += f"      Scheduled: {stats['scheduled']}, Completed: {stats['completed']}\n"
                
                # Priority analysis
                high_priority = [c for c in count_data if c.priority_level and c.priority_level >= 8]
                if high_priority:
                    response += f"\n🔴 **High Priority Counts:** {len(high_priority)}\n"
                    pending_high_priority = [c for c in high_priority if c.count_status in ['SCHEDULED', 'IN_PROGRESS']]
                    if pending_high_priority:
                        response += f"   Pending high priority: {len(pending_high_priority)}\n"
                
                # Recommendations
                response += f"\n💡 **Scheduling Recommendations:**\n"
                
                completion_rate = (completed_counts / total_counts) * 100 if total_counts > 0 else 0
                if completion_rate < 90:
                    response += f"   • Completion rate is {completion_rate:.1f}% - review scheduling and resource allocation\n"
                
                if overdue_counts:
                    response += f"   • {len(overdue_counts)} overdue counts need immediate attention\n"
                
                if high_priority and pending_high_priority:
                    response += f"   • Prioritize {len(pending_high_priority)} pending high-priority counts\n"
                
                # Check for workload balance
                if zone_counts:
                    zone_totals = [stats["total"] for stats in zone_counts.values()]
                    max_zone = max(zone_totals)
                    min_zone = min(zone_totals)
                    if max_zone > min_zone * 2:
                        response += f"   • Workload imbalance across zones - consider redistribution\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing cycle count scheduling: {str(e)}"
    
    def _parse_schedule_query(self, query: str) -> Dict[str, Any]:
        """Parse scheduling query parameters"""
        query_lower = query.lower()
        params = {}
        
        import re
        
        # Extract count type
        if "full" in query_lower:
            params["count_type"] = "FULL"
        elif "spot" in query_lower:
            params["count_type"] = "SPOT"
        elif "blind" in query_lower:
            params["count_type"] = "BLIND"
        
        # Extract status
        if "scheduled" in query_lower:
            params["status"] = "SCHEDULED"
        elif "completed" in query_lower:
            params["status"] = "COMPLETED"
        elif "overdue" in query_lower:
            params["overdue"] = True
        
        # Extract zone
        zone_pattern = r'zone[:\s]+([a-zA-Z0-9-]+)'
        zone_match = re.search(zone_pattern, query_lower)
        if zone_match:
            params["zone_id"] = zone_match.group(1).upper()
        
        return params


class CountAccuracyTool(WMSBaseTool):
    """Tool for analyzing cycle count accuracy and variance tracking"""
    
    name = "count_accuracy"
    description = "Analyze cycle count accuracy, track variances, and identify accuracy trends"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute accuracy analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get count accuracy data
                accuracy_query = """
                SELECT 
                    cc.count_id,
                    cc.item_id,
                    i.item_description,
                    i.item_category,
                    cc.location_id,
                    l.zone_id,
                    cc.assigned_user_id,
                    u.full_name,
                    cc.count_date,
                    cc.count_type,
                    inv.quantity_on_hand as system_quantity,
                    cc.counted_quantity,
                    ABS(COALESCE(cc.counted_quantity, 0) - COALESCE(inv.quantity_on_hand, 0)) as variance_abs,
                    (COALESCE(cc.counted_quantity, 0) - COALESCE(inv.quantity_on_hand, 0)) as variance_signed,
                    CASE 
                        WHEN inv.quantity_on_hand > 0 THEN
                            ABS(COALESCE(cc.counted_quantity, 0) - COALESCE(inv.quantity_on_hand, 0)) / inv.quantity_on_hand * 100
                        ELSE 
                            CASE WHEN cc.counted_quantity > 0 THEN 100 ELSE 0 END
                    END as variance_percentage,
                    cc.count_reason,
                    cc.recount_required
                FROM cycle_counts cc
                JOIN items i ON cc.item_id = i.item_id
                LEFT JOIN locations l ON cc.location_id = l.location_id
                LEFT JOIN inventory inv ON cc.item_id = inv.item_id AND cc.location_id = inv.location_id
                LEFT JOIN users u ON cc.assigned_user_id = u.user_id
                WHERE cc.count_status = 'COMPLETED'
                    AND cc.count_date >= NOW() - INTERVAL '90 days'
                ORDER BY cc.count_date DESC
                LIMIT 500;
                """
                
                result = await session.execute(accuracy_query)
                accuracy_data = result.fetchall()
                
                if not accuracy_data:
                    return "No completed cycle count accuracy data available for the last 90 days."
                
                response = "🎯 **Cycle Count Accuracy Analysis (Last 90 days):**\n\n"
                
                # Overall accuracy metrics
                total_counts = len(accuracy_data)
                accurate_counts = len([c for c in accuracy_data if c.variance_abs == 0])
                minor_variance_counts = len([c for c in accuracy_data if 0 < c.variance_abs <= 5])
                major_variance_counts = len([c for c in accuracy_data if c.variance_abs > 5])
                
                overall_accuracy = (accurate_counts / total_counts) * 100 if total_counts > 0 else 0
                
                response += f"📊 **Overall Accuracy:**\n"
                response += f"   Total counts analyzed: {total_counts}\n"
                response += f"   Perfect accuracy: {accurate_counts} ({overall_accuracy:.1f}%)\n"
                response += f"   Minor variances (1-5): {minor_variance_counts} ({minor_variance_counts/total_counts*100:.1f}%)\n"
                response += f"   Major variances (>5): {major_variance_counts} ({major_variance_counts/total_counts*100:.1f}%)\n\n"
                
                # Variance statistics
                variances = [float(c.variance_abs) for c in accuracy_data]
                signed_variances = [float(c.variance_signed) for c in accuracy_data]
                
                if variances:
                    avg_variance = sum(variances) / len(variances)
                    max_variance = max(variances)
                    avg_signed_variance = sum(signed_variances) / len(signed_variances)
                    
                    positive_variances = [v for v in signed_variances if v > 0]
                    negative_variances = [v for v in signed_variances if v < 0]
                    
                    response += f"📏 **Variance Statistics:**\n"
                    response += f"   Average absolute variance: {avg_variance:.2f}\n"
                    response += f"   Maximum variance: {max_variance:.2f}\n"
                    response += f"   Average signed variance: {avg_signed_variance:+.2f}\n"
                    response += f"   Positive variances (overage): {len(positive_variances)}\n"
                    response += f"   Negative variances (shortage): {len(negative_variances)}\n\n"
                
                # Accuracy by count type
                type_accuracy = {}
                for count in accuracy_data:
                    ctype = count.count_type or "STANDARD"
                    if ctype not in type_accuracy:
                        type_accuracy[ctype] = {"total": 0, "accurate": 0, "variances": []}
                    type_accuracy[ctype]["total"] += 1
                    type_accuracy[ctype]["variances"].append(float(count.variance_abs))
                    if count.variance_abs == 0:
                        type_accuracy[ctype]["accurate"] += 1
                
                response += f"🔄 **Accuracy by Count Type:**\n"
                for ctype, stats in sorted(type_accuracy.items(), key=lambda x: x[1]["total"], reverse=True):
                    accuracy_rate = (stats["accurate"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                    avg_variance = sum(stats["variances"]) / len(stats["variances"]) if stats["variances"] else 0
                    
                    response += f"   {ctype}:\n"
                    response += f"      Accuracy rate: {accuracy_rate:.1f}%\n"
                    response += f"      Average variance: {avg_variance:.2f}\n"
                    response += f"      Total counts: {stats['total']}\n"
                
                # User performance analysis
                user_performance = {}
                for count in accuracy_data:
                    if count.assigned_user_id:
                        user_id = count.assigned_user_id
                        user_name = count.full_name or f"User {user_id}"
                        
                        if user_id not in user_performance:
                            user_performance[user_id] = {
                                "name": user_name, "total": 0, "accurate": 0, "variances": []
                            }
                        
                        user_performance[user_id]["total"] += 1
                        user_performance[user_id]["variances"].append(float(count.variance_abs))
                        if count.variance_abs == 0:
                            user_performance[user_id]["accurate"] += 1
                
                # Top performers by accuracy
                if user_performance:
                    top_performers = sorted(
                        [(user_id, stats) for user_id, stats in user_performance.items() if stats["total"] >= 5],
                        key=lambda x: x[1]["accurate"] / x[1]["total"],
                        reverse=True
                    )[:5]
                    
                    response += f"\n🏆 **Top Performers (accuracy, min 5 counts):**\n"
                    for user_id, stats in top_performers:
                        accuracy_rate = (stats["accurate"] / stats["total"]) * 100
                        avg_variance = sum(stats["variances"]) / len(stats["variances"])
                        
                        response += f"   {stats['name']}:\n"
                        response += f"      Accuracy: {accuracy_rate:.1f}% ({stats['accurate']}/{stats['total']})\n"
                        response += f"      Avg variance: {avg_variance:.2f}\n"
                
                # Zone accuracy analysis
                zone_accuracy = {}
                for count in accuracy_data:
                    if count.zone_id:
                        zone = count.zone_id
                        if zone not in zone_accuracy:
                            zone_accuracy[zone] = {"total": 0, "accurate": 0, "variances": []}
                        zone_accuracy[zone]["total"] += 1
                        zone_accuracy[zone]["variances"].append(float(count.variance_abs))
                        if count.variance_abs == 0:
                            zone_accuracy[zone]["accurate"] += 1
                
                if zone_accuracy:
                    response += f"\n📍 **Accuracy by Zone:**\n"
                    for zone, stats in sorted(zone_accuracy.items(), key=lambda x: x[1]["total"], reverse=True):
                        accuracy_rate = (stats["accurate"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                        avg_variance = sum(stats["variances"]) / len(stats["variances"]) if stats["variances"] else 0
                        
                        response += f"   Zone {zone}: {accuracy_rate:.1f}% accuracy, {avg_variance:.2f} avg variance ({stats['total']} counts)\n"
                
                # Item category accuracy
                category_accuracy = {}
                for count in accuracy_data:
                    category = count.item_category or "Unknown"
                    if category not in category_accuracy:
                        category_accuracy[category] = {"total": 0, "accurate": 0, "variances": []}
                    category_accuracy[category]["total"] += 1
                    category_accuracy[category]["variances"].append(float(count.variance_abs))
                    if count.variance_abs == 0:
                        category_accuracy[category]["accurate"] += 1
                
                response += f"\n📂 **Accuracy by Item Category:**\n"
                sorted_categories = sorted(category_accuracy.items(), key=lambda x: x[1]["total"], reverse=True)
                for category, stats in sorted_categories[:5]:
                    accuracy_rate = (stats["accurate"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                    avg_variance = sum(stats["variances"]) / len(stats["variances"]) if stats["variances"] else 0
                    
                    response += f"   {category}: {accuracy_rate:.1f}% accuracy, {avg_variance:.2f} avg variance\n"
                
                # Identify problem areas
                high_variance_items = [
                    count for count in accuracy_data 
                    if count.variance_abs > 10 or count.variance_percentage > 20
                ]
                
                if high_variance_items:
                    response += f"\n⚠️ **High Variance Items:** {len(high_variance_items)}\n"
                    # Group by item
                    item_variances = {}
                    for count in high_variance_items:
                        item_id = count.item_id
                        if item_id not in item_variances:
                            item_variances[item_id] = []
                        item_variances[item_id].append(count.variance_abs)
                    
                    # Items with multiple high variances
                    repeat_offenders = {item: vars for item, vars in item_variances.items() if len(vars) > 1}
                    if repeat_offenders:
                        response += f"   Items with multiple high variances: {len(repeat_offenders)}\n"
                        for item_id, variances in sorted(repeat_offenders.items(), key=lambda x: len(x[1]), reverse=True)[:3]:
                            response += f"      {item_id}: {len(variances)} high variances\n"
                
                # Recount analysis
                recounts_required = [count for count in accuracy_data if count.recount_required]
                if recounts_required:
                    response += f"\n🔄 **Recounts Required:** {len(recounts_required)} ({len(recounts_required)/total_counts*100:.1f}%)\n"
                
                # Recommendations
                response += f"\n💡 **Accuracy Recommendations:**\n"
                
                if overall_accuracy < 85:
                    response += f"   • Overall accuracy is {overall_accuracy:.1f}% - investigate root causes\n"
                
                if major_variance_counts > total_counts * 0.1:  # More than 10%
                    response += f"   • {major_variance_counts} counts have major variances - review counting procedures\n"
                
                if user_performance:
                    poor_performers = [
                        (uid, stats) for uid, stats in user_performance.items() 
                        if stats["total"] >= 5 and (stats["accurate"] / stats["total"]) < 0.8
                    ]
                    if poor_performers:
                        response += f"   • Provide additional training for {len(poor_performers)} users with <80% accuracy\n"
                
                if avg_signed_variance > 1:
                    response += f"   • Positive bias detected (+{avg_signed_variance:.2f}) - investigate overage patterns\n"
                elif avg_signed_variance < -1:
                    response += f"   • Negative bias detected ({avg_signed_variance:.2f}) - investigate shortage patterns\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing count accuracy: {str(e)}"


class CountPerformanceTool(WMSBaseTool):
    """Tool for cycle count performance and efficiency analysis"""
    
    name = "count_performance"
    description = "Analyze cycle count performance, completion times, and productivity metrics"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute performance analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get count performance data
                performance_query = """
                SELECT 
                    cc.assigned_user_id,
                    u.full_name,
                    DATE(cc.count_date) as count_day,
                    cc.count_type,
                    COUNT(*) as counts_completed,
                    AVG(CASE 
                        WHEN cc.count_completed_at IS NOT NULL AND cc.count_started_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (cc.count_completed_at - cc.count_started_at)) / 60
                        ELSE NULL
                    END) as avg_count_time_minutes,
                    SUM(CASE 
                        WHEN cc.count_completed_at IS NOT NULL AND cc.count_started_at IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (cc.count_completed_at - cc.count_started_at)) / 60
                        ELSE 0
                    END) as total_count_time_minutes,
                    AVG(ABS(COALESCE(cc.counted_quantity, 0) - COALESCE(inv.quantity_on_hand, 0))) as avg_variance,
                    COUNT(CASE WHEN cc.recount_required = true THEN 1 END) as recounts_required
                FROM cycle_counts cc
                LEFT JOIN users u ON cc.assigned_user_id = u.user_id
                LEFT JOIN inventory inv ON cc.item_id = inv.item_id AND cc.location_id = inv.location_id
                WHERE cc.count_status = 'COMPLETED'
                    AND cc.count_date >= NOW() - INTERVAL '30 days'
                    AND cc.assigned_user_id IS NOT NULL
                GROUP BY cc.assigned_user_id, u.full_name, DATE(cc.count_date), cc.count_type
                ORDER BY count_day DESC, counts_completed DESC
                LIMIT 200;
                """
                
                result = await session.execute(performance_query)
                performance_data = result.fetchall()
                
                if not performance_data:
                    return "No cycle count performance data available for the last 30 days."
                
                response = "🚀 **Cycle Count Performance Analysis (Last 30 days):**\n\n"
                
                # Aggregate user performance
                user_performance = {}
                for record in performance_data:
                    user_id = record.assigned_user_id
                    user_name = record.full_name or f"User {user_id}"
                    
                    if user_id not in user_performance:
                        user_performance[user_id] = {
                            "name": user_name,
                            "total_counts": 0,
                            "total_time": 0,
                            "total_variance": 0,
                            "total_recounts": 0,
                            "work_days": set(),
                            "count_types": set()
                        }
                    
                    user_performance[user_id]["total_counts"] += record.counts_completed
                    user_performance[user_id]["total_time"] += float(record.total_count_time_minutes or 0)
                    user_performance[user_id]["total_variance"] += float(record.avg_variance or 0) * record.counts_completed
                    user_performance[user_id]["total_recounts"] += record.recounts_required or 0
                    user_performance[user_id]["work_days"].add(record.count_day)
                    user_performance[user_id]["count_types"].add(record.count_type)
                
                # Calculate overall metrics
                total_users = len(user_performance)
                total_counts = sum(user["total_counts"] for user in user_performance.values())
                total_time = sum(user["total_time"] for user in user_performance.values())
                total_recounts = sum(user["total_recounts"] for user in user_performance.values())
                
                avg_counts_per_user = total_counts / total_users if total_users > 0 else 0
                avg_time_per_count = total_time / total_counts if total_counts > 0 else 0
                recount_rate = (total_recounts / total_counts) * 100 if total_counts > 0 else 0
                
                response += f"🎯 **Overall Performance:**\n"
                response += f"   Active counters: {total_users}\n"
                response += f"   Total counts completed: {total_counts:,}\n"
                response += f"   Average counts per user: {avg_counts_per_user:.1f}\n"
                response += f"   Average time per count: {avg_time_per_count:.1f} minutes\n"
                response += f"   Total counting time: {total_time/60:.1f} hours\n"
                response += f"   Recount rate: {recount_rate:.1f}%\n\n"
                
                # Top performers by different metrics
                # By count volume
                top_by_volume = sorted(
                    user_performance.items(),
                    key=lambda x: x[1]["total_counts"],
                    reverse=True
                )[:5]
                
                response += f"🏆 **Top Performers (by volume):**\n"
                for user_id, stats in top_by_volume:
                    daily_avg = stats["total_counts"] / len(stats["work_days"]) if stats["work_days"] else 0
                    avg_time_per_count = stats["total_time"] / stats["total_counts"] if stats["total_counts"] > 0 else 0
                    recount_rate = (stats["total_recounts"] / stats["total_counts"]) * 100 if stats["total_counts"] > 0 else 0
                    
                    response += f"   {stats['name']}:\n"
                    response += f"      Total counts: {stats['total_counts']}\n"
                    response += f"      Daily average: {daily_avg:.1f}\n"
                    response += f"      Avg time per count: {avg_time_per_count:.1f} min\n"
                    response += f"      Recount rate: {recount_rate:.1f}%\n"
                    response += f"      Work days: {len(stats['work_days'])}\n"
                
                # Speed analysis (fastest counters)
                speed_performers = [
                    (user_id, stats) for user_id, stats in user_performance.items()
                    if stats["total_counts"] >= 10  # Minimum threshold
                ]
                
                if speed_performers:
                    speed_performers.sort(key=lambda x: x[1]["total_time"] / x[1]["total_counts"])
                    
                    response += f"\n⚡ **Fastest Counters (min 10 counts):**\n"
                    for user_id, stats in speed_performers[:5]:
                        avg_time = stats["total_time"] / stats["total_counts"]
                        response += f"   {stats['name']}: {avg_time:.1f} min/count ({stats['total_counts']} counts)\n"
                
                # Count type performance
                count_type_performance = {}
                for record in performance_data:
                    ctype = record.count_type
                    if ctype not in count_type_performance:
                        count_type_performance[ctype] = {
                            "total_counts": 0, "total_time": 0, "total_recounts": 0, "users": set()
                        }
                    
                    count_type_performance[ctype]["total_counts"] += record.counts_completed
                    count_type_performance[ctype]["total_time"] += float(record.total_count_time_minutes or 0)
                    count_type_performance[ctype]["total_recounts"] += record.recounts_required or 0
                    count_type_performance[ctype]["users"].add(record.assigned_user_id)
                
                response += f"\n📊 **Performance by Count Type:**\n"
                for ctype, stats in sorted(count_type_performance.items(), key=lambda x: x[1]["total_counts"], reverse=True):
                    avg_time = stats["total_time"] / stats["total_counts"] if stats["total_counts"] > 0 else 0
                    recount_rate = (stats["total_recounts"] / stats["total_counts"]) * 100 if stats["total_counts"] > 0 else 0
                    
                    response += f"   {ctype}:\n"
                    response += f"      Users: {len(stats['users'])}\n"
                    response += f"      Avg time per count: {avg_time:.1f} minutes\n"
                    response += f"      Recount rate: {recount_rate:.1f}%\n"
                    response += f"      Total counts: {stats['total_counts']}\n"
                
                # Daily productivity trends
                daily_productivity = {}
                for record in performance_data:
                    date = record.count_day
                    if date not in daily_productivity:
                        daily_productivity[date] = {"counts": 0, "time": 0, "users": set()}
                    daily_productivity[date]["counts"] += record.counts_completed
                    daily_productivity[date]["time"] += float(record.total_count_time_minutes or 0)
                    daily_productivity[date]["users"].add(record.assigned_user_id)
                
                if len(daily_productivity) >= 2:
                    sorted_days = sorted(daily_productivity.items(), key=lambda x: x[0], reverse=True)
                    
                    response += f"\n📅 **Daily Productivity Trends:**\n"
                    for date, stats in sorted_days[:7]:
                        avg_time_per_count = stats["time"] / stats["counts"] if stats["counts"] > 0 else 0
                        counts_per_user = stats["counts"] / len(stats["users"]) if stats["users"] else 0
                        
                        response += f"   {date.strftime('%Y-%m-%d')}:\n"
                        response += f"      Counts: {stats['counts']} by {len(stats['users'])} users\n"
                        response += f"      Avg per user: {counts_per_user:.1f}\n"
                        response += f"      Avg time: {avg_time_per_count:.1f} min/count\n"
                
                # Performance insights
                high_performers = [
                    user_id for user_id, stats in user_performance.items()
                    if stats["total_counts"] >= avg_counts_per_user * 1.5  # 50% above average
                ]
                
                consistent_performers = [
                    user_id for user_id, stats in user_performance.items()
                    if len(stats["work_days"]) >= 20  # 20+ active days
                ]
                
                quality_performers = [
                    user_id for user_id, stats in user_performance.items()
                    if stats["total_counts"] >= 10 and (stats["total_recounts"] / stats["total_counts"]) < 0.05  # <5% recount rate
                ]
                
                response += f"\n📈 **Performance Insights:**\n"
                response += f"   High volume performers: {len(high_performers)} (>150% avg volume)\n"
                response += f"   Consistent workers: {len(consistent_performers)} (20+ active days)\n"
                response += f"   Quality performers: {len(quality_performers)} (<5% recount rate)\n"
                
                # Recommendations
                response += f"\n💡 **Performance Recommendations:**\n"
                
                if avg_time_per_count > 15:  # More than 15 minutes per count
                    response += f"   • Average count time is {avg_time_per_count:.1f} minutes - investigate efficiency opportunities\n"
                
                if recount_rate > 10:
                    response += f"   • Recount rate is {recount_rate:.1f}% - review counting procedures and training\n"
                
                # Check for skill development opportunities
                versatile_counters = [
                    user_id for user_id, stats in user_performance.items()
                    if len(stats["count_types"]) >= 3
                ]
                
                if len(versatile_counters) < total_users * 0.5:
                    response += f"   • Only {len(versatile_counters)} users work multiple count types - consider cross-training\n"
                
                # Workload balance
                count_volumes = [stats["total_counts"] for stats in user_performance.values()]
                if count_volumes:
                    max_counts = max(count_volumes)
                    min_counts = min(count_volumes)
                    if max_counts > min_counts * 3:
                        response += f"   • Significant workload imbalance detected - consider redistribution\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing count performance: {str(e)}"


# Functional Agent - Business processes and workflows
class CycleCountingFunctionalAgent(WMSBaseAgent):
    """Handles functional aspects of cycle counting"""
    
    def __init__(self):
        tools = [
            CycleCountSchedulingTool("cycle_counting", "functional"),
            CountAccuracyTool("cycle_counting", "functional"),
            CountPerformanceTool("cycle_counting", "functional")
        ]
        super().__init__("cycle_counting", "functional", tools)
    
    def _get_specialization(self) -> str:
        return "Cycle counting workflows, count scheduling, accuracy validation, and variance resolution"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "count_scheduling",
            "accuracy_validation",
            "variance_analysis",
            "count_coordination",
            "performance_tracking",
            "workflow_optimization"
        ]


# Technical Agent - System specifications
class CycleCountingTechnicalAgent(WMSBaseAgent):
    """Handles technical aspects of cycle counting"""
    
    def __init__(self):
        tools = [CycleCountSchedulingTool("cycle_counting", "technical")]
        super().__init__("cycle_counting", "technical", tools)
    
    def _get_specialization(self) -> str:
        return "Count scheduling algorithms, mobile counting systems, and automated variance detection"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "scheduling_algorithms",
            "mobile_integration",
            "automated_validation",
            "variance_detection",
            "system_integration",
            "real_time_processing"
        ]


# Configuration Agent - Setup and parameters
class CycleCountingConfigurationAgent(WMSBaseAgent):
    """Handles cycle counting configuration"""
    
    def __init__(self):
        tools = [CountAccuracyTool("cycle_counting", "configuration")]
        super().__init__("cycle_counting", "configuration", tools)
    
    def _get_specialization(self) -> str:
        return "Count frequency setup, tolerance configuration, and accuracy threshold management"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "frequency_configuration",
            "tolerance_settings",
            "threshold_management",
            "rule_configuration",
            "policy_setup",
            "validation_rules"
        ]


# Relationships Agent - Integration with other modules
class CycleCountingRelationshipsAgent(WMSBaseAgent):
    """Handles cycle counting relationships with other WMS modules"""
    
    def __init__(self):
        tools = [CycleCountSchedulingTool("cycle_counting", "relationships")]
        super().__init__("cycle_counting", "relationships", tools)
    
    def _get_specialization(self) -> str:
        return "Count integration with inventory management, adjustments, and financial reconciliation"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "inventory_integration",
            "adjustment_processing",
            "financial_reconciliation",
            "audit_trail_management",
            "cross_module_sync",
            "workflow_coordination"
        ]


# Notes Agent - Best practices and recommendations
class CycleCountingNotesAgent(WMSBaseAgent):
    """Provides cycle counting best practices and recommendations"""
    
    def __init__(self):
        tools = [CountPerformanceTool("cycle_counting", "notes")]
        super().__init__("cycle_counting", "notes", tools)
    
    def _get_specialization(self) -> str:
        return "Counting accuracy best practices, frequency optimization, and continuous improvement strategies"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "accuracy_best_practices",
            "frequency_optimization",
            "training_guidelines",
            "process_improvement",
            "quality_standards",
            "performance_benchmarking"
        ]