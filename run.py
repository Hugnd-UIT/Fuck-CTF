import argparse
import json
import dotenv
from agent import Orchestrator
from sandbox import init
import re

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
flag_pattern = config.get("flag", "247CTF{")
import time
timeout_minutes = config.get("timeout", 15)
timeout_seconds = timeout_minutes * 60
start_time = time.time()
step = 0

print(f"Target: \n{json.dumps(target, indent=2)}")
print(f"Flag  : {flag_pattern}")
print(f"Timeout: {timeout_minutes} minutes\n")

# Start hacking loop
while True:
    elapsed = time.time() - start_time
    if elapsed > timeout_seconds:
        print(f"\nTime is up! Reached {timeout_minutes} minutes timeout.")
        break
        
    step += 1
    print(f"\n=======================================================\n[ Elapsed: {int(elapsed//60)}m {int(elapsed%60)}s ]")
    
    try:
        summary, exec_json = agent.execute_step(target=target, sandbox=container)
        
        if summary == "Goal Achieved":
            print("\n>>> AGENT DECLARED FINISHED <<<")
            print(exec_json)
            break
            
        print(f"> {summary}")
        
    except KeyboardInterrupt:
        print("\nStopped by user")
        break
    except Exception as e:
        import traceback
        traceback.print_exc()
        continue

    # Check for flag
    if flag_pattern in summary or "CTF{" in summary:
        print(f"\n[!] FLAG FOUND in {step} steps! <<<")
        break

# Stop sandbox if needed
if not args.keep_running:
    container.stop()