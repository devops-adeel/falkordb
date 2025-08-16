#!/usr/bin/env python3
"""
Basic FalkorDB connection test without Graphiti to isolate the issue.
"""

import asyncio
from falkordb import FalkorDB

async def test_basic_connection():
    """Test basic FalkorDB connectivity."""
    
    try:
        # Connect directly to FalkorDB
        db = FalkorDB(host='localhost', port=6380)
        
        # Select a graph
        g = db.select_graph('test_graph')
        
        # Create a simple node
        result = g.query("CREATE (n:TestNode {name: 'test', value: 123}) RETURN n")
        print("✅ Created node successfully")
        
        # Query the node
        result = g.query("MATCH (n:TestNode) RETURN n.name, n.value")
        for row in result.result_set:
            print(f"✅ Found node: name={row[0]}, value={row[1]}")
        
        # Clean up
        g.query("MATCH (n:TestNode) DELETE n")
        print("✅ Cleaned up test data")
        
        # Delete the test graph
        g.delete()
        print("✅ Deleted test graph")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_basic_connection())
    if success:
        print("\n✅ FalkorDB is working correctly on port 6380")
    else:
        print("\n❌ FalkorDB connection issues detected")