# Custom Entities with FalkorDB - Comprehensive Report

## Executive Summary

This report documents the comprehensive testing of Graphiti v0.18.7 custom entity types with FalkorDB. While Graphiti supports custom entity definitions using Pydantic models, there are significant limitations when using FalkorDB as the backend, particularly around entity persistence and querying.

**Key Finding**: Custom entities work for semantic extraction during episode processing but face critical limitations in persistence and retrieval with FalkorDB.

## Test Environment

- **Graphiti Version**: 0.18.7
- **FalkorDB**: Running on port 6380 (custom port to avoid conflicts)
- **Python**: 3.13
- **Test Date**: January 2025
- **Configuration**: No group_id (shared knowledge graph for all agents)

## Custom Entity Definitions Created

### 1. Arabic Tutor Entities
- `Student`: Tracks learner progress and preferences
- `Lesson`: Represents learning sessions
- `VocabularyWord`: Arabic vocabulary with transliteration
- `GrammarRule`: Grammar concepts and patterns
- `Progress`: Learning milestones and assessments
- `PracticeSession`: Study session tracking

### 2. GTD Coach Entities
- `Task`: Next actions with contexts and priorities
- `Project`: Multi-step outcomes
- `Context`: Locations/tools for tasks (@home, @office, etc.)
- `NextAction`: Project-specific next steps
- `Review`: Weekly/periodic review sessions
- `AreaOfFocus`: Life areas (Health, Finance, Career)
- `InboxItem`: Unprocessed captures

### 3. Islamic Finance Entities
- `Account`: Shariah-compliant accounts (Mudarabah, Wadiah, etc.)
- `Transaction`: Halal financial transactions
- `ZakatCalculation`: Annual charity calculations
- `Investment`: Shariah-screened investments (Sukuk, etc.)
- `Contract`: Islamic contracts (Murabahah, Ijarah, etc.)
- `Beneficiary`: Zakat recipients

## Critical Issues Identified

### 1. ❌ group_id RediSearch Error
**Issue**: FalkorDB's RediSearch module doesn't support the group_id field that Graphiti uses.

```
Error: RediSearch: Syntax error at offset 12 near group_id
```

**Impact**: 
- Cannot add episodes with custom entities
- Search functionality fails
- Complete blocker for standard Graphiti usage

**Root Cause**: 
- Graphiti hardcodes group_id in fulltext search queries
- FalkorDB's RediSearch doesn't recognize this field

### 2. ❌ Custom Entity Labels Not Persisted
**Issue**: Custom entity labels (e.g., `:Task`, `:Project`) are not saved to FalkorDB nodes.

**Expected**:
```cypher
CREATE (t:Task:Entity {uuid: '...', priority: 'A'})
```

**Actual**:
```cypher
CREATE (n:Entity {uuid: '...', name: '...', summary: '...'})
```

**Impact**:
- Cannot query by entity type
- All nodes are generic `:Entity`
- Lose semantic meaning in graph

### 3. ❌ Custom Properties Not Persisted  
**Issue**: Properties defined in Pydantic models are not saved to nodes.

**Expected Properties**:
- Task: priority, energy_required, time_estimate, context
- Student: proficiency_level, learning_goals, weekly_study_hours
- Account: account_type, balance, profit_rate

**Actual Properties**:
- Only: uuid, name, summary, created_at

**Impact**:
- Lose all domain-specific data
- Cannot filter or sort by custom attributes
- Reduces entities to basic text storage

### 4. ❌ Complex Query Limitations
**Issue**: Cannot perform entity-type-specific queries.

**Wanted Queries**:
```cypher
MATCH (t:Task) WHERE t.priority = 'A' RETURN t
MATCH (s:Student)-[:COMPLETED]->(l:Lesson) RETURN s, l
MATCH (a:Account)-[:PAID_ZAKAT]->(b:Beneficiary) RETURN sum(a.amount)
```

**Available Queries**:
```cypher
MATCH (n:Entity) RETURN n  // All nodes are Entity
```

### 5. ⚠️ Edge Property Limitations
**Issue**: Custom edge properties have limited support.

**Partial Success**: 
- Edge properties can be created directly in FalkorDB
- But Graphiti doesn't fully utilize Pydantic edge models

## Working Features

### ✅ Entity Extraction
- Custom entities ARE extracted from text during episode processing
- LLM correctly identifies entity types based on Pydantic models
- Relationships between entities are detected

### ✅ Basic Search
- Text search works (without entity type filtering)
- Can find entities by content
- Relationships appear in search results as facts

### ✅ Episode Processing
- Episodes are added successfully (without group_id)
- Text, JSON, and message sources work
- Source descriptions are preserved

## Practical Workarounds

### 1. JSON Backup Strategy
Store full entity data in JSON files alongside FalkorDB:

```python
from tests.utils.entity_workarounds import EntityWorkaroundManager

manager = EntityWorkaroundManager()
await manager.save_entities_to_json(entities, entity_types, session_id)
```

### 2. Entity Type in Summary
Encode entity information in the summary field:

```python
summary = manager.encode_entity_in_summary(task_entity, "Task")
# Result: "[Task] priority=A | context=@office | energy=high |||METADATA:{...}|||"
```

### 3. Simple Entity Store
Use a parallel JSON store for full entity functionality:

```python
from tests.utils.entity_workarounds import SimpleEntityStore

store = SimpleEntityStore()
entity_id = store.add_entity(task, "Task")
results = store.search("urgent", entity_type="Task")
```

### 4. Fact String Enhancement
Include entity type information in fact strings:

```python
fact = manager.create_fact_with_entity_info(
    "Student completed lesson",
    source_type="Student",
    target_type="Lesson",
    edge_type="COMPLETED"
)
# Result: "Student completed lesson [Student--COMPLETED-->Lesson]"
```

### 5. Direct Property Addition
Add entity_type property directly to FalkorDB nodes:

```python
await manager.add_entity_type_property(
    node_uuid="...",
    entity_type="Task",
    custom_props={"priority": "A", "context": "@office"}
)
```

## Recommendations for Production

### For Your Use Case (3 Agents, Shared Knowledge Graph)

1. **Primary Storage**: Use JSON backup for complete entity data
2. **FalkorDB Role**: Use for relationship graph and basic search
3. **Entity Identification**: Encode type in summary or facts
4. **Search Strategy**: Combine FalkorDB search with JSON filtering
5. **Avoid**: Don't rely on group_id or custom node properties

### Architecture Suggestions

```
┌─────────────────┐
│   Agent Input   │
└────────┬────────┘
         │
         v
┌─────────────────┐
│    Graphiti     │──> Custom Entities (Pydantic)
└────────┬────────┘
         │
         ├────────────────┐
         v                v
┌─────────────────┐  ┌─────────────────┐
│    FalkorDB     │  │  JSON Backup    │
│  (Relationships)│  │ (Full Entities) │
└─────────────────┘  └─────────────────┘
         │                │
         └────────┬───────┘
                  v
         ┌─────────────────┐
         │  Search/Query   │
         └─────────────────┘
```

### Implementation Priority

1. **High Priority**: 
   - Implement JSON backup immediately
   - Use summary field encoding
   - Create search wrapper that handles both stores

2. **Medium Priority**:
   - Build entity type detection from facts
   - Create migration utilities
   - Implement caching layer

3. **Low Priority**:
   - Wait for FalkorDB group_id support
   - Custom Cypher query builders
   - Complex relationship queries

## Performance Considerations

- **Entity Extraction**: ~2-3 seconds per episode with custom entities
- **Search**: Similar performance with or without custom entities
- **JSON Backup**: Minimal overhead (<100ms per episode)
- **Memory**: Entity cache grows with usage (consider TTL)

## Future Improvements

### Graphiti Improvements Needed
1. Make group_id optional in search queries
2. Allow custom node labels in save operations
3. Support arbitrary properties in EntityNode
4. Better FalkorDB compatibility

### FalkorDB Improvements Needed
1. Support group_id in RediSearch
2. Better integration with Graphiti
3. Documentation for graph patterns

## Conclusion

While custom entities in Graphiti provide powerful semantic extraction capabilities, the persistence layer with FalkorDB has significant limitations. The workarounds provided make it feasible for production use, but with architectural adjustments.

**For your specific use case** (Arabic tutor, GTD coach, Islamic finance advisor):
- ✅ Entity extraction will identify domain concepts
- ✅ Basic search will find related information
- ⚠️ Use JSON backup for complete entity data
- ⚠️ Don't rely on entity-specific queries in FalkorDB
- ✅ Shared knowledge graph works (no group_id needed)

**Recommendation**: Proceed with the hybrid approach (FalkorDB + JSON backup) until either Graphiti or FalkorDB addresses these limitations.

## Test Files Reference

1. `entities/arabic_entities.py` - Arabic learning domain models
2. `entities/gtd_entities.py` - GTD/productivity domain models  
3. `entities/islamic_finance_entities.py` - Islamic finance domain models
4. `test_custom_entities_basic.py` - Basic functionality tests
5. `test_falkordb_gaps.py` - Gap identification tests
6. `utils/entity_workarounds.py` - Practical workaround utilities
7. `CUSTOM_ENTITIES_REPORT.md` - This comprehensive report

---

*Report generated: January 2025*
*Graphiti Version: 0.18.7*
*FalkorDB Port: 6380*