#!/usr/bin/env python3
"""
Test version 0.17.7 which supposedly fixed group_id with FalkorDB (PR #733)
"""

import asyncio
from datetime import datetime, timezone


async def test_v0177():
    """Test if v0.17.7 actually fixed the group_id issue."""
    
    print("="*60)
    print("TESTING VERSION 0.17.7 (PR #733 FIX)")
    print("="*60)
    
    try:
        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        from graphiti_core.nodes import EpisodeType
        from graphiti_core.utils.maintenance.graph_data_operations import clear_data
        
        print("✓ Imports successful")
        
        # Check version if possible
        try:
            import graphiti_core
            if hasattr(graphiti_core, '__version__'):
                print(f"Version: {graphiti_core.__version__}")
        except:
            pass
        
        driver = FalkorDriver(
            host="localhost",
            port=6380,
            database="test_v0177"
        )
        
        client = Graphiti(graph_driver=driver)
        
        # Clear and setup
        await clear_data(client.driver)
        print("✓ Cleared data")
        
        await client.build_indices_and_constraints()
        print("✓ Built indices")
        
        # The critical test
        print("\nTesting add_episode...")
        await client.add_episode(
            name="Test v0.17.7",
            episode_body="Testing if PR #733 fixed group_id with FalkorDB",
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Version test"
        )
        
        print("\n🎉 SUCCESS! Version 0.17.7 WORKS with FalkorDB!")
        print("PR #733 DID fix the group_id issue")
        print("\n⚠️  THIS CONFIRMS A REGRESSION IN v0.18.x!")
        return True
        
    except Exception as e:
        error_str = str(e)
        if "group_id" in error_str:
            print(f"\n❌ Version 0.17.7 STILL HAS group_id ERROR!")
            print(f"Error: {error_str}")
            print("\nPR #733 did NOT fully fix the issue")
            return False
        else:
            print(f"\n❌ Different error: {error_str}")
            return False


async def main():
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    result = await test_v0177()
    
    print("\n" + "="*60)
    print("CONCLUSION")
    print("="*60)
    
    if result:
        print("""
CRITICAL FINDING: REGRESSION DETECTED!
- Version 0.17.7 (with PR #733) WORKS with FalkorDB
- Version 0.18.7 (current) FAILS with group_id error
- This is a REGRESSION introduced between v0.17.7 and v0.18.0

GitHub Issue Priority: HIGH / CRITICAL
Label as: regression, breaking-change
""")
    else:
        print("""
FINDING: Original fix incomplete
- Version 0.17.7 (PR #733) still has the issue
- The fix in PR #733 was incomplete or didn't work
- This is an ongoing issue, not a regression

GitHub Issue Priority: HIGH
Label as: bug, falkordb
""")


if __name__ == "__main__":
    asyncio.run(main())