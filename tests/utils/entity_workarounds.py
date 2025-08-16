#!/usr/bin/env python3
"""
Workarounds for FalkorDB-Graphiti custom entity limitations.
Provides practical solutions for production use despite known gaps.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.driver.falkordb_driver import FalkorDriver


class EntityWorkaroundManager:
    """Manages workarounds for custom entity limitations in FalkorDB."""
    
    def __init__(self, graphiti_client: Optional[Graphiti] = None, 
                 json_backup_dir: str = "./entity_backups"):
        """
        Initialize workaround manager.
        
        Args:
            graphiti_client: Optional Graphiti client (can work without it)
            json_backup_dir: Directory for JSON backups
        """
        self.client = graphiti_client
        self.backup_dir = Path(json_backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.entity_cache: Dict[str, Dict] = {}
        
    def encode_entity_in_summary(self, entity: BaseModel, entity_type: str) -> str:
        """
        Encode custom entity data in the summary field.
        
        Args:
            entity: Pydantic model instance
            entity_type: Type name (e.g., "Task", "Project")
            
        Returns:
            Summary string with encoded entity data
        """
        # Create a structured summary that includes entity type and key properties
        entity_data = entity.model_dump()
        
        # Build human-readable summary with embedded metadata
        summary_parts = [f"[{entity_type}]"]
        
        # Add key fields to summary
        key_fields = []
        for field, value in entity_data.items():
            if value is not None and field not in ["uuid", "created_at"]:
                if isinstance(value, (str, int, float, bool)):
                    key_fields.append(f"{field}={value}")
                elif isinstance(value, list) and len(value) > 0:
                    key_fields.append(f"{field}=[{len(value)} items]")
        
        summary = f"{' '.join(summary_parts)} {' | '.join(key_fields[:5])}"
        
        # Add JSON metadata at the end (parseable but not intrusive)
        metadata = {
            "entity_type": entity_type,
            "custom_data": entity_data
        }
        summary += f" |||METADATA:{json.dumps(metadata, separators=(',', ':'))}|||"
        
        return summary
    
    def decode_entity_from_summary(self, summary: str) -> Optional[Dict[str, Any]]:
        """
        Decode entity data from a summary field.
        
        Args:
            summary: Summary string potentially containing encoded data
            
        Returns:
            Decoded entity data or None
        """
        if "|||METADATA:" in summary and "|||" in summary:
            try:
                # Extract JSON metadata
                start = summary.index("|||METADATA:") + len("|||METADATA:")
                end = summary.rindex("|||")
                metadata_str = summary[start:end]
                metadata = json.loads(metadata_str)
                return metadata
            except (ValueError, json.JSONDecodeError):
                pass
        return None
    
    def create_episode_with_entity_type(self, 
                                       episode_body: str,
                                       entity_types_used: List[str],
                                       **episode_kwargs) -> Dict[str, Any]:
        """
        Create an episode with entity type information embedded.
        
        Args:
            episode_body: Original episode body
            entity_types_used: List of entity types this episode uses
            **episode_kwargs: Other arguments for add_episode
            
        Returns:
            Modified episode arguments
        """
        # Embed entity type info in episode body
        entity_marker = f"\n[ENTITY_TYPES: {','.join(entity_types_used)}]"
        modified_body = episode_body + entity_marker
        
        episode_kwargs["episode_body"] = modified_body
        
        # Add to source_description if present
        if "source_description" in episode_kwargs:
            episode_kwargs["source_description"] += f" | Entities: {','.join(entity_types_used)}"
        
        return episode_kwargs
    
    async def save_entities_to_json(self, 
                                   entities: List[BaseModel],
                                   entity_types: Dict[str, str],
                                   session_id: str) -> str:
        """
        Save entities to JSON backup with full custom properties.
        
        Args:
            entities: List of Pydantic model instances
            entity_types: Mapping of entity instances to type names
            session_id: Session identifier for the backup
            
        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"entities_{session_id}_{timestamp}.json"
        
        backup_data = {
            "session_id": session_id,
            "timestamp": timestamp,
            "entities": []
        }
        
        for entity in entities:
            entity_type = entity_types.get(id(entity), "Unknown")
            entity_record = {
                "type": entity_type,
                "data": entity.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            backup_data["entities"].append(entity_record)
            
            # Cache for quick retrieval
            if hasattr(entity, 'uuid'):
                self.entity_cache[entity.uuid] = entity_record
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        return str(backup_file)
    
    def load_entities_from_json(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Load entities from JSON backup.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of entity records
        """
        entities = []
        
        # Find all backup files for this session
        pattern = f"entities_{session_id}_*.json"
        for backup_file in self.backup_dir.glob(pattern):
            with open(backup_file, 'r') as f:
                data = json.load(f)
                entities.extend(data.get("entities", []))
        
        return entities
    
    async def add_entity_type_property(self, 
                                      node_uuid: str,
                                      entity_type: str,
                                      custom_props: Dict[str, Any]) -> bool:
        """
        Add entity_type and custom properties to existing node.
        Note: This requires direct FalkorDB access.
        
        Args:
            node_uuid: UUID of the node
            entity_type: Entity type name
            custom_props: Custom properties to add
            
        Returns:
            Success status
        """
        if not self.client:
            return False
            
        try:
            from falkordb import FalkorDB
            
            # Get database name from driver
            db_name = self.client.driver.database
            
            # Direct connection to add properties
            db = FalkorDB(host='localhost', port=6380)
            g = db.select_graph(db_name)
            
            # Build SET clause for properties
            set_clauses = ["n.entity_type = $entity_type"]
            params = {"uuid": node_uuid, "entity_type": entity_type}
            
            for key, value in custom_props.items():
                if key not in ["uuid", "name", "created_at", "summary"]:
                    safe_key = key.replace("-", "_")
                    set_clauses.append(f"n.{safe_key} = ${safe_key}")
                    params[safe_key] = value
            
            query = f"""
                MATCH (n:Entity {{uuid: $uuid}})
                SET {', '.join(set_clauses)}
                RETURN n
            """
            
            result = g.query(query, params)
            return len(result.result_set) > 0
            
        except Exception as e:
            print(f"Warning: Could not add entity type property: {e}")
            return False
    
    def create_fact_with_entity_info(self, 
                                    fact: str,
                                    source_type: str,
                                    target_type: str,
                                    edge_type: str) -> str:
        """
        Enhance fact string with entity type information.
        
        Args:
            fact: Original fact string
            source_type: Source entity type
            target_type: Target entity type  
            edge_type: Relationship type
            
        Returns:
            Enhanced fact string
        """
        # Add type information to fact
        enhanced = f"{fact} [{source_type}--{edge_type}-->{target_type}]"
        return enhanced
    
    async def search_by_entity_type(self,
                                   query: str,
                                   entity_type: str,
                                   num_results: int = 10) -> List[Any]:
        """
        Search for entities of a specific type using workarounds.
        
        Args:
            query: Search query
            entity_type: Entity type to filter
            num_results: Number of results
            
        Returns:
            Filtered search results
        """
        if not self.client:
            return []
        
        # Search with entity type in query
        enhanced_query = f"{query} [{entity_type}]"
        
        try:
            # Try regular search first
            results = await self.client.search(enhanced_query, num_results=num_results * 2)
            
            # Filter results by entity type markers in facts
            filtered = []
            for result in results:
                if f"[{entity_type}]" in result.fact or entity_type.lower() in result.fact.lower():
                    filtered.append(result)
                    if len(filtered) >= num_results:
                        break
            
            return filtered
            
        except Exception as e:
            print(f"Search failed: {e}")
            return []
    
    def create_migration_script(self, 
                               source_db: str,
                               target_db: str) -> str:
        """
        Create a script to migrate entities with proper types.
        
        Args:
            source_db: Source database name
            target_db: Target database name
            
        Returns:
            Migration script content
        """
        script = f"""#!/bin/bash
# Migration script for custom entities from {source_db} to {target_db}

# This script shows how to properly migrate entities with type information

# 1. Export entities with type information
redis-cli -p 6380 GRAPH.QUERY {source_db} "
    MATCH (n:Entity)
    RETURN n.uuid, n.name, n.summary, properties(n)
" > entities_export.json

# 2. Process and add entity_type field (would need Python script)
python3 -c "
import json
data = json.load(open('entities_export.json'))
for entity in data:
    # Extract entity type from summary if encoded
    if '|||METADATA:' in entity.get('summary', ''):
        # Parse and add entity_type
        pass
"

# 3. Import to new database with types
# Would need custom import logic

echo "Migration requires custom processing for entity types"
"""
        return script


class SimpleEntityStore:
    """Simple JSON-based entity store as complete workaround."""
    
    def __init__(self, store_dir: str = "./entity_store"):
        """Initialize simple store."""
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.entities_file = self.store_dir / "entities.json"
        self.relationships_file = self.store_dir / "relationships.json"
        self._load()
    
    def _load(self):
        """Load existing data."""
        if self.entities_file.exists():
            with open(self.entities_file, 'r') as f:
                self.entities = json.load(f)
        else:
            self.entities = {}
        
        if self.relationships_file.exists():
            with open(self.relationships_file, 'r') as f:
                self.relationships = json.load(f)
        else:
            self.relationships = []
    
    def _save(self):
        """Save data to disk."""
        with open(self.entities_file, 'w') as f:
            json.dump(self.entities, f, indent=2, default=str)
        
        with open(self.relationships_file, 'w') as f:
            json.dump(self.relationships, f, indent=2, default=str)
    
    def add_entity(self, entity: BaseModel, entity_type: str) -> str:
        """Add entity to store."""
        import uuid
        entity_id = str(uuid.uuid4())
        
        self.entities[entity_id] = {
            "id": entity_id,
            "type": entity_type,
            "data": entity.model_dump(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        self._save()
        return entity_id
    
    def add_relationship(self, source_id: str, target_id: str, 
                        rel_type: str, properties: Dict = None):
        """Add relationship between entities."""
        self.relationships.append({
            "source": source_id,
            "target": target_id,
            "type": rel_type,
            "properties": properties or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        self._save()
    
    def search(self, query: str, entity_type: Optional[str] = None) -> List[Dict]:
        """Simple search in entities."""
        results = []
        query_lower = query.lower()
        
        for entity_id, entity in self.entities.items():
            # Type filter
            if entity_type and entity["type"] != entity_type:
                continue
            
            # Simple text search in data
            entity_str = json.dumps(entity["data"]).lower()
            if query_lower in entity_str:
                results.append(entity)
        
        return results
    
    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """Get entity by ID."""
        return self.entities.get(entity_id)
    
    def get_relationships(self, entity_id: str) -> List[Dict]:
        """Get relationships for an entity."""
        rels = []
        for rel in self.relationships:
            if rel["source"] == entity_id or rel["target"] == entity_id:
                rels.append(rel)
        return rels


# Convenience functions

def workaround_add_episode(episode_body: str,
                          entity_types: Dict[str, Type[BaseModel]],
                          use_json_backup: bool = True) -> Dict[str, Any]:
    """
    Prepare episode for adding with workarounds applied.
    
    Args:
        episode_body: Episode content
        entity_types: Entity type definitions
        use_json_backup: Whether to prepare for JSON backup
        
    Returns:
        Modified episode arguments
    """
    # Mark entity types in body
    type_names = list(entity_types.keys())
    marked_body = episode_body + f"\n[Entity Types: {', '.join(type_names)}]"
    
    # Prepare episode args
    episode_args = {
        "episode_body": marked_body,
        "source_description": f"Custom entities: {', '.join(type_names)}"
    }
    
    if use_json_backup:
        episode_args["metadata"] = {
            "entity_types": type_names,
            "workaround_version": "1.0"
        }
    
    return episode_args


def extract_entity_type_from_fact(fact: str) -> Optional[str]:
    """
    Extract entity type from fact string if encoded.
    
    Args:
        fact: Fact string
        
    Returns:
        Entity type or None
    """
    import re
    
    # Look for [EntityType] pattern
    pattern = r'\[([A-Z][a-zA-Z]+)\]'
    match = re.search(pattern, fact)
    if match:
        return match.group(1)
    
    # Look for entity type markers
    for entity_type in ["Task", "Project", "Student", "Lesson", "Account", "Investment"]:
        if entity_type.lower() in fact.lower():
            return entity_type
    
    return None