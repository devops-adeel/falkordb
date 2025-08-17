#!/usr/bin/env python3
"""
Test all Graphiti versions between v0.17.7 and v0.18.7
to pinpoint exact version where regression occurred.
"""

import asyncio
import subprocess
import sys
from datetime import datetime, timezone


async def test_single_version(version):
    """Test a specific version for the group_id issue."""
    
    print(f"\n{'='*50}")
    print(f"Testing v{version}")
    print(f"{'='*50}")
    
    # Install version
    print(f"Installing graphiti-core=={version}...")
    cmd = [sys.executable, "-m", "pip", "install", 
           f"graphiti-core[falkordb]=={version}", "--quiet"]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Failed to install v{version}")
        return None
    
    try:
        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        from graphiti_core.nodes import EpisodeType
        from graphiti_core.utils.maintenance.graph_data_operations import clear_data
        
        driver = FalkorDriver(
            host="localhost",
            port=6380,
            database=f"test_{version.replace('.', '_')}"
        )
        
        client = Graphiti(graph_driver=driver)
        
        await clear_data(client.driver)
        await client.build_indices_and_constraints()
        
        await client.add_episode(
            name=f"Test {version}",
            episode_body="Testing group_id compatibility",
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc)
        )
        
        print(f"✅ v{version} WORKS!")
        return True
        
    except Exception as e:
        if "group_id" in str(e):
            print(f"❌ v{version} FAILS with group_id error")
            return False
        else:
            print(f"⚠️  v{version} - Other error")
            return None


async def main():
    from dotenv import load_dotenv
    load_dotenv()
    
    print("="*60)
    print("GRAPHITI VERSION REGRESSION FINDER")
    print("="*60)
    
    versions = [
        "0.17.7",   # PR #733 - Known working
        "0.17.8",   # Test
        "0.17.9",   # Test
        "0.17.10",  # Test
        "0.17.11",  # Test
        "0.18.0",   # Known broken
        "0.18.1",   # PR #761 - Test
    ]
    
    results = {}
    
    for version in versions:
        results[version] = await test_single_version(version)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for v, r in results.items():
        status = "✅ WORKS" if r == True else "❌ BROKEN" if r == False else "⚠️  ERROR"
        print(f"v{v}: {status}")
    
    # Find regression point
    last_working = None
    first_broken = None
    
    for v, r in results.items():
        if r == True:
            last_working = v
        elif r == False and first_broken is None:
            first_broken = v
    
    if last_working and first_broken:
        print(f"\n🔍 REGRESSION: v{last_working} → v{first_broken}")


if __name__ == "__main__":
    asyncio.run(main())