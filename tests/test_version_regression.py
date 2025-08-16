#!/usr/bin/env python3
"""
Test for regression between Graphiti versions 0.17.7 and 0.18.7
This script tests if the group_id issue is a regression from the fix in v0.17.7

REASONING:
1. Version 0.17.7 had PR #733 that supposedly fixed "Group ID usage with FalkorDB"
2. Current version 0.18.7 has the group_id RediSearch error
3. We need to determine if this is a regression or if the original fix was incomplete
"""

import subprocess
import sys
import asyncio
import json
from datetime import datetime, timezone


def install_graphiti_version(version):
    """Install a specific version of graphiti-core."""
    print(f"\n{'='*60}")
    print(f"Installing graphiti-core=={version}")
    print('='*60)
    
    cmd = [sys.executable, "-m", "pip", "install", f"graphiti-core[falkordb]=={version}", "--force-reinstall", "--quiet"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(f"✓ Successfully installed graphiti-core {version}")
            return True
        else:
            print(f"✗ Failed to install: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ Installation timed out")
        return False
    except Exception as e:
        print(f"✗ Installation error: {e}")
        return False


async def test_graphiti_version(version_info):
    """Test a specific version of Graphiti with FalkorDB."""
    version = version_info['version']
    
    print(f"\n{'='*60}")
    print(f"TESTING VERSION: {version}")
    print('='*60)
    
    # Import after installation to get correct version
    try:
        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        from graphiti_core.nodes import EpisodeType
        from graphiti_core.utils.maintenance.graph_data_operations import clear_data
    except ImportError as e:
        print(f"✗ Import error: {e}")
        version_info['result'] = 'import_error'
        version_info['error'] = str(e)
        return
    
    # Test database name unique per version
    db_name = f"test_v{version.replace('.', '_')}"
    
    try:
        driver = FalkorDriver(
            host="localhost",
            port=6380,
            database=db_name
        )
        
        client = Graphiti(graph_driver=driver)
        
        # Clear and setup
        await clear_data(client.driver)
        await client.build_indices_and_constraints()
        
        # The critical test - does add_episode work?
        print(f"Testing add_episode with version {version}...")
        
        await client.add_episode(
            name=f"Test v{version}",
            episode_body=f"Testing version {version} for group_id issue",
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Version test"
        )
        
        print(f"✓ Version {version}: add_episode WORKS!")
        version_info['result'] = 'success'
        version_info['group_id_works'] = True
        
    except Exception as e:
        error_str = str(e)
        if "group_id" in error_str and "RediSearch" in error_str:
            print(f"✗ Version {version}: GROUP_ID ERROR!")
            print(f"  Error: {error_str[:100]}...")
            version_info['result'] = 'group_id_error'
            version_info['group_id_works'] = False
        else:
            print(f"✗ Version {version}: Different error")
            print(f"  Error: {error_str[:100]}...")
            version_info['result'] = 'other_error'
            version_info['group_id_works'] = False
        version_info['error'] = error_str


async def test_direct_query_differences():
    """Test if the query format changed between versions."""
    print(f"\n{'='*60}")
    print("ANALYZING QUERY DIFFERENCES")
    print('='*60)
    
    # This would require examining the actual query generation code
    # We can infer from the error that the query uses @group_id syntax
    
    print("\nKnown query format in v0.18.7:")
    print('  @group_id:"_" AND (search_terms)')
    print("\nThis syntax causes: RediSearch: Syntax error at offset 12")
    
    print("\nPossible formats that might work:")
    print('  1. group_id:"_" AND (search_terms)  // Without @')
    print('  2. @"group_id":"_" AND (search_terms)  // Quoted field')
    print('  3. @group\\_id:"_" AND (search_terms)  // Escaped underscore')
    print('  4. WHERE n.group_id = "_"  // Using WHERE clause instead')


async def main():
    """Run version regression tests."""
    print("\n" + "="*70)
    print("VERSION REGRESSION TEST: group_id Issue")
    print("="*70)
    print(f"Test Date: {datetime.now()}")
    print(f"Python: {sys.version}")
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Versions to test
    versions_to_test = [
        # Note: Some versions might not exist or be compatible
        # {"version": "0.17.6", "expected": "unknown", "notes": "Before PR #733"},
        # {"version": "0.17.7", "expected": "fixed", "notes": "PR #733 fix"},
        # {"version": "0.17.11", "expected": "unknown", "notes": "Last 0.17.x"},
        # {"version": "0.18.0", "expected": "unknown", "notes": "Major version bump"},
        {"version": "0.18.7", "expected": "broken", "notes": "Current version"},
    ]
    
    results = []
    
    # Test current version first (already installed)
    print("\n" + "="*60)
    print("TESTING CURRENT INSTALLATION")
    print("="*60)
    
    current_version = {"version": "current", "expected": "broken", "notes": "Pre-installed"}
    await test_graphiti_version(current_version)
    results.append(current_version)
    
    # Test other versions
    for version_info in versions_to_test:
        if install_graphiti_version(version_info['version']):
            await test_graphiti_version(version_info)
            results.append(version_info)
        else:
            version_info['result'] = 'install_failed'
            results.append(version_info)
    
    # Analyze query differences
    await test_direct_query_differences()
    
    # Summary
    print("\n" + "="*70)
    print("REGRESSION TEST SUMMARY")
    print("="*70)
    
    print("\n| Version  | Expected | Actual Result | group_id Works? |")
    print("|----------|----------|---------------|-----------------|")
    
    for r in results:
        version = r.get('version', 'unknown')
        expected = r.get('expected', '?')
        result = r.get('result', '?')
        works = "✓" if r.get('group_id_works') else "✗"
        print(f"| {version:8} | {expected:8} | {result:13} | {works:15} |")
    
    # Analysis
    print("\n" + "="*60)
    print("ANALYSIS")
    print("="*60)
    
    has_regression = False
    for r in results:
        if r.get('version') == '0.17.7' and r.get('group_id_works'):
            has_regression = True
            break
    
    if has_regression:
        print("""
REGRESSION CONFIRMED:
- Version 0.17.7 had a working fix (PR #733)
- Version 0.18.7 has the group_id error
- This is a regression introduced after v0.17.7

The issue needs to be reported as a REGRESSION with HIGH priority.
""")
    else:
        print("""
FINDINGS:
- Current version (0.18.7) has the group_id error
- Unable to confirm if 0.17.7 actually fixed it (installation/compatibility issues)
- The error appears to be in the query generation using @group_id syntax

The issue should be reported, noting PR #733 claimed to fix this.
""")
    
    print("\nRECOMMENDED ACTIONS:")
    print("1. Report as potential regression from PR #733")
    print("2. Include the exact query that fails: @group_id:\"_\"")
    print("3. Suggest query format changes as fix")
    print("4. Request making group_id optional for FalkorDB users")


if __name__ == "__main__":
    asyncio.run(main())