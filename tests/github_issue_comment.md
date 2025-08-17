## Update: Root Cause Identified & Fix Available

After extensive testing and bisecting through versions, I've identified the exact regression point and root cause of this FalkorDB compatibility issue.

### Corrected Timeline
The regression was introduced in **v0.17.10**, not v0.18.0 as initially reported:
- ✅ **v0.17.7 - v0.17.9**: Working (PR #733 fix was effective)
- ❌ **v0.17.10 onwards**: Broken (including all v0.18.x versions)

### Root Cause
The issue stems from a quote style change in `graphiti_core/search/search_utils.py` in the `fulltext_query()` function:

**Commits causing regression:**
- c0cae61d ("fulltext query update")
- 5bbc3cf8 ("optimize fulltext query update")

**The specific change:**
```python
# BEFORE (v0.17.9 - WORKING):
[fulltext_syntax + f"group_id:'{lucene_sanitize(g)}'" for g in group_ids]

# AFTER (v0.17.10 - BROKEN):
[fulltext_syntax + f'group_id:"{g}"' for g in group_ids]
```

This produces queries like:
- **v0.17.9**: `@group_id:'_' AND (test)` ✅ Works with FalkorDB
- **v0.17.10+**: `@group_id:"_" AND (test)` ❌ Fails with "Syntax error at offset 12 near group_id"

### Why This Matters
- **FalkorDB's RediSearch**: Requires single quotes for field values
- **Neo4j**: Accepts both single and double quotes
- **Solution**: Use single quotes (works for both databases)

### Existing PR Already Addresses This!
I discovered that **PR #775** ("Fix: syntax error in Fulltext queries") from @mohdjami already attempts to fix this exact issue by reverting to single quotes. The PR has been waiting for review since July 27.

**I strongly support merging PR #775** as it directly addresses the root cause.

### Immediate Workarounds
For users affected by this issue, here are two immediate solutions:

**Option 1: Downgrade to v0.17.9**
```bash
pip install 'graphiti-core[falkordb]==0.17.9'
```

**Option 2: Apply Local Patch**
I've created a patch script that modifies your installed graphiti-core:
```python
#!/usr/bin/env python3
"""Patch graphiti-core for FalkorDB compatibility"""
import sys
from pathlib import Path

# Find and patch search_utils.py
import graphiti_core
target = Path(graphiti_core.__file__).parent / "search" / "search_utils.py"

with open(target, 'r') as f:
    content = f.read()

# Replace double quotes with single quotes in group_id queries
content = content.replace('f\'group_id:"{g}"\'', 'f"group_id:\'{g}\'"')
content = content.replace('f\'group_id:"{lucene_sanitize(g)}"\'', 
                         'f"group_id:\'{lucene_sanitize(g)}\'"')

with open(target, 'w') as f:
    f.write(content)

print("✅ Patch applied! FalkorDB should now work.")
```

### Testing Performed
I've created comprehensive test suites that:
1. Confirmed the regression point (v0.17.9 → v0.17.10)
2. Validated that single quotes fix FalkorDB
3. Verified Neo4j compatibility is maintained
4. Tested across versions v0.17.7 through v0.18.7

### Recommendations
1. **Merge PR #775** to fix this regression
2. **Add FalkorDB to CI pipeline** to prevent future regressions
3. **Consider a patch release** (v0.18.8 or v0.17.12) for affected users

### Technical Details Available
I have detailed test scripts, the full patch tool, and extensive documentation of this issue. Happy to provide these or help test the fix if needed.

---
*This analysis was performed using Claude Code with extensive testing on FalkorDB and Graphiti versions v0.17.7 through v0.18.7*