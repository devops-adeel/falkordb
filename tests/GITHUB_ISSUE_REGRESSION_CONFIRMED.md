# [REGRESSION] RediSearch syntax error with @group_id field breaks FalkorDB backend (v0.17.7 → v0.18.x)

## 🚨 Critical Regression Confirmed

**This is a CONFIRMED REGRESSION** - Version 0.17.7 works perfectly with FalkorDB, but all v0.18.x versions are broken.

## Description

FalkorDB's RediSearch module throws "Syntax error at offset 12 near group_id" when Graphiti v0.18.x attempts fulltext search operations. This is a **regression** from v0.17.7 where PR #733 successfully fixed "Group ID usage with FalkorDB".

**Version 0.17.7**: ✅ WORKS  
**Version 0.18.7**: ❌ BROKEN

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
    
    # Works in v0.17.7, fails in v0.18.x
    await client.add_episode(
        name="Test",
        episode_body="Simple test",
        source=EpisodeType.text,
        reference_time=datetime.now(timezone.utc),
        source_description="Test"
    )

asyncio.run(reproduce())
```

## Test Results

### Version 0.17.7 (✅ WORKING)
```
Testing add_episode...
🎉 SUCCESS! Version 0.17.7 WORKS with FalkorDB!
PR #733 DID fix the group_id issue
```

### Version 0.18.7 (❌ BROKEN)
```
Error executing FalkorDB query: RediSearch: Syntax error at offset 12 near group_id
CALL db.idx.fulltext.queryNodes('Entity', $query)
{'query': '@group_id:"_" AND (test)', 'group_ids': ['_'], 'limit': 20}
```

## Environment

- **Working Version**: 0.17.7
- **Broken Versions**: 0.18.0 - 0.18.7 (all v0.18.x)
- **FalkorDB**: Latest Docker image
- **Python**: 3.13.5
- **OS**: macOS Darwin 24.5.0

## Root Cause

Between v0.17.7 and v0.18.0, the query generation for FalkorDB was changed, reintroducing the `@group_id` syntax that FalkorDB's RediSearch cannot parse.

The problematic query:
```
@group_id:"_" AND (search_terms)
```

## Impact

- **Severity**: CRITICAL - Complete blocker
- **Scope**: ALL users using Graphiti with FalkorDB backend
- **Regression**: Breaks previously working functionality
- **Workaround**: Users must downgrade to v0.17.7

## Regression Timeline

1. **v0.17.6**: group_id issue exists
2. **v0.17.7**: PR #733 fixes the issue ✅
3. **v0.18.0**: Regression introduced ❌
4. **v0.18.7**: Issue still present ❌

## Related Issues/PRs

- **PR #733** (v0.17.7): "Fix the Group ID usage with FalkorDB" by @galshubeli
- **Issue #169**: group_id lacks documentation
- **Issue #749**: Docker image FalkorDB support issues

## Proposed Solutions

### Immediate Fix (Restore v0.17.7 behavior)
Review PR #733 and restore the query generation logic that worked in v0.17.7.

### Alternative Fixes
1. **Escape the field**: `@"group_id":"_"` or `@group\\_id:"_"`
2. **Remove @ prefix**: `group_id:"_" AND ...`
3. **Use WHERE clause**: `WHERE n.group_id = $group_id`
4. **Make optional**: Allow disabling group_id for FalkorDB users

## Verification Script

```bash
# Test v0.17.7 (working)
pip install 'graphiti-core[falkordb]==0.17.7'
python test_script.py  # Success

# Test v0.18.7 (broken)
pip install 'graphiti-core[falkordb]==0.18.7'
python test_script.py  # Fails with group_id error
```

## Recommended Actions

1. **Immediate**: Add warning to documentation about FalkorDB incompatibility in v0.18.x
2. **Short-term**: Review what changed between v0.17.7 and v0.18.0
3. **Fix**: Restore the working query generation from v0.17.7
4. **Test**: Add regression test for FalkorDB + group_id

## User Workaround

Until fixed, FalkorDB users should:
```bash
pip install 'graphiti-core[falkordb]==0.17.7'
```

---

**Labels**: `regression`, `breaking-change`, `falkordb`, `high-priority`, `v0.18.x`

**Assignees**: @galshubeli (original fix author)

**Note**: This regression completely breaks FalkorDB support that was working in v0.17.7. All users who upgraded to v0.18.x and use FalkorDB are affected.