"""
Data categorization agents (Category 16) - 5 specialized sub-category agents.
Handles automatic data classification, validation, and multi-category assignment.
"""

import json
import hashlib
import uuid
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import WMSBaseAgent, WMSBaseTool, WMSContext
from ...database.models import (
    DataCategorizationRequest, DataCategoryAssignment, 
    DataValidationRule, DataValidationResult, DataStorageMapping,
    WMSCategory, WMSSubCategory
)


class DataClassificationTool(WMSBaseTool):
    """Tool for automatic data classification using ML and pattern matching"""
    
    name = "data_classification"
    description = "Automatically classify incoming data into appropriate WMS categories and sub-categories"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute data classification"""
        try:
            # Parse the data from query (in real implementation, this would be structured data)
            data_to_classify = self._parse_input_data(query)
            
            if not data_to_classify:
                return "No data provided for classification. Please provide data in JSON format or describe the data to classify."
            
            # Perform classification
            classification_result = await self._classify_data(data_to_classify, context)
            
            # Format results
            response = "🤖 **Data Classification Results:**\n\n"
            
            if classification_result["success"]:
                response += f"📊 **Primary Category:** {classification_result['primary_category']}\n"
                response += f"   Confidence: {classification_result['primary_confidence']:.2%}\n\n"
                
                if classification_result.get("secondary_categories"):
                    response += f"📋 **Secondary Categories:**\n"
                    for cat, conf in classification_result["secondary_categories"]:
                        response += f"   • {cat}: {conf:.2%}\n"
                    response += "\n"
                
                response += f"🔍 **Classification Method:** {classification_result['method']}\n"
                response += f"⏱️ **Processing Time:** {classification_result['processing_time']:.3f}s\n"
                
                if classification_result.get("warnings"):
                    response += f"\n⚠️ **Warnings:**\n"
                    for warning in classification_result["warnings"]:
                        response += f"   • {warning}\n"
                
                if classification_result.get("manual_review_required"):
                    response += f"\n🔍 **Manual Review Required:** {classification_result['manual_review_reason']}\n"
            else:
                response += f"❌ **Classification Failed:** {classification_result['error']}\n"
            
            return response
            
        except Exception as e:
            return f"Error during classification: {str(e)}"
    
    def _parse_input_data(self, query: str) -> Optional[Dict[str, Any]]:
        """Parse input data from query"""
        query = query.strip()
        
        # Try to parse as JSON first
        try:
            return json.loads(query)
        except json.JSONDecodeError:
            pass
        
        # Try to extract structured information from text
        if any(keyword in query.lower() for keyword in ["location", "item", "inventory", "order", "shipment"]):
            return {"raw_text": query, "format": "text"}
        
        return None
    
    async def _classify_data(self, data: Dict[str, Any], context: WMSContext) -> Dict[str, Any]:
        """Classify data using multiple methods"""
        import time
        start_time = time.time()
        
        try:
            # Method 1: Keyword-based classification
            keyword_results = self._classify_by_keywords(data)
            
            # Method 2: Pattern matching
            pattern_results = self._classify_by_patterns(data)
            
            # Method 3: Field analysis
            field_results = self._classify_by_fields(data)
            
            # Combine results
            combined_results = self._combine_classification_results([
                keyword_results, pattern_results, field_results
            ])
            
            # Determine primary and secondary categories
            primary_category, primary_confidence = self._get_primary_category(combined_results)
            secondary_categories = self._get_secondary_categories(combined_results, primary_category)
            
            # Check if manual review is required
            manual_review_required = primary_confidence < 0.8
            manual_review_reason = "Low confidence score" if manual_review_required else None
            
            processing_time = time.time() - start_time
            
            return {
                "success": True,
                "primary_category": primary_category,
                "primary_confidence": primary_confidence,
                "secondary_categories": secondary_categories,
                "method": "hybrid_ml_pattern_keyword",
                "processing_time": processing_time,
                "manual_review_required": manual_review_required,
                "manual_review_reason": manual_review_reason,
                "warnings": []
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "processing_time": time.time() - start_time
            }
    
    def _classify_by_keywords(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Classify based on keyword presence"""
        keyword_scores = {}
        
        # Convert data to searchable text
        text_content = self._extract_text_content(data)
        text_lower = text_content.lower()
        
        # WMS category keywords
        category_keywords = {
            "wms_introduction": ["wms", "system", "overview", "introduction", "warehouse management"],
            "locations": ["location", "bin", "aisle", "zone", "coordinate", "layout", "position"],
            "items": ["item", "product", "sku", "part", "material", "catalog", "product"],
            "receiving": ["receive", "receipt", "inbound", "asn", "purchase order", "delivery"],
            "locating_putaway": ["putaway", "put away", "locate", "placement", "storage"],
            "work": ["work", "task", "assignment", "labor", "productivity", "performance"],
            "inventory_management": ["inventory", "stock", "quantity", "balance", "on hand"],
            "cycle_counting": ["cycle count", "count", "counting", "accuracy", "audit"],
            "wave_management": ["wave", "batch", "release", "planning", "workload"],
            "allocation": ["allocate", "allocation", "reserve", "assign", "shortage"],
            "replenishment": ["replenish", "replenishment", "min max", "reorder", "refill"],
            "picking": ["pick", "picking", "order picking", "selection", "fulfillment"],
            "packing": ["pack", "packing", "carton", "box", "packaging", "shipment prep"],
            "shipping": ["ship", "shipping", "outbound", "carrier", "freight", "dispatch"],
            "yard_management": ["yard", "dock", "trailer", "appointment", "gate"],
            "other_data_categorization": ["categorize", "classify", "data", "upload", "process", "unknown"]
        }
        
        for category, keywords in category_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1
            
            if score > 0:
                # Normalize score based on number of keywords
                keyword_scores[category] = min(score / len(keywords), 1.0)
        
        return keyword_scores
    
    def _classify_by_patterns(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Classify based on data patterns"""
        pattern_scores = {}
        
        # Check for common WMS data patterns
        if self._has_location_pattern(data):
            pattern_scores["locations"] = 0.8
        
        if self._has_item_pattern(data):
            pattern_scores["items"] = 0.8
        
        if self._has_quantity_pattern(data):
            pattern_scores["inventory_management"] = 0.7
        
        if self._has_order_pattern(data):
            pattern_scores["receiving"] = 0.6
            pattern_scores["shipping"] = 0.6
        
        if self._has_movement_pattern(data):
            pattern_scores["work"] = 0.7
        
        return pattern_scores
    
    def _classify_by_fields(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Classify based on field names and structure"""
        field_scores = {}
        
        if isinstance(data, dict):
            field_names = [key.lower() for key in data.keys()]
            
            # Location-related fields
            location_fields = ["location_id", "bin", "aisle", "zone", "position"]
            if any(field in field_names for field in location_fields):
                field_scores["locations"] = 0.9
            
            # Item-related fields
            item_fields = ["item_id", "sku", "part_number", "product_id", "item_description"]
            if any(field in field_names for field in item_fields):
                field_scores["items"] = 0.9
            
            # Inventory-related fields
            inventory_fields = ["quantity", "qty", "stock", "on_hand", "available"]
            if any(field in field_names for field in inventory_fields):
                field_scores["inventory_management"] = 0.8
            
            # Work-related fields
            work_fields = ["task_id", "work_type", "assignment", "user_id", "completed"]
            if any(field in field_names for field in work_fields):
                field_scores["work"] = 0.8
        
        return field_scores
    
    def _extract_text_content(self, data: Dict[str, Any]) -> str:
        """Extract all text content from data structure"""
        if isinstance(data, dict):
            text_parts = []
            for key, value in data.items():
                text_parts.append(str(key))
                text_parts.append(str(value))
            return " ".join(text_parts)
        else:
            return str(data)
    
    def _has_location_pattern(self, data: Dict[str, Any]) -> bool:
        """Check for location ID patterns like A-01-B-03"""
        text = self._extract_text_content(data)
        import re
        location_pattern = r'[A-Z]{1,3}-\d{2,4}-[A-Z]{1,2}-\d{1,3}'
        return bool(re.search(location_pattern, text))
    
    def _has_item_pattern(self, data: Dict[str, Any]) -> bool:
        """Check for item/SKU patterns"""
        text = self._extract_text_content(data)
        import re
        item_patterns = [
            r'SKU\d{4,12}',
            r'[A-Z]{2,4}\d{6,12}',
            r'ITEM-[A-Z0-9]+'
        ]
        return any(re.search(pattern, text) for pattern in item_patterns)
    
    def _has_quantity_pattern(self, data: Dict[str, Any]) -> bool:
        """Check for quantity/measurement patterns"""
        text = self._extract_text_content(data)
        import re
        qty_pattern = r'\d+\.?\d*\s*(EA|EACH|BOX|CASE|PALLET|KG|LB|UNITS?)'
        return bool(re.search(qty_pattern, text, re.IGNORECASE))
    
    def _has_order_pattern(self, data: Dict[str, Any]) -> bool:
        """Check for order number patterns"""
        text = self._extract_text_content(data)
        import re
        order_patterns = [
            r'(PO|SO|ORDER)\d{6,12}',
            r'ORD-[A-Z0-9]+'
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in order_patterns)
    
    def _has_movement_pattern(self, data: Dict[str, Any]) -> bool:
        """Check for movement/work patterns"""
        text = self._extract_text_content(data).lower()
        movement_keywords = ["pick", "putaway", "move", "transfer", "assign", "complete"]
        return any(keyword in text for keyword in movement_keywords)
    
    def _combine_classification_results(self, results_list: List[Dict[str, float]]) -> Dict[str, float]:
        """Combine multiple classification results"""
        combined = {}
        
        for results in results_list:
            for category, score in results.items():
                if category not in combined:
                    combined[category] = []
                combined[category].append(score)
        
        # Average the scores
        final_scores = {}
        for category, scores in combined.items():
            final_scores[category] = sum(scores) / len(scores)
        
        return final_scores
    
    def _get_primary_category(self, combined_results: Dict[str, float]) -> Tuple[str, float]:
        """Get the primary category with highest confidence"""
        if not combined_results:
            return "other_data_categorization", 0.5
        
        best_category = max(combined_results.keys(), key=lambda k: combined_results[k])
        best_score = combined_results[best_category]
        
        return best_category, best_score
    
    def _get_secondary_categories(self, combined_results: Dict[str, float], 
                                primary_category: str) -> List[Tuple[str, float]]:
        """Get secondary categories above threshold"""
        secondary = []
        
        for category, score in combined_results.items():
            if category != primary_category and score >= 0.5:
                secondary.append((category, score))
        
        # Sort by score descending
        secondary.sort(key=lambda x: x[1], reverse=True)
        
        return secondary[:3]  # Return top 3 secondary categories


class CategoryValidationTool(WMSBaseTool):
    """Tool for validating category assignments using business rules"""
    
    name = "category_validation"
    description = "Validate category assignments against business rules and constraints"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute category validation"""
        try:
            # Parse validation request
            validation_request = self._parse_validation_request(query)
            
            if not validation_request:
                return "Please provide validation details including category, data, and validation rules."
            
            # Perform validation
            validation_result = await self._validate_category_assignment(validation_request, context)
            
            # Format results
            response = "✅ **Category Validation Results:**\n\n"
            
            if validation_result["valid"]:
                response += f"✅ **Validation Passed**\n"
                response += f"Category: {validation_request['category']}\n"
                response += f"Confidence: {validation_result['confidence']:.2%}\n"
                
                if validation_result.get("warnings"):
                    response += f"\n⚠️ **Warnings:**\n"
                    for warning in validation_result["warnings"]:
                        response += f"   • {warning}\n"
            else:
                response += f"❌ **Validation Failed**\n"
                response += f"Category: {validation_request['category']}\n"
                response += f"Reason: {validation_result['reason']}\n"
                
                if validation_result.get("violations"):
                    response += f"\n🚫 **Rule Violations:**\n"
                    for violation in validation_result["violations"]:
                        response += f"   • {violation}\n"
                
                if validation_result.get("suggestions"):
                    response += f"\n💡 **Suggestions:**\n"
                    for suggestion in validation_result["suggestions"]:
                        response += f"   • {suggestion}\n"
            
            return response
            
        except Exception as e:
            return f"Error during validation: {str(e)}"
    
    def _parse_validation_request(self, query: str) -> Optional[Dict[str, Any]]:
        """Parse validation request from query"""
        # In a real implementation, this would parse structured validation requests
        # For now, return a sample structure
        if "validate" in query.lower():
            return {
                "category": "inventory_management",
                "data": {"item_id": "SKU123", "quantity": 100},
                "rules": ["required_fields", "data_types", "business_logic"]
            }
        return None
    
    async def _validate_category_assignment(self, request: Dict[str, Any], 
                                          context: WMSContext) -> Dict[str, Any]:
        """Validate category assignment against rules"""
        try:
            async with self.db_manager.get_async_session() as session:
                # Get validation rules for the category
                category_name = request["category"]
                
                # In a real implementation, this would fetch actual rules from the database
                validation_rules = await self._get_validation_rules(session, category_name)
                
                # Apply each rule
                violations = []
                warnings = []
                
                data = request["data"]
                
                # Check required fields
                required_fields = validation_rules.get("required_fields", [])
                for field in required_fields:
                    if field not in data:
                        violations.append(f"Required field '{field}' is missing")
                
                # Check data types
                field_types = validation_rules.get("field_types", {})
                for field, expected_type in field_types.items():
                    if field in data:
                        actual_value = data[field]
                        if not self._validate_data_type(actual_value, expected_type):
                            violations.append(f"Field '{field}' should be {expected_type}")
                
                # Check business logic
                business_rules = validation_rules.get("business_rules", [])
                for rule in business_rules:
                    rule_result = self._evaluate_business_rule(rule, data)
                    if not rule_result["passed"]:
                        violations.append(rule_result["message"])
                
                # Determine overall validation result
                is_valid = len(violations) == 0
                confidence = 1.0 if is_valid else max(0.0, 1.0 - (len(violations) * 0.2))
                
                result = {
                    "valid": is_valid,
                    "confidence": confidence,
                    "violations": violations,
                    "warnings": warnings
                }
                
                if not is_valid:
                    result["reason"] = f"Failed {len(violations)} validation rule(s)"
                    result["suggestions"] = self._generate_suggestions(violations, data)
                
                return result
                
        except Exception as e:
            return {
                "valid": False,
                "reason": f"Validation error: {str(e)}",
                "confidence": 0.0,
                "violations": [],
                "warnings": []
            }
    
    async def _get_validation_rules(self, session: AsyncSession, 
                                  category: str) -> Dict[str, Any]:
        """Get validation rules for a category"""
        # This would query the database for actual rules
        # For now, return sample rules
        sample_rules = {
            "inventory_management": {
                "required_fields": ["item_id", "location_id", "quantity"],
                "field_types": {
                    "quantity": "number",
                    "item_id": "string",
                    "location_id": "string"
                },
                "business_rules": [
                    {
                        "rule": "quantity_positive",
                        "description": "Quantity must be positive"
                    }
                ]
            },
            "locations": {
                "required_fields": ["location_id", "zone_id"],
                "field_types": {
                    "location_id": "string",
                    "zone_id": "string",
                    "capacity": "number"
                },
                "business_rules": [
                    {
                        "rule": "location_id_format",
                        "description": "Location ID must follow naming convention"
                    }
                ]
            }
        }
        
        return sample_rules.get(category, {})
    
    def _validate_data_type(self, value: Any, expected_type: str) -> bool:
        """Validate data type"""
        if expected_type == "string":
            return isinstance(value, str)
        elif expected_type == "number":
            return isinstance(value, (int, float))
        elif expected_type == "boolean":
            return isinstance(value, bool)
        elif expected_type == "array":
            return isinstance(value, list)
        elif expected_type == "object":
            return isinstance(value, dict)
        
        return True  # Default to valid for unknown types
    
    def _evaluate_business_rule(self, rule: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a business rule"""
        rule_name = rule.get("rule")
        
        if rule_name == "quantity_positive":
            quantity = data.get("quantity", 0)
            passed = isinstance(quantity, (int, float)) and quantity > 0
            return {
                "passed": passed,
                "message": "Quantity must be a positive number" if not passed else ""
            }
        elif rule_name == "location_id_format":
            location_id = data.get("location_id", "")
            # Check for pattern like A-01-B-03
            import re
            pattern = r'^[A-Z]{1,3}-\d{2,4}-[A-Z]{1,2}-\d{1,3}$'
            passed = bool(re.match(pattern, location_id))
            return {
                "passed": passed,
                "message": "Location ID must follow format like A-01-B-03" if not passed else ""
            }
        
        # Default: rule passes
        return {"passed": True, "message": ""}
    
    def _generate_suggestions(self, violations: List[str], data: Dict[str, Any]) -> List[str]:
        """Generate suggestions based on violations"""
        suggestions = []
        
        for violation in violations:
            if "missing" in violation.lower():
                suggestions.append("Add the missing required fields to your data")
            elif "should be" in violation.lower():
                suggestions.append("Check the data types of your fields")
            elif "positive" in violation.lower():
                suggestions.append("Ensure quantity values are positive numbers")
            elif "format" in violation.lower():
                suggestions.append("Check the format requirements for ID fields")
        
        if not suggestions:
            suggestions.append("Review the data structure and try again")
        
        return suggestions


class MultiCategoryAssignmentTool(WMSBaseTool):
    """Tool for handling multi-category data assignments"""
    
    name = "multi_category_assignment"
    description = "Handle data that belongs to multiple WMS categories and create appropriate assignments"
    
    async def _execute(self, query: str, context: WMSContext = None) -> str:
        """Execute multi-category assignment"""
        try:
            # Parse assignment request
            assignment_request = self._parse_assignment_request(query)
            
            if not assignment_request:
                return "Please provide data for multi-category assignment analysis."
            
            # Analyze multi-category relevance
            assignment_result = await self._analyze_multi_category_assignment(assignment_request, context)
            
            # Format results
            response = "🔗 **Multi-Category Assignment Analysis:**\n\n"
            
            response += f"📊 **Primary Assignment:**\n"
            response += f"   Category: {assignment_result['primary']['category']}\n"
            response += f"   Sub-category: {assignment_result['primary']['sub_category']}\n"
            response += f"   Confidence: {assignment_result['primary']['confidence']:.2%}\n\n"
            
            if assignment_result.get("secondary_assignments"):
                response += f"🔗 **Secondary Assignments:**\n"
                for i, assignment in enumerate(assignment_result["secondary_assignments"], 1):
                    response += f"   {i}. {assignment['category']}.{assignment['sub_category']}\n"
                    response += f"      Confidence: {assignment['confidence']:.2%}\n"
                    response += f"      Relationship: {assignment['relationship']}\n"
                response += "\n"
            
            if assignment_result.get("cross_references"):
                response += f"🔄 **Cross-References:**\n"
                for ref in assignment_result["cross_references"]:
                    response += f"   • {ref['description']}\n"
                response += "\n"
            
            response += f"💾 **Storage Strategy:**\n"
            response += f"   Primary Table: {assignment_result['storage']['primary_table']}\n"
            response += f"   Vector Collections: {', '.join(assignment_result['storage']['vector_collections'])}\n"
            response += f"   Cross-Reference Links: {len(assignment_result['storage']['cross_links'])}\n"
            
            return response
            
        except Exception as e:
            return f"Error during multi-category assignment: {str(e)}"
    
    def _parse_assignment_request(self, query: str) -> Optional[Dict[str, Any]]:
        """Parse assignment request from query"""
        # In a real implementation, this would parse structured data
        # For now, return a sample request
        if any(keyword in query.lower() for keyword in ["assign", "multi", "category"]):
            return {
                "data": {
                    "item_id": "SKU12345",
                    "location_id": "A-01-B-03", 
                    "quantity": 100,
                    "movement_type": "RECEIPT"
                },
                "suggested_categories": ["items", "locations", "inventory_management", "receiving"]
            }
        return None
    
    async def _analyze_multi_category_assignment(self, request: Dict[str, Any], 
                                               context: WMSContext) -> Dict[str, Any]:
        """Analyze and create multi-category assignments"""
        data = request["data"]
        suggested_categories = request.get("suggested_categories", [])
        
        # Analyze data for multi-category relevance
        assignments = []
        
        # Primary assignment (highest confidence)
        primary_assignment = {
            "category": "inventory_management",
            "sub_category": "functional",
            "confidence": 0.95,
            "relationship": "primary"
        }
        
        # Secondary assignments based on data content
        secondary_assignments = []
        
        # If data contains item information
        if "item_id" in data:
            secondary_assignments.append({
                "category": "items",
                "sub_category": "functional",
                "confidence": 0.85,
                "relationship": "item_reference"
            })
        
        # If data contains location information
        if "location_id" in data:
            secondary_assignments.append({
                "category": "locations", 
                "sub_category": "functional",
                "confidence": 0.80,
                "relationship": "location_reference"
            })
        
        # If data contains movement information
        if "movement_type" in data:
            movement_type = data["movement_type"].upper()
            if movement_type == "RECEIPT":
                secondary_assignments.append({
                    "category": "receiving",
                    "sub_category": "functional", 
                    "confidence": 0.75,
                    "relationship": "process_integration"
                })
            elif movement_type == "PICK":
                secondary_assignments.append({
                    "category": "picking",
                    "sub_category": "functional",
                    "confidence": 0.75,
                    "relationship": "process_integration"
                })
        
        # Generate cross-references
        cross_references = []
        for assignment in secondary_assignments:
            cross_references.append({
                "description": f"Links to {assignment['category']} for {assignment['relationship']}",
                "category": assignment["category"],
                "relationship_type": assignment["relationship"]
            })
        
        # Determine storage strategy
        storage_strategy = {
            "primary_table": "inventory",
            "vector_collections": ["WMSKnowledge"],
            "cross_links": []
        }
        
        # Add category-specific vector collections
        all_categories = [primary_assignment["category"]] + [a["category"] for a in secondary_assignments]
        for category in all_categories:
            if category == "inventory_management":
                storage_strategy["vector_collections"].append("InventoryKnowledge")
            elif category == "items":
                storage_strategy["vector_collections"].append("ItemsKnowledge")
            elif category == "locations":
                storage_strategy["vector_collections"].append("LocationsKnowledge")
        
        # Remove duplicates
        storage_strategy["vector_collections"] = list(set(storage_strategy["vector_collections"]))
        
        # Generate cross-reference links
        for assignment in secondary_assignments:
            storage_strategy["cross_links"].append({
                "category": assignment["category"],
                "table": self._get_table_for_category(assignment["category"]),
                "relationship": assignment["relationship"]
            })
        
        return {
            "primary": primary_assignment,
            "secondary_assignments": secondary_assignments,
            "cross_references": cross_references,
            "storage": storage_strategy,
            "total_assignments": 1 + len(secondary_assignments)
        }
    
    def _get_table_for_category(self, category: str) -> str:
        """Get database table name for category"""
        table_mapping = {
            "inventory_management": "inventory",
            "items": "items",
            "locations": "locations",
            "receiving": "inventory_movements",
            "picking": "work_assignments",
            "shipping": "inventory_movements"
        }
        return table_mapping.get(category, "data_storage_mappings")


# Functional Agent - Core categorization processes
class DataCategorizationFunctionalAgent(WMSBaseAgent):
    """Handles functional aspects of data categorization"""
    
    def __init__(self):
        tools = [
            DataClassificationTool("other_data_categorization", "functional"),
            MultiCategoryAssignmentTool("other_data_categorization", "functional")
        ]
        super().__init__("other_data_categorization", "functional", tools)
    
    def _get_specialization(self) -> str:
        return "Automated data classification, category assignment workflows, and validation processes"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "automatic_classification",
            "multi_category_assignment",
            "validation_workflows",
            "confidence_scoring",
            "manual_review_triggers",
            "data_routing"
        ]


# Technical Agent - ML algorithms and system implementation
class DataCategorizationTechnicalAgent(WMSBaseAgent):
    """Handles technical aspects of data categorization"""
    
    def __init__(self):
        tools = [DataClassificationTool("other_data_categorization", "technical")]
        super().__init__("other_data_categorization", "technical", tools)
    
    def _get_specialization(self) -> str:
        return "ML classification algorithms, pattern recognition engines, and technical validation systems"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "ml_classification",
            "pattern_recognition",
            "algorithm_optimization",
            "model_training",
            "performance_tuning",
            "system_integration"
        ]


# Configuration Agent - Rules and validation setup
class DataCategorizationConfigurationAgent(WMSBaseAgent):
    """Handles categorization configuration and rules"""
    
    def __init__(self):
        tools = [CategoryValidationTool("other_data_categorization", "configuration")]
        super().__init__("other_data_categorization", "configuration", tools)
    
    def _get_specialization(self) -> str:
        return "Classification rules configuration, validation thresholds, and approval workflow setup"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "rule_configuration",
            "threshold_settings",
            "workflow_setup",
            "approval_processes",
            "escalation_paths",
            "system_parameters"
        ]


# Relationships Agent - Cross-category mappings
class DataCategorizationRelationshipsAgent(WMSBaseAgent):
    """Handles relationships between categories and data mappings"""
    
    def __init__(self):
        tools = [MultiCategoryAssignmentTool("other_data_categorization", "relationships")]
        super().__init__("other_data_categorization", "relationships", tools)
    
    def _get_specialization(self) -> str:
        return "Cross-category data mapping, multi-category assignments, and data lineage tracking"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "cross_category_mapping",
            "relationship_analysis",
            "data_lineage",
            "multi_assignment_logic",
            "integration_patterns",
            "dependency_tracking"
        ]


# Notes Agent - Best practices and quality assurance
class DataCategorizationNotesAgent(WMSBaseAgent):
    """Provides data categorization best practices and quality guidelines"""
    
    def __init__(self):
        tools = [CategoryValidationTool("other_data_categorization", "notes")]
        super().__init__("other_data_categorization", "notes", tools)
    
    def _get_specialization(self) -> str:
        return "Data quality standards, classification best practices, and accuracy improvement strategies"
    
    def _get_capabilities(self) -> List[str]:
        return [
            "quality_standards",
            "best_practices",
            "accuracy_improvement",
            "process_optimization",
            "training_guidelines",
            "continuous_learning"
        ]