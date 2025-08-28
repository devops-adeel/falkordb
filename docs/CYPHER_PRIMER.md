# Cypher Query Primer for GraphRAG

> **Purpose**: Learn Cypher query language specifically for GraphRAG workloads with Graphiti + FalkorDB

## Table of Contents
1. [Cypher Basics](#cypher-basics)
2. [GraphRAG Query Patterns](#graphrag-query-patterns)
3. [Temporal Queries](#temporal-queries)
4. [Context Extraction](#context-extraction)
5. [Performance Optimization](#performance-optimization)
6. [Advanced Patterns](#advanced-patterns)
7. [Query Debugging](#query-debugging)

---

## Cypher Basics

### Core Concepts

```cypher
// Nodes are in parentheses
(n)                          // Anonymous node
(p:Person)                   // Node with label
(p:Person {name: 'Alice'})   // Node with properties

// Relationships are in square brackets with arrows
-[r]->                       // Anonymous directed relationship
-[r:KNOWS]->                 // Relationship with type
-[r:KNOWS {since: 2020}]->   // Relationship with properties

// Patterns combine nodes and relationships
(alice:Person)-[:KNOWS]->(bob:Person)
```

### Essential Commands

#### CREATE - Add new data

```cypher
// Create a single node
CREATE (n:Concept {name: 'Machine Learning', category: 'AI'})

// Create nodes with relationship
CREATE (alice:Person {name: 'Alice'})-[:LEARNS]->(ml:Concept {name: 'ML'})

// Create multiple connected nodes
CREATE path = (a:Agent {id: 'agent_1'})-[:DISCOVERED]->(f:Fact {content: 'Python is interpreted'})-[:RELATES_TO]->(p:Concept {name: 'Python'})
RETURN path
```

#### MATCH - Find existing data

```cypher
// Find all nodes with a label
MATCH (n:Entity) RETURN n

// Find nodes with specific properties
MATCH (n:Entity {group_id: 'tech_knowledge'}) RETURN n.name

// Find connected nodes
MATCH (p:Person)-[:KNOWS]->(other:Person)
RETURN p.name, other.name
```

#### MERGE - Create or match

```cypher
// Create node only if it doesn't exist
MERGE (n:Entity {uuid: 'entity_123'})

// Update on match, set on create
MERGE (n:Entity {uuid: 'entity_123'})
ON CREATE SET n.created = timestamp()
ON MATCH SET n.accessed = timestamp()
```

#### WHERE - Filter results

```cypher
// Simple property filter
MATCH (n:Entity)
WHERE n.confidence > 0.8
RETURN n

// Pattern exists
MATCH (p:Person)
WHERE EXISTS((p)-[:KNOWS]->(:Person {name: 'Bob'}))
RETURN p

// Complex conditions
MATCH (n:Fact)
WHERE n.valid_from <= datetime() <= n.valid_to
  AND n.confidence >= 0.7
RETURN n
```

---

## GraphRAG Query Patterns

### Pattern 1: Entity Discovery

```cypher
// Find all entities related to a topic
MATCH (topic:Entity {name: 'Python'})-[*1..3]-(related:Entity)
WHERE related.uuid <> topic.uuid
RETURN DISTINCT related.name, related.category
ORDER BY related.confidence DESC
LIMIT 20

// Find entities with similar attributes
MATCH (target:Entity {name: 'Python'})
MATCH (similar:Entity)
WHERE similar.uuid <> target.uuid
  AND similar.category = target.category
  AND SIZE([(target)-[]-(common) | common]) > 0
RETURN similar.name, 
       SIZE([(target)-[]-(common) | common]) as common_connections
ORDER BY common_connections DESC
```

### Pattern 2: Fact Retrieval

```cypher
// Get all facts about an entity
MATCH (e:Entity {name: 'Python'})<-[:ABOUT]-(f:Fact)
WHERE f.confidence > 0.5
RETURN f.content, f.source, f.confidence
ORDER BY f.confidence DESC

// Get facts with evidence chains
MATCH path = (e:Entity {name: 'Python'})<-[:ABOUT]-(f:Fact)-[:SUPPORTED_BY]->(evidence)
RETURN f.content, COLLECT(evidence.content) as supporting_evidence
```

### Pattern 3: Knowledge Path Finding

```cypher
// Find learning path between concepts
MATCH path = shortestPath(
  (start:Concept {name: 'Variables'})-[*]-(end:Concept {name: 'Machine Learning'})
)
WHERE ALL(r IN relationships(path) WHERE r.confidence > 0.6)
RETURN [n IN nodes(path) | n.name] as learning_path

// Find all paths with explanations
MATCH path = (start:Concept {name: 'Python'})-[*1..4]-(end:Concept {name: 'Web Development'})
WHERE ALL(n IN nodes(path) WHERE n.group_id = 'tech_knowledge')
WITH path, 
     [r IN relationships(path) | type(r)] as relationship_types,
     LENGTH(path) as path_length
RETURN [n IN nodes(path) | n.name] as concepts,
       relationship_types,
       path_length
ORDER BY path_length
LIMIT 5
```

### Pattern 4: Contextual Retrieval

```cypher
// Get context for answering a question about Python
WITH 'How do decorators work in Python?' as question
MATCH (python:Entity {name: 'Python'})-[r1]-(decorator:Entity)
WHERE decorator.name CONTAINS 'decorator' 
   OR decorator.description CONTAINS 'decorator'
OPTIONAL MATCH (decorator)-[r2]-(example:Example)
OPTIONAL MATCH (decorator)-[r3]-(usecase:UseCase)
RETURN python.description as language_context,
       COLLECT(DISTINCT decorator.description) as decorator_info,
       COLLECT(DISTINCT example.code) as examples,
       COLLECT(DISTINCT usecase.description) as use_cases
```

---

## Temporal Queries

### Time-based Filtering

```cypher
// Facts valid at specific time
WITH datetime('2025-01-15T14:00:00') as query_time
MATCH (f:Fact)
WHERE f.valid_from <= query_time <= f.valid_to
RETURN f.content, f.confidence

// Evolution of knowledge over time
MATCH (e:Entity {name: 'Python'})<-[:ABOUT]-(f:Fact)
RETURN f.content, f.valid_from, f.valid_to
ORDER BY f.valid_from

// Latest facts only
MATCH (e:Entity)<-[:ABOUT]-(f:Fact)
WHERE NOT EXISTS(f.valid_to) OR f.valid_to > datetime()
RETURN e.name, COLLECT(f.content) as current_facts
```

### Episodic Memory Queries

```cypher
// Find episodes in time range
MATCH (ep:Episodic)
WHERE datetime('2025-01-01') <= ep.timestamp <= datetime('2025-01-31')
RETURN ep.name, ep.content, ep.participants
ORDER BY ep.timestamp DESC

// Find learning progression
MATCH (agent:Agent {id: 'agent_1'})-[:PARTICIPATED_IN]->(ep:Episodic)-[:RESULTED_IN]->(knowledge:Entity)
RETURN ep.timestamp, ep.name, COLLECT(knowledge.name) as learned_concepts
ORDER BY ep.timestamp

// Trace knowledge origin
MATCH (fact:Fact)-[:LEARNED_DURING]->(episode:Episodic)
MATCH (episode)<-[:PARTICIPATED_IN]-(agent:Agent)
RETURN fact.content, episode.name, COLLECT(agent.id) as contributing_agents
```

---

## Context Extraction

### Multi-hop Context Retrieval

```cypher
// Get n-hop context around entity
WITH 'Machine Learning' as target_concept, 2 as max_hops
MATCH path = (e:Entity {name: target_concept})-[*1..2]-(context)
WHERE ALL(r IN relationships(path) WHERE r.confidence > 0.6)
WITH e, context, LENGTH(path) as distance
RETURN e.name as center,
       COLLECT({
         node: context.name,
         distance: distance,
         type: labels(context)[0]
       }) as context_nodes
```

### Subgraph Extraction

```cypher
// Extract subgraph for RAG context
MATCH (center:Entity {name: 'Neural Networks'})
CALL {
  WITH center
  MATCH (center)-[r1]-(layer1)
  WHERE r1.confidence > 0.7
  RETURN layer1, r1
  LIMIT 10
  UNION
  WITH center
  MATCH (center)-[*2]-(layer2)
  WHERE layer2.importance > 0.5
  RETURN layer2, NULL as r1
  LIMIT 5
}
WITH center, COLLECT(DISTINCT layer1) + COLLECT(DISTINCT layer2) as nodes
MATCH (n1) WHERE n1 IN nodes
MATCH (n2) WHERE n2 IN nodes AND n1.uuid < n2.uuid
OPTIONAL MATCH (n1)-[r]-(n2)
RETURN center, nodes, COLLECT(r) as edges
```

### Contextual Scoring

```cypher
// Score context relevance for RAG
WITH 'How to implement async in Python' as query
MATCH (python:Entity {name: 'Python'})-[*1..2]-(context:Entity)
WITH context,
     CASE 
       WHEN context.name CONTAINS 'async' THEN 3.0
       WHEN context.name CONTAINS 'await' THEN 3.0
       WHEN context.name CONTAINS 'concurrent' THEN 2.0
       WHEN context.category = 'Programming' THEN 1.0
       ELSE 0.5
     END as relevance_score
WHERE relevance_score > 0
RETURN context.name, context.description, relevance_score
ORDER BY relevance_score DESC
LIMIT 10
```

---

## Performance Optimization

### Index Usage

```cypher
// Create indices for common queries
CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.uuid);
CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.group_id);
CREATE INDEX IF NOT EXISTS FOR (f:Fact) ON (f.valid_from);
CREATE INDEX IF NOT EXISTS FOR (ep:Episodic) ON (ep.timestamp);

// Composite indices for complex queries
CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.group_id, e.confidence);

// Full-text search index
CREATE FULLTEXT INDEX entity_search IF NOT EXISTS
FOR (e:Entity) ON EACH [e.name, e.description];
```

### Query Optimization Tips

```cypher
// BAD: Cartesian product
MATCH (a:Entity), (b:Entity)
WHERE a.group_id = b.group_id
RETURN a, b

// GOOD: Direct pattern
MATCH (a:Entity)-[]-(b:Entity)
WHERE a.group_id = b.group_id
RETURN a, b

// BAD: Multiple MATCH clauses without WITH
MATCH (a:Entity {name: 'Python'})
MATCH (b:Entity {name: 'JavaScript'})
MATCH path = shortestPath((a)-[*]-(b))
RETURN path

// GOOD: Use WITH to pipeline
MATCH (a:Entity {name: 'Python'})
WITH a
MATCH (b:Entity {name: 'JavaScript'})
WITH a, b
MATCH path = shortestPath((a)-[*]-(b))
RETURN path
```

### Limiting Search Space

```cypher
// Use LIMIT in subqueries
MATCH (topic:Entity {name: 'AI'})
CALL {
  WITH topic
  MATCH (topic)-[:RELATES_TO]-(related)
  RETURN related
  ORDER BY related.confidence DESC
  LIMIT 20
}
RETURN topic, COLLECT(related) as top_related

// Early filtering with WHERE
MATCH (n:Fact)
WHERE n.confidence > 0.8  // Filter early
WITH n
MATCH (n)-[:SUPPORTED_BY]->(evidence)
WHERE evidence.valid = true  // Filter again
RETURN n, evidence
```

---

## Advanced Patterns

### Graph Algorithms

```cypher
// PageRank for importance scoring
CALL algo.pageRank.stream('Entity', 'RELATES_TO', {iterations:20, dampingFactor:0.85})
YIELD nodeId, score
MATCH (e:Entity) WHERE ID(e) = nodeId
RETURN e.name, score
ORDER BY score DESC
LIMIT 10

// Community detection
CALL algo.louvain.stream('Entity', 'RELATES_TO', {})
YIELD nodeId, community
MATCH (e:Entity) WHERE ID(e) = nodeId
RETURN community, COLLECT(e.name) as members
ORDER BY SIZE(members) DESC

// Similarity computation
MATCH (e1:Entity)-[:HAS_PROPERTY]->(p:Property)<-[:HAS_PROPERTY]-(e2:Entity)
WHERE e1.uuid < e2.uuid
WITH e1, e2, COUNT(p) as common_properties
MATCH (e1)-[:HAS_PROPERTY]->(p1:Property)
WITH e1, e2, common_properties, COUNT(p1) as e1_properties
MATCH (e2)-[:HAS_PROPERTY]->(p2:Property)
WITH e1, e2, common_properties, e1_properties, COUNT(p2) as e2_properties
RETURN e1.name, e2.name, 
       common_properties * 2.0 / (e1_properties + e2_properties) as jaccard_similarity
ORDER BY jaccard_similarity DESC
```

### Dynamic Query Building

```cypher
// Build query based on conditions
WITH {
  must_have: ['Python', 'async'],
  should_have: ['await', 'concurrent'],
  min_confidence: 0.7
} as criteria
MATCH (e:Entity)
WHERE ALL(term IN criteria.must_have WHERE e.description CONTAINS term)
  AND ANY(term IN criteria.should_have WHERE e.description CONTAINS term)
  AND e.confidence >= criteria.min_confidence
RETURN e

// Conditional path expansion
WITH 3 as max_depth, 0.6 as min_confidence
MATCH (start:Entity {name: 'Python'})
CALL apoc.path.expandConfig(start, {
  maxLevel: max_depth,
  relationshipFilter: 'RELATES_TO|CONTAINS|PART_OF',
  labelFilter: '+Entity|+Concept',
  minLevel: 1,
  uniqueness: 'NODE_GLOBAL',
  bfs: true
}) YIELD path
WHERE ALL(r IN relationships(path) WHERE r.confidence >= min_confidence)
RETURN path
```

### Aggregation Patterns

```cypher
// Group and aggregate
MATCH (e:Entity)-[:HAS_FACT]->(f:Fact)
RETURN e.category,
       COUNT(*) as fact_count,
       AVG(f.confidence) as avg_confidence,
       COLLECT(f.content)[0..5] as sample_facts
ORDER BY fact_count DESC

// Window functions (if supported)
MATCH (ep:Episodic)
WITH ep
ORDER BY ep.timestamp
RETURN ep.name, 
       ep.timestamp,
       LAG(ep.timestamp, 1) OVER (ORDER BY ep.timestamp) as previous_episode_time,
       LEAD(ep.timestamp, 1) OVER (ORDER BY ep.timestamp) as next_episode_time
```

---

## Query Debugging

### Execution Plan Analysis

```cypher
// Use EXPLAIN to see query plan without execution
EXPLAIN
MATCH (n:Entity {group_id: 'tech'})-[:RELATES_TO*1..3]-(m:Entity)
WHERE n.confidence > 0.8
RETURN n, m

// Use PROFILE for detailed execution stats
PROFILE
MATCH (n:Entity {group_id: 'tech'})-[:RELATES_TO*1..3]-(m:Entity)
WHERE n.confidence > 0.8
RETURN n, m
LIMIT 10
```

### Common Issues and Fixes

#### Issue 1: Slow Variable-Length Paths

```cypher
// SLOW: Unbounded path search
MATCH path = (a:Entity)-[*]-(b:Entity)
WHERE a.name = 'Start' AND b.name = 'End'
RETURN path

// FAST: Bounded with early termination
MATCH path = shortestPath((a:Entity {name: 'Start'})-[*..5]-(b:Entity {name: 'End'}))
WHERE ALL(n IN nodes(path) WHERE n.group_id = 'tech')
RETURN path
```

#### Issue 2: Memory Explosion in Aggregation

```cypher
// BAD: Collecting everything
MATCH (e:Entity)-[:HAS_FACT]->(f:Fact)
RETURN e, COLLECT(f) as all_facts

// GOOD: Limit collection size
MATCH (e:Entity)-[:HAS_FACT]->(f:Fact)
WITH e, f
ORDER BY f.confidence DESC
WITH e, COLLECT(f)[0..10] as top_facts
RETURN e, top_facts
```

#### Issue 3: Cartesian Products

```cypher
// BAD: Creates n×m results
MATCH (a:Agent)
MATCH (e:Entity)
RETURN a, e

// GOOD: Only connected pairs
MATCH (a:Agent)-[:DISCOVERED]->(e:Entity)
RETURN a, e

// GOOD: If you need all combinations, be explicit and limit
MATCH (a:Agent)
WITH COLLECT(a)[0..5] as agents
MATCH (e:Entity)
WITH agents, COLLECT(e)[0..10] as entities
UNWIND agents as agent
UNWIND entities as entity
RETURN agent, entity
```

### Performance Monitoring Queries

```cypher
// Find slow queries in FalkorDB
CALL db.stats() YIELD stats
RETURN stats

// Check index usage
CALL db.indexes() YIELD name, type, state, populationPercent
RETURN name, type, state, populationPercent

// Memory usage per graph
CALL db.graphs() YIELD graph
CALL db.memory(graph) YIELD memory
RETURN graph, memory

// Query cache statistics
CALL cache.stats() YIELD hits, misses, evictions
RETURN hits, misses, evictions, 
       hits * 100.0 / (hits + misses) as hit_rate
```

---

## Query Templates for GraphRAG

### Template 1: Context Retrieval for Question Answering

```cypher
// Parameters: $question, $max_context_size
WITH $question as question, $max_context_size as limit
// Extract key terms from question (simplified - use NLP in practice)
WITH question, limit, 
     [term IN split(toLower(question), ' ') 
      WHERE SIZE(term) > 3] as terms
// Find relevant entities
MATCH (e:Entity)
WHERE ANY(term IN terms WHERE toLower(e.name) CONTAINS term 
                            OR toLower(e.description) CONTAINS term)
WITH e, SIZE([term IN terms WHERE toLower(e.name) CONTAINS term]) as relevance
ORDER BY relevance DESC
LIMIT limit
// Get context around entities
MATCH (e)-[r]-(context)
WHERE r.confidence > 0.5
RETURN e.name, e.description,
       COLLECT({
         related: context.name,
         relationship: type(r),
         confidence: r.confidence
       }) as context
```

### Template 2: Incremental Knowledge Update

```cypher
// Parameters: $entity_uuid, $new_facts, $timestamp
MERGE (e:Entity {uuid: $entity_uuid})
ON CREATE SET e.created = $timestamp
ON MATCH SET e.updated = $timestamp
WITH e
UNWIND $new_facts as fact_data
MERGE (f:Fact {content: fact_data.content})
ON CREATE SET 
  f.confidence = fact_data.confidence,
  f.valid_from = $timestamp,
  f.source = fact_data.source
MERGE (e)-[r:HAS_FACT]->(f)
ON CREATE SET r.created = $timestamp
RETURN e.uuid, COUNT(f) as facts_updated
```

### Template 3: Temporal Context Window

```cypher
// Parameters: $entity_name, $timestamp, $window_hours
WITH datetime($timestamp) as target_time,
     duration({hours: $window_hours}) as window
MATCH (e:Entity {name: $entity_name})
MATCH (e)-[]-(related)-[:OCCURRED_AT]->(ep:Episodic)
WHERE ep.timestamp >= target_time - window
  AND ep.timestamp <= target_time + window
RETURN related.name, ep.timestamp, ep.content
ORDER BY ABS(duration.between(ep.timestamp, target_time).seconds)
LIMIT 20
```

---

## Summary

### Essential Cypher for GraphRAG

✅ **MERGE over CREATE** to prevent duplicates

✅ **Use indices** on uuid, name, group_id, timestamps

✅ **Limit path lengths** in variable-length patterns

✅ **Filter early** with WHERE clauses

✅ **Use WITH** to control query flow

✅ **Profile queries** before production

✅ **Batch operations** for bulk updates

✅ **Cache query results** when appropriate

✅ **Monitor slow queries** regularly

✅ **Test with production-size data**

### Quick Reference Card

```cypher
// Find entities
MATCH (n:Entity {group_id: $group}) RETURN n

// Create if not exists
MERGE (n:Entity {uuid: $uuid})

// Update properties
MATCH (n:Entity {uuid: $uuid})
SET n.updated = timestamp(), n.access_count = n.access_count + 1

// Find paths
MATCH path = shortestPath((a)-[*..5]-(b))

// Temporal filter
WHERE n.valid_from <= datetime() <= n.valid_to

// Aggregate
RETURN e.category, COUNT(*) as cnt, AVG(f.confidence) as avg_conf

// Limit results
ORDER BY n.confidence DESC LIMIT 10
```

🚀 **Pro Tip**: Start with simple queries and add complexity gradually. Use EXPLAIN to understand query execution before running on large datasets.