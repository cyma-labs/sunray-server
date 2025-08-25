#!/usr/bin/env python3
"""
Audit Event Validation Script

Ensures all audit log events are properly declared and prevents missing event type errors.
This script should be run before deployments and can be integrated into pre-commit hooks.
"""

import os
import re
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple


def extract_declared_events(audit_log_file: Path) -> Set[str]:
    """Extract all declared event types from the audit log model."""
    with open(audit_log_file, 'r') as f:
        content = f.read()
    
    # Find the event_type field definition
    pattern = r"event_type\s*=\s*fields\.Selection\(\[\s*(.*?)\s*\]"
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("❌ Could not find event_type field definition")
        return set()
    
    selection_content = match.group(1)
    
    # Extract individual event declarations
    event_pattern = r"\(['\"]([^'\"]+)['\"],\s*['\"][^'\"]*['\"]\)"
    events = re.findall(event_pattern, selection_content)
    
    return set(events)


def extract_used_events(project_dir: Path) -> Dict[str, List[str]]:
    """Extract all used event types from the codebase."""
    used_events = {}
    
    # Files to scan for event usage
    patterns = [
        "**/*.py",  # All Python files
    ]
    
    for pattern in patterns:
        for file_path in project_dir.glob(pattern):
            if file_path.name.startswith('.'):
                continue
                
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Look for event_type assignments
                event_pattern = r"event_type\s*=\s*['\"]([^'\"]+)['\"]"
                matches = re.findall(event_pattern, content)
                
                for event in matches:
                    relative_path = str(file_path.relative_to(project_dir))
                    if event not in used_events:
                        used_events[event] = []
                    used_events[event].append(relative_path)
                    
            except (UnicodeDecodeError, PermissionError):
                continue
    
    return used_events


def check_method_calls(project_dir: Path) -> List[str]:
    """Check for missing audit log methods that could cause AttributeError."""
    errors = []
    
    # Known audit log methods (including Odoo built-in methods)
    audit_methods = {
        'create_api_event', 'create_admin_event', 'create_user_event', 
        'create_worker_event', 'create_security_event', 'cleanup_old_logs',
        # Odoo built-in methods
        'search', 'search_count', 'create', 'write', 'unlink', 'browse',
        'sudo', 'with_context', 'with_env', 'exists', 'ensure_one'
    }
    
    for py_file in project_dir.glob("**/*.py"):
        try:
            with open(py_file, 'r') as f:
                content = f.read()
            
            # Look for audit log method calls
            pattern = r"\.env\[['\"']sunray\.audit\.log['\"']\]\.(?:sudo\(\)\.)?(\w+)\("
            matches = re.findall(pattern, content)
            
            for method in matches:
                if method not in audit_methods and not method.startswith('_'):
                    relative_path = str(py_file.relative_to(project_dir))
                    errors.append(f"Unknown audit method '{method}' in {relative_path}")
                    
        except (UnicodeDecodeError, PermissionError):
            continue
    
    return errors


def main():
    """Main validation function."""
    project_dir = Path(__file__).parent.parent / "project_addons"
    audit_log_file = project_dir / "sunray_core/models/sunray_audit_log.py"
    
    if not audit_log_file.exists():
        print("❌ Audit log model file not found")
        return 1
    
    print("🔍 Validating audit log events...")
    
    # Extract declared and used events
    declared_events = extract_declared_events(audit_log_file)
    used_events = extract_used_events(project_dir)
    
    print(f"📊 Found {len(declared_events)} declared events")
    print(f"📊 Found {len(used_events)} used events")
    
    # Check for issues
    issues_found = 0
    
    # 1. Check for undeclared events being used
    undeclared = set(used_events.keys()) - declared_events
    if undeclared:
        print("\n❌ UNDECLARED EVENTS BEING USED:")
        issues_found += len(undeclared)
        for event in sorted(undeclared):
            print(f"  • '{event}' used but not declared")
            for file_path in used_events[event]:
                print(f"    - {file_path}")
    
    # 2. Check for declared but unused events
    unused = declared_events - set(used_events.keys())
    if unused:
        print(f"\n⚠️  DECLARED BUT UNUSED EVENTS ({len(unused)}):")
        for event in sorted(unused):
            print(f"  • '{event}' declared but never used")
    
    # 3. Check for missing audit log methods
    method_errors = check_method_calls(project_dir)
    if method_errors:
        print(f"\n❌ AUDIT METHOD ISSUES ({len(method_errors)}):")
        issues_found += len(method_errors)
        for error in method_errors:
            print(f"  • {error}")
    
    # Summary
    if issues_found:
        print(f"\n💥 {issues_found} critical issues found that could cause runtime errors!")
        return 1
    elif unused:
        print(f"\n✅ No critical issues found ({len(unused)} unused events)")
        return 0
    else:
        print("\n✅ All audit events properly declared and used!")
        return 0


if __name__ == '__main__':
    sys.exit(main())