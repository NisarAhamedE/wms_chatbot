import pytest
import asyncio
from api.agents.langchain_agents import agent_manager, WMSAgent
from api.agents.models import ALL_WMS_AGENTS

class TestWMSAgents:
    """Test WMS agent functionality"""
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test that all 80 agents can be initialized"""
        await agent_manager.initialize()
        
        # Check all agents are loaded
        assert len(agent_manager.agents) == 80
        
        # Check all categories are represented
        categories = set(agent.category for agent in agent_manager.agents.values())
        assert len(categories) == 16
    
    @pytest.mark.asyncio
    async def test_wave_management_agent(self):
        """Test Wave Management Functional Agent"""
        agent = agent_manager.get_agent("wave_management_functional")
        assert agent is not None
        assert agent.category == "Wave Management"
        
        # Test wave planning
        result = await agent.process(
            "Plan a wave for 100 orders with high priority",
            {"user_id": "test_user"}
        )
        
        assert "response" in result
        assert "wave" in result["response"].lower()
    
    @pytest.mark.asyncio
    async def test_inventory_agent(self):
        """Test Inventory Management Agent"""
        agent = agent_manager.get_agent("inventory_management_functional")
        assert agent is not None
        
        # Test inventory query
        result = await agent.process(
            "What is the stock level for SKU-12345?",
            {"user_id": "test_user"}
        )
        
        assert "response" in result
        assert result["agent"] == "inventory_management_functional"
    
    @pytest.mark.asyncio
    async def test_allocation_agent(self):
        """Test Allocation Technical Agent"""
        agent = agent_manager.get_agent("allocation_technical")
        assert agent is not None
        
        # Test allocation algorithm
        result = await agent.process(
            "Explain FIFO allocation strategy",
            {"user_id": "test_user"}
        )
        
        assert "response" in result
        assert "FIFO" in result["response"]
    
    @pytest.mark.asyncio
    async def test_picking_agent(self):
        """Test Picking Functional Agent"""
        agent = agent_manager.get_agent("picking_functional")
        assert agent is not None
        
        # Test picking strategy
        result = await agent.process(
            "What is the best picking strategy for small items?",
            {"user_id": "test_user"}
        )
        
        assert "response" in result
        assert any(word in result["response"].lower() for word in ["batch", "zone", "pick"])
    
    @pytest.mark.asyncio
    async def test_agent_routing(self):
        """Test automatic agent routing"""
        # Test query about waves
        query1 = "How do I release a wave?"
        suggested_agent = agent_manager.suggest_agent(query1)
        assert suggested_agent["category"] == "Wave Management"
        
        # Test query about inventory
        query2 = "Show me low stock items"
        suggested_agent = agent_manager.suggest_agent(query2)
        assert suggested_agent["category"] == "Inventory Management"
        
        # Test query about shipping
        query3 = "Which carrier should I use for express delivery?"
        suggested_agent = agent_manager.suggest_agent(query3)
        assert suggested_agent["category"] == "Shipping and Carrier Management"
    
    @pytest.mark.asyncio
    async def test_multi_agent_collaboration(self):
        """Test multiple agents working together"""
        # Start with allocation
        allocation_agent = agent_manager.get_agent("allocation_functional")
        allocation_result = await allocation_agent.process(
            "Allocate inventory for order #12345",
            {"user_id": "test_user"}
        )
        
        # Then move to picking
        picking_agent = agent_manager.get_agent("picking_functional")
        picking_result = await picking_agent.process(
            f"Create pick list based on allocation: {allocation_result['response'][:100]}",
            {"user_id": "test_user"}
        )
        
        assert "response" in picking_result
        assert picking_result["agent"] == "picking_functional"
    
    @pytest.mark.asyncio
    async def test_agent_memory(self):
        """Test agent conversation memory"""
        agent = agent_manager.get_agent("inventory_management_functional")
        
        # First query
        result1 = await agent.process(
            "Track SKU-999",
            {"user_id": "test_user", "conversation_id": "test_conv_1"}
        )
        
        # Follow-up query using context
        result2 = await agent.process(
            "What's its location?",
            {"user_id": "test_user", "conversation_id": "test_conv_1"}
        )
        
        # Should remember SKU-999 from context
        assert "response" in result2
    
    @pytest.mark.asyncio
    async def test_agent_error_handling(self):
        """Test agent error handling"""
        agent = agent_manager.get_agent("wave_management_technical")
        
        # Test with invalid input
        result = await agent.process(
            "",  # Empty query
            {"user_id": "test_user"}
        )
        
        assert "error" in result or "response" in result
    
    @pytest.mark.asyncio
    async def test_all_agent_categories(self):
        """Test each category has 5 agents"""
        categories = {}
        for agent_name, agent in agent_manager.agents.items():
            if agent.category not in categories:
                categories[agent.category] = []
            categories[agent.category].append(agent_name)
        
        # Each category should have exactly 5 agents
        for category, agents in categories.items():
            assert len(agents) == 5, f"{category} has {len(agents)} agents instead of 5"
            
            # Check agent types
            agent_types = [a.split('_')[-1] for a in agents]
            expected_types = ['functional', 'technical', 'configuration', 'relationships', 'notes']
            for expected in expected_types:
                assert expected in agent_types, f"{category} missing {expected} agent"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])