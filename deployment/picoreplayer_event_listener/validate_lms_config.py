#!/usr/bin/env python3
"""
validate_lms_config.py
Validates and provides detailed diagnostics for lmseventtrigger.json
"""

import json
import os
import sys
from pathlib import Path

def validate_config(config_path):
    """Validate LMS event trigger configuration."""
    errors = []
    warnings = []
    
    print(f"Validating: {config_path}")
    print("=" * 60)
    
    # Check file exists
    if not os.path.exists(config_path):
        errors.append(f"Config file not found: {config_path}")
        return errors, warnings
    
    # Check file readable
    if not os.access(config_path, os.R_OK):
        errors.append(f"Config file not readable: {config_path}")
        return errors, warnings
    
    # Parse JSON
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print("✓ JSON syntax is valid")
    except json.JSONDecodeError as e:
        errors.append(f"JSON syntax error: {e}")
        return errors, warnings
    
    # Validate structure
    if not isinstance(config, dict):
        errors.append("Config must be a JSON object")
        return errors, warnings
    
    # Check enabled
    if "enabled" not in config:
        warnings.append("Missing 'enabled' field (defaults to false)")
    elif config["enabled"] is True:
        print("✓ Plugin is enabled")
    else:
        warnings.append("Plugin is disabled in config")
    
    # Check events
    if "events" not in config:
        errors.append("Missing 'events' array")
        return errors, warnings
    
    events = config["events"]
    if not isinstance(events, list):
        errors.append("'events' must be an array")
        return errors, warnings
    
    print(f"✓ Found {len(events)} event(s)")
    
    # Validate each event
    for i, event in enumerate(events):
        print(f"\n  Event {i+1}:")
        
        if not isinstance(event, dict):
            errors.append(f"  Event {i+1}: must be an object")
            continue
        
        # Check cmd
        if "cmd" not in event:
            errors.append(f"  Event {i+1}: missing 'cmd' field")
        else:
            cmd_path = event["cmd"]
            print(f"    cmd: {cmd_path}")
            
            # Check if script exists (if path is absolute and local)
            if cmd_path.startswith("/") and os.path.exists(cmd_path):
                print(f"    ✓ Command file exists")
                if not os.access(cmd_path, os.X_OK):
                    warnings.append(f"  Event {i+1}: command not executable: {cmd_path}")
                else:
                    print(f"    ✓ Command is executable")
            elif cmd_path.startswith("/"):
                warnings.append(f"  Event {i+1}: command path not found locally (may exist on target): {cmd_path}")
        
        # Check event
        if "event" not in event:
            errors.append(f"  Event {i+1}: missing 'event' field")
        else:
            event_spec = event["event"]
            print(f"    event: {event_spec}")
            
            if not isinstance(event_spec, list):
                errors.append(f"  Event {i+1}: 'event' must be an array")
            else:
                print(f"    ✓ Event has {len(event_spec)} trigger(s)")
                for j, trigger in enumerate(event_spec):
                    if not isinstance(trigger, list):
                        errors.append(f"  Event {i+1}, trigger {j+1}: must be an array")
                    else:
                        print(f"      Trigger {j+1}: {trigger}")
    
    return errors, warnings


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "lmseventtrigger.json"
    
    errors, warnings = validate_config(config_path)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if errors:
        print(f"\n❌ {len(errors)} ERROR(S):")
        for err in errors:
            print(f"  • {err}")
    
    if warnings:
        print(f"\n⚠️  {len(warnings)} WARNING(S):")
        for warn in warnings:
            print(f"  • {warn}")
    
    if not errors and not warnings:
        print("\n✅ Configuration is valid!")
    
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
