## Description
FalkorDB compatibility that worked in v0.17.7-v0.17.9 is broken since v0.17.10 due to a quote style change in RediSearch query generation. The issue stems from changing single quotes to double quotes in the `fulltext_query` function.

## The Regression Timeline
- **v0.17.7-v0.17.9**: ✅ Works (PR #733 fixed "Group ID usage with FalkorDB")  
- **v0.17.10 onwards**: ❌ Fails with `RediSearch: Syntax error at offset 12 near group_id`
- **Regression introduced**: Between v0.17.9 and v0.17.10

## Root Cause Analysis

### The Exact Code Change
**File**: `graphiti_core/search/search_utils.py`  
**Function**: `fulltext_query()`  
**Commits**: 
- c0cae61d ("fulltext query update") 
- 5bbc3cf8 ("optimize fulltext query update")

```python
# BEFORE (v0.17.9 - WORKING):
[fulltext_syntax + f"group_id:'{lucene_sanitize(g)}'" for g in group_ids]

# AFTER (v0.17.10 - BROKEN):
[fulltext_syntax + f'group_id:"{g}"' for g in group_ids]
```

The change from single quotes to double quotes breaks FalkorDB's RediSearch parser while Neo4j continues to work with both styles.

## Minimal Reproduction
```python
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver

driver = FalkorDriver(host="localhost", port=6379)
client = Graphiti(graph_driver=driver)

# This fails in v0.17.10+ but works in v0.17.7-v0.17.9
await client.add_episode(
    name="Test",
    episode_body="Any content",
    source="text"
)
```

## Error Details
```
Error executing FalkorDB query: RediSearch: Syntax error at offset 12 near group_id
Query: @group_id:"_" AND (test)
```

## Impact
- Complete blocker for FalkorDB users
- Forces downgrade to v0.17.9 as only workaround (last working version)
- Affects all operations, not just custom entities
- Regression has persisted through 8+ releases (v0.17.10 through v0.18.7)

## Environment
- Graphiti: v0.18.7 (latest)
- FalkorDB: Latest Docker
- Python: 3.13.5
- OS: macOS

## Version Test Results
| Version | Status | Notes |
|---------|--------|-------|
| v0.17.7-v0.17.9 | ✅ Works | PR #733 fix effective |
| **v0.17.10** | ❌ **Regression** | First broken version |
| v0.17.11-v0.18.7 | ❌ Broken | All subsequent versions affected |

## Proposed Solutions

### Option 1: Revert to Single Quotes (Simplest)
```python
# In graphiti_core/search/search_utils.py
[fulltext_syntax + f"group_id:'{g}'" for g in group_ids]
```

### Option 2: Database-Aware Quotes
```python
# Detect database type and use appropriate quotes
quote_char = "'" if is_falkordb else '"'
[fulltext_syntax + f'group_id:{quote_char}{g}{quote_char}' for g in group_ids]
```

## Temporary Workaround

Until an official fix is released, FalkorDB users can:

1. **Downgrade to v0.17.9**: `pip install 'graphiti-core[falkordb]==0.17.9'`
2. **Use the patch script** (attached in comments) to modify their local installation

## Testing

I've created comprehensive test scripts (available on request) that:
- Confirm the regression across all versions
- Validate that the proposed fix works
- Ensure Neo4j compatibility is maintained

## Additional Context

- PR #761 in v0.18.1 ("feat/falkordb dynamic graph names") did NOT fix this issue
- The regression has persisted through 8+ releases without detection
- This affects ALL FalkorDB users - there is no configuration workaround

## Note from Reporter
This is my first GitHub issue - I used Claude Code to help identify and document this regression through extensive testing. The root cause analysis, test scripts, and proposed solutions are all available. I'm happy to:
- Provide the test scripts and patch tool
- Help test potential fixes
- Submit a PR if the maintainers approve the approach

Thank you for your work on Graphiti! Despite this issue, it's an excellent framework for knowledge graphs.