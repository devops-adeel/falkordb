# Version Compatibility Matrix

## Critical Version Information

⚠️ **ACTIVE REGRESSION**: Graphiti v0.17.10+ breaks FalkorDB compatibility  
✅ **RECOMMENDED VERSION**: `graphiti-core[falkordb]==0.17.9`

## Compatibility Matrix Overview

```mermaid
gantt
    title Graphiti-FalkorDB Compatibility Timeline
    dateFormat YYYY-MM-DD
    axisFormat %m/%d
    
    section Working
    v0.17.7 (PR #733 fix)    :done, 2024-01-01, 30d
    v0.17.8 (stable)          :done, 2024-02-01, 30d
    v0.17.9 (last working)    :done, 2024-03-01, 30d
    
    section Broken
    v0.17.10 (regression)     :crit, 2024-04-01, 30d
    v0.17.11 (still broken)   :crit, 2024-05-01, 30d
    v0.18.0 (major, broken)   :crit, 2024-06-01, 30d
    v0.18.1 (PR #761 no fix)  :crit, 2024-07-01, 30d
    v0.18.7 (latest, broken)  :crit, 2024-08-01, 90d
```

## Detailed Compatibility Table

| Graphiti Version | FalkorDB | Status | Custom Entities | Arabic | GTD | Islamic Finance | Notes |
|-----------------|----------|---------|-----------------|--------|-----|-----------------|-------|
| **v0.17.7** | ✅ All | ✅ Working | ✅ | ✅ | ✅ | ✅ | PR #733 fixed group_id |
| **v0.17.8** | ✅ All | ✅ Working | ✅ | ✅ | ✅ | ✅ | Stable release |
| **v0.17.9** | ✅ All | ✅ Working | ✅ | ✅ | ✅ | ✅ | **RECOMMENDED** |
| v0.17.10 | ❌ All | ❌ BROKEN | ❌ | ❌ | ❌ | ❌ | Regression introduced |
| v0.17.11 | ❌ All | ❌ BROKEN | ❌ | ❌ | ❌ | ❌ | Not fixed |
| v0.18.0 | ❌ All | ❌ BROKEN | ❌ | ❌ | ❌ | ❌ | Major version, still broken |
| v0.18.1 | ❌ All | ❌ BROKEN | ❌ | ❌ | ❌ | ❌ | PR #761 didn't fix |
| v0.18.7 | ❌ All | ❌ BROKEN | ❌ | ❌ | ❌ | ❌ | Latest, still broken |

## Component Compatibility

### FalkorDB Versions
```mermaid
graph LR
    subgraph "FalkorDB Versions"
        F1[Latest Docker]
        F2[v2.x]
        F3[v1.x]
    end
    
    subgraph "Graphiti Versions"
        G1[v0.17.9 ✅]
        G2[v0.17.10+ ❌]
    end
    
    F1 -->|Works| G1
    F2 -->|Works| G1
    F3 -->|Works| G1
    F1 -->|Fails| G2
    F2 -->|Fails| G2
    F3 -->|Fails| G2
    
    style G1 fill:#ccffcc
    style G2 fill:#ffcccc
```

### Python Version Compatibility

| Python | Graphiti v0.17.9 | Graphiti v0.18.x | FalkorDB Client | Status |
|--------|------------------|-------------------|-----------------|---------|
| 3.8 | ✅ | ✅ | ✅ | Works with v0.17.9 only |
| 3.9 | ✅ | ✅ | ✅ | Works with v0.17.9 only |
| 3.10 | ✅ | ✅ | ✅ | Works with v0.17.9 only |
| 3.11 | ✅ | ✅ | ✅ | Works with v0.17.9 only |
| 3.12 | ✅ | ✅ | ✅ | Works with v0.17.9 only |
| 3.13 | ✅ | ⚠️ | ✅ | **Tested & Working** with v0.17.9 |

## Dependency Tree

```mermaid
graph TD
    A[Your Application] --> B[graphiti-core v0.17.9]
    B --> C[falkordb Python Client]
    B --> D[Pydantic]
    B --> E[Other Dependencies]
    
    C --> F[FalkorDB Server]
    F --> G[Redis Protocol]
    F --> H[RediSearch Module]
    
    H -->|v0.17.10+| I[❌ group_id Error]
    H -->|v0.17.9| J[✅ Works]
    
    style I fill:#ffcccc
    style J fill:#ccffcc
```

## Version Feature Comparison

| Feature | v0.17.9 ✅ | v0.17.10+ ❌ |
|---------|------------|--------------|
| Basic Queries | ✅ Working | ❌ group_id error |
| Custom Entities | ✅ Full support | ❌ Fails on creation |
| Entity Extraction | ✅ All domains | ❌ None work |
| Search Operations | ✅ RediSearch OK | ❌ RediSearch syntax error |
| Graph Creation | ✅ Success | ❌ Fails at index |
| Relationship Creation | ✅ Working | ❌ Can't reach this step |
| Episode Addition | ✅ Complete | ❌ Blocked by group_id |
| Index Building | ✅ Successful | ❌ Error at build |

## Installation Commands by Version

### ✅ Working Version (RECOMMENDED)
```bash
# Clean install of working version
pip uninstall graphiti-core -y
pip install 'graphiti-core[falkordb]==0.17.9'

# Verify installation
python -c "import graphiti_core; print(graphiti_core.__version__)"
# Should output: 0.17.9
```

### ❌ Broken Versions (AVOID)
```bash
# These will cause group_id errors:
pip install 'graphiti-core[falkordb]==0.17.10'  # ❌ First broken
pip install 'graphiti-core[falkordb]==0.17.11'  # ❌ Still broken
pip install 'graphiti-core[falkordb]==0.18.0'   # ❌ Major, broken
pip install 'graphiti-core[falkordb]==0.18.1'   # ❌ PR #761 no help
pip install 'graphiti-core[falkordb]'           # ❌ Latest is broken
```

## Testing Version Compatibility

### Quick Version Test Script
```python
#!/usr/bin/env python3
"""test_version.py - Quick version compatibility test"""

import asyncio
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
import graphiti_core

async def test_version():
    version = graphiti_core.__version__
    print(f"Testing Graphiti {version}")
    
    driver = FalkorDriver(
        host="localhost",
        port=6380,
        database="version_test"
    )
    
    client = Graphiti(graph_driver=driver)
    
    try:
        await client.build_indices_and_constraints()
        print(f"✅ Version {version} WORKS")
        return True
    except Exception as e:
        if "group_id" in str(e):
            print(f"❌ Version {version} BROKEN - group_id error")
        else:
            print(f"❌ Version {version} FAILED - {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_version())
```

## Version Migration Guide

### Downgrading from Broken Version

```mermaid
flowchart LR
    A[Detect group_id Error] --> B[Check Current Version]
    B --> C{Version >= 0.17.10?}
    C -->|Yes| D[Backup Current Code]
    C -->|No| E[Different Issue]
    D --> F[pip uninstall graphiti-core]
    F --> G[pip install 'graphiti-core[falkordb]==0.17.9']
    G --> H[Update requirements.txt]
    H --> I[Pin version in code]
    I --> J[Test Connection]
    J --> K[✅ Working]
```

### requirements.txt Examples

```bash
# ✅ GOOD - Pinned to working version
graphiti-core[falkordb]==0.17.9

# ❌ BAD - Will install broken version
graphiti-core[falkordb]
graphiti-core[falkordb]>=0.17.10
graphiti-core[falkordb]~=0.18.0
```

## Docker Compose Compatibility

### FalkorDB Configuration
```yaml
# Works with ALL FalkorDB versions when using Graphiti v0.17.9
services:
  falkordb:
    image: falkordb/falkordb:latest  # ✅ Works
    # image: falkordb/falkordb:v2.0   # ✅ Also works
    # image: falkordb/falkordb:v1.0   # ✅ Also works
    ports:
      - "6380:6379"  # Using 6380 to avoid conflicts
```

## Known Issues by Version

### v0.17.10 - v0.18.7
- **Issue**: RediSearch syntax error with group_id parameter
- **Error**: `RediSearch: Syntax error at offset 12 near group_id`
- **Impact**: Complete failure of all FalkorDB operations
- **Workaround**: Downgrade to v0.17.9

### v0.17.9 and Earlier
- **Status**: Fully functional
- **Known Issues**: None with FalkorDB
- **Custom Entities**: Full support for all domains

## Future Version Planning

```mermaid
timeline
    title Version Resolution Timeline
    
    2024 Q1 : v0.17.9 Working
            : Last stable version
    
    2024 Q2 : v0.17.10 Broken
            : Regression introduced
            
    2024 Q3 : v0.18.x Still Broken
            : Multiple attempts to fix
            
    2024 Q4 : Awaiting Fix
            : GitHub Issue #841 opened
            
    2025 Q1 : Current State
            : Using v0.17.9 workaround
```

---

## Quick Reference

| Need | Use This Version | Command |
|------|-----------------|---------|
| **Production** | v0.17.9 | `pip install 'graphiti-core[falkordb]==0.17.9'` |
| **Development** | v0.17.9 | `pip install 'graphiti-core[falkordb]==0.17.9'` |
| **Testing** | v0.17.9 | `pip install 'graphiti-core[falkordb]==0.17.9'` |
| **Latest Features** | Not Available | Must wait for fix in future version |

---

## See Also

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - How to diagnose and fix issues
- [Entity Debugging Visual](entity-debugging-visual.md) - Visual debugging guide
- [Debug Commands Reference](debug-commands-reference.md) - Complete command reference