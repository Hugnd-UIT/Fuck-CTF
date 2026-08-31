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
from timeline import print_header, print_footer, console, print_line

FLAG = re.compile(r"[A-Za-z0-9_]{0,10}CTF\{[^}\s]{1,200}\}")

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

target = config["target"]
target["flag"] = config.get("flag", "247CTF{")
timeout_minutes = config.get("timeout", 15) 
timeout_seconds = timeout_minutes * 60
start_time = time.time()
step = 0

print_header(target, timeout_minutes)

consecutive_crashes = 0
MAX_CONSECUTIVE_CRASHES = 5

while True:
    elapsed = time.time() - start_time
    remaining = timeout_seconds - elapsed

    if elapsed > timeout_seconds:
        print_line(f"└─ 🛑 TIMEOUT: Reached {timeout_minutes} minutes.", color="red")
        break
    
    try:
        summary, exec_json = agent.execute(
            target=target,
            sandbox=container,
            time_left=remaining
        )
        consecutive_crashes = 0

        if summary == "Goal Achieved":
            elapsed = time.time() - start_time
            break

    except KeyboardInterrupt:
        print_line("└─ 🛑 STOPPED BY USER", color="red")
        break

    except Exception:
        import traceback
        traceback.print_exc()
        consecutive_crashes += 1
        if consecutive_crashes >= MAX_CONSECUTIVE_CRASHES:
            print_line(f"└─ 🛑 ABORTED: {consecutive_crashes} consecutive crashes.", color="red")
            break
        time.sleep(min(2 ** consecutive_crashes, 30))
        continue

    # Check for flag
    found = FLAG.search(summary)
    if found:
        elapsed = time.time() - start_time
        print_footer(found.group(0), elapsed)
        break

# Stop sandbox if needed
if not args.keep_running:
    container.stop()