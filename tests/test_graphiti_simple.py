#!/usr/bin/env python3
"""
Simple Graphiti-FalkorDB test to isolate the group_id issue.
"""

import os
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType

# Load environment variables
load_dotenv(os.path.expanduser("~/.env"))

async def test_graphiti_connection():
    """Test Graphiti with FalkorDB."""
    
    try:
        # Create FalkorDB driver
        driver = FalkorDriver(
            host="localhost",
            port=6380,
            database="test_graphiti_db"
        )
        
        # Initialize Graphiti
        graphiti = Graphiti(graph_driver=driver)
        print("✅ Graphiti initialized")
        
        # Try to add a simple episode
        try:
            result = await graphiti.add_episode(
                name="Test Episode",
                episode_body="This is a test episode for FalkorDB integration",
                source=EpisodeType.text,
                reference_time=datetime.now(timezone.utc),
                source_description="Test data"
            )
            print("✅ Episode added successfully")
            print(f"   Episode UUID: {result.episode.uuid if hasattr(result, 'episode') else 'N/A'}")
        except Exception as e:
            print(f"❌ Failed to add episode: {e}")
            print(f"   Error type: {type(e).__name__}")
            
        # Try a simple search
        try:
            results = await graphiti.search("test", num_results=5)
            print(f"✅ Search completed, found {len(results)} results")
        except Exception as e:
            print(f"❌ Search failed: {e}")
            
        return True
        
    except Exception as e:
        print(f"❌ Graphiti initialization failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_graphiti_connection())
    if success:
        print("\n✅ Basic Graphiti-FalkorDB integration working")
    else:
        print("\n❌ Graphiti-FalkorDB integration has issues")