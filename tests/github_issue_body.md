## Description
FalkorDB compatibility that worked in v0.17.7 is broken in all v0.18.x versions due to a RediSearch syntax error with the `group_id` field.

## The Regression
- **v0.17.7**: ✅ Works (PR #733 fixed "Group ID usage with FalkorDB")  
- **v0.18.x**: ❌ Fails with `RediSearch: Syntax error at offset 12 near group_id`

## Minimal Reproduction
```python
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver

driver = FalkorDriver(host="localhost", port=6379)
client = Graphiti(graph_driver=driver)

# This fails in v0.18.x but works in v0.17.7
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
- Forces downgrade to v0.17.7 as only workaround
- Affects all operations, not just custom entities

## Environment
- Graphiti: v0.18.7 (latest)
- FalkorDB: Latest Docker
- Python: 3.13.5
- OS: macOS

## Related Issue
Issue #757 reports the same error but doesn't mention the regression from v0.17.7

## Note from Reporter
This is my first GitHub issue - I used Claude Code to help identify and document this regression through extensive testing. I'm open to learning and providing any additional information needed. Happy to help test potential fixes!