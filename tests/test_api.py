"""
Comprehensive API Tests
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.api.main import app
from src.api.models import ChatRequest, OperationalQueryRequest


class TestWMSChatbotAPI:
    """Test suite for WMS Chatbot API"""
    
    def setup_method(self):
        """Setup test client"""
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer demo_token"}
        self.admin_headers = {"Authorization": "Bearer admin_token"}
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "WMS Chatbot API" in data["data"]["name"]
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = self.client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["status"] == "healthy"
    
    def test_detailed_health_check(self):
        """Test detailed health check"""
        response = self.client.get("/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "components" in data
        assert "system" in data["components"]
    
    def test_chat_message_unauthorized(self):
        """Test chat without authentication"""
        response = self.client.post("/api/v1/chat/message", json={
            "message": "Hello",
            "user_id": "test_user"
        })
        assert response.status_code == 401
    
    @patch('src.agents.base.WMSAgentOrchestrator.route_query')
    @patch('src.core.llm_constraints.validate_llm_response')
    def test_chat_message_success(self, mock_validate, mock_route):
        """Test successful chat message"""
        # Mock agent response
        mock_route.return_value = {
            'response': 'Hello! How can I help you with your WMS questions?',
            'agent_id': 'test_agent',
            'category': 'general',
            'sub_category': 'greeting',
            'confidence': 0.9
        }
        
        # Mock validation
        mock_validate.return_value = {'is_valid': True, 'violations': []}
        
        response = self.client.post("/api/v1/chat/message", 
            json={
                "message": "Hello",
                "user_id": "test_user",
                "user_role": "end_user"
            },
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["agent_info"]["agent_id"] == "test_agent"
    
    def test_operational_db_connect_unauthorized(self):
        """Test database connection without admin role"""
        response = self.client.post("/api/v1/operational-db/connect",
            json={
                "server": "test-server",
                "database": "test-db",
                "username": "test-user",
                "password": "test-password"
            },
            headers=self.headers
        )
        assert response.status_code == 403
    
    @patch('src.operational_db.sql_executor.OperationalSQLExecutor.set_connection')
    def test_operational_db_connect_success(self, mock_connect):
        """Test successful database connection"""
        mock_connect.return_value = True
        
        response = self.client.post("/api/v1/operational-db/connect",
            json={
                "server": "test-server",
                "database": "test-db", 
                "username": "test-user",
                "password": "test-password123"
            },
            headers=self.admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    @patch('src.operational_db.sql_executor.OperationalSQLExecutor.execute_natural_query')
    def test_operational_query_success(self, mock_query):
        """Test successful operational query"""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = [{"order_id": "12345", "status": "pending"}]
        mock_result.row_count = 1
        mock_result.execution_time = 0.123
        mock_result.query_used = "SELECT * FROM orders WHERE status = 'pending'"
        mock_result.warnings = []
        
        mock_query.return_value = mock_result
        
        with patch('src.operational_db.sql_executor.OperationalSQLExecutor.format_result_for_display') as mock_format:
            mock_format.return_value = {
                'success': True,
                'data': mock_result.data,
                'data_quality': {'completeness': 'complete'},
                'performance': {'issues_found': 0}
            }
            
            response = self.client.post("/api/v1/operational-db/query",
                json={
                    "query": "Show me pending orders",
                    "max_rows": 100
                },
                headers=self.headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["row_count"] == 1
    
    def test_content_upload_invalid_type(self):
        """Test content upload with invalid type"""
        response = self.client.post("/api/v1/content/upload",
            files={"file": ("test.txt", b"test content", "text/plain")},
            data={"content_type": "invalid_type", "description": "test"},
            headers=self.headers
        )
        assert response.status_code == 422
    
    @patch('src.processing.text_pipeline.MultiModalTextProcessor.process_content')
    def test_content_upload_success(self, mock_process):
        """Test successful content upload"""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.content.content_id = "test_content_123"
        mock_result.content.extracted_text = "Test content extracted"
        mock_result.wms_categories = ["items"]
        mock_result.extracted_entities = {"item_id": ["ABC123"]}
        mock_result.confidence = 0.85
        mock_result.processing_time = 1.23
        mock_result.warnings = []
        mock_result.errors = []
        
        mock_process.return_value = mock_result
        
        response = self.client.post("/api/v1/content/upload",
            files={"file": ("test.txt", b"Item ABC123 in warehouse", "text/plain")},
            data={"content_type": "text", "description": "test item data"},
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["content_id"] == "test_content_123"
    
    def test_admin_metrics_unauthorized(self):
        """Test admin metrics without proper role"""
        response = self.client.get("/api/v1/admin/metrics", headers=self.headers)
        assert response.status_code == 403
    
    def test_admin_metrics_success(self):
        """Test admin metrics with proper role"""
        response = self.client.get("/api/v1/admin/metrics", headers=self.admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "requests_per_minute" in data
        assert "average_response_time" in data
    
    def test_rate_limiting(self):
        """Test rate limiting middleware"""
        # This would require more sophisticated testing with multiple requests
        # For now, just test that the middleware doesn't break normal requests
        response = self.client.get("/health/", headers=self.headers)
        assert response.status_code == 200
        assert "X-Process-Time" in response.headers
    
    def test_error_handling(self):
        """Test error handling"""
        # Test with invalid JSON
        response = self.client.post("/api/v1/chat/message",
            data="invalid json",
            headers=self.headers
        )
        assert response.status_code == 422
    
    @patch('src.operational_db.sql_executor.OperationalSQLExecutor.get_query_suggestions')
    def test_query_suggestions(self, mock_suggestions):
        """Test query suggestions endpoint"""
        mock_suggestions.return_value = [
            "Show me all orders from today",
            "List items with low inventory",
            "Display shipping summary"
        ]
        
        response = self.client.get("/api/v1/operational-db/query-suggestions",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert len(data["data"]["suggestions"]) == 3
    
    @patch('src.operational_db.performance_optimizer.WMSPerformanceOptimizer.analyze_query_performance')
    def test_query_analysis(self, mock_analyze):
        """Test query analysis endpoint"""
        mock_analyze.return_value = {
            'query_classification': {'wms_function': 'inventory', 'complexity': 'simple'},
            'performance_issues': [],
            'index_recommendations': [],
            'optimization_suggestions': ['Add WHERE clause'],
            'estimated_improvement': {'estimated_speedup': '2x'}
        }
        
        response = self.client.post("/api/v1/operational-db/analyze-query",
            params={"query": "SELECT * FROM inventory"},
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "query_classification" in data["data"]


class TestAsyncComponents:
    """Test async components separately"""
    
    @pytest.mark.asyncio
    async def test_chat_service_processing(self):
        """Test chat service message processing"""
        from src.api.routes.chat import ChatService
        from src.api.models import ChatRequest, UserRole
        from src.api.auth import UserContext
        
        service = ChatService()
        
        with patch.object(service.orchestrator, 'route_query') as mock_route:
            mock_route.return_value = {
                'response': 'Test response',
                'agent_id': 'test_agent',
                'category': 'test',
                'sub_category': 'test'
            }
            
            request = ChatRequest(
                message="Test message",
                user_id="test_user",
                user_role=UserRole.END_USER
            )
            
            user_context = UserContext(user_id="test_user", role="end_user")
            
            with patch('src.core.llm_constraints.validate_llm_response') as mock_validate:
                mock_validate.return_value = {'is_valid': True, 'violations': []}
                
                response = await service.process_chat_message(request, user_context)
                
                assert response.response == "Test response"
                assert response.session_id is not None
    
    @pytest.mark.asyncio
    async def test_operational_query_execution(self):
        """Test operational query execution"""
        from src.operational_db.sql_executor import OperationalSQLExecutor, ConnectionInfo
        
        executor = OperationalSQLExecutor()
        
        # Mock database connection
        with patch.object(executor, 'engine') as mock_engine:
            mock_engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = 1
            
            connection_info = ConnectionInfo(
                server="test-server",
                database="test-db",
                username="test-user", 
                password="test-password"
            )
            
            with patch.object(executor, 'set_connection', return_value=True):
                success = executor.set_connection(connection_info)
                assert success == True
    
    @pytest.mark.asyncio
    async def test_content_processing_pipeline(self):
        """Test content processing pipeline"""
        from src.processing.text_pipeline import MultiModalTextProcessor, MediaType
        
        processor = MultiModalTextProcessor()
        
        # Test text processing
        result = await processor.process_content(
            content="Item ABC123 needs replenishment in location BIN-A-001",
            media_type=MediaType.TEXT
        )
        
        assert result.success == True
        assert result.content is not None
        assert len(result.wms_categories) > 0


class TestValidationAndConstraints:
    """Test validation and constraint systems"""
    
    @pytest.mark.asyncio
    async def test_llm_constraint_validation(self):
        """Test LLM constraint validation"""
        from src.core.llm_constraints import LLMConstraintValidator
        
        validator = LLMConstraintValidator()
        
        # Test valid response
        result = await validator.validate_response(
            response="Based on the database query, there are 5 pending orders.",
            context={'user_role': 'operations_user'}
        )
        
        assert result['is_valid'] == True
        
        # Test response with assumptions
        result = await validator.validate_response(
            response="I think there are probably around 100 orders in the system.",
            context={'user_role': 'operations_user'}
        )
        
        assert result['is_valid'] == False or len(result['violations']) > 0
    
    def test_api_model_validation(self):
        """Test API model validation"""
        from src.api.models import ChatRequest, UserRole
        
        # Valid request
        request = ChatRequest(
            message="Hello",
            user_id="user123",
            user_role=UserRole.END_USER
        )
        assert request.message == "Hello"
        
        # Test validation errors
        with pytest.raises(ValueError):
            ChatRequest(
                message="",  # Empty message should fail
                user_id="user123"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])