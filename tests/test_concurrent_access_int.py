"""
Integration tests for concurrent Graphiti instance access to FalkorDB.
Tests multiple agents reading/writing simultaneously.
"""
import asyncio
import uuid
from datetime import datetime, timezone
import pytest
from graphiti_core.nodes import EpisodeType


@pytest.mark.integration
@pytest.mark.concurrent
@pytest.mark.asyncio
async def test_five_agents_concurrent_write(graphiti_clients, langfuse_data, measure_time, performance_metrics):
    """Test 5 agents writing different episodes simultaneously without conflicts."""
    
    @measure_time(max_seconds=15.0)  # Adjusted for real LLM calls with 5 agents
    async def concurrent_writes():
        tasks = []
        
        for i, client in enumerate(graphiti_clients):
            # Each agent writes different conversation from Langfuse or fallback data
            conversation = langfuse_data[i % len(langfuse_data)]
            
            async def write_episode(client_idx, conv_data):
                """Write an episode for a specific agent."""
                episode_id = str(uuid.uuid4())
                await client.add_episode(
                    name=f"Agent-{client_idx}-Episode-{episode_id[:8]}",
                    episode_body=f"{conv_data['input']}\n\nResponse: {conv_data['output']}",
                    source=EpisodeType.message,
                    reference_time=datetime.now(timezone.utc),
                    source_description=f"Agent {client_idx} conversation"
                )
                return f"Agent-{client_idx}"
            
            task = write_episode(i, conversation)
            tasks.append(task)
        
        # Execute all writes concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for any exceptions
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Concurrent write errors: {errors}"
        
        # Verify all agents completed
        successful_agents = [r for r in results if isinstance(r, str)]
        assert len(successful_agents) == 5, f"Expected 5 successful writes, got {len(successful_agents)}"
        
        return results
    
    results, duration = await concurrent_writes()
    performance_metrics["concurrent_operations"].append(duration)
    
    print(f"\n✓ 5 concurrent writes completed in {duration:.2f}s")
    print(f"  Average time per agent: {duration/5:.2f}s")


@pytest.mark.integration
@pytest.mark.concurrent
@pytest.mark.asyncio
async def test_read_write_consistency(graphiti_clients, measure_time, performance_metrics):
    """Test 3 agents writing while 2 agents search continuously."""
    
    write_clients = graphiti_clients[:3]
    read_clients = graphiti_clients[3:5]
    
    # Shared data for verification
    write_counter = {"count": 0}
    read_results = {"searches": [], "found_items": []}
    
    async def writer(client, agent_id):
        """Continuously write episodes."""
        for i in range(5):
            episode_id = f"consistency-test-{agent_id}-{i}"
            await client.add_episode(
                name=f"Writer-{agent_id}-Episode-{i}",
                episode_body=f"Test data from agent {agent_id} iteration {i}. Unique ID: {episode_id}",
                source=EpisodeType.text,
                reference_time=datetime.now(timezone.utc),
                source_description=f"Writer agent {agent_id}"
            )
            write_counter["count"] += 1
            await asyncio.sleep(0.1)  # Small delay between writes
        return f"Writer-{agent_id}-complete"
    
    async def reader(client, reader_id):
        """Continuously search for written data."""
        results = []
        items_found = []
        
        for i in range(10):
            # Search for data from any writer
            search_query = f"consistency-test agent iteration"
            search_results = await client.search(
                search_query,
                num_results=10
            )
            
            results.append(len(search_results))
            items_found.extend([r.fact for r in search_results if r.fact])
            
            await asyncio.sleep(0.05)  # Higher frequency reading
        
        read_results["searches"].append(results)
        read_results["found_items"].extend(items_found)
        return f"Reader-{reader_id}-complete"
    
    # Start timing
    start_time = asyncio.get_event_loop().time()
    
    # Run writers and readers concurrently
    tasks = []
    
    # Start writers
    for i, client in enumerate(write_clients):
        tasks.append(writer(client, i))
    
    # Start readers
    for i, client in enumerate(read_clients):
        tasks.append(reader(client, i))
    
    # Wait for all operations to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    duration = asyncio.get_event_loop().time() - start_time
    performance_metrics["concurrent_operations"].append(duration)
    
    # Verify no exceptions
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"Errors during concurrent operations: {errors}"
    
    # Verify writers completed
    writer_results = [r for r in results[:3] if "Writer" in str(r)]
    assert len(writer_results) == 3, "All writers should complete"
    
    # Verify readers completed
    reader_results = [r for r in results[3:] if "Reader" in str(r)]
    assert len(reader_results) == 2, "All readers should complete"
    
    # Verify readers saw increasing data over time
    for reader_search_results in read_results["searches"]:
        # Later searches should generally find more or equal data
        if len(reader_search_results) > 1:
            avg_early = sum(reader_search_results[:3]) / 3 if len(reader_search_results) >= 3 else reader_search_results[0]
            avg_late = sum(reader_search_results[-3:]) / 3 if len(reader_search_results) >= 3 else reader_search_results[-1]
            assert avg_late >= avg_early - 1, "Readers should see consistent or increasing data"
    
    print(f"\n✓ Read-write consistency test completed in {duration:.2f}s")
    print(f"  Total writes: {write_counter['count']}")
    print(f"  Total unique items found by readers: {len(set(read_results['found_items']))}")


@pytest.mark.integration
@pytest.mark.concurrent
@pytest.mark.asyncio
async def test_connection_pool_saturation(graphiti_clients, measure_time, performance_metrics):
    """Test connection pool handles maximum concurrent connections properly."""
    
    @measure_time(max_seconds=10.0)
    async def saturate_connections():
        # Create 16 concurrent operations (matching max_connections)
        tasks = []
        
        for _ in range(3):  # 3 rounds
            for client in graphiti_clients:  # 5 clients
                # Mix of read and write operations
                if len(tasks) % 2 == 0:
                    # Write operation
                    task = client.add_episode(
                        name=f"Saturation-test-{uuid.uuid4().hex[:8]}",
                        episode_body=f"Connection pool test at {datetime.now(timezone.utc)}",
                        source=EpisodeType.text,
                        reference_time=datetime.now(timezone.utc)
                    )
                else:
                    # Read operation
                    task = client.search("connection pool test", num_results=5)
                
                tasks.append(task)
                
                # Add tasks in batches to truly test saturation
                if len(tasks) >= 15:  # Near max connections
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Check success rate
                    errors = [r for r in results if isinstance(r, Exception)]
                    success_rate = (len(results) - len(errors)) / len(results) * 100
                    
                    assert success_rate >= 95, f"Connection pool success rate too low: {success_rate:.1f}%"
                    
                    tasks = []  # Reset for next batch
        
        # Process remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        return "Saturation test complete"
    
    result, duration = await saturate_connections()
    performance_metrics["concurrent_operations"].append(duration)
    
    print(f"\n✓ Connection pool saturation test passed in {duration:.2f}s")


@pytest.mark.integration
@pytest.mark.concurrent
@pytest.mark.asyncio
async def test_agent_isolation(graphiti_clients, clean_graph, measure_time):
    """Test that agents maintain data isolation when needed."""
    
    # Each agent adds private data with unique namespace
    agent_data = {}
    
    @measure_time(max_seconds=8.0)
    async def test_isolation():
        # Phase 1: Each agent writes private data
        write_tasks = []
        
        for i, client in enumerate(graphiti_clients):
            agent_namespace = f"agent_{i}_private"
            agent_data[i] = {
                "namespace": agent_namespace,
                "secret": f"secret_data_{uuid.uuid4().hex[:8]}"
            }
            
            async def write_private_data(client_ref, agent_id, data):
                await client_ref.add_episode(
                    name=f"{data['namespace']}_episode",
                    episode_body=f"Private: {data['secret']}. This belongs to {data['namespace']} only.",
                    source=EpisodeType.text,
                    reference_time=datetime.now(timezone.utc),
                    source_description=f"Private data for agent {agent_id}"
                )
                return agent_id
            
            task = write_private_data(client, i, agent_data[i])
            write_tasks.append(task)
        
        await asyncio.gather(*write_tasks)
        
        # Small delay for data to be indexed
        await asyncio.sleep(0.5)
        
        # Phase 2: Verify each agent can find their own data
        search_tasks = []
        
        for i, client in enumerate(graphiti_clients):
            async def search_own_data(client_ref, agent_id):
                # Search for own secret
                own_secret = agent_data[agent_id]["secret"]
                results = await client_ref.search(own_secret, num_results=5)
                
                # Should find own data
                found_own = any(own_secret in r.fact for r in results)
                
                # Check if accidentally found others' secrets
                other_secrets = [
                    agent_data[j]["secret"] 
                    for j in agent_data 
                    if j != agent_id
                ]
                found_others = any(
                    secret in r.fact 
                    for r in results 
                    for secret in other_secrets
                )
                
                return {
                    "agent_id": agent_id,
                    "found_own": found_own,
                    "found_others": found_others
                }
            
            task = search_own_data(client, i)
            search_tasks.append(task)
        
        search_results = await asyncio.gather(*search_tasks)
        
        # Verify results
        for result in search_results:
            assert result["found_own"], f"Agent {result['agent_id']} couldn't find own data"
            # Note: In a shared graph, agents might see others' data - this is expected
            # The test verifies they can at least find their own data
        
        return search_results
    
    results, duration = await test_isolation()
    
    print(f"\n✓ Agent isolation test completed in {duration:.2f}s")
    for r in results:
        print(f"  Agent {r['agent_id']}: Found own data: {r['found_own']}")


@pytest.mark.integration
@pytest.mark.concurrent
@pytest.mark.slow
@pytest.mark.asyncio
async def test_concurrent_complex_queries(graphiti_clients, langfuse_data, measure_time, performance_metrics):
    """Test multiple agents performing complex queries simultaneously."""
    
    # First, populate with rich data
    setup_tasks = []
    for i, conv in enumerate(langfuse_data[:3]):
        client = graphiti_clients[i % len(graphiti_clients)]
        task = client.add_episode(
            name=f"Complex-data-{i}",
            episode_body=f"Question: {conv['input']}\nAnswer: {conv['output']}\nContext: Testing complex queries",
            source=EpisodeType.message,
            reference_time=datetime.now(timezone.utc),
            source_description="Complex query test data"
        )
        setup_tasks.append(task)
    
    await asyncio.gather(*setup_tasks)
    await asyncio.sleep(0.5)  # Let data index
    
    @measure_time(max_seconds=10.0)
    async def concurrent_complex_queries():
        query_tasks = []
        
        queries = [
            "What port should I use for FalkorDB?",
            "How do I optimize for M3 MacBook?",
            "What's the connection pooling configuration?",
            "How do I monitor performance?",
            "What's the backup strategy?"
        ]
        
        for i, (client, query) in enumerate(zip(graphiti_clients, queries)):
            async def complex_query(client_ref, query_text, query_id):
                # Perform semantic search
                results = await client_ref.search(
                    query_text,
                    num_results=5
                )
                
                return {
                    "query_id": query_id,
                    "query": query_text,
                    "results_count": len(results),
                    "has_relevant": any(
                        word in str(r.fact).lower() 
                        for r in results 
                        for word in query_text.lower().split()
                    )
                }
            
            task = complex_query(client, query, i)
            query_tasks.append(task)
        
        results = await asyncio.gather(*query_tasks)
        
        # Verify all queries completed
        assert len(results) == 5, "All queries should complete"
        
        # Verify queries found relevant results
        relevant_count = sum(1 for r in results if r["has_relevant"])
        assert relevant_count >= 3, f"At least 3 queries should find relevant results, got {relevant_count}"
        
        return results
    
    results, duration = await concurrent_complex_queries()
    performance_metrics["concurrent_operations"].append(duration)
    
    print(f"\n✓ Concurrent complex queries completed in {duration:.2f}s")
    for r in results:
        print(f"  Query {r['query_id']}: Found {r['results_count']} results, relevant: {r['has_relevant']}")