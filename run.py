import argparse
import json
import sys

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import dotenv
from agent import Orchestrator
from sandbox import init
import time
import re
from cli.run import header, footer, timeout, crashes, noflag, stop

# Load environment
dotenv.load_dotenv()

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', required=True, help='Path to config JSON')
parser.add_argument('-k', '--keep-running', action='store_true')
args = parser.parse_args()

# Load configuration
with open(args.config) as f:
    config = json.load(f)

# Initialize sandbox
container = init(config=config)

# Initialize agent
agent = Orchestrator(config=config, container=container)

# Setup config
target = config["target"]
target["flag"] = config.get("flag", "")
timeout_minutes = config.get("timeout", 15) 
timeout_seconds = timeout_minutes * 60
start_time = time.time()
step = 0

# Start script
header(target, timeout_minutes)

crash_count = 0
false_done = 0

# Start loop
while True:
    elapsed = time.time() - start_time
    remaining = timeout_seconds - elapsed

    # Check timeout
    if elapsed > timeout_seconds:
        timeout(timeout_minutes)
        break
    
    try:
        # Execute agent
        summary, exec_json = agent.execute(
            target=target,
            sandbox=container,
            time_left=remaining
        )
        crash_count = 0

        # Check flag
        if "captured" in exec_json:
            elapsed = time.time() - start_time
            footer(exec_json["captured"], elapsed)
            break
            
        if summary == "Goal Achieved":
            false_done += 1
            if false_done >= 3:
                elapsed = time.time() - start_time
                noflag()
                break
            agent.warning("SYSTEM: No flag! Please check your solver logic!")
        else:
            false_done = 0

    # Handle interrupt
    except KeyboardInterrupt:
        stop()
        break

    # Handle error
    except Exception:
        import traceback
        traceback.print_exc()
        crash_count += 1
        if crash_count >= 5:
            crashes(crash_count)
            break
        time.sleep(min(2 ** crash_count, 30))
        continue

# Stop sandbox
if not args.keep_running:
    container.stop()