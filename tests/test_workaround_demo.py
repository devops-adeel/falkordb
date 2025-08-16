#!/usr/bin/env python3
"""
Demonstration of practical workarounds for using custom entities with FalkorDB.
Shows how to successfully work with custom entities despite the limitations.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
from pydantic import BaseModel, Field

# Import workarounds
from utils.entity_workarounds import (
    EntityWorkaroundManager,
    SimpleEntityStore,
    workaround_add_episode,
    extract_entity_type_from_fact
)

# Import entity definitions
from entities.gtd_entities import Task, Project, Context
from entities.arabic_entities import Student, Lesson, VocabularyWord
from entities.islamic_finance_entities import Account, ZakatCalculation


class WorkaroundDemo:
    """Demonstrates successful workarounds for custom entities."""
    
    def __init__(self):
        self.workaround_manager = EntityWorkaroundManager(json_backup_dir="./demo_backups")
        self.simple_store = SimpleEntityStore(store_dir="./demo_store")
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    async def demo_json_backup_approach(self):
        """Demonstrate using JSON backup for full entity preservation."""
        
        print("\n" + "="*60)
        print("DEMO: JSON Backup Approach")
        print("="*60)
        
        # Create some entities
        task1 = Task(
            description="Review quarterly budget",
            project="Q1 Planning",
            context="@office",
            priority="A",
            energy_required="high",
            time_estimate=60
        )
        
        task2 = Task(
            description="Call team members",
            project="Q1 Planning",
            context="@phone",
            priority="B",
            energy_required="medium",
            time_estimate=30
        )
        
        project = Project(
            project_name="Q1 Planning",
            status="active",
            area_of_focus="Business",
            next_action="Review quarterly budget",
            deadline="2025-03-31"
        )
        
        # Save to JSON with full properties
        entities = [task1, task2, project]
        entity_types = {
            id(task1): "Task",
            id(task2): "Task",
            id(project): "Project"
        }
        
        backup_file = await self.workaround_manager.save_entities_to_json(
            entities, entity_types, self.session_id
        )
        
        print(f"✅ Saved {len(entities)} entities to: {backup_file}")
        
        # Load and verify
        loaded = self.workaround_manager.load_entities_from_json(self.session_id)
        print(f"✅ Loaded {len(loaded)} entities from backup")
        
        for entity in loaded[:2]:
            print(f"\n   Entity Type: {entity['type']}")
            print(f"   Data preserved: {list(entity['data'].keys())}")
            
        return True
    
    async def demo_summary_encoding(self):
        """Demonstrate encoding entity data in summary field."""
        
        print("\n" + "="*60)
        print("DEMO: Summary Field Encoding")
        print("="*60)
        
        # Create an Arabic learning entity
        student = Student(
            student_name="Ahmed",
            proficiency_level="intermediate",
            native_language="English",
            learning_goals=["Conversational fluency", "Read classical texts"],
            weekly_study_hours=10.5
        )
        
        # Encode in summary
        summary = self.workaround_manager.encode_entity_in_summary(student, "Student")
        print(f"\n📝 Encoded summary (first 150 chars):")
        print(f"   {summary[:150]}...")
        
        # Decode from summary
        decoded = self.workaround_manager.decode_entity_from_summary(summary)
        if decoded:
            print(f"\n✅ Successfully decoded:")
            print(f"   Entity type: {decoded['entity_type']}")
            print(f"   Student name: {decoded['custom_data']['student_name']}")
            print(f"   Proficiency: {decoded['custom_data']['proficiency_level']}")
            print(f"   Study hours: {decoded['custom_data']['weekly_study_hours']}")
        
        return True
    
    async def demo_simple_entity_store(self):
        """Demonstrate using simple JSON store as complete workaround."""
        
        print("\n" + "="*60)
        print("DEMO: Simple Entity Store")
        print("="*60)
        
        # Add Islamic finance entities
        account = Account(
            account_name="Savings-001",
            account_type="mudarabah",
            institution="Al-Rajhi Bank",
            balance=50000.0,
            currency="USD",
            opened_date="2024-01-01",
            profit_rate=3.5,
            is_zakat_eligible=True
        )
        
        zakat = ZakatCalculation(
            calculation_date="2025-01-15",
            lunar_year="1446",
            total_wealth=50000.0,
            nisab_threshold=3500.0,
            eligible_wealth=46500.0,
            zakat_rate=0.025,
            zakat_due=1162.50,
            cash_value=50000.0,
            remaining_due=1162.50
        )
        
        # Add to store
        account_id = self.simple_store.add_entity(account, "Account")
        zakat_id = self.simple_store.add_entity(zakat, "ZakatCalculation")
        
        print(f"✅ Added Account: {account_id[:8]}...")
        print(f"✅ Added ZakatCalculation: {zakat_id[:8]}...")
        
        # Add relationship
        self.simple_store.add_relationship(
            zakat_id, account_id, "CALCULATED_FOR",
            {"year": "1446", "amount": 1162.50}
        )
        print(f"✅ Added relationship: ZakatCalculation -> Account")
        
        # Search by type
        results = self.simple_store.search("Rajhi", entity_type="Account")
        print(f"\n🔍 Search results for 'Rajhi' (Account type only):")
        for result in results:
            print(f"   - {result['type']}: {result['data']['account_name']}")
        
        # Get relationships
        rels = self.simple_store.get_relationships(account_id)
        print(f"\n🔗 Relationships for account: {len(rels)} found")
        
        return True
    
    async def demo_enhanced_facts(self):
        """Demonstrate enhancing facts with entity type information."""
        
        print("\n" + "="*60)
        print("DEMO: Enhanced Fact Strings")
        print("="*60)
        
        # Create facts with entity info
        facts = [
            self.workaround_manager.create_fact_with_entity_info(
                "Ahmed completed Arabic lesson on past tense verbs",
                "Student", "Lesson", "COMPLETED"
            ),
            self.workaround_manager.create_fact_with_entity_info(
                "Review quarterly budget is next action for Q1 Planning",
                "Task", "Project", "BELONGS_TO"
            ),
            self.workaround_manager.create_fact_with_entity_info(
                "Zakat payment of $1162.50 sent to Local Mosque",
                "ZakatCalculation", "Beneficiary", "PAID_TO"
            )
        ]
        
        print("\n📊 Enhanced facts with entity types:")
        for i, fact in enumerate(facts, 1):
            print(f"\n{i}. {fact}")
            
            # Extract entity type
            extracted = extract_entity_type_from_fact(fact)
            if extracted:
                print(f"   Extracted type: {extracted}")
        
        return True
    
    async def demo_combined_approach(self):
        """Demonstrate combining multiple workarounds for best results."""
        
        print("\n" + "="*60)
        print("DEMO: Combined Workaround Approach")
        print("="*60)
        
        print("\n🎯 Strategy for production use:")
        print("1. Use JSON backup for complete entity data")
        print("2. Encode critical info in summaries")
        print("3. Enhance facts with type markers")
        print("4. Maintain simple store for complex queries")
        
        # Example workflow
        print("\n📋 Example workflow:")
        
        # Step 1: Create entity
        task = Task(
            description="Complete zakat calculation for 2025",
            project="Islamic Finance",
            context="@computer",
            priority="A",
            energy_required="high",
            time_estimate=120
        )
        
        # Step 2: Save to JSON backup
        entities = [task]
        entity_types = {id(task): "Task"}
        backup_file = await self.workaround_manager.save_entities_to_json(
            entities, entity_types, f"combined_{self.session_id}"
        )
        print(f"   ✅ Backed up to: {Path(backup_file).name}")
        
        # Step 3: Encode in summary
        summary = self.workaround_manager.encode_entity_in_summary(task, "Task")
        print(f"   ✅ Encoded summary created")
        
        # Step 4: Add to simple store
        entity_id = self.simple_store.add_entity(task, "Task")
        print(f"   ✅ Added to simple store: {entity_id[:8]}...")
        
        # Step 5: Create enhanced fact
        fact = self.workaround_manager.create_fact_with_entity_info(
            task.description,
            "Task", "Project", "BELONGS_TO"
        )
        print(f"   ✅ Enhanced fact: {fact[:60]}...")
        
        print("\n✨ All workarounds applied successfully!")
        
        return True


async def main():
    """Run all demonstrations."""
    print("\n" + "="*60)
    print("🚀 CUSTOM ENTITY WORKAROUND DEMONSTRATIONS")
    print("="*60)
    
    demo = WorkaroundDemo()
    
    # Run all demos
    results = []
    
    print("\nRunning demonstrations...")
    
    results.append(await demo.demo_json_backup_approach())
    results.append(await demo.demo_summary_encoding())
    results.append(await demo.demo_simple_entity_store())
    results.append(await demo.demo_enhanced_facts())
    results.append(await demo.demo_combined_approach())
    
    # Summary
    print("\n" + "="*60)
    print("DEMONSTRATION SUMMARY")
    print("="*60)
    
    if all(results):
        print("\n✅ All workarounds demonstrated successfully!")
        print("\nKey Takeaways:")
        print("1. JSON backup preserves all custom entity properties")
        print("2. Summary encoding allows entity data in FalkorDB")
        print("3. Simple store provides full query capabilities")
        print("4. Enhanced facts maintain entity type context")
        print("5. Combined approach gives best of all worlds")
        
        print("\n📚 For your agents (Arabic tutor, GTD coach, Finance advisor):")
        print("   - Use JSON backup as primary entity storage")
        print("   - Let FalkorDB handle relationships and basic search")
        print("   - Implement simple store for entity-specific queries")
        print("   - Mark entity types in all text representations")
        
    else:
        print("\n⚠️ Some demonstrations had issues")
    
    # Cleanup
    print("\n🧹 Cleaning up demo files...")
    import shutil
    for dir_path in ["./demo_backups", "./demo_store"]:
        if Path(dir_path).exists():
            shutil.rmtree(dir_path)
            print(f"   Removed {dir_path}")


if __name__ == "__main__":
    asyncio.run(main())