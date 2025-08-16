# [BUG] RediSearch syntax error with @group_id field when using FalkorDB backend

## Description

FalkorDB's RediSearch module throws "Syntax error at offset 12 near group_id" when Graphiti attempts fulltext search operations during entity extraction. This is a complete blocker for using Graphiti with FalkorDB backend.

The error occurs because Graphiti generates a RediSearch query using `@group_id:"_"` syntax which FalkorDB's RediSearch parser cannot handle, likely due to the underscore in the field name or a conflict with reserved syntax.

## Steps to Reproduce

```python
import asyncio
from datetime import datetime, timezone
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType

async def reproduce():
    driver = FalkorDriver(host="localhost", port=6379, database="test")
    client = Graphiti(graph_driver=driver)
    
    # This fails with RediSearch syntax error
    await client.add_episode(
        name="Test",
        episode_body="Simple test",
        source=EpisodeType.text,
        reference_time=datetime.now(timezone.utc),
        source_description="Test"
    )

asyncio.run(reproduce())
```

## Expected Behavior

Episodes should be added successfully to the knowledge graph using FalkorDB backend.

## Actual Behavior

```
Error executing FalkorDB query: RediSearch: Syntax error at offset 12 near group_id
CALL db.idx.fulltext.queryNodes('Entity', $query)
...
{'query': '@group_id:"_" AND (test)', 'group_ids': ['_'], 'limit': 20}
```

## Environment

- **Graphiti Version**: 0.18.7
- **FalkorDB**: Latest (running on Docker)
- **Python**: 3.13.5
- **OS**: macOS Darwin 24.5.0
- **Installation**: `pip install graphiti-core[falkordb]`

## Root Cause Analysis

The issue occurs in the fulltext search query generation. Graphiti creates a query like:

```
@group_id:"_" AND (search_terms)
```

This fails because:
1. RediSearch may not support underscores in field names with @ syntax
2. The field 'group_id' might need escaping
3. This could be a FalkorDB-specific RediSearch limitation

The error message "Syntax error at offset 12" points exactly to where "group_id" starts in the query string after "RediSearch: ".

## Impact

- **Severity**: HIGH - Complete blocker
- **Affects**: ALL users trying to use Graphiti with FalkorDB
- **Workaround**: None available (group_id is hardcoded in queries)
- **Regression**: Version 0.17.7 had PR #733 fixing "Group ID usage with FalkorDB"

## Related Issues

- PR #733 (v0.17.7) - Previous fix for group_id with FalkorDB
- Issue #169 - group_id lacks documentation
- Issue #749 - Docker image FalkorDB support issues

## Proposed Solutions

### Option 1: Escape the Field Name
```python
# Current: @group_id:"_"
# Fixed:   @"group_id":"_" or @group\_id:"_"
```

### Option 2: Rename the Field
```python
# Change group_id to groupId or groupID (avoid underscore)
```

### Option 3: Make group_id Optional
```python
# Allow disabling group_id in fulltext searches for FalkorDB users
```

### Option 4: Use WHERE Clause Instead
```python
# Use WHERE n.group_id = $group_id instead of fulltext search
```

## Additional Context

Testing shows:
- The issue occurs on EVERY episode addition, not just with custom entities
- Direct FalkorDB fulltext index creation with standard fields works
- The problem is specifically with the @group_id syntax in RediSearch queries
- This affects the entity extraction phase of episode processing

## Reproduction Repository

Full test suite available at: [link to reproduction code]

---

**Note to maintainers**: This appears to be a regression from the fix in v0.17.7. The issue completely blocks FalkorDB usage, so users are forced to use Neo4j or implement workarounds. Since the user mentioned not needing group_id functionality, making it optional would be a valuable feature.