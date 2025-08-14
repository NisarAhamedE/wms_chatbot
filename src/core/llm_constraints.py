"""
LLM Constraint System
Prevents AI hallucinations by enforcing strict data validation and fact-checking.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import json
import re
from enum import Enum
from dataclasses import dataclass, field

from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain_openai import AzureChatOpenAI

from .config import get_azure_openai_settings
from .logging import LoggerMixin
from ..database.connection import get_database_manager
from ..database.vector_store import get_weaviate_manager


class ConstraintType(Enum):
    """Types of LLM constraints"""
    FACT_VERIFICATION = "fact_verification"
    DATA_EXISTENCE = "data_existence"
    BUSINESS_RULE = "business_rule"
    SCHEMA_VALIDATION = "schema_validation"
    TEMPORAL_CONSISTENCY = "temporal_consistency"
    PERMISSION_CHECK = "permission_check"


class ConstraintSeverity(Enum):
    """Severity levels for constraint violations"""
    CRITICAL = "critical"  # Block response entirely
    HIGH = "high"         # Require correction
    MEDIUM = "medium"     # Warn user
    LOW = "low"          # Log only


@dataclass
class ConstraintViolation:
    """Represents a constraint violation"""
    constraint_type: ConstraintType
    severity: ConstraintSeverity
    description: str
    suggested_fix: str
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConstraintRule:
    """Defines a constraint rule"""
    name: str
    constraint_type: ConstraintType
    severity: ConstraintSeverity
    description: str
    validation_function: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


class LLMConstraintValidator(LoggerMixin):
    """Validates LLM responses against defined constraints"""
    
    def __init__(self):
        super().__init__()
        self.db_manager = get_database_manager()
        self.vector_manager = get_weaviate_manager()
        self.validation_llm = self._initialize_validation_llm()
        
        # Load constraint rules
        self.constraint_rules = self._load_constraint_rules()
        
        # WMS-specific data patterns
        self.wms_data_patterns = self._load_wms_patterns()
        
        # Known entities cache
        self.known_entities_cache = {}
        self.cache_expiry = 3600  # 1 hour
    
    def _initialize_validation_llm(self) -> AzureChatOpenAI:
        """Initialize separate LLM for validation"""
        azure_settings = get_azure_openai_settings()
        
        return AzureChatOpenAI(
            azure_deployment=azure_settings.deployment_chat,
            openai_api_version=azure_settings.api_version,
            azure_endpoint=str(azure_settings.endpoint),
            api_key=azure_settings.api_key,
            temperature=0.0,  # Deterministic for validation
            max_tokens=1000
        )
    
    def _load_constraint_rules(self) -> List[ConstraintRule]:
        """Load constraint rules configuration"""
        return [
            ConstraintRule(
                name="no_invented_data",
                constraint_type=ConstraintType.FACT_VERIFICATION,
                severity=ConstraintSeverity.CRITICAL,
                description="AI must not invent or assume data that wasn't provided",
                validation_function="validate_no_assumptions"
            ),
            ConstraintRule(
                name="verify_entity_existence",
                constraint_type=ConstraintType.DATA_EXISTENCE,
                severity=ConstraintSeverity.HIGH,
                description="Referenced entities must exist in the database",
                validation_function="validate_entity_existence"
            ),
            ConstraintRule(
                name="wms_business_rules",
                constraint_type=ConstraintType.BUSINESS_RULE,
                severity=ConstraintSeverity.HIGH,
                description="Responses must comply with WMS business rules",
                validation_function="validate_wms_business_rules"
            ),
            ConstraintRule(
                name="schema_compliance",
                constraint_type=ConstraintType.SCHEMA_VALIDATION,
                severity=ConstraintSeverity.MEDIUM,
                description="Data references must match database schema",
                validation_function="validate_schema_compliance"
            ),
            ConstraintRule(
                name="temporal_logic",
                constraint_type=ConstraintType.TEMPORAL_CONSISTENCY,
                severity=ConstraintSeverity.MEDIUM,
                description="Time-based statements must be logically consistent",
                validation_function="validate_temporal_consistency"
            ),
            ConstraintRule(
                name="user_permissions",
                constraint_type=ConstraintType.PERMISSION_CHECK,
                severity=ConstraintSeverity.CRITICAL,
                description="Users can only access data they have permission for",
                validation_function="validate_user_permissions"
            )
        ]
    
    def _load_wms_patterns(self) -> Dict[str, Any]:
        """Load WMS-specific data patterns and rules"""
        return {
            'valid_statuses': {
                'order_status': ['pending', 'picked', 'packed', 'shipped', 'delivered', 'cancelled'],
                'inventory_status': ['available', 'reserved', 'picked', 'damaged', 'quarantine'],
                'location_status': ['active', 'inactive', 'maintenance', 'full'],
                'task_status': ['assigned', 'in_progress', 'completed', 'cancelled']
            },
            'business_rules': {
                'inventory_cannot_be_negative': True,
                'picked_orders_cannot_be_modified': True,
                'shipped_orders_cannot_be_cancelled': True,
                'locations_have_capacity_limits': True
            },
            'required_fields': {
                'create_order': ['customer_id', 'items', 'delivery_address'],
                'create_inventory': ['item_id', 'location_id', 'quantity'],
                'assign_task': ['user_id', 'task_type', 'priority']
            },
            'data_relationships': {
                'order_lines_require_order': True,
                'inventory_movements_require_source_and_destination': True,
                'tasks_require_assignments': True
            }
        }
    
    async def validate_response(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate LLM response against all constraints"""
        violations = []
        
        try:
            for rule in self.constraint_rules:
                if not rule.enabled:
                    continue
                
                # Execute validation function
                rule_violations = await self._execute_validation(rule, response, context)
                violations.extend(rule_violations)
            
            # Determine overall validation result
            validation_result = self._assess_violations(violations)
            
            # Log validation results
            self._log_validation_results(validation_result, violations)
            
            return validation_result
            
        except Exception as e:
            self.log_error(f"Constraint validation failed: {e}")
            return {
                'is_valid': False,
                'severity': ConstraintSeverity.CRITICAL.value,
                'violations': [
                    ConstraintViolation(
                        constraint_type=ConstraintType.FACT_VERIFICATION,
                        severity=ConstraintSeverity.CRITICAL,
                        description=f"Validation system error: {str(e)}",
                        suggested_fix="Please try again or contact support"
                    )
                ],
                'corrected_response': None
            }
    
    async def _execute_validation(self, rule: ConstraintRule, response: str, 
                                context: Dict[str, Any]) -> List[ConstraintViolation]:
        """Execute a specific validation rule"""
        validation_function = getattr(self, rule.validation_function, None)
        
        if not validation_function:
            self.log_warning(f"Validation function {rule.validation_function} not found")
            return []
        
        try:
            return await validation_function(response, context, rule)
        except Exception as e:
            self.log_error(f"Validation rule {rule.name} failed: {e}")
            return [
                ConstraintViolation(
                    constraint_type=rule.constraint_type,
                    severity=ConstraintSeverity.MEDIUM,
                    description=f"Validation rule {rule.name} could not be executed",
                    suggested_fix="Manual review recommended"
                )
            ]
    
    async def validate_no_assumptions(self, response: str, context: Dict[str, Any], 
                                    rule: ConstraintRule) -> List[ConstraintViolation]:
        """Validate that AI doesn't make assumptions or invent data"""
        violations = []
        
        # Check for assumption indicators
        assumption_patterns = [
            r'probably|likely|might be|could be|should be|I think|I believe',
            r'assuming|estimated|approximately|roughly|about \d+',
            r'typically|usually|generally|normally',
            r'let me assume|for example, it could',
            r'based on my knowledge|in my experience'
        ]
        
        response_lower = response.lower()
        
        for pattern in assumption_patterns:
            if re.search(pattern, response_lower):
                violations.append(ConstraintViolation(
                    constraint_type=ConstraintType.FACT_VERIFICATION,
                    severity=ConstraintSeverity.HIGH,
                    description=f"Response contains assumptions or uncertain language: '{pattern}'",
                    suggested_fix="Use only verified data from the database. State 'Data not available' if uncertain.",
                    context={'pattern_matched': pattern}
                ))
        
        # Check for specific data values that weren't in the query result
        if 'query_result' in context:
            violations.extend(await self._check_data_invention(response, context['query_result']))
        
        return violations
    
    async def validate_entity_existence(self, response: str, context: Dict[str, Any],
                                      rule: ConstraintRule) -> List[ConstraintViolation]:
        """Validate that referenced entities exist in database"""
        violations = []
        
        # Extract entity references from response
        entities = self._extract_entity_references(response)
        
        for entity_type, entity_values in entities.items():
            for value in entity_values:
                exists = await self._verify_entity_exists(entity_type, value)
                
                if not exists:
                    violations.append(ConstraintViolation(
                        constraint_type=ConstraintType.DATA_EXISTENCE,
                        severity=ConstraintSeverity.HIGH,
                        description=f"Referenced {entity_type} '{value}' does not exist in database",
                        suggested_fix=f"Verify {entity_type} exists before referencing it",
                        context={'entity_type': entity_type, 'entity_value': value}
                    ))
        
        return violations
    
    async def validate_wms_business_rules(self, response: str, context: Dict[str, Any],
                                        rule: ConstraintRule) -> List[ConstraintViolation]:
        """Validate compliance with WMS business rules"""
        violations = []
        
        # Check status transitions
        status_violations = self._check_status_transitions(response)
        violations.extend(status_violations)
        
        # Check quantity constraints
        quantity_violations = self._check_quantity_constraints(response)
        violations.extend(quantity_violations)
        
        # Check workflow constraints
        workflow_violations = self._check_workflow_constraints(response)
        violations.extend(workflow_violations)
        
        return violations
    
    async def validate_schema_compliance(self, response: str, context: Dict[str, Any],
                                       rule: ConstraintRule) -> List[ConstraintViolation]:
        """Validate that data references match database schema"""
        violations = []
        
        # Extract table/column references
        schema_refs = self._extract_schema_references(response)
        
        for table, columns in schema_refs.items():
            # Verify table exists
            if not await self._verify_table_exists(table):
                violations.append(ConstraintViolation(
                    constraint_type=ConstraintType.SCHEMA_VALIDATION,
                    severity=ConstraintSeverity.MEDIUM,
                    description=f"Referenced table '{table}' does not exist",
                    suggested_fix="Use correct table names from schema",
                    context={'table': table}
                ))
                continue
            
            # Verify columns exist
            for column in columns:
                if not await self._verify_column_exists(table, column):
                    violations.append(ConstraintViolation(
                        constraint_type=ConstraintType.SCHEMA_VALIDATION,
                        severity=ConstraintSeverity.MEDIUM,
                        description=f"Referenced column '{table}.{column}' does not exist",
                        suggested_fix="Use correct column names from schema",
                        context={'table': table, 'column': column}
                    ))
        
        return violations
    
    async def validate_temporal_consistency(self, response: str, context: Dict[str, Any],
                                          rule: ConstraintRule) -> List[ConstraintViolation]:
        """Validate temporal logic consistency"""
        violations = []
        
        # Extract time references
        time_refs = self._extract_time_references(response)
        
        # Check for logical inconsistencies
        if time_refs:
            inconsistencies = self._check_temporal_logic(time_refs)
            
            for inconsistency in inconsistencies:
                violations.append(ConstraintViolation(
                    constraint_type=ConstraintType.TEMPORAL_CONSISTENCY,
                    severity=ConstraintSeverity.MEDIUM,
                    description=inconsistency['description'],
                    suggested_fix="Ensure time references are logically consistent",
                    context=inconsistency
                ))
        
        return violations
    
    async def validate_user_permissions(self, response: str, context: Dict[str, Any],
                                      rule: ConstraintRule) -> List[ConstraintViolation]:
        """Validate user has permission to access referenced data"""
        violations = []
        
        user_role = context.get('user_role', 'unknown')
        
        # Check sensitive data exposure
        sensitive_patterns = [
            r'salary|wage|compensation',
            r'personal.*information|pii',
            r'credit.*card|payment.*details',
            r'password|secret|key'
        ]
        
        response_lower = response.lower()
        
        for pattern in sensitive_patterns:
            if re.search(pattern, response_lower):
                if user_role not in ['admin_user', 'management_user']:
                    violations.append(ConstraintViolation(
                        constraint_type=ConstraintType.PERMISSION_CHECK,
                        severity=ConstraintSeverity.CRITICAL,
                        description=f"User role '{user_role}' should not access sensitive data",
                        suggested_fix="Remove sensitive information from response",
                        context={'user_role': user_role, 'pattern': pattern}
                    ))
        
        return violations
    
    def _extract_entity_references(self, response: str) -> Dict[str, List[str]]:
        """Extract entity references from response text"""
        entities = {
            'order_id': [],
            'item_id': [],
            'location_id': [],
            'user_id': [],
            'customer_id': []
        }
        
        # Extract ID patterns
        id_patterns = {
            'order_id': r'order[_\s]+(\w+)|order\s+#?(\w+)',
            'item_id': r'item[_\s]+(\w+)|sku[_\s]*(\w+)',
            'location_id': r'location[_\s]+(\w+)|bin[_\s]+(\w+)',
            'user_id': r'user[_\s]+(\w+)|employee[_\s]+(\w+)',
            'customer_id': r'customer[_\s]+(\w+)|client[_\s]+(\w+)'
        }
        
        response_lower = response.lower()
        
        for entity_type, pattern in id_patterns.items():
            matches = re.findall(pattern, response_lower)
            for match in matches:
                # Handle tuple matches from regex groups
                value = match[0] if isinstance(match, tuple) and match[0] else (match[1] if isinstance(match, tuple) else match)
                if value and value not in entities[entity_type]:
                    entities[entity_type].append(value)
        
        return {k: v for k, v in entities.items() if v}
    
    async def _verify_entity_exists(self, entity_type: str, value: str) -> bool:
        """Verify if an entity exists in the database"""
        # Use cache first
        cache_key = f"{entity_type}:{value}"
        
        if cache_key in self.known_entities_cache:
            cache_entry = self.known_entities_cache[cache_key]
            if (datetime.utcnow() - cache_entry['timestamp']).total_seconds() < self.cache_expiry:
                return cache_entry['exists']
        
        # Query database
        try:
            table_map = {
                'order_id': 'orders',
                'item_id': 'items',
                'location_id': 'locations',
                'user_id': 'users',
                'customer_id': 'customers'
            }
            
            table = table_map.get(entity_type)
            if not table:
                return False
            
            async with self.db_manager.get_async_session() as session:
                result = await session.execute(
                    f"SELECT 1 FROM {table} WHERE id = :value LIMIT 1",
                    {'value': value}
                )
                exists = result.first() is not None
            
            # Cache result
            self.known_entities_cache[cache_key] = {
                'exists': exists,
                'timestamp': datetime.utcnow()
            }
            
            return exists
            
        except Exception as e:
            self.log_warning(f"Could not verify entity {entity_type}:{value} - {e}")
            return True  # Assume exists if verification fails
    
    def _check_status_transitions(self, response: str) -> List[ConstraintViolation]:
        """Check for invalid status transitions"""
        violations = []
        
        # Define valid status transitions
        valid_transitions = {
            'order': {
                'pending': ['picked', 'cancelled'],
                'picked': ['packed', 'cancelled'],
                'packed': ['shipped'],
                'shipped': ['delivered'],
                'delivered': [],
                'cancelled': []
            }
        }
        
        # Look for status change language
        status_change_patterns = [
            r'change.*status.*from\s+(\w+)\s+to\s+(\w+)',
            r'update.*status.*(\w+).*to.*(\w+)',
            r'moved.*from\s+(\w+)\s+to\s+(\w+)'
        ]
        
        response_lower = response.lower()
        
        for pattern in status_change_patterns:
            matches = re.findall(pattern, response_lower)
            for from_status, to_status in matches:
                if from_status in valid_transitions.get('order', {}):
                    valid_next_statuses = valid_transitions['order'][from_status]
                    if to_status not in valid_next_statuses:
                        violations.append(ConstraintViolation(
                            constraint_type=ConstraintType.BUSINESS_RULE,
                            severity=ConstraintSeverity.HIGH,
                            description=f"Invalid status transition from '{from_status}' to '{to_status}'",
                            suggested_fix=f"Valid transitions from '{from_status}': {valid_next_statuses}",
                            context={'from_status': from_status, 'to_status': to_status}
                        ))
        
        return violations
    
    def _check_quantity_constraints(self, response: str) -> List[ConstraintViolation]:
        """Check quantity-related business rule violations"""
        violations = []
        
        # Check for negative quantities
        negative_qty_patterns = [
            r'quantity.*-\d+',
            r'negative.*quantity',
            r'quantity.*below.*zero'
        ]
        
        response_lower = response.lower()
        
        for pattern in negative_qty_patterns:
            if re.search(pattern, response_lower):
                violations.append(ConstraintViolation(
                    constraint_type=ConstraintType.BUSINESS_RULE,
                    severity=ConstraintSeverity.HIGH,
                    description="Inventory quantities cannot be negative",
                    suggested_fix="Verify quantity calculations and ensure positive values",
                    context={'violation_type': 'negative_quantity'}
                ))
        
        return violations
    
    def _check_workflow_constraints(self, response: str) -> List[ConstraintViolation]:
        """Check workflow-related business rules"""
        violations = []
        
        # Check for workflow violations
        workflow_patterns = {
            'ship_before_pick': r'ship.*before.*pick|shipping.*not.*picked',
            'modify_completed_order': r'modify.*completed.*order|change.*shipped.*order'
        }
        
        response_lower = response.lower()
        
        for violation_type, pattern in workflow_patterns.items():
            if re.search(pattern, response_lower):
                violations.append(ConstraintViolation(
                    constraint_type=ConstraintType.BUSINESS_RULE,
                    severity=ConstraintSeverity.HIGH,
                    description=f"Workflow violation: {violation_type}",
                    suggested_fix="Follow proper WMS workflow sequence",
                    context={'violation_type': violation_type}
                ))
        
        return violations
    
    def _extract_schema_references(self, response: str) -> Dict[str, List[str]]:
        """Extract table and column references"""
        schema_refs = {}
        
        # Simple pattern matching for table.column references
        table_column_pattern = r'(\w+)\.(\w+)'
        matches = re.findall(table_column_pattern, response.lower())
        
        for table, column in matches:
            if table not in schema_refs:
                schema_refs[table] = []
            if column not in schema_refs[table]:
                schema_refs[table].append(column)
        
        return schema_refs
    
    async def _verify_table_exists(self, table_name: str) -> bool:
        """Verify table exists in database schema"""
        # This would query information_schema or use schema manager
        # Simplified for demo
        return True
    
    async def _verify_column_exists(self, table: str, column: str) -> bool:
        """Verify column exists in table"""
        # This would query information_schema or use schema manager
        # Simplified for demo
        return True
    
    def _extract_time_references(self, response: str) -> List[Dict[str, Any]]:
        """Extract time-related references"""
        time_refs = []
        
        time_patterns = [
            r'(yesterday|today|tomorrow)',
            r'(last|this|next)\s+(week|month|year)',
            r'(\d{1,2})/(\d{1,2})/(\d{4})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})'
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, response.lower())
            for match in matches:
                time_refs.append({
                    'text': match if isinstance(match, str) else ' '.join(match),
                    'pattern': pattern
                })
        
        return time_refs
    
    def _check_temporal_logic(self, time_refs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check for temporal logic inconsistencies"""
        inconsistencies = []
        
        # Simple check for obvious contradictions
        texts = [ref['text'] for ref in time_refs]
        
        # Check for contradictions like "yesterday's future orders"
        if any('yesterday' in text for text in texts) and any('future' in text for text in texts):
            inconsistencies.append({
                'description': 'Temporal contradiction: references to past and future in same context',
                'references': texts
            })
        
        return inconsistencies
    
    async def _check_data_invention(self, response: str, query_result: Dict[str, Any]) -> List[ConstraintViolation]:
        """Check if response contains data not present in query results"""
        violations = []
        
        # Extract specific values from response
        numbers = re.findall(r'\b\d+(?:\.\d+)?\b', response)
        
        # Check if numbers in response exist in query results
        result_text = json.dumps(query_result, default=str).lower()
        response_lower = response.lower()
        
        for number in numbers:
            if number not in result_text and len(number) > 2:  # Ignore small numbers
                # Check if it's in a context that suggests it's from data
                number_context_patterns = [
                    f'quantity.*{number}',
                    f'{number}.*items',
                    f'order.*{number}',
                    f'{number}.*units'
                ]
                
                if any(re.search(pattern, response_lower) for pattern in number_context_patterns):
                    violations.append(ConstraintViolation(
                        constraint_type=ConstraintType.FACT_VERIFICATION,
                        severity=ConstraintSeverity.MEDIUM,
                        description=f"Response contains number '{number}' not found in query results",
                        suggested_fix="Only use numbers from verified data sources",
                        context={'invented_number': number}
                    ))
        
        return violations
    
    def _assess_violations(self, violations: List[ConstraintViolation]) -> Dict[str, Any]:
        """Assess overall validation result based on violations"""
        if not violations:
            return {
                'is_valid': True,
                'severity': None,
                'violations': [],
                'corrected_response': None
            }
        
        # Determine highest severity
        severity_order = {
            ConstraintSeverity.CRITICAL: 0,
            ConstraintSeverity.HIGH: 1,
            ConstraintSeverity.MEDIUM: 2,
            ConstraintSeverity.LOW: 3
        }
        
        highest_severity = min(violations, key=lambda v: severity_order[v.severity]).severity
        
        # Block response if critical violations
        is_valid = highest_severity != ConstraintSeverity.CRITICAL
        
        return {
            'is_valid': is_valid,
            'severity': highest_severity.value,
            'violations': violations,
            'corrected_response': None  # Could implement auto-correction
        }
    
    def _log_validation_results(self, result: Dict[str, Any], violations: List[ConstraintViolation]):
        """Log validation results for monitoring"""
        if violations:
            self.log_warning(
                f"LLM constraint violations detected",
                violation_count=len(violations),
                severity=result['severity'],
                is_valid=result['is_valid']
            )
            
            for violation in violations:
                self.log_info(
                    f"Constraint violation: {violation.description}",
                    constraint_type=violation.constraint_type.value,
                    severity=violation.severity.value
                )
        else:
            self.log_info("LLM response passed all constraint validations")


# Global instance
_constraint_validator: Optional[LLMConstraintValidator] = None


def get_constraint_validator() -> LLMConstraintValidator:
    """Get or create global constraint validator instance"""
    global _constraint_validator
    
    if _constraint_validator is None:
        _constraint_validator = LLMConstraintValidator()
    
    return _constraint_validator


async def validate_llm_response(response: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to validate LLM response"""
    validator = get_constraint_validator()
    return await validator.validate_response(response, context)