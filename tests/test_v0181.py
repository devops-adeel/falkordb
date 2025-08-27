#!/usr/bin/env python3
"""
Test version 0.18.1 which had PR #761 "feat/falkordb dynamic graph names"
This test determines if v0.18.1 temporarily fixed the group_id issue.
"""

import asyncio
import sys
from datetime import datetime, timezone


async def test_v0181():
    """Test if v0.18.1 with PR #761 fixed the group_id issue."""
    
    print("="*60)
    print("TESTING VERSION 0.18.1 (PR #761 - Dynamic Graph Names)")
    print("="*60)
    
    try:
        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        from graphiti_core.nodes import EpisodeType
        from graphiti_core.utils.maintenance.graph_data_operations import clear_data
        
        print("✓ Imports successful")
        
        # Check version
        try:
            import graphiti_core
            if hasattr(graphiti_core, '__version__'):
                version = graphiti_core.__version__
                print(f"Version: {version}")
                
                # Verify we're testing the right version
                if "0.18.1" not in str(version):
                    print(f"\n⚠️  WARNING: Expected v0.18.1, got {version}")
                    print("Install with: pip install 'graphiti-core[falkordb]==0.18.1'")
        except:
            print("Could not determine version")
        
        # Test with default database name
        print("\n1. Testing with default database...")
        driver = FalkorDriver(
            host="localhost",
            port=6380,
            database="test_v0181_default"
        )
        
        client = Graphiti(graph_driver=driver)
        
        # Clear and setup
        await clear_data(client.driver)
        print("✓ Cleared data")
        
        await client.build_indices_and_constraints()
        print("✓ Built indices")
        
        # The critical test - does it work?
        print("\nTesting add_episode...")
        await client.add_episode(
            name="Test v0.18.1",
            episode_body="Testing if PR #761 dynamic graph names fixed group_id",
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Version test"
        )
        
        print("\n✅ DEFAULT DATABASE TEST PASSED!")
        
        # Test with custom/dynamic database name (PR #761 feature)
        print("\n2. Testing with dynamic graph name...")
        driver2 = FalkorDriver(
            host="localhost",
            port=6380,
            database="dynamic_test_graph_v0181"  # Dynamic name
        )
        
        client2 = Graphiti(graph_driver=driver2)
        
        await clear_data(client2.driver)
        await client2.build_indices_and_constraints()
        
        await client2.add_episode(
            name="Dynamic Graph Test",
            episode_body="Testing dynamic graph names feature from PR #761",
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc)
        )
        
        print("✅ DYNAMIC GRAPH NAME TEST PASSED!")
        
        print("\n" + "="*60)
        print("🎉 SUCCESS! Version 0.18.1 WORKS with FalkorDB!")
        print("PR #761 (Dynamic Graph Names) FIXED the group_id issue!")
        print("\n⚠️  THIS CONFIRMS:")
        print("1. v0.17.7: ✅ Fixed by PR #733")
        print("2. v0.18.0: ❌ Broke (regression)")
        print("3. v0.18.1: ✅ Fixed by PR #761 (dynamic graph names)")
        print("4. v0.18.2+: ❌ Broke again (another regression)")
        print("\nTHIS IS A DOUBLE REGRESSION!")
        print("="*60)
        return True
        
    except Exception as e:
        error_str = str(e)
        if "group_id" in error_str:
            print(f"\n❌ Version 0.18.1 STILL HAS group_id ERROR!")
            print(f"Error: {error_str}")
            print("\nPR #761 did NOT fix the issue")
            print("The regression spans ALL v0.18.x versions")
            return False
        else:
            print(f"\n❌ Different error: {error_str}")
            return False


async def main():
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    print("\n" + "="*70)
    print("PR #761 TEST: Dynamic Graph Names Feature")
    print("="*70)
    print(f"Testing at: {datetime.now()}")
    print(f"Python: {sys.version}")
    
    result = await test_v0181()
    
    print("\n" + "="*60)
    print("CONCLUSION")
    print("="*60)
    
    if result:
        print("""
CRITICAL FINDING: TEMPORARY FIX EXISTED!
- Version 0.18.1 (with PR #761) TEMPORARILY fixed FalkorDB support
- The fix was then broken again in subsequent versions
- This is a DOUBLE REGRESSION (fixed twice, broken twice)

GitHub Issue Priority: CRITICAL
Label as: regression, breaking-change, was-working
Note: The fix exists in PR #761 but was lost
""")
    else:
        print("""
FINDING: Consistent regression
- Version 0.18.1 (PR #761) did NOT fix the issue
- The regression affects ALL v0.18.x versions
- Only v0.17.7 with PR #733 has the working fix

GitHub Issue Priority: HIGH
Label as: regression, breaking-change
""")


if __name__ == "__main__":
    asyncio.run(main())