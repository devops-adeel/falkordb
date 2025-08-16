#!/usr/bin/env python3
"""
GitHub Issue Report: group_id RediSearch Syntax Error
======================================================
This script demonstrates the group_id issue for GitHub bug report.

ISSUE TITLE: [BUG] RediSearch syntax error with @group_id field when using FalkorDB backend

ERROR FOUND:
RediSearch: Syntax error at offset 12 near group_id

ROOT CAUSE:
Graphiti generates a query using '@group_id:"_"' syntax which RediSearch cannot parse.
The @ symbol in RediSearch is used for field queries, but group_id appears to be
incompatible with this syntax in FalkorDB's RediSearch implementation.

ACTUAL QUERY THAT FAILS:
CALL db.idx.fulltext.queryNodes('Entity', $query)
WHERE query = '@group_id:"_" AND (test)'
"""

import asyncio
import os
from datetime import datetime, timezone
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType
from graphiti_core.utils.maintenance.graph_data_operations import clear_data


async def reproduce_issue():
    """Minimal code to reproduce the group_id error."""
    
    # Initialize FalkorDB driver
    driver = FalkorDriver(
        host="localhost",
        port=6380,  # Using custom port to avoid conflicts
        database="test_group_id_issue"
    )
    
    # Create Graphiti client
    client = Graphiti(graph_driver=driver)
    
    # Clear and setup
    await clear_data(client.driver)
    await client.build_indices_and_constraints()
    
    # This will fail with: RediSearch: Syntax error at offset 12 near group_id
    try:
        await client.add_episode(
            name="Test Episode",
            episode_body="Simple test to demonstrate group_id issue",
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Test"
        )
        print("✓ Success (unexpected)")
    except Exception as e:
        print(f"✗ Error: {e}")
        return str(e)


async def main():
    """Run the reproduction and document findings."""
    print("="*60)
    print("GROUP_ID REDISEARCH SYNTAX ERROR - REPRODUCTION")
    print("="*60)
    print(f"Date: {datetime.now()}")
    print(f"Graphiti: 0.18.7")
    print(f"FalkorDB: Running on port 6380")
    print(f"Python: 3.13.5")
    print()
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    print("Reproducing issue...")
    print("-"*40)
    error = await reproduce_issue()
    
    print()
    print("="*60)
    print("ANALYSIS")
    print("="*60)
    print("""
1. ERROR LOCATION:
   - Occurs during entity extraction when searching for existing entities
   - Happens on EVERY episode addition, not just with custom entities
   
2. EXACT ERROR:
   RediSearch: Syntax error at offset 12 near group_id
   
3. PROBLEMATIC QUERY:
   @group_id:"_" AND (test)
   
4. WHY IT FAILS:
   - RediSearch expects @field_name syntax for field queries
   - The underscore in 'group_id' may be causing parsing issues
   - Or 'group_id' might conflict with reserved syntax
   
5. IMPACT:
   - Complete blocker for using Graphiti with FalkorDB
   - Affects all users, not just those using custom entities
   - No workaround available (group_id is hardcoded in queries)
   
6. REGRESSION:
   - Version 0.17.7 had PR #733 fixing "Group ID usage with FalkorDB"
   - This appears to be a regression or incomplete fix
""")
    
    print("="*60)
    print("PROPOSED SOLUTIONS")
    print("="*60)
    print("""
1. ESCAPE THE FIELD NAME:
   Change: @group_id:"_"
   To: @"group_id":"_" or @group\\_id:"_"
   
2. RENAME THE FIELD:
   Change: group_id
   To: groupId or groupID (avoid underscore)
   
3. MAKE IT OPTIONAL:
   Allow users to disable group_id in fulltext searches
   
4. USE DIFFERENT SYNTAX:
   Use WHERE clause instead of fulltext search for group_id
""")


if __name__ == "__main__":
    asyncio.run(main())