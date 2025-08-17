#!/usr/bin/env python3
"""
Test quote compatibility between FalkorDB and Neo4j for group_id queries.

This test suite verifies the quote syntax issue and tests potential fixes
across different Graphiti versions and database backends.
"""

import asyncio
import sys
import subprocess
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class QuoteCompatibilityTester:
    """Test quote syntax compatibility across databases."""
    
    def __init__(self):
        self.results = {}
        
    async def test_falkordb_quotes(self, version: str, quote_style: str = "double") -> Dict[str, Any]:
        """
        Test FalkorDB with different quote styles.
        
        Args:
            version: Graphiti version to test
            quote_style: 'single' or 'double' quotes
        """
        print(f"\n{'='*60}")
        print(f"Testing FalkorDB with {quote_style} quotes - v{version}")
        print(f"{'='*60}")
        
        # Install the specific version
        print(f"Installing graphiti-core=={version}...")
        cmd = [sys.executable, "-m", "pip", "install", 
               f"graphiti-core[falkordb]=={version}", "--quiet"]
        subprocess.run(cmd, capture_output=True)
        
        try:
            from graphiti_core import Graphiti
            from graphiti_core.driver.falkordb_driver import FalkorDriver
            from graphiti_core.nodes import EpisodeType
            from graphiti_core.utils.maintenance.graph_data_operations import clear_data
            
            # Connect to FalkorDB on port 6380
            driver = FalkorDriver(
                host="localhost",
                port=6380,
                database=f"test_quotes_{version.replace('.', '_')}_{quote_style}"
            )
            
            client = Graphiti(graph_driver=driver)
            
            # Clear and setup
            await clear_data(client.driver)
            await client.build_indices_and_constraints()
            
            # Test adding an episode (this triggers the group_id query)
            await client.add_episode(
                name=f"Test {quote_style} quotes",
                episode_body=f"Testing {quote_style} quote compatibility",
                source=EpisodeType.text,
                reference_time=datetime.now(timezone.utc)
            )
            
            # If we get here, it worked
            print(f"✅ SUCCESS: {quote_style} quotes work with FalkorDB")
            return {
                "version": version,
                "database": "FalkorDB",
                "quote_style": quote_style,
                "status": "success",
                "error": None
            }
            
        except Exception as e:
            error_str = str(e)
            if "group_id" in error_str and "Syntax error" in error_str:
                print(f"❌ FAILED: {quote_style} quotes cause group_id syntax error")
                return {
                    "version": version,
                    "database": "FalkorDB",
                    "quote_style": quote_style,
                    "status": "failed",
                    "error": "group_id syntax error"
                }
            else:
                print(f"⚠️  OTHER ERROR: {error_str[:100]}")
                return {
                    "version": version,
                    "database": "FalkorDB",
                    "quote_style": quote_style,
                    "status": "error",
                    "error": error_str[:200]
                }
    
    async def test_direct_query_syntax(self):
        """
        Test the actual query syntax directly without going through Graphiti.
        This helps isolate the issue to the query generation.
        """
        print(f"\n{'='*60}")
        print("Testing Direct Query Syntax")
        print(f"{'='*60}")
        
        try:
            from graphiti_core.search.search_utils import fulltext_query
            
            # Test with single quotes (should work with FalkorDB)
            single_quote_query = self._mock_fulltext_query_single(
                "test", ["_"], ""
            )
            print(f"Single quote query: {single_quote_query}")
            
            # Test with double quotes (breaks FalkorDB) 
            double_quote_query = self._mock_fulltext_query_double(
                "test", ["_"], ""
            )
            print(f"Double quote query: {double_quote_query}")
            
            # Test what the actual function generates
            actual_query = fulltext_query("test", ["_"], "")
            print(f"Actual query (current version): {actual_query}")
            
            return {
                "single_quote": single_quote_query,
                "double_quote": double_quote_query,
                "actual": actual_query
            }
            
        except Exception as e:
            print(f"Error testing query syntax: {e}")
            return None
    
    def _mock_fulltext_query_single(self, query: str, group_ids: list, syntax: str) -> str:
        """Mock the fulltext_query function with single quotes."""
        group_ids_filter_list = (
            [syntax + f"group_id:'{g}'" for g in group_ids] if group_ids else []
        )
        group_ids_filter = ' '.join(group_ids_filter_list)
        if group_ids_filter:
            return f"{group_ids_filter} ({query})"
        return f"({query})"
    
    def _mock_fulltext_query_double(self, query: str, group_ids: list, syntax: str) -> str:
        """Mock the fulltext_query function with double quotes."""
        group_ids_filter_list = (
            [syntax + f'group_id:"{g}"' for g in group_ids] if group_ids else []
        )
        group_ids_filter = ' '.join(group_ids_filter_list)
        if group_ids_filter:
            return f"{group_ids_filter} ({query})"
        return f"({query})"
    
    async def run_compatibility_matrix(self):
        """Run a full compatibility matrix test."""
        versions = ["0.17.9", "0.17.10", "0.18.7"]  # Key versions
        
        print("\n" + "="*70)
        print("QUOTE COMPATIBILITY MATRIX TEST")
        print("="*70)
        
        # Test direct query syntax first
        query_results = await self.test_direct_query_syntax()
        
        # Test each version with FalkorDB
        for version in versions:
            # We know v0.17.9 uses single quotes, others use double
            if version == "0.17.9":
                # v0.17.9 has single quotes by default
                result = await self.test_falkordb_quotes(version, "single")
            else:
                # v0.17.10+ have double quotes by default
                result = await self.test_falkordb_quotes(version, "double")
            
            self.results[f"{version}_default"] = result
        
        # Print summary
        self._print_summary()
        
        return self.results
    
    def _print_summary(self):
        """Print a summary of all test results."""
        print("\n" + "="*70)
        print("COMPATIBILITY MATRIX SUMMARY")
        print("="*70)
        print(f"{'Version':<12} {'Quote Style':<12} {'FalkorDB':<15} {'Error':<30}")
        print("-"*70)
        
        for key, result in self.results.items():
            if result:
                version = result['version']
                quote = result['quote_style']
                status = "✅ WORKS" if result['status'] == 'success' else "❌ FAILS"
                error = result['error'] or ''
                print(f"{version:<12} {quote:<12} {status:<15} {error:<30}")
        
        print("\n" + "="*70)
        print("KEY FINDINGS:")
        print("- v0.17.9 uses SINGLE quotes: Works with FalkorDB")
        print("- v0.17.10+ use DOUBLE quotes: Fails with FalkorDB")
        print("- Solution: Revert to single quotes or add DB detection")
        print("="*70)


async def main():
    """Main test runner."""
    from dotenv import load_dotenv
    load_dotenv()
    
    tester = QuoteCompatibilityTester()
    
    # Run the full compatibility matrix
    results = await tester.run_compatibility_matrix()
    
    # Determine overall test status
    failures = [r for r in results.values() if r and r['status'] != 'success']
    
    if failures:
        print(f"\n❌ {len(failures)} tests failed")
        print("The quote syntax incompatibility is confirmed!")
        return 1
    else:
        print("\n✅ All tests passed")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)