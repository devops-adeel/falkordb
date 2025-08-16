#!/usr/bin/env python3
"""
Minimal reproducible example for group_id RediSearch error with FalkorDB.
This test isolates the issue to help create a GitHub bug report.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType
from graphiti_core.utils.maintenance.graph_data_operations import clear_data


async def test_vanilla_graphiti():
    """Test 1: Vanilla Graphiti without custom entities."""
    print("\n" + "="*60)
    print("TEST 1: Vanilla Graphiti (No Custom Entities)")
    print("="*60)
    
    driver = FalkorDriver(
        host="localhost",
        port=6380,
        database="test_minimal_group_id"
    )
    
    client = Graphiti(graph_driver=driver)
    
    # Clear any existing data
    try:
        await clear_data(client.driver)
        print("✓ Cleared existing data")
    except Exception as e:
        print(f"  Note: Clear data had issue: {e}")
    
    # Build indices - this might be where group_id issue occurs
    try:
        await client.build_indices_and_constraints()
        print("✓ Built indices and constraints")
    except Exception as e:
        print(f"✗ Error building indices: {e}")
        return False
    
    # Try to add a simple episode WITHOUT custom entities
    print("\nAttempting to add episode without custom entities...")
    try:
        result = await client.add_episode(
            name="Test Episode",
            episode_body="This is a simple test without custom entities",
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Minimal test"
            # Note: NOT passing entity_types or edge_types
        )
        print(f"✓ Episode added successfully: {result}")
        return True
    except Exception as e:
        error_str = str(e)
        if "group_id" in error_str:
            print(f"✗ GROUP_ID ERROR FOUND: {error_str}")
            # Extract the exact error location
            if "offset" in error_str:
                print(f"  Error details: {error_str}")
        else:
            print(f"✗ Different error: {error_str}")
        return False


async def test_with_explicit_group_id():
    """Test 2: Explicitly use group_id parameter."""
    print("\n" + "="*60)
    print("TEST 2: Explicit group_id Parameter")
    print("="*60)
    
    driver = FalkorDriver(
        host="localhost",
        port=6380,
        database="test_explicit_group"
    )
    
    client = Graphiti(graph_driver=driver)
    
    try:
        await clear_data(client.driver)
        await client.build_indices_and_constraints()
        print("✓ Setup complete")
    except Exception as e:
        print(f"  Setup issue: {e}")
    
    # Try with explicit group_id
    print("\nAttempting to add episode WITH group_id...")
    try:
        result = await client.add_episode(
            name="Test with Group",
            episode_body="Testing with explicit group_id",
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            group_id="test_group_123"  # Explicitly setting group_id
        )
        print(f"✓ Episode with group_id added: {result}")
        return True
    except Exception as e:
        if "group_id" in str(e):
            print(f"✗ GROUP_ID ERROR: {e}")
        else:
            print(f"✗ Error: {e}")
        return False


async def test_search_operations():
    """Test 3: Test search operations that might trigger group_id issues."""
    print("\n" + "="*60)
    print("TEST 3: Search Operations")
    print("="*60)
    
    driver = FalkorDriver(
        host="localhost",
        port=6380,
        database="test_search"
    )
    
    client = Graphiti(graph_driver=driver)
    
    try:
        await clear_data(client.driver)
        await client.build_indices_and_constraints()
        print("✓ Setup complete")
    except Exception as e:
        print(f"  Setup issue: {e}")
        return False
    
    # Try a search operation
    print("\nAttempting search operation...")
    try:
        results = await client.search("test query", num_results=5)
        print(f"✓ Search successful: {len(results)} results")
        return True
    except Exception as e:
        if "group_id" in str(e):
            print(f"✗ GROUP_ID ERROR in search: {e}")
        else:
            print(f"✗ Search error: {e}")
        return False


async def test_direct_falkordb_index():
    """Test 4: Direct FalkorDB fulltext index creation with group_id."""
    print("\n" + "="*60)
    print("TEST 4: Direct FalkorDB Fulltext Index")
    print("="*60)
    
    from falkordb import FalkorDB
    
    db = FalkorDB(host='localhost', port=6380)
    g = db.select_graph('test_direct_index')
    
    # Try to create a fulltext index with group_id field
    print("Creating fulltext index with group_id field...")
    
    queries_to_test = [
        # Standard fields only
        ("Standard fields", "CALL db.idx.fulltext.createNodeIndex('Entity', 'name', 'summary')"),
        # With group_id
        ("With group_id", "CALL db.idx.fulltext.createNodeIndex('Entity', 'name', 'summary', 'group_id')"),
        # With escaped group_id
        ("Escaped group_id", "CALL db.idx.fulltext.createNodeIndex('Entity', 'name', 'summary', 'group\\_id')"),
        # With quoted group_id
        ("Quoted group_id", "CALL db.idx.fulltext.createNodeIndex('Entity', 'name', 'summary', '\"group_id\"')"),
    ]
    
    for desc, query in queries_to_test:
        print(f"\n  Testing: {desc}")
        print(f"  Query: {query}")
        try:
            result = g.query(query)
            print(f"  ✓ Success: Index created")
        except Exception as e:
            error_str = str(e)
            if "group_id" in error_str or "offset" in error_str:
                print(f"  ✗ GROUP_ID ERROR: {error_str}")
            else:
                print(f"  ✗ Error: {error_str}")
    
    # Cleanup
    try:
        g.delete()
    except:
        pass


async def test_graphiti_versions():
    """Test 5: Check Graphiti version and configuration."""
    print("\n" + "="*60)
    print("TEST 5: Version Information")
    print("="*60)
    
    import graphiti_core
    print(f"Graphiti version: {graphiti_core.__version__}")
    
    # Check if there's a way to see what indices Graphiti tries to create
    driver = FalkorDriver(
        host="localhost",
        port=6380,
        database="test_version_check"
    )
    
    client = Graphiti(graph_driver=driver)
    
    # Inspect what Graphiti does during index creation
    print("\nInspecting index creation...")
    try:
        # This will fail but we want to see the exact query
        await client.build_indices_and_constraints()
        print("✓ Indices built")
    except Exception as e:
        print(f"Index creation details: {e}")


async def main():
    """Run all minimal tests to isolate the group_id issue."""
    print("\n" + "="*70)
    print("MINIMAL REPRODUCIBLE EXAMPLE: group_id RediSearch Error")
    print("="*70)
    print(f"Testing at: {datetime.now()}")
    print(f"Python: {sys.version}")
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run tests
    results = []
    
    # Test 1: Vanilla Graphiti
    result1 = await test_vanilla_graphiti()
    results.append(("Vanilla Graphiti", result1))
    
    # Test 2: Explicit group_id
    result2 = await test_with_explicit_group_id()
    results.append(("Explicit group_id", result2))
    
    # Test 3: Search operations
    result3 = await test_search_operations()
    results.append(("Search operations", result3))
    
    # Test 4: Direct FalkorDB
    await test_direct_falkordb_index()
    results.append(("Direct FalkorDB index", "See output above"))
    
    # Test 5: Version info
    await test_graphiti_versions()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for test_name, result in results:
        status = "✓ PASS" if result == True else "✗ FAIL" if result == False else "ℹ INFO"
        print(f"{status} - {test_name}")
    
    print("\n" + "="*60)
    print("FINDINGS FOR GITHUB ISSUE")
    print("="*60)
    print("""
1. The error occurs at: [Document where it happens]
2. The exact error is: 'RediSearch: Syntax error at offset 12 near group_id'
3. This affects: [Which operations fail]
4. Workaround: [What works if anything]
5. Root cause hypothesis: FalkorDB's RediSearch module doesn't support
   underscores in certain contexts, or 'group_id' conflicts with reserved syntax
""")


if __name__ == "__main__":
    asyncio.run(main())