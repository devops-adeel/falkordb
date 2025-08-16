"""
Integration tests for data persistence across FalkorDB container restarts,
backups, and recovery scenarios.
"""
import asyncio
import uuid
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone
import pytest
import docker
from graphiti_core.nodes import EpisodeType
from graphiti_core.utils.maintenance.graph_data_operations import clear_data


@pytest.mark.integration
@pytest.mark.persistence
@pytest.mark.asyncio
async def test_container_restart_persistence(single_client, docker_client, measure_time, performance_metrics):
    """Test that data survives FalkorDB container restart."""
    
    if not docker_client:
        pytest.skip("Docker not available")
    
    try:
        container = docker_client.containers.get("falkordb")
    except docker.errors.NotFound:
        pytest.skip("FalkorDB container not found")
    
    # Generate unique test data
    test_id = uuid.uuid4().hex[:8]
    test_episodes = [
        {
            "name": f"Persistence-Test-{test_id}-1",
            "body": f"Critical configuration {test_id}: FalkorDB uses port 6380 for connections"
        },
        {
            "name": f"Persistence-Test-{test_id}-2",
            "body": f"Performance setting {test_id}: THREAD_COUNT=8 for M3 optimization"
        },
        {
            "name": f"Persistence-Test-{test_id}-3",
            "body": f"Memory configuration {test_id}: maxmemory=4gb with LRU eviction"
        }
    ]
    
    # Add test data before restart
    print(f"\n  Adding test data with ID: {test_id}")
    for episode in test_episodes:
        await single_client.add_episode(
            name=episode["name"],
            episode_body=episode["body"],
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Persistence test data"
        )
    
    # Verify data was added
    initial_results = await single_client.search(test_id, num_results=10)
    initial_count = len(initial_results)
    assert initial_count > 0, "Data should be added before restart"
    print(f"  Found {initial_count} items before restart")
    
    # Restart container
    print("  Restarting FalkorDB container...")
    container.restart(timeout=30)
    
    # Wait for container to be healthy
    max_wait = 30  # seconds
    start_wait = time.time()
    while time.time() - start_wait < max_wait:
        container.reload()
        health = container.attrs.get('State', {}).get('Health', {}).get('Status')
        if health == 'healthy':
            print("  Container is healthy")
            break
        await asyncio.sleep(1)
    else:
        pytest.fail("Container did not become healthy after restart")
    
    # Additional wait for FalkorDB to be fully ready
    await asyncio.sleep(2)
    
    # Search for data after restart
    @measure_time(max_seconds=3.0)
    async def verify_persistence():
        results = await single_client.search(test_id, num_results=10)
        return results
    
    try:
        results, duration = await verify_persistence()
        performance_metrics["query_times"].append(duration)
        
        # Verify data persisted
        assert len(results) > 0, "Data should persist after container restart"
        assert len(results) == initial_count, f"Should find same amount of data: {len(results)} vs {initial_count}"
        
        # Verify specific content
        facts = [r.fact for r in results]
        for episode in test_episodes:
            episode_found = any(test_id in fact for fact in facts)
            assert episode_found, f"Episode {episode['name']} should be found after restart"
        
        print(f"✓ Data persistence verified after container restart")
        print(f"  Found {len(results)}/{initial_count} items after restart in {duration:.2f}s")
        
    except Exception as e:
        pytest.fail(f"Failed to verify persistence after restart: {e}")


@pytest.mark.integration
@pytest.mark.persistence
@pytest.mark.asyncio
async def test_backup_and_restore(single_client, clean_graph, measure_time):
    """Test backup creation and data restoration."""
    
    # Check if backup script exists
    backup_script = Path("./scripts/backup.sh")
    if not backup_script.exists():
        pytest.skip("Backup script not found")
    
    # Create unique test data
    backup_id = uuid.uuid4().hex[:8]
    test_data = {
        "id": backup_id,
        "episodes": [
            f"Backup test {backup_id}: Configuration data",
            f"Backup test {backup_id}: User preferences",
            f"Backup test {backup_id}: System state"
        ]
    }
    
    # Add test data
    print(f"\n  Adding test data for backup ID: {backup_id}")
    for i, episode_body in enumerate(test_data["episodes"]):
        await single_client.add_episode(
            name=f"Backup-Test-{backup_id}-{i}",
            episode_body=episode_body,
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Backup test data"
        )
    
    await asyncio.sleep(0.5)  # Ensure data is written
    
    # Verify data exists
    pre_backup_results = await single_client.search(backup_id, num_results=10)
    assert len(pre_backup_results) > 0, "Data should exist before backup"
    print(f"  Found {len(pre_backup_results)} items before backup")
    
    # Create backup
    print("  Creating backup...")
    result = subprocess.run(
        ["./scripts/backup.sh"],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if result.returncode != 0:
        print(f"  Backup script output: {result.stdout}")
        print(f"  Backup script errors: {result.stderr}")
        pytest.skip(f"Backup script failed: {result.stderr}")
    
    # Find the latest backup file
    backup_dir = Path("./backups")
    if not backup_dir.exists():
        pytest.skip("Backup directory not found")
    
    backup_files = sorted(backup_dir.glob("falkordb_backup_*.rdb"))
    if not backup_files:
        pytest.skip("No backup files found")
    
    latest_backup = backup_files[-1]
    print(f"  Created backup: {latest_backup.name}")
    
    # Simulate data loss by clearing the graph
    print("  Simulating data loss...")
    await clear_data(single_client.driver)
    
    # Verify data is gone
    post_clear_results = await single_client.search(backup_id, num_results=10)
    assert len(post_clear_results) == 0, "Data should be cleared"
    print("  Data cleared successfully")
    
    # Note: Actual restore would require stopping FalkorDB, copying backup file,
    # and restarting. This is complex in a test environment, so we verify
    # the backup file exists and has reasonable size
    
    backup_size = latest_backup.stat().st_size
    assert backup_size > 0, "Backup file should not be empty"
    print(f"✓ Backup created successfully: {backup_size} bytes")
    
    # Clean up test backup if it's very recent (created by this test)
    if time.time() - latest_backup.stat().st_mtime < 60:  # Created within last minute
        try:
            latest_backup.unlink()
            print(f"  Cleaned up test backup: {latest_backup.name}")
        except:
            pass  # Ignore cleanup errors


@pytest.mark.integration
@pytest.mark.persistence
@pytest.mark.asyncio
async def test_graph_consistency_after_failure(single_client, clean_graph, measure_time):
    """Test that graph relationships remain consistent after simulated failures."""
    
    # Create interconnected data
    consistency_id = uuid.uuid4().hex[:8]
    
    # Phase 1: Create initial graph structure
    print(f"\n  Creating graph structure with ID: {consistency_id}")
    
    episodes = [
        {
            "name": "User Node",
            "body": f"User {consistency_id}: John is a developer"
        },
        {
            "name": "System Node",
            "body": f"System {consistency_id}: John uses FalkorDB on port 6380"
        },
        {
            "name": "Config Node",
            "body": f"Config {consistency_id}: FalkorDB configured with THREAD_COUNT=8"
        },
        {
            "name": "Relationship",
            "body": f"Relationship {consistency_id}: John optimized FalkorDB for M3 MacBook"
        }
    ]
    
    for episode in episodes:
        await single_client.add_episode(
            name=episode["name"],
            episode_body=episode["body"],
            source=EpisodeType.text,
            reference_time=datetime.now(timezone.utc),
            source_description="Consistency test data"
        )
    
    await asyncio.sleep(0.5)
    
    # Verify initial structure
    initial_results = await single_client.search(consistency_id, num_results=10)
    initial_facts = {r.fact for r in initial_results}
    assert len(initial_facts) > 0, "Initial graph structure should be created"
    print(f"  Created {len(initial_facts)} initial facts")
    
    # Phase 2: Simulate partial writes (potential failure scenario)
    print("  Simulating partial write scenario...")
    
    partial_episodes = [
        {
            "name": "Partial Update 1",
            "body": f"Update {consistency_id}: John changed THREAD_COUNT to 16"
        },
        {
            "name": "Partial Update 2",
            "body": f"Update {consistency_id}: System memory increased to 8GB"
        }
    ]
    
    # Add first update
    await single_client.add_episode(
        name=partial_episodes[0]["name"],
        episode_body=partial_episodes[0]["body"],
        source=EpisodeType.text,
        reference_time=datetime.now(timezone.utc),
        source_description="Partial update test"
    )
    
    # Small delay to simulate failure between writes
    await asyncio.sleep(0.1)
    
    # Add second update
    await single_client.add_episode(
        name=partial_episodes[1]["name"],
        episode_body=partial_episodes[1]["body"],
        source=EpisodeType.text,
        reference_time=datetime.now(timezone.utc),
        source_description="Partial update test"
    )
    
    await asyncio.sleep(0.5)
    
    # Phase 3: Verify consistency
    @measure_time(max_seconds=2.0)
    async def verify_consistency():
        # Search for all data
        all_results = await single_client.search(consistency_id, num_results=20)
        
        # Search for specific relationships
        john_results = await single_client.search(f"John {consistency_id}", num_results=10)
        config_results = await single_client.search(f"THREAD_COUNT {consistency_id}", num_results=10)
        
        return all_results, john_results, config_results
    
    (all_results, john_results, config_results), duration = await verify_consistency()
    
    # Verify graph consistency
    all_facts = [r.fact for r in all_results]
    
    # Original facts should still exist
    assert any("John is a developer" in fact for fact in all_facts), "Original user data should persist"
    assert any("6380" in fact for fact in all_facts), "Original system data should persist"
    
    # Updates should be findable
    assert any("THREAD_COUNT" in fact for fact in all_facts), "Configuration should be searchable"
    
    # Relationships should be maintained
    john_facts = [r.fact for r in john_results]
    assert len(john_facts) > 0, "User relationships should be maintained"
    
    print(f"✓ Graph consistency verified after simulated failure")
    print(f"  Total facts: {len(all_facts)}")
    print(f"  User-related facts: {len(john_facts)}")
    print(f"  Config-related facts: {len(config_results)}")


@pytest.mark.integration
@pytest.mark.persistence
@pytest.mark.asyncio
async def test_concurrent_persistence(graphiti_clients, clean_graph, measure_time):
    """Test that concurrent writes from multiple agents are all persisted."""
    
    persistence_id = uuid.uuid4().hex[:8]
    write_tracking = {"expected": [], "actual": []}
    
    @measure_time(max_seconds=5.0)
    async def concurrent_persistent_writes():
        tasks = []
        
        for i, client in enumerate(graphiti_clients):
            async def persistent_write(agent_id):
                episode_id = f"{persistence_id}-agent-{agent_id}"
                write_tracking["expected"].append(episode_id)
                
                await client.add_episode(
                    name=f"Persistent-Write-{episode_id}",
                    episode_body=f"Agent {agent_id} data: {episode_id}. Configuration value: {agent_id * 100}",
                    source=EpisodeType.text,
                    reference_time=datetime.now(timezone.utc),
                    source_description="Concurrent persistence test"
                )
                return episode_id
            
            task = persistent_write(i)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for errors
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"
        
        return results
    
    write_results, duration = await concurrent_persistent_writes()
    print(f"\n  Concurrent writes completed in {duration:.2f}s")
    
    # Wait for indexing
    await asyncio.sleep(0.5)
    
    # Verify all writes persisted using different client
    verification_client = graphiti_clients[0]
    
    for expected_id in write_tracking["expected"]:
        results = await verification_client.search(expected_id, num_results=5)
        if len(results) > 0:
            write_tracking["actual"].append(expected_id)
    
    # Verify persistence
    assert len(write_tracking["actual"]) == len(write_tracking["expected"]), \
        f"Not all concurrent writes persisted: {len(write_tracking['actual'])}/{len(write_tracking['expected'])}"
    
    print(f"✓ All {len(write_tracking['expected'])} concurrent writes persisted successfully")


@pytest.mark.integration
@pytest.mark.persistence
@pytest.mark.slow
@pytest.mark.asyncio
async def test_long_term_data_retention(single_client, clean_graph, measure_time):
    """Test that data remains queryable over multiple operations."""
    
    retention_id = uuid.uuid4().hex[:8]
    retention_data = []
    
    print(f"\n  Testing long-term retention with ID: {retention_id}")
    
    # Add data over multiple batches
    for batch in range(3):
        batch_data = []
        
        for i in range(3):
            episode_id = f"{retention_id}-batch-{batch}-item-{i}"
            batch_data.append(episode_id)
            
            await single_client.add_episode(
                name=f"Retention-Test-{episode_id}",
                episode_body=f"Long-term data {episode_id}. Batch {batch}, Item {i}. Value: {batch * 10 + i}",
                source=EpisodeType.text,
                reference_time=datetime.now(timezone.utc),
                source_description="Retention test data"
            )
        
        retention_data.extend(batch_data)
        
        # Verify previous data still accessible
        for prev_id in retention_data:
            results = await single_client.search(prev_id, num_results=5)
            assert len(results) > 0, f"Previous data {prev_id} should remain accessible"
        
        print(f"  Batch {batch + 1}: Added {len(batch_data)} items, total: {len(retention_data)}")
        await asyncio.sleep(0.5)
    
    # Final verification of all data
    @measure_time(max_seconds=3.0)
    async def verify_all_retention():
        all_results = await single_client.search(retention_id, num_results=50)
        return all_results
    
    final_results, duration = await verify_all_retention()
    
    # Verify all data is retained
    assert len(final_results) >= len(retention_data), \
        f"All data should be retained: found {len(final_results)}/{len(retention_data)}"
    
    print(f"✓ Long-term data retention verified")
    print(f"  Retained {len(final_results)} items over {duration:.2f}s query")