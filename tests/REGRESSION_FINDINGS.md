# Graphiti FalkorDB group_id Regression - Test Results

## Executive Summary

**CRITICAL REGRESSION CONFIRMED**: FalkorDB support that worked in v0.17.7-v0.17.9 is broken in v0.17.10 onwards.

## Detailed Version Testing Results

| Version | Status | Notes |
|---------|--------|-------|
| v0.17.7 | ✅ WORKS | PR #733 fixed group_id issue |
| v0.17.8 | ✅ WORKS | Still working |
| v0.17.9 | ✅ WORKS | Last fully working version |
| **v0.17.10** | **❌ BROKEN** | **REGRESSION INTRODUCED HERE** |
| v0.17.11 | ❌ BROKEN | Still broken |
| v0.18.0 | ❌ BROKEN | Still broken |
| v0.18.1 | ❌ BROKEN | PR #761 did NOT fix it |
| v0.18.7 | ❌ BROKEN | Latest - still broken |

## Key Findings

1. **Regression Point**: v0.17.9 → v0.17.10
   - Last working: v0.17.9
   - First broken: v0.17.10
   
2. **PR #761 in v0.18.1** ("feat/falkordb dynamic graph names") did NOT fix the issue
   - Despite the promising name, this PR did not address the group_id RediSearch error

3. **Error Details**:
   ```
   Error executing FalkorDB query: RediSearch: Syntax error at offset 12 near group_id
   Query: @group_id:"_" AND (search terms)
   ```

4. **Impact**: 
   - Complete blocker for ALL FalkorDB users
   - Affects all operations, not just custom entities
   - No workaround available except downgrading

## Timeline

1. **Pre-v0.17.7**: group_id issue exists
2. **v0.17.7**: PR #733 fixes the issue ✅
3. **v0.17.8-v0.17.9**: Still working ✅
4. **v0.17.10**: Regression introduced ❌
5. **v0.17.11-v0.18.7**: All broken ❌

## Recommendations for GitHub Issue

### Title
[REGRESSION] FalkorDB compatibility broken since v0.17.10 (was working in v0.17.7-v0.17.9)

### Labels
- `regression`
- `breaking-change`
- `falkordb`
- `high-priority`

### Description
Should emphasize:
- This is a REGRESSION, not a new bug
- It worked for 3 versions (v0.17.7, v0.17.8, v0.17.9)
- Something changed in v0.17.10 that broke it
- All subsequent versions remain broken
- Users must downgrade to v0.17.9 as the only workaround

### Action Items for Maintainers
1. Review changes between v0.17.9 and v0.17.10
2. Identify what modified the RediSearch query generation
3. Restore the working behavior from v0.17.9
4. Add regression test for FalkorDB compatibility

## Test Commands Used

```bash
# Working versions
pip install 'graphiti-core[falkordb]==0.17.7'  # ✅ Works
pip install 'graphiti-core[falkordb]==0.17.8'  # ✅ Works
pip install 'graphiti-core[falkordb]==0.17.9'  # ✅ Works

# Broken versions
pip install 'graphiti-core[falkordb]==0.17.10' # ❌ Broken
pip install 'graphiti-core[falkordb]==0.17.11' # ❌ Broken
pip install 'graphiti-core[falkordb]==0.18.0'  # ❌ Broken
pip install 'graphiti-core[falkordb]==0.18.1'  # ❌ Broken
pip install 'graphiti-core[falkordb]==0.18.7'  # ❌ Broken
```

## Workaround

Until fixed, FalkorDB users should use:
```bash
pip install 'graphiti-core[falkordb]==0.17.9'
```

---

*Testing completed: January 16, 2025*
*Tested with: Python 3.13.5, FalkorDB latest Docker, macOS*