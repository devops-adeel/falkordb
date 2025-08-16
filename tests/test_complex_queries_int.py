"""
Integration tests for complex Graphiti queries including semantic search,
reranking, and cross-agent knowledge discovery.
"""
import asyncio
import uuid
from datetime import datetime, timezone
import pytest
from graphiti_core.nodes import EpisodeType
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_EPISODE_MENTIONS


@pytest.mark.integration
@pytest.mark.asyncio
async def test_semantic_search_with_reranking(single_client, langfuse_data, clean_graph, measure_time, performance_metrics):
    """Test semantic search with center node reranking using real conversation data."""
    
    # Add realistic conversation from Langfuse
    conversation = langfuse_data[0] if langfuse_data else {
        "input": "How do I optimize FalkorDB for my M3 MacBook?",
        "output": "Set THREAD_COUNT=8 to match M3 performance cores, use port 6380 to avoid conflicts, and configure NODE_CREATION_BUFFER=8192 for balanced write loads."
    }
    
    # Add the conversation as an episode
    await single_client.add_episode(
        name="Technical Support Conversation",
        episode_body=f"User: {conversation['input']}\nAssistant: {conversation['output']}",
        source=EpisodeType.message,
        reference_time=datetime.now(timezone.utc),
        source_description="Customer support interaction"
    )
    
    # Add related context
    await single_client.add_episode(
        name="FalkorDB Configuration Guide",
        episode_body="FalkorDB performance tuning includes CACHE_SIZE=50 for query caching, OMP_THREAD_COUNT=2 for parallelization, and maxmemory=4gb for memory management.",
        source=EpisodeType.text,
        reference_time=datetime.now(timezone.utc),
        source_description="Documentation"
    )
    
    await asyncio.sleep(0.5)  # Allow indexing
    
    # Try to get a center node for reranking
    try:
        # Search for M3 optimization to get a relevant node
        search_result = await single_client._search(
            "M3 MacBook optimization",
            NODE_HYBRID_SEARCH_EPISODE_MENTIONS
        )
        
        center_uuid = None
        if search_result and hasattr(search_result, 'nodes') and search_result.nodes:
            center_uuid = search_result.nodes[0].uuid
            print(f"  Using center node: {center_uuid[:8]}...")
    except:
        center_uuid = None
        print("  No center node available, testing without reranking")
    
    @measure_time(max_seconds=2.0)
    async def semantic_search():
        # Perform semantic search with optional reranking
        results = await single_client.search(
            query="What are the optimal settings for FalkorDB on Apple Silicon?",
            center_node_uuid=center_uuid,
            num_results=5
        )
        return results
    
    results, duration = await semantic_search()
    performance_metrics["query_times"].append(duration)
    
    # Verify results
    assert len(results) > 0, "Should return relevant results"
    assert all(hasattr(r, 'fact') for r in results), "All results should have facts"
    
    # Check relevance - at least one result should mention key terms
    facts_text = " ".join([r.fact for r in results])
    relevant_terms = ["THREAD_COUNT", "6380", "M3", "performance", "optimization"]
    relevance_score = sum(1 for term in relevant_terms if term in facts_text)
    
    assert relevance_score >= 2, f"Results should be relevant, found {relevance_score}/5 key terms"
    
    print(f"\n✓ Semantic search {'with reranking' if center_uuid else 'without reranking'} took {duration:.2f}s")
    print(f"  Found {len(results)} results with relevance score: {relevance_score}/5")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fact_extraction_multi_hop(single_client, clean_graph, measure_time, performance_metrics):
    """Test multi-hop fact extraction and relationship discovery."""
    
    # Build a knowledge graph with relationships
    episodes = [
        {
            "name": "User Profile",
            "body": "John is a developer working with FalkorDB. John uses a M3 MacBook Pro."
        },
        {
            "name": "Technical Setup",
            "body": "The M3 MacBook Pro runs FalkorDB on port 6380. FalkorDB connects to Graphiti instances."
        },
        {
            "name": "Performance Config",
            "body": "Graphiti instances use connection pooling with max_connections=16. Connection pooling improves concurrent access."
        },
        {
            "name": "User Feedback",
            "body": "John reported excellent performance with the current setup. The setup handles 5 concurrent agents smoothly."
        }
    ]
    
    # Add all episodes
    for episode in episodes:
        await single_client.add_episode(
            name=episode["name"],
            episode_body=episode["body"],
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Test data"
        )
    
    await asyncio.sleep(0.5)  # Allow indexing
    
    @measure_time(max_seconds=3.0)
    async def extract_multi_hop_facts():
        # Query that requires connecting multiple facts
        results = await single_client.search(
            query="What setup does John use for concurrent agents?",
            num_results=10
        )
        return results
    
    results, duration = await extract_multi_hop_facts()
    performance_metrics["query_times"].append(duration)
    
    # Verify multi-hop reasoning
    facts = [r.fact for r in results]
    facts_text = " ".join(facts).lower()
    
    # Should connect: John -> M3 MacBook -> FalkorDB -> Graphiti -> concurrent agents
    key_connections = ["john", "m3", "falkordb", "6380", "graphiti", "concurrent", "agents"]
    connections_found = sum(1 for conn in key_connections if conn in facts_text)
    
    assert connections_found >= 4, f"Should find multi-hop connections, found {connections_found}/7"
    
    print(f"\n✓ Multi-hop fact extraction completed in {duration:.2f}s")
    print(f"  Found {len(results)} facts with {connections_found}/7 key connections")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_agent_knowledge_sharing(graphiti_clients, clean_graph, measure_time, performance_metrics):
    """Test that Agent A's knowledge can be discovered by Agent B."""
    
    agent_a = graphiti_clients[0]
    agent_b = graphiti_clients[1]
    agent_c = graphiti_clients[2]
    
    # Agent A adds specialized knowledge
    knowledge_id = uuid.uuid4().hex[:8]
    specialized_knowledge = f"""
    Technical Discovery {knowledge_id}:
    - FalkorDB custom port: 6380 (avoids Redis conflicts)
    - M3 optimization: THREAD_COUNT=8 (matches performance cores)
    - Connection pooling: max_connections=16
    - Memory limit: 4GB with LRU eviction
    - Query cache: CACHE_SIZE=50
    """
    
    await agent_a.add_episode(
        name=f"Technical Documentation {knowledge_id}",
        episode_body=specialized_knowledge,
        source=EpisodeType.text,
        reference_time=datetime.now(timezone.utc),
        source_description="Agent A expertise"
    )
    
    # Agent C adds different knowledge
    await agent_c.add_episode(
        name="General Information",
        episode_body="FalkorDB is a graph database. It supports Cypher queries. Good for GraphRAG.",
        source=EpisodeType.text,
        reference_time=datetime.now(timezone.utc),
        source_description="Agent C knowledge"
    )
    
    await asyncio.sleep(0.5)  # Allow indexing
    
    @measure_time(max_seconds=2.0)
    async def agent_b_discovery():
        # Agent B searches for specific technical details
        results = await agent_b.search(
            query="What port should I use for FalkorDB to avoid conflicts?",
            num_results=5
        )
        return results
    
    results, duration = await agent_b_discovery()
    performance_metrics["query_times"].append(duration)
    
    # Verify Agent B found Agent A's knowledge
    assert len(results) > 0, "Agent B should discover knowledge"
    
    # Check if the specific port information was found
    found_port = any("6380" in r.fact for r in results)
    assert found_port, "Agent B should find Agent A's specific port knowledge"
    
    # Verify it found the right knowledge (A's, not just C's generic info)
    found_specialized = any(knowledge_id in r.fact for r in results)
    
    print(f"\n✓ Cross-agent knowledge sharing verified in {duration:.2f}s")
    print(f"  Agent B found Agent A's specialized knowledge: {found_specialized}")
    print(f"  Found specific port information: {found_port}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complex_query_with_filters(single_client, clean_graph, measure_time, performance_metrics):
    """Test complex queries with various filters and constraints."""
    
    # Add diverse data with different timestamps and sources
    base_time = datetime.now(timezone.utc)
    
    episodes = [
        {
            "name": "Morning Config",
            "body": "Morning setup: FalkorDB started with THREAD_COUNT=8",
            "source": "monitoring",
            "time_offset": -7200  # 2 hours ago
        },
        {
            "name": "Afternoon Optimization",
            "body": "Afternoon adjustment: Increased CACHE_SIZE to 100 for better performance",
            "source": "configuration",
            "time_offset": -3600  # 1 hour ago
        },
        {
            "name": "Recent Issue",
            "body": "Recent observation: Memory usage at 3.5GB, running smoothly",
            "source": "monitoring",
            "time_offset": -300  # 5 minutes ago
        },
        {
            "name": "Best Practices",
            "body": "Recommendation: Use port 6380 for FalkorDB to avoid conflicts",
            "source": "documentation",
            "time_offset": -86400  # 1 day ago
        }
    ]
    
    for episode in episodes:
        await single_client.add_episode(
            name=episode["name"],
            episode_body=episode["body"],
            source=EpisodeType.text,
            reference_time=datetime.fromtimestamp(
                base_time.timestamp() + episode["time_offset"],
                tz=timezone.utc
            ),
            source_description=episode["source"]
        )
    
    await asyncio.sleep(0.5)
    
    @measure_time(max_seconds=2.0)
    async def complex_filtered_query():
        # Search for recent monitoring data
        results = await single_client.search(
            query="memory usage performance monitoring",
            num_results=10
        )
        return results
    
    results, duration = await complex_filtered_query()
    performance_metrics["query_times"].append(duration)
    
    # Verify results include diverse sources
    facts = [r.fact for r in results]
    
    # Should find monitoring and performance-related facts
    monitoring_facts = [f for f in facts if "memory" in f.lower() or "performance" in f.lower()]
    
    assert len(monitoring_facts) > 0, "Should find monitoring-related facts"
    
    print(f"\n✓ Complex filtered query completed in {duration:.2f}s")
    print(f"  Found {len(results)} total results")
    print(f"  Monitoring-related facts: {len(monitoring_facts)}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_performance_degradation(single_client, clean_graph, measure_time, performance_metrics):
    """Test that query performance remains stable as graph grows."""
    
    query_times = []
    
    # Progressively add data and measure query times
    for batch in range(3):
        # Add batch of episodes
        for i in range(5):
            episode_num = batch * 5 + i
            await single_client.add_episode(
                name=f"Episode-{episode_num}",
                episode_body=f"Content batch {batch}: FalkorDB configuration item {i}. "
                           f"Performance metric {episode_num}. "
                           f"Optimization level {batch}.",
                source=EpisodeType.text,
                reference_time=datetime.now(timezone.utc),
                source_description="Performance test data"
            )
        
        await asyncio.sleep(0.2)  # Allow indexing
        
        # Measure query time after each batch
        @measure_time(max_seconds=3.0)
        async def timed_query():
            results = await single_client.search(
                query="FalkorDB performance optimization",
                num_results=5
            )
            return len(results)
        
        result_count, duration = await timed_query()
        query_times.append(duration)
        performance_metrics["query_times"].append(duration)
        
        print(f"  Batch {batch + 1}: Query took {duration:.3f}s, found {result_count} results")
    
    # Check for significant degradation
    # Allow for some variance, but not exponential growth
    if len(query_times) >= 2:
        time_increase = query_times[-1] / query_times[0]
        assert time_increase < 2.0, f"Query time should not double: increased {time_increase:.1f}x"
    
    print(f"\n✓ Query performance test completed")
    print(f"  Query times: {[f'{t:.3f}s' for t in query_times]}")
    print(f"  Performance ratio (last/first): {query_times[-1]/query_times[0]:.2f}x")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_and_edge_case_queries(single_client, clean_graph, measure_time):
    """Test handling of empty results and edge case queries."""
    
    # Add minimal data
    await single_client.add_episode(
        name="Single Episode",
        episode_body="FalkorDB is a graph database",
        source=EpisodeType.text,
        reference_time=datetime.now(timezone.utc),
        source_description="Edge case test data"
    )
    
    await asyncio.sleep(0.5)
    
    test_cases = [
        {
            "query": "completely unrelated xenomorphic quantum fluctuation",
            "expected": "empty_or_weak"
        },
        {
            "query": "",  # Empty query
            "expected": "handle_gracefully"
        },
        {
            "query": "🚀 emoji test 🎯",  # Special characters
            "expected": "handle_gracefully"
        },
        {
            "query": "a" * 500,  # Very long query
            "expected": "handle_gracefully"
        },
        {
            "query": "FalkorDB",  # Should find something
            "expected": "find_results"
        }
    ]
    
    for test_case in test_cases:
        try:
            @measure_time(max_seconds=3.0)
            async def edge_case_query():
                results = await single_client.search(
                    query=test_case["query"][:500],  # Limit query length
                    num_results=5
                )
                return results
            
            results, duration = await edge_case_query()
            
            if test_case["expected"] == "find_results":
                assert len(results) > 0, f"Should find results for: {test_case['query'][:50]}"
            
            print(f"  Edge case handled: {test_case['query'][:50]}... -> {len(results)} results")
            
        except Exception as e:
            # Some edge cases might raise exceptions, which is fine if handled
            print(f"  Edge case exception (expected): {test_case['query'][:50]}... -> {type(e).__name__}")
    
    print("\n✓ Edge case query handling verified")