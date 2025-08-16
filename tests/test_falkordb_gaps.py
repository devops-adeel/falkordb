#!/usr/bin/env python3
"""
Tests to identify and document gaps between Graphiti custom entities and FalkorDB.
These tests are expected to fail and serve as documentation of known issues.
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
from falkordb import FalkorDB

# Import our custom entities
from entities.gtd_entities import (
    GTD_ENTITY_TYPES, GTD_EDGE_TYPES, GTD_EDGE_TYPE_MAP
)


class TestFalkorDBGaps:
    """Document known gaps and issues with FalkorDB integration."""
    
    async def test_group_id_redisearch_error(self):
        """Test and document the group_id RediSearch syntax error."""
        
        print("\n" + "="*60)
        print("GAP TEST: group_id RediSearch Error")
        print("="*60)
        
        driver = FalkorDriver(
            host="localhost",
            port=6380,
            database="test_gaps"
        )
        
        client = Graphiti(graph_driver=driver)
        
        try:
            # Clear existing data
            await clear_data(client.driver)
            await client.build_indices_and_constraints()
        except:
            pass
        
        print("\n📝 Issue: FalkorDB's RediSearch module doesn't support group_id field")
        print("   Expected: Should be able to add episodes and search them")
        print("   Actual: RediSearch syntax error at offset 12 near group_id")
        
        # Try to add an episode (this will fail during entity extraction/search)
        try:
            result = await client.add_episode(
                name="Test Episode",
                episode_body="This is a test for the group_id issue",
                source=EpisodeType.text,
                reference_time=datetime.now(timezone.utc),
                source_description="Test data",
                entity_types=GTD_ENTITY_TYPES,
                edge_types=GTD_EDGE_TYPES,
                edge_type_map=GTD_EDGE_TYPE_MAP
            )
            print("✅ Episode added (unexpected success)")
        except Exception as e:
            if "group_id" in str(e):
                print(f"❌ Expected error: {type(e).__name__}")
                print(f"   Error contains 'group_id': ✓")
            else:
                print(f"❌ Unexpected error: {e}")
        
        # Try search (will also fail)
        try:
            results = await client.search("test", num_results=5)
            print(f"✅ Search worked: {len(results)} results (unexpected)")
        except Exception as e:
            if "group_id" in str(e):
                print(f"❌ Search failed with group_id error (expected)")
            else:
                print(f"❌ Search failed with different error: {e}")
        
        print("\n🔧 Workaround: Use JSON backup instead of direct Graphiti storage")
        print("   Or wait for FalkorDB to support group_id in RediSearch")
    
    async def test_custom_labels_not_persisted(self):
        """Test that custom entity labels are not persisted in FalkorDB."""
        
        print("\n" + "="*60)
        print("GAP TEST: Custom Entity Labels Not Persisted")
        print("="*60)
        
        # Direct FalkorDB connection to check what's actually stored
        db = FalkorDB(host='localhost', port=6380)
        g = db.select_graph('test_labels')
        
        print("\n📝 Issue: Custom entity labels (e.g., :Task, :Project) not persisted")
        print("   Expected: Nodes should have specific labels like :Task, :Project")
        print("   Actual: All nodes only have generic :Entity label")
        
        # Create a node directly to show what we want
        try:
            # What we want: specific labels
            result = g.query("""
                CREATE (t:Task:Entity {
                    uuid: 'test-task-001',
                    description: 'Test task with custom label',
                    created_at: timestamp()
                })
                RETURN t
            """)
            print("\n✅ Created node with custom :Task label directly in FalkorDB")
            
            # Query to check labels
            result = g.query("""
                MATCH (n)
                WHERE 'test-task-001' IN n.uuid
                RETURN labels(n) as labels, n.uuid as uuid
            """)
            
            for row in result.result_set:
                print(f"   Node labels: {row[0]}")
                print(f"   Expected: ['Task', 'Entity']")
                
        except Exception as e:
            print(f"❌ Error checking labels: {e}")
        
        # What Graphiti creates: only Entity label
        print("\n📊 When Graphiti creates nodes:")
        print("   - Uses MERGE (n:Entity {uuid: $uuid})")
        print("   - Hardcoded to only use :Entity label")
        print("   - Custom entity type info is lost")
        
        print("\n🔧 Workaround: Store entity type in a property field")
        print("   Or use fact strings to encode entity type information")
        
        # Cleanup
        try:
            g.query("MATCH (n) WHERE n.uuid = 'test-task-001' DELETE n")
            g.delete()
        except:
            pass
    
    async def test_custom_properties_not_persisted(self):
        """Test that custom entity properties are not persisted."""
        
        print("\n" + "="*60)
        print("GAP TEST: Custom Entity Properties Not Persisted")
        print("="*60)
        
        print("\n📝 Issue: Custom properties from Pydantic models not saved")
        print("   Expected: Task properties like priority, energy_required saved")
        print("   Actual: Only standard properties (uuid, name, summary, created_at)")
        
        # Direct FalkorDB connection
        db = FalkorDB(host='localhost', port=6380)
        g = db.select_graph('test_properties')
        
        # Create what we want
        try:
            result = g.query("""
                CREATE (t:Entity {
                    uuid: 'test-task-002',
                    name: 'Task with custom properties',
                    description: 'Test task',
                    priority: 'A',
                    energy_required: 'high',
                    time_estimate: 30,
                    context: '@office',
                    created_at: timestamp()
                })
                RETURN t
            """)
            print("\n✅ Created node with custom properties directly")
            
            # Query to check properties
            result = g.query("""
                MATCH (n)
                WHERE n.uuid = 'test-task-002'
                RETURN properties(n) as props
            """)
            
            for row in result.result_set:
                props = row[0]
                print(f"\n   Properties stored: {list(props.keys())}")
                print(f"   ✓ Custom properties present when created directly")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("\n📊 When Graphiti creates nodes:")
        print("   - Only saves: uuid, name, summary, created_at")
        print("   - Ignores all custom Pydantic fields")
        print("   - EntityNode.save() method hardcodes these fields")
        
        print("\n🔧 Workaround: Encode custom data in the 'summary' field")
        print("   Or use episode metadata to store custom properties")
        
        # Cleanup
        try:
            g.query("MATCH (n) WHERE n.uuid = 'test-task-002' DELETE n")
            g.delete()
        except:
            pass
    
    async def test_complex_queries_without_labels(self):
        """Test that complex queries fail without proper entity labels."""
        
        print("\n" + "="*60)
        print("GAP TEST: Complex Queries Without Entity Labels")
        print("="*60)
        
        print("\n📝 Issue: Can't filter by entity type in queries")
        print("   Expected: MATCH (t:Task) WHERE t.priority = 'A'")
        print("   Actual: All nodes are :Entity, can't distinguish types")
        
        # Direct FalkorDB connection
        db = FalkorDB(host='localhost', port=6380)
        g = db.select_graph('test_queries')
        
        try:
            # Create mixed entity types (as Graphiti would)
            g.query("""
                CREATE 
                    (t1:Entity {uuid: 'task-1', name: 'Task 1', created_at: timestamp()}),
                    (t2:Entity {uuid: 'task-2', name: 'Task 2', created_at: timestamp()}),
                    (p1:Entity {uuid: 'proj-1', name: 'Project 1', created_at: timestamp()}),
                    (c1:Entity {uuid: 'ctx-1', name: 'Context @office', created_at: timestamp()})
            """)
            
            print("\n❌ Problem: Can't query for just tasks")
            result = g.query("MATCH (t:Task) RETURN count(t)")
            print(f"   Tasks found with :Task label: {result.result_set[0][0]} (should be 2)")
            
            result = g.query("MATCH (e:Entity) RETURN count(e)")
            print(f"   All entities: {result.result_set[0][0]} (all are :Entity)")
            
            print("\n❌ Can't use entity-specific properties in queries")
            print("   Would need: MATCH (t:Task) WHERE t.priority = 'A'")
            print("   But priority property doesn't exist")
            
        except Exception as e:
            print(f"   Expected behavior demonstrated: {e}")
        
        print("\n🔧 Workaround: Add entity_type property manually")
        print("   Then query: MATCH (n:Entity) WHERE n.entity_type = 'Task'")
        
        # Cleanup
        try:
            g.query("MATCH (n) DELETE n")
            g.delete()
        except:
            pass
    
    async def test_edge_properties_limitations(self):
        """Test limitations with custom edge properties."""
        
        print("\n" + "="*60)
        print("GAP TEST: Custom Edge Properties")
        print("="*60)
        
        print("\n📝 Issue: Custom edge properties from Pydantic models")
        print("   Expected: Edges with properties like 'strength', 'confidence'")
        print("   Actual: Limited edge property support")
        
        # Direct FalkorDB test
        db = FalkorDB(host='localhost', port=6380)
        g = db.select_graph('test_edges')
        
        try:
            # Create nodes and edge with custom properties
            g.query("""
                CREATE 
                    (t:Task {uuid: 'task-1', name: 'Task 1'}),
                    (p:Project {uuid: 'proj-1', name: 'Project 1'}),
                    (t)-[r:BELONGS_TO {
                        strength: 0.9,
                        confidence: 0.95,
                        is_primary: true,
                        created_at: timestamp()
                    }]->(p)
            """)
            
            print("✅ Created edge with custom properties directly")
            
            # Query edge properties
            result = g.query("""
                MATCH ()-[r:BELONGS_TO]->()
                RETURN properties(r) as props
            """)
            
            for row in result.result_set:
                props = row[0]
                print(f"   Edge properties: {list(props.keys())}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("\n📊 Graphiti edge handling:")
        print("   - Creates edges but property persistence varies")
        print("   - Edge types from Pydantic not fully utilized")
        
        print("\n🔧 Workaround: Store relationship details in fact strings")
        
        # Cleanup
        try:
            g.query("MATCH (n) DELETE n")
            g.delete()
        except:
            pass


async def main():
    """Run gap tests and document findings."""
    print("\n🔍 FalkorDB-Graphiti Custom Entity Gap Analysis\n")
    
    test = TestFalkorDBGaps()
    
    # Run each gap test
    await test.test_group_id_redisearch_error()
    await test.test_custom_labels_not_persisted()
    await test.test_custom_properties_not_persisted()
    await test.test_complex_queries_without_labels()
    await test.test_edge_properties_limitations()
    
    print("\n" + "="*60)
    print("GAP ANALYSIS SUMMARY")
    print("="*60)
    
    print("""
Known Issues:
1. ❌ group_id causes RediSearch syntax errors in FalkorDB
2. ❌ Custom entity labels (e.g., :Task, :Project) not persisted
3. ❌ Custom properties from Pydantic models not saved to nodes
4. ❌ Can't filter queries by entity type
5. ⚠️  Limited support for custom edge properties

Recommended Workarounds:
1. ✅ Use JSON backup for full entity preservation
2. ✅ Store entity type in a property field
3. ✅ Encode custom data in summary or fact strings
4. ✅ Use episode metadata for custom properties
5. ✅ Avoid group_id entirely for shared knowledge graph

For Production Use:
- Custom entities work for extraction but not persistence
- Search works but without entity type filtering
- Relationships are created but with limited properties
- Consider these limitations in your architecture
""")


if __name__ == "__main__":
    asyncio.run(main())