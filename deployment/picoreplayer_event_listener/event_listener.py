#!/usr/bin/env python3
# piCorePlayer Event Listener Plugin Script
# This script is called by piCorePlayer's event system and invokes Bird.py logic.
# Place this script in the piCorePlayer event plugin directory and configure event actions to call it.

import sys
import os
import subprocess
import json
from typing import List

# Path to bird.py in the deployed location (lowercase matches original source file)
BIRD_PY_PATH = os.path.join(os.path.dirname(__file__), 'bird.py')

def build_args_from_event(raw_args: List[str]) -> List[str]:
    """Translate piCorePlayer event listener arguments into bird.py CLI args.
    Expected usage examples (adjust as needed):
      event_listener.py SONG_START --song tiki
      event_listener.py SONG_STOP
    Returns a list of additional args for bird.py.
    """
    if not raw_args:
        return []
    event_type = raw_args[0].upper()
    rest = raw_args[1:]
    cli_args: List[str] = []
    if event_type == 'SONG_START':
        # Pass through any --song value or assume first arg after event is song name
        if rest:
            if rest[0].startswith('--song'):
                cli_args.extend(rest)
            else:
                # treat first as song name
                cli_args.extend(['--song', rest[0]])
    elif event_type == 'SONG_STOP':
        # For stop we could invoke a cancellation routine if implemented. For now no-op.
        pass
    else:
        # Generic passthrough
        cli_args.extend(rest)
    return cli_args

if __name__ == '__main__':
    raw_args = sys.argv[1:]
    bird_cli_args = build_args_from_event(raw_args)
    cmd = ['python3', BIRD_PY_PATH] + bird_cli_args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print(f"bird.py not found at {BIRD_PY_PATH}. Did you run the setup script?", file=sys.stderr)
        sys.exit(127)
    except Exception as e:
        print(f'Error running bird.py: {e}', file=sys.stderr)
        sys.exit(1)
