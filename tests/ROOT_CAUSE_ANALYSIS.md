# FalkorDB Group_ID Regression - Root Cause Analysis

## Executive Summary

A regression in Graphiti v0.17.10 broke FalkorDB compatibility due to a quote style change in RediSearch query generation. The issue persists through all versions from v0.17.10 to v0.18.7 (latest).

## The Exact Code Change

### Location
File: `graphiti_core/search/search_utils.py`
Function: `fulltext_query()`
Line: ~65

### The Change (v0.17.9 → v0.17.10)

#### Commit 1: c0cae61d (July 22, 2025)
**Message**: "fulltext query update"
**Author**: prestonrasmussen (prasmuss15@gmail.com)

```python
# BEFORE (v0.17.9 - WORKING):
[fulltext_syntax + f"group_id:'{lucene_sanitize(g)}'" for g in group_ids]

# AFTER (v0.17.10 - BROKEN):
[fulltext_syntax + f'group_id:"{lucene_sanitize(g)}"' for g in group_ids]
```

#### Commit 2: 5bbc3cf8 (July 22, 2025) 
**Message**: "optimize fulltext query update"
**Author**: prestonrasmussen (prasmuss15@gmail.com)

```python
# FURTHER CHANGED TO:
[fulltext_syntax + f'group_id:"{g}"' for g in group_ids]
# Note: Also removed lucene_sanitize() call
```

## Why This Breaks FalkorDB

### The Problem
FalkorDB's RediSearch implementation has different quote parsing rules than Neo4j:

1. **FalkorDB RediSearch**:
   - `@group_id:'value'` ✅ WORKS
   - `@group_id:"value"` ❌ FAILS with "Syntax error at offset 12 near group_id"

2. **Neo4j Full-Text Search**:
   - `@group_id:'value'` ✅ WORKS
   - `@group_id:"value"` ✅ WORKS

### Technical Explanation
In RediSearch (which FalkorDB uses):
- Double quotes (`"`) are reserved for exact phrase matching
- Single quotes (`'`) are treated differently or as literals
- The syntax parser encounters an error when field names are combined with double quotes in certain contexts

The error "Syntax error at offset 12" points to the position right after `@group_id:` where the double quote appears.

## Query Examples

### What Gets Generated
```python
# With v0.17.9 (WORKING):
query = "@group_id:'_' AND (test content)"

# With v0.17.10+ (BROKEN):  
query = '@group_id:"_" AND (test content)'
```

### Error Message
```
Error executing FalkorDB query: RediSearch: Syntax error at offset 12 near group_id
```

## Impact Analysis

### Affected Versions
- **Last Working**: v0.17.9
- **First Broken**: v0.17.10
- **Still Broken**: v0.18.7 (latest as of Jan 2025)

### Affected Operations
- ALL operations that use full-text search with group_id filtering
- This includes: `add_episode()`, `search()`, and any query operations
- Complete blocker for FalkorDB users - no workaround except downgrading

### PR #761 Did Not Fix This
Despite its name "feat/falkordb dynamic graph names" in v0.18.1, PR #761 did not address this quote syntax issue.

## Related Code Context

### The Full Function (v0.17.10)
```python
def fulltext_query(query: str, group_ids: list[str] | None = None, fulltext_syntax: str = ''):
    group_ids_filter_list = (
        [fulltext_syntax + f'group_id:"{g}"' for g in group_ids] if group_ids is not None else []
    )
    group_ids_filter = ''
    for f in group_ids_filter_list:
        group_ids_filter += f'{f} '
    # ... rest of function
```

## Proposed Solutions

### Solution 1: Revert to Single Quotes (Simplest)
```python
# Change back to:
[fulltext_syntax + f"group_id:'{g}'" for g in group_ids]
```

### Solution 2: Database-Aware Quotes
```python
# Detect database type and use appropriate quotes
quote_char = "'" if is_falkordb else '"'
[fulltext_syntax + f'group_id:{quote_char}{g}{quote_char}' for g in group_ids]
```

### Solution 3: Escape or Alternative Syntax
Research if there's a quote-free syntax or proper escaping that works for both databases.

## Testing Requirements

1. Test with FalkorDB on port 6380
2. Test with Neo4j on standard port
3. Verify with various group_id values:
   - Default: "_"
   - Custom: "my_group_123"
   - Special chars: "group-id-test"
4. Ensure no regression in Neo4j functionality

## References

- GitHub Comparison: https://github.com/getzep/graphiti/compare/v0.17.9...v0.17.10
- Commit c0cae61d: https://github.com/getzep/graphiti/commit/c0cae61d52a408d881f61b642733494a87b14ea0
- Commit 5bbc3cf8: https://github.com/getzep/graphiti/commit/5bbc3cf8149a1a7fa4cc331d41b7331e61768830
- Original PR #733 (v0.17.7): Fixed "Group ID usage with FalkorDB"
- RediSearch Query Syntax: https://redis.io/docs/latest/develop/ai/search-and-query/advanced-concepts/query_syntax/