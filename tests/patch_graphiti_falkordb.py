#!/usr/bin/env python3
"""
Patch script to fix FalkorDB compatibility in graphiti-core v0.17.10+

This script patches the installed graphiti-core to use single quotes instead
of double quotes in the fulltext_query function, restoring FalkorDB compatibility.

Usage:
    python patch_graphiti_falkordb.py           # Apply patch
    python patch_graphiti_falkordb.py --revert  # Revert patch
    python patch_graphiti_falkordb.py --check   # Check current status
"""

import os
import sys
import shutil
import argparse
import importlib.util
from pathlib import Path


class GraphitiFalkorDBPatcher:
    """Patch graphiti-core for FalkorDB compatibility."""
    
    def __init__(self):
        self.target_file = None
        self.backup_file = None
        self.find_target_file()
        
    def find_target_file(self):
        """Find the search_utils.py file in the installed graphiti-core."""
        try:
            import graphiti_core
            package_dir = Path(graphiti_core.__file__).parent
            self.target_file = package_dir / "search" / "search_utils.py"
            self.backup_file = package_dir / "search" / "search_utils.py.backup"
            
            if not self.target_file.exists():
                print(f"❌ Error: Target file not found: {self.target_file}")
                sys.exit(1)
                
            print(f"✓ Found target file: {self.target_file}")
            
        except ImportError:
            print("❌ Error: graphiti-core is not installed")
            print("Please install it first: pip install graphiti-core[falkordb]")
            sys.exit(1)
    
    def check_current_status(self) -> str:
        """Check the current quote style in the file."""
        with open(self.target_file, 'r') as f:
            content = f.read()
        
        # Check for the different patterns
        if 'f"group_id:\'{lucene_sanitize(g)}\'"' in content:
            return "single_quotes_with_sanitize"
        elif "f\"group_id:'{g}'\"" in content:
            return "single_quotes_no_sanitize"
        elif "f'group_id:\"{lucene_sanitize(g)}\"'" in content:
            return "double_quotes_with_sanitize"
        elif 'f\'group_id:"{g}"' in content:
            return "double_quotes_no_sanitize"
        else:
            return "unknown"
    
    def apply_patch(self, dry_run=False):
        """Apply the FalkorDB compatibility patch."""
        print("\n" + "="*60)
        print("APPLYING FALKORDB COMPATIBILITY PATCH")
        print("="*60)
        
        # Check current status
        status = self.check_current_status()
        print(f"Current status: {status}")
        
        if "single_quotes" in status:
            print("✅ Already patched! File uses single quotes.")
            return True
        
        if not dry_run:
            # Create backup
            print(f"Creating backup: {self.backup_file}")
            shutil.copy2(self.target_file, self.backup_file)
        
        # Read the file
        with open(self.target_file, 'r') as f:
            lines = f.readlines()
        
        # Find and patch the line
        patched = False
        for i, line in enumerate(lines):
            # Look for the problematic line with double quotes
            if 'group_id:"' in line and 'for g in group_ids' in line:
                original_line = line
                
                # Replace double quotes with single quotes
                # Handle both versions (with and without lucene_sanitize)
                if 'lucene_sanitize(g)' in line:
                    new_line = line.replace('f\'group_id:"{lucene_sanitize(g)}"\'', 
                                           'f"group_id:\'{lucene_sanitize(g)}\'"')
                else:
                    new_line = line.replace('f\'group_id:"{g}"\'', 
                                           'f"group_id:\'{g}\'"')
                
                if new_line != original_line:
                    lines[i] = new_line
                    patched = True
                    print(f"\nLine {i+1} patched:")
                    print(f"  OLD: {original_line.strip()}")
                    print(f"  NEW: {new_line.strip()}")
        
        if not patched:
            print("⚠️  Warning: Could not find the line to patch")
            print("The file may have been modified or uses a different format")
            return False
        
        if not dry_run:
            # Write the patched file
            with open(self.target_file, 'w') as f:
                f.writelines(lines)
            print("\n✅ Patch applied successfully!")
            print(f"Backup saved to: {self.backup_file}")
        else:
            print("\n✅ Dry run completed - no files modified")
        
        return True
    
    def revert_patch(self):
        """Revert the patch using the backup file."""
        print("\n" + "="*60)
        print("REVERTING FALKORDB COMPATIBILITY PATCH")
        print("="*60)
        
        if not self.backup_file.exists():
            print("❌ Error: No backup file found")
            print("Cannot revert without a backup")
            return False
        
        print(f"Restoring from backup: {self.backup_file}")
        shutil.copy2(self.backup_file, self.target_file)
        
        # Remove backup file
        self.backup_file.unlink()
        
        print("✅ Patch reverted successfully!")
        return True
    
    def verify_patch(self):
        """Verify the patch works by testing the function."""
        print("\n" + "="*60)
        print("VERIFYING PATCH")
        print("="*60)
        
        try:
            # Reload the module to get the patched version
            import importlib
            import graphiti_core.search.search_utils
            importlib.reload(graphiti_core.search.search_utils)
            
            from graphiti_core.search.search_utils import fulltext_query
            
            # Test the function
            test_query = fulltext_query("test", ["my_group"], "")
            print(f"Generated query: {test_query}")
            
            if "'my_group'" in test_query or "\'my_group\'" in test_query:
                print("✅ Verification passed: Using single quotes")
                return True
            elif '"my_group"' in test_query or '\"my_group\"' in test_query:
                print("❌ Verification failed: Still using double quotes")
                return False
            else:
                print("⚠️  Verification inconclusive")
                return None
                
        except Exception as e:
            print(f"❌ Verification error: {e}")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Patch graphiti-core for FalkorDB compatibility"
    )
    parser.add_argument(
        "--revert",
        action="store_true",
        help="Revert the patch to original state"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check current patch status without modifying"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files"
    )
    
    args = parser.parse_args()
    
    patcher = GraphitiFalkorDBPatcher()
    
    if args.check:
        status = patcher.check_current_status()
        print(f"\nCurrent quote style: {status}")
        if "single" in status:
            print("✅ FalkorDB compatible (using single quotes)")
        elif "double" in status:
            print("❌ NOT FalkorDB compatible (using double quotes)")
        else:
            print("⚠️  Unknown status")
            
    elif args.revert:
        success = patcher.revert_patch()
        sys.exit(0 if success else 1)
        
    else:
        # Apply patch
        success = patcher.apply_patch(dry_run=args.dry_run)
        
        if success and not args.dry_run:
            # Verify the patch
            patcher.verify_patch()
            
            print("\n" + "="*60)
            print("IMPORTANT NOTES:")
            print("="*60)
            print("1. This patch modifies your installed graphiti-core")
            print("2. The patch will be lost if you reinstall/upgrade graphiti-core")
            print("3. To revert: python patch_graphiti_falkordb.py --revert")
            print("4. This is a temporary workaround until the official fix")
            print("="*60)
        
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()