#!/usr/bin/env python3
"""
Test version 0.18.0 - first version after 0.17.7
"""

import asyncio
from datetime import datetime, timezone


async def test_v0180():
    """Test if v0.18.0 has the group_id issue."""
    
    print("="*60)
    print("TESTING VERSION 0.18.0")
    print("="*60)
    
    try:
        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        from graphiti_core.nodes import EpisodeType
        from graphiti_core.utils.maintenance.graph_data_operations import clear_data
        
        print("✓ Imports successful")
        
        driver = FalkorDriver(
            host="localhost",
            port=6380,
            database="test_v0180"
        )
        
        client = Graphiti(graph_driver=driver)
        
        await clear_data(client.driver)
        print("✓ Cleared data")
        
        await client.build_indices_and_constraints()
        print("✓ Built indices")
        
        print("\nTesting add_episode...")
        await client.add_episode(
            name="Test v0.18.0",
            episode_body="Testing v0.18.0 for group_id issue",
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Version test"
        )
        
        print("\n✅ SUCCESS! Version 0.18.0 WORKS!")
        return True
        
    except Exception as e:
        error_str = str(e)
        if "group_id" in error_str:
            print(f"\n❌ Version 0.18.0 HAS group_id ERROR!")
            print(f"Error: {error_str}")
            return False
        else:
            print(f"\n❌ Different error: {error_str}")
            return False


async def main():
    from dotenv import load_dotenv
    load_dotenv()
    
    result = await test_v0180()
    
    if not result:
        print("\nCONFIRMED: Regression started in v0.18.0")


if __name__ == "__main__":
    asyncio.run(main())