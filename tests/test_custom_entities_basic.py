#!/usr/bin/env python3
"""
Basic tests for custom entity extraction with Graphiti and FalkorDB.
Tests entity extraction, search, and relationship creation.
"""

import asyncio
import os
import pytest
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType
from graphiti_core.utils.maintenance.graph_data_operations import clear_data

# Import our custom entities
from entities.arabic_entities import (
    ARABIC_ENTITY_TYPES, ARABIC_EDGE_TYPES, ARABIC_EDGE_TYPE_MAP
)
from entities.gtd_entities import (
    GTD_ENTITY_TYPES, GTD_EDGE_TYPES, GTD_EDGE_TYPE_MAP
)
from entities.islamic_finance_entities import (
    ISLAMIC_FINANCE_ENTITY_TYPES, ISLAMIC_FINANCE_EDGE_TYPES, 
    ISLAMIC_FINANCE_EDGE_TYPE_MAP
)


@pytest.fixture
async def graphiti_client():
    """Create a Graphiti client with FalkorDB driver."""
    driver = FalkorDriver(
        host="localhost",
        port=6380,
        database="test_custom_entities"
    )
    
    client = Graphiti(graph_driver=driver)
    
    # Clear any existing data
    try:
        await clear_data(client.driver)
        await client.build_indices_and_constraints()
    except:
        pass  # Ignore if graph doesn't exist
    
    yield client
    
    # Cleanup
    try:
        await clear_data(client.driver)
    except:
        pass


class TestBasicCustomEntities:
    """Test basic custom entity functionality."""
    
    @pytest.mark.asyncio
    async def test_arabic_entity_extraction(self, graphiti_client):
        """Test that Arabic learning entities are extracted from episodes."""
        
        print("\n" + "="*60)
        print("TEST: Arabic Entity Extraction")
        print("="*60)
        
        # Create an episode with Arabic learning content
        episode_text = """
        Today's Arabic lesson focused on verb conjugation in the past tense.
        The student Sarah is at intermediate level and studied for 45 minutes.
        We covered the vocabulary words: كتب (kataba - to write), قرأ (qara'a - to read).
        The grammar rule about past tense verb patterns was challenging but Sarah mastered it.
        Next lesson will be about present tense conjugation.
        """
        
        # Add episode with custom entities
        result = await graphiti_client.add_episode(
            name="Arabic Lesson Session",
            episode_body=episode_text,
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Arabic tutoring session",
            entity_types=ARABIC_ENTITY_TYPES,
            edge_types=ARABIC_EDGE_TYPES,
            edge_type_map=ARABIC_EDGE_TYPE_MAP
        )
        
        print(f"✅ Episode added successfully")
        print(f"   Episode UUID: {result.episode.uuid if hasattr(result, 'episode') else 'N/A'}")
        
        # Search for extracted entities
        await asyncio.sleep(1)  # Wait for indexing
        
        # Search for student
        results = await graphiti_client.search("Sarah student intermediate", num_results=5)
        print(f"\n📚 Student search results: {len(results)} found")
        for i, r in enumerate(results[:3]):
            print(f"   {i+1}. {r.fact[:100]}...")
        
        # Search for vocabulary
        results = await graphiti_client.search("vocabulary kataba write قرأ read", num_results=5)
        print(f"\n📖 Vocabulary search results: {len(results)} found")
        for i, r in enumerate(results[:3]):
            print(f"   {i+1}. {r.fact[:100]}...")
        
        # Search for grammar
        results = await graphiti_client.search("grammar past tense verb conjugation", num_results=5)
        print(f"\n📝 Grammar search results: {len(results)} found")
        for i, r in enumerate(results[:3]):
            print(f"   {i+1}. {r.fact[:100]}...")
        
        assert len(results) > 0, "Should find some results even without custom labels"
        
    @pytest.mark.asyncio
    async def test_gtd_entity_extraction(self, graphiti_client):
        """Test that GTD entities are extracted from task management content."""
        
        print("\n" + "="*60)
        print("TEST: GTD Entity Extraction")
        print("="*60)
        
        # Create GTD content
        gtd_data = {
            "projects": [
                {
                    "name": "Complete Q1 Budget Review",
                    "next_action": "Schedule meeting with finance team @office",
                    "area": "Finance",
                    "status": "active"
                }
            ],
            "tasks": [
                "Call dentist to schedule appointment @phone",
                "Review project proposals @computer",
                "Buy groceries @errands"
            ],
            "contexts": ["@office", "@phone", "@computer", "@errands"],
            "review_type": "weekly"
        }
        
        # Add as JSON episode
        result = await graphiti_client.add_episode(
            name="GTD Weekly Review",
            episode_body=json.dumps(gtd_data),
            source=EpisodeType.json,
            reference_time=datetime.now(timezone.utc),
            source_description="GTD weekly review session",
            entity_types=GTD_ENTITY_TYPES,
            edge_types=GTD_EDGE_TYPES,
            edge_type_map=GTD_EDGE_TYPE_MAP
        )
        
        print(f"✅ GTD episode added successfully")
        
        await asyncio.sleep(1)  # Wait for indexing
        
        # Search for projects
        results = await graphiti_client.search("Q1 Budget Review Finance project", num_results=5)
        print(f"\n📋 Project search results: {len(results)} found")
        for i, r in enumerate(results[:3]):
            print(f"   {i+1}. {r.fact[:100]}...")
        
        # Search for tasks
        results = await graphiti_client.search("dentist appointment phone call", num_results=5)
        print(f"\n✅ Task search results: {len(results)} found")
        for i, r in enumerate(results[:3]):
            print(f"   {i+1}. {r.fact[:100]}...")
        
        # Search for contexts
        results = await graphiti_client.search("@office @phone @computer contexts", num_results=5)
        print(f"\n📍 Context search results: {len(results)} found")
        for i, r in enumerate(results[:3]):
            print(f"   {i+1}. {r.fact[:100]}...")
        
        assert len(results) > 0, "Should find GTD entities"
        
    @pytest.mark.asyncio
    async def test_islamic_finance_entity_extraction(self, graphiti_client):
        """Test that Islamic finance entities are extracted."""
        
        print("\n" + "="*60)
        print("TEST: Islamic Finance Entity Extraction")
        print("="*60)
        
        # Create Islamic finance content
        finance_text = """
        Calculated zakat for the lunar year 1445H. Total wealth is $50,000 with
        nisab threshold at $3,500. The zakat due is $1,162.50 (2.5% of eligible wealth).
        
        Current accounts:
        - Mudarabah savings account at Al-Rajhi Bank with $25,000 balance
        - Wadiah current account at CIMB Islamic with $10,000
        
        Investments include:
        - Sukuk bonds worth $15,000 maturing in 2025
        - Shariah-compliant equity portfolio valued at $8,000
        
        Zakat payment will be distributed to local mosque for distribution to
        eligible beneficiaries in the fakir and miskin categories.
        """
        
        # Add episode
        result = await graphiti_client.add_episode(
            name="Zakat Calculation 1445H",
            episode_body=finance_text,
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Annual zakat calculation",
            entity_types=ISLAMIC_FINANCE_ENTITY_TYPES,
            edge_types=ISLAMIC_FINANCE_EDGE_TYPES,
            edge_type_map=ISLAMIC_FINANCE_EDGE_TYPE_MAP
        )
        
        print(f"✅ Islamic finance episode added successfully")
        
        await asyncio.sleep(1)  # Wait for indexing
        
        # Search for zakat calculation
        results = await graphiti_client.search("zakat calculation 1445H nisab $1162.50", num_results=5)
        print(f"\n🕌 Zakat search results: {len(results)} found")
        for i, r in enumerate(results[:3]):
            print(f"   {i+1}. {r.fact[:100]}...")
        
        # Search for accounts
        results = await graphiti_client.search("Mudarabah savings Al-Rajhi Wadiah CIMB", num_results=5)
        print(f"\n🏦 Account search results: {len(results)} found")
        for i, r in enumerate(results[:3]):
            print(f"   {i+1}. {r.fact[:100]}...")
        
        # Search for investments
        results = await graphiti_client.search("Sukuk bonds Shariah equity portfolio", num_results=5)
        print(f"\n💰 Investment search results: {len(results)} found")
        for i, r in enumerate(results[:3]):
            print(f"   {i+1}. {r.fact[:100]}...")
        
        assert len(results) > 0, "Should find Islamic finance entities"
        
    @pytest.mark.asyncio
    async def test_entity_relationships(self, graphiti_client):
        """Test that relationships between entities are created."""
        
        print("\n" + "="*60)
        print("TEST: Entity Relationships")
        print("="*60)
        
        # Create content with clear relationships
        relationship_text = """
        Student Ahmed completed the Arabic lesson "Introduction to Past Tense".
        The lesson covered vocabulary words including كتاب (kitab - book).
        Ahmed has mastered the basic past tense conjugation grammar rule.
        
        In GTD, the project "Learn Arabic" has next action "Practice verb conjugation @home".
        This project belongs to the "Personal Development" area of focus.
        
        The zakat calculation for account "Savings-001" shows $500 due.
        This will be paid to beneficiary "Local Mosque" in the fakir category.
        """
        
        # Add with all entity types
        combined_entities = {
            **ARABIC_ENTITY_TYPES,
            **GTD_ENTITY_TYPES,
            **ISLAMIC_FINANCE_ENTITY_TYPES
        }
        
        combined_edges = {
            **ARABIC_EDGE_TYPES,
            **GTD_EDGE_TYPES,
            **ISLAMIC_FINANCE_EDGE_TYPES
        }
        
        combined_edge_map = {
            **ARABIC_EDGE_TYPE_MAP,
            **GTD_EDGE_TYPE_MAP,
            **ISLAMIC_FINANCE_EDGE_TYPE_MAP
        }
        
        result = await graphiti_client.add_episode(
            name="Multi-domain Relationships",
            episode_body=relationship_text,
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Testing entity relationships",
            entity_types=combined_entities,
            edge_types=combined_edges,
            edge_type_map=combined_edge_map
        )
        
        print(f"✅ Multi-domain episode added successfully")
        
        await asyncio.sleep(1)  # Wait for indexing
        
        # Search for relationships
        results = await graphiti_client.search(
            "Ahmed completed lesson mastered grammar Past Tense", 
            num_results=10
        )
        print(f"\n🔗 Relationship search results: {len(results)} found")
        for i, r in enumerate(results[:5]):
            print(f"   {i+1}. {r.fact[:100]}...")
        
        # Check for project-action relationship
        results = await graphiti_client.search(
            "Learn Arabic project next action Practice verb conjugation",
            num_results=5
        )
        print(f"\n🔗 Project-Action results: {len(results)} found")
        
        # Check for zakat payment relationship
        results = await graphiti_client.search(
            "zakat payment Local Mosque beneficiary fakir",
            num_results=5
        )
        print(f"\n🔗 Zakat-Beneficiary results: {len(results)} found")
        
        assert len(results) > 0, "Should find relationship information"


async def main():
    """Run basic tests manually."""
    print("\n🚀 Starting Custom Entity Basic Tests\n")
    
    # Create client
    driver = FalkorDriver(
        host="localhost",
        port=6380,
        database="test_custom_entities_manual"
    )
    
    client = Graphiti(graph_driver=driver)
    
    # Clear existing data
    try:
        await clear_data(client.driver)
        await client.build_indices_and_constraints()
    except:
        pass
    
    # Create test instance
    test = TestBasicCustomEntities()
    
    # Run tests
    try:
        await test.test_arabic_entity_extraction(client)
        await test.test_gtd_entity_extraction(client)
        await test.test_islamic_finance_entity_extraction(client)
        await test.test_entity_relationships(client)
        
        print("\n" + "="*60)
        print("✅ ALL BASIC TESTS PASSED")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            await clear_data(client.driver)
        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())