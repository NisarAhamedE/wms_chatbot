"""
Receiving management agents (Category 4) - 5 specialized sub-category agents.
Handles all aspects of inbound receiving including ASN processing, receipt validation, and putaway initiation.
"""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import WMSBaseAgent, WMSBaseTool, WMSContext
from ...database.models import (
    ReceivingTransaction, Item, Location, Inventory, 
    InventoryMovement, AdvancedShipmentNotice
)


class ReceiptProcessingTool(WMSBaseTool):
    """Tool for processing incoming receipts and ASNs"""
    
    name = "receipt_processing"
    description = "Process incoming receipts, validate against ASNs, and manage receipt workflows"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute receipt processing"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Parse receipt parameters
                receipt_params = self._parse_receipt_query(query)
                
                # Get recent receiving transactions
                stmt = (
                    select(
                        ReceivingTransaction.transaction_id,
                        ReceivingTransaction.receipt_number,
                        ReceivingTransaction.item_id,
                        Item.item_description,
                        ReceivingTransaction.expected_quantity,
                        ReceivingTransaction.received_quantity,
                        ReceivingTransaction.receipt_date,
                        ReceivingTransaction.receipt_status,
                        ReceivingTransaction.supplier_id,
                        ReceivingTransaction.po_number
                    )
                    .join(Item, ReceivingTransaction.item_id == Item.item_id)
                )
                
                # Apply filters
                if receipt_params.get("receipt_number"):
                    stmt = stmt.where(ReceivingTransaction.receipt_number.ilike(f"%{receipt_params['receipt_number']}%"))
                if receipt_params.get("po_number"):
                    stmt = stmt.where(ReceivingTransaction.po_number.ilike(f"%{receipt_params['po_number']}%"))
                if receipt_params.get("status"):
                    stmt = stmt.where(ReceivingTransaction.receipt_status == receipt_params["status"])
                if receipt_params.get("date_range"):
                    start_date = datetime.utcnow() - timedelta(days=receipt_params["date_range"])
                    stmt = stmt.where(ReceivingTransaction.receipt_date >= start_date)
                
                # Execute query
                result = await session.execute(stmt.order_by(ReceivingTransaction.receipt_date.desc()).limit(50))
                receipts = result.fetchall()
                
                if not receipts:
                    return "No receiving transactions found matching the specified criteria."
                
                # Format results
                response = f"📦 **Found {len(receipts)} receiving transaction(s):**\n\n"
                
                # Summary statistics
                total_receipts = len(receipts)
                pending_receipts = len([r for r in receipts if r.receipt_status == 'PENDING'])
                completed_receipts = len([r for r in receipts if r.receipt_status == 'COMPLETED'])
                discrepancy_receipts = len([r for r in receipts if r.expected_quantity != r.received_quantity])
                
                response += f"📊 **Summary:**\n"
                response += f"   Total receipts: {total_receipts}\n"
                response += f"   Pending: {pending_receipts}\n"
                response += f"   Completed: {completed_receipts}\n"
                response += f"   With discrepancies: {discrepancy_receipts}\n\n"
                
                # Recent receipts
                response += f"📋 **Recent Receipts:**\n"
                for receipt in receipts[:10]:
                    status_emoji = "✅" if receipt.receipt_status == "COMPLETED" else "⏳" if receipt.receipt_status == "PENDING" else "⚠️"
                    
                    response += f"{status_emoji} **{receipt.receipt_number}**\n"
                    response += f"   📅 Date: {receipt.receipt_date.strftime('%Y-%m-%d %H:%M')}\n"
                    response += f"   🏷️ Item: {receipt.item_id} - {receipt.item_description[:40]}...\n"
                    response += f"   📊 Qty: {receipt.received_quantity}/{receipt.expected_quantity}\n"
                    
                    if receipt.po_number:
                        response += f"   📝 PO: {receipt.po_number}\n"
                    if receipt.supplier_id:
                        response += f"   🏢 Supplier: {receipt.supplier_id}\n"
                    
                    # Check for discrepancy
                    if receipt.expected_quantity != receipt.received_quantity:
                        variance = receipt.received_quantity - receipt.expected_quantity
                        response += f"   ⚠️ Variance: {variance:+.2f}\n"
                    
                    response += f"   🔄 Status: {receipt.receipt_status}\n\n"
                
                # Highlight issues
                if discrepancy_receipts > 0:
                    response += f"⚠️ **Attention Required:**\n"
                    response += f"   {discrepancy_receipts} receipts have quantity discrepancies\n"
                    response += f"   Review and resolve variances before putaway\n\n"
                
                if pending_receipts > 0:
                    response += f"⏳ **Pending Actions:**\n"
                    response += f"   {pending_receipts} receipts awaiting completion\n"
                    response += f"   Process receipts to continue putaway workflow\n"
                
                return response
                
        except Exception as e:
            return f"Error processing receipts: {str(e)}"
    
    def _parse_receipt_query(self, query: str) -> Dict[str, Any]:
        """Parse receipt query parameters"""
        query_lower = query.lower()
        params = {}
        
        import re
        
        # Extract receipt number
        receipt_pattern = r'receipt[:\s]+([a-zA-Z0-9-]+)'
        receipt_match = re.search(receipt_pattern, query_lower)
        if receipt_match:
            params["receipt_number"] = receipt_match.group(1).upper()
        
        # Extract PO number
        po_pattern = r'(?:po|purchase order)[:\s]+([a-zA-Z0-9-]+)'
        po_match = re.search(po_pattern, query_lower)
        if po_match:
            params["po_number"] = po_match.group(1).upper()
        
        # Extract status
        if "pending" in query_lower:
            params["status"] = "PENDING"
        elif "completed" in query_lower:
            params["status"] = "COMPLETED"
        elif "discrepancy" in query_lower or "variance" in query_lower:
            params["status"] = "DISCREPANCY"
        
        # Extract date range
        if "today" in query_lower:
            params["date_range"] = 1
        elif "week" in query_lower:
            params["date_range"] = 7
        elif "month" in query_lower:
            params["date_range"] = 30
        else:
            params["date_range"] = 7  # Default to last week
        
        return params


class ASNValidationTool(WMSBaseTool):
    """Tool for ASN validation and processing"""
    
    name = "asn_validation"
    description = "Validate Advanced Shipment Notices and track compliance"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute ASN validation"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get ASN data with validation status
                asn_query = """
                SELECT 
                    asn.asn_number,
                    asn.supplier_id,
                    asn.expected_arrival_date,
                    asn.asn_status,
                    asn.total_lines,
                    asn.created_at,
                    COUNT(rt.transaction_id) as receipts_processed,
                    SUM(CASE WHEN rt.receipt_status = 'COMPLETED' THEN 1 ELSE 0 END) as receipts_completed,
                    AVG(CASE 
                        WHEN rt.expected_quantity > 0 THEN 
                            ABS(rt.received_quantity - rt.expected_quantity) / rt.expected_quantity * 100
                        ELSE 0 
                    END) as avg_variance_pct
                FROM advanced_shipment_notices asn
                LEFT JOIN receiving_transactions rt ON asn.asn_number = rt.asn_number
                WHERE asn.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY asn.asn_number, asn.supplier_id, asn.expected_arrival_date, 
                         asn.asn_status, asn.total_lines, asn.created_at
                ORDER BY asn.created_at DESC
                LIMIT 50;
                """
                
                result = await session.execute(asn_query)
                asn_data = result.fetchall()
                
                if not asn_data:
                    return "No ASN data available for the last 30 days."
                
                response = "📋 **ASN Validation Analysis:**\n\n"
                
                # ASN statistics
                total_asns = len(asn_data)
                received_asns = len([asn for asn in asn_data if asn.asn_status == 'RECEIVED'])
                pending_asns = len([asn for asn in asn_data if asn.asn_status == 'PENDING'])
                processing_asns = len([asn for asn in asn_data if asn.asn_status == 'PROCESSING'])
                
                response += f"📊 **ASN Summary (Last 30 days):**\n"
                response += f"   Total ASNs: {total_asns}\n"
                response += f"   Received: {received_asns}\n"
                response += f"   Processing: {processing_asns}\n"
                response += f"   Pending: {pending_asns}\n\n"
                
                # Validation accuracy
                asns_with_receipts = [asn for asn in asn_data if asn.receipts_processed > 0]
                if asns_with_receipts:
                    avg_completion_rate = sum(
                        (asn.receipts_completed / asn.receipts_processed) * 100 
                        for asn in asns_with_receipts
                    ) / len(asns_with_receipts)
                    
                    avg_variance = sum(
                        asn.avg_variance_pct or 0 for asn in asns_with_receipts
                    ) / len(asns_with_receipts)
                    
                    response += f"✅ **Validation Metrics:**\n"
                    response += f"   Average completion rate: {avg_completion_rate:.1f}%\n"
                    response += f"   Average quantity variance: {avg_variance:.1f}%\n\n"
                
                # Recent ASNs
                response += f"📦 **Recent ASNs:**\n"
                for asn in asn_data[:10]:
                    status_emoji = "✅" if asn.asn_status == "RECEIVED" else "🔄" if asn.asn_status == "PROCESSING" else "⏳"
                    
                    response += f"{status_emoji} **{asn.asn_number}**\n"
                    response += f"   🏢 Supplier: {asn.supplier_id}\n"
                    response += f"   📅 Expected: {asn.expected_arrival_date.strftime('%Y-%m-%d')}\n"
                    response += f"   📊 Lines: {asn.total_lines}\n"
                    
                    if asn.receipts_processed:
                        completion_pct = (asn.receipts_completed / asn.receipts_processed) * 100
                        response += f"   🔄 Progress: {asn.receipts_completed}/{asn.receipts_processed} ({completion_pct:.0f}%)\n"
                        
                        if asn.avg_variance_pct:
                            response += f"   📏 Avg Variance: {asn.avg_variance_pct:.1f}%\n"
                    
                    response += f"   🔄 Status: {asn.asn_status}\n\n"
                
                # ASNs needing attention
                problem_asns = [
                    asn for asn in asn_data 
                    if asn.avg_variance_pct and asn.avg_variance_pct > 5.0
                ]
                
                if problem_asns:
                    response += f"⚠️ **ASNs with High Variance (>5%):**\n"
                    for asn in problem_asns[:5]:
                        response += f"   {asn.asn_number}: {asn.avg_variance_pct:.1f}% variance\n"
                    response += "\n"
                
                # Overdue ASNs
                current_date = datetime.utcnow().date()
                overdue_asns = [
                    asn for asn in asn_data 
                    if asn.expected_arrival_date < current_date and asn.asn_status != 'RECEIVED'
                ]
                
                if overdue_asns:
                    response += f"🚨 **Overdue ASNs:**\n"
                    for asn in overdue_asns:
                        days_overdue = (current_date - asn.expected_arrival_date).days
                        response += f"   {asn.asn_number}: {days_overdue} days overdue\n"
                
                return response
                
        except Exception as e:
            return f"Error validating ASNs: {str(e)}"


class ReceivingMetricsTool(WMSBaseTool):
    """Tool for receiving performance metrics and KPIs"""
    
    name = "receiving_metrics"
    description = "Analyze receiving performance, throughput, and accuracy metrics"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute metrics analysis"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get receiving performance metrics
                metrics_query = """
                SELECT 
                    DATE(rt.receipt_date) as receipt_day,
                    COUNT(*) as total_receipts,
                    SUM(rt.received_quantity) as total_quantity,
                    AVG(rt.received_quantity) as avg_quantity_per_receipt,
                    COUNT(DISTINCT rt.item_id) as unique_items,
                    COUNT(DISTINCT rt.supplier_id) as unique_suppliers,
                    SUM(CASE WHEN rt.receipt_status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_receipts,
                    AVG(CASE 
                        WHEN rt.expected_quantity > 0 THEN 
                            ABS(rt.received_quantity - rt.expected_quantity) / rt.expected_quantity * 100
                        ELSE 0 
                    END) as avg_accuracy_variance
                FROM receiving_transactions rt
                WHERE rt.receipt_date >= NOW() - INTERVAL '30 days'
                GROUP BY DATE(rt.receipt_date)
                ORDER BY receipt_day DESC
                LIMIT 30;
                """
                
                result = await session.execute(metrics_query)
                daily_metrics = result.fetchall()
                
                if not daily_metrics:
                    return "No receiving metrics data available."
                
                response = "📈 **Receiving Performance Metrics (Last 30 days):**\n\n"
                
                # Overall statistics
                total_receipts = sum(day.total_receipts for day in daily_metrics)
                total_quantity = sum(float(day.total_quantity) for day in daily_metrics)
                total_completed = sum(day.completed_receipts for day in daily_metrics)
                avg_accuracy = sum(float(day.avg_accuracy_variance or 0) for day in daily_metrics) / len(daily_metrics)
                
                completion_rate = (total_completed / total_receipts) * 100 if total_receipts > 0 else 0
                daily_avg_receipts = total_receipts / len(daily_metrics)
                daily_avg_quantity = total_quantity / len(daily_metrics)
                
                response += f"🎯 **Overall Performance:**\n"
                response += f"   Total receipts processed: {total_receipts:,}\n"
                response += f"   Total quantity received: {total_quantity:,.2f}\n"
                response += f"   Completion rate: {completion_rate:.1f}%\n"
                response += f"   Average accuracy: {100 - avg_accuracy:.1f}%\n"
                response += f"   Daily average receipts: {daily_avg_receipts:.1f}\n"
                response += f"   Daily average quantity: {daily_avg_quantity:,.1f}\n\n"
                
                # Daily breakdown (last 7 days)
                response += f"📅 **Daily Breakdown (Last 7 days):**\n"
                for day in daily_metrics[:7]:
                    completion_pct = (day.completed_receipts / day.total_receipts) * 100 if day.total_receipts > 0 else 0
                    accuracy_pct = 100 - (day.avg_accuracy_variance or 0)
                    
                    response += f"   {day.receipt_day.strftime('%Y-%m-%d')}:\n"
                    response += f"      Receipts: {day.total_receipts} ({completion_pct:.0f}% completed)\n"
                    response += f"      Quantity: {day.total_quantity:,.1f}\n"
                    response += f"      Items: {day.unique_items}, Suppliers: {day.unique_suppliers}\n"
                    response += f"      Accuracy: {accuracy_pct:.1f}%\n"
                
                # Performance trends
                if len(daily_metrics) >= 7:
                    recent_week = daily_metrics[:7]
                    previous_week = daily_metrics[7:14] if len(daily_metrics) >= 14 else daily_metrics[7:]
                    
                    if previous_week:
                        recent_avg = sum(day.total_receipts for day in recent_week) / len(recent_week)
                        previous_avg = sum(day.total_receipts for day in previous_week) / len(previous_week)
                        
                        if previous_avg > 0:
                            trend_pct = ((recent_avg - previous_avg) / previous_avg) * 100
                            trend_direction = "📈" if trend_pct > 0 else "📉" if trend_pct < 0 else "➡️"
                            
                            response += f"\n{trend_direction} **Weekly Trend:**\n"
                            response += f"   Volume change: {trend_pct:+.1f}%\n"
                            response += f"   Recent week avg: {recent_avg:.1f} receipts/day\n"
                            response += f"   Previous week avg: {previous_avg:.1f} receipts/day\n"
                
                # Peak performance analysis
                best_day = max(daily_metrics, key=lambda x: x.total_receipts)
                worst_accuracy_day = max(daily_metrics, key=lambda x: x.avg_accuracy_variance or 0)
                
                response += f"\n🏆 **Performance Highlights:**\n"
                response += f"   Best volume day: {best_day.receipt_day.strftime('%Y-%m-%d')} ({best_day.total_receipts} receipts)\n"
                if worst_accuracy_day.avg_accuracy_variance and worst_accuracy_day.avg_accuracy_variance > 5:
                    response += f"   Attention needed: {worst_accuracy_day.receipt_day.strftime('%Y-%m-%d')} ({worst_accuracy_day.avg_accuracy_variance:.1f}% variance)\n"
                
                return response
                
        except Exception as e:
            return f"Error analyzing metrics: {str(e)}"


# Functional Agent - Business processes and workflows
class ReceivingFunctionalAgent(WMSBaseAgent):
    """Handles functional aspects of receiving management"""
    
    def __init__(self):
        tools = [
            ReceiptProcessingTool("receiving", "functional"),
            ASNValidationTool("receiving", "functional"),
            ReceivingMetricsTool("receiving", "functional")
        ]
        super().__init__("receiving", "functional", tools)
    
    def _get_specialization(self) -> str:
        return "Inbound receiving workflows, ASN processing, receipt validation, and dock management"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "receipt_processing",
            "asn_validation",
            "dock_scheduling",
            "quality_inspection",
            "putaway_initiation",
            "supplier_performance"
        ]


# Technical Agent - System specifications
class ReceivingTechnicalAgent(WMSBaseAgent):
    """Handles technical aspects of receiving management"""
    
    def __init__(self):
        tools = [ReceiptProcessingTool("receiving", "technical")]
        super().__init__("receiving", "technical", tools)
    
    def _get_specialization(self) -> str:
        return "EDI processing, barcode scanning, RFID integration, and automated receiving systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "edi_processing",
            "barcode_scanning",
            "rfid_integration",
            "automated_validation",
            "system_integration",
            "data_synchronization"
        ]


# Configuration Agent - Setup and parameters
class ReceivingConfigurationAgent(WMSBaseAgent):
    """Handles receiving configuration and setup"""
    
    def __init__(self):
        tools = [ASNValidationTool("receiving", "configuration")]
        super().__init__("receiving", "configuration", tools)
    
    def _get_specialization(self) -> str:
        return "Receiving policies, validation rules, tolerance settings, and workflow configuration"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "policy_configuration",
            "validation_rules",
            "tolerance_settings",
            "workflow_setup",
            "dock_configuration",
            "supplier_setup"
        ]


# Relationships Agent - Integration with other modules
class ReceivingRelationshipsAgent(WMSBaseAgent):
    """Handles receiving relationships with other WMS modules"""
    
    def __init__(self):
        tools = [ReceiptProcessingTool("receiving", "relationships")]
        super().__init__("receiving", "relationships", tools)
    
    def _get_specialization(self) -> str:
        return "Receiving integration with inventory, putaway, quality control, and purchasing systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "inventory_integration",
            "putaway_coordination",
            "quality_integration",
            "purchasing_linkage",
            "cross_docking",
            "workflow_orchestration"
        ]


# Notes Agent - Best practices and recommendations
class ReceivingNotesAgent(WMSBaseAgent):
    """Provides receiving management best practices and recommendations"""
    
    def __init__(self):
        tools = [ReceivingMetricsTool("receiving", "notes")]
        super().__init__("receiving", "notes", tools)
    
    def _get_specialization(self) -> str:
        return "Receiving accuracy best practices, throughput optimization, and supplier compliance strategies"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "accuracy_best_practices",
            "throughput_optimization",
            "supplier_compliance",
            "process_improvement",
            "kpi_optimization",
            "training_guidelines"
        ]