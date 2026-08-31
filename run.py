import argparse
import json
import dotenv
from agent import Orchestrator
from sandbox import init
import time
import re

FLAG_REGEX = re.compile(r"[A-Za-z0-9_]{0,10}CTF\{[^}\s]{1,200}\}")

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

display = (
    f"\n"
    f"  Category      : {target.get('category', '-')}\n"
    f"  Description   : {target.get('desc', '-')}\n"
    f"  Server        : {target.get('server', '-')}\n"
    f"  Directory     : {target.get('dir', '-')}\n"
    f"  Flag          : {target['flag']}"
)

print()
print("╭──────────────────────────────────────────────────────────────╮")
print("│                     F*ck Capture The Flag                    │")
print("╰──────────────────────────────────────────────────────────────╯")
print(display)
print(f"\n  Timeout   : {timeout_minutes} minutes")
print()
print("────────────────────────────────────────────────────────────────")

consecutive_crashes = 0
MAX_CONSECUTIVE_CRASHES = 5

while True:
    elapsed = time.time() - start_time
    remaining = timeout_seconds - elapsed

    if elapsed > timeout_seconds:
        print()
        print("  ✗ TIMEOUT")
        print(f"    Reached {timeout_minutes} minutes.")
        break

    step += 1

    print()
    print("────────────────────────────────────────────────────────────────")
    print(
        f"  STEP {step:02d}"
        f"  •  {int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
    )
    print("────────────────────────────────────────────────────────────────")

    try:
        summary, exec_json = agent.execute(
            target=target,
            sandbox=container,
            time_left=remaining
        )
        consecutive_crashes = 0

        if summary == "Goal Achieved":
            elapsed = time.time() - start_time

            print()
            print("  ✓ GOAL ACHIEVED")
            print()
            print(f"  {exec_json}")
            print()
            print(
                f"  Completed in {step} steps"
                f"  •  {int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
            )
            break

        print(f"  > {summary}")

    except KeyboardInterrupt:
        print()
        print("  ✗ STOPPED BY USER")
        break

    except Exception:
        import traceback
        traceback.print_exc()
        consecutive_crashes += 1
        if consecutive_crashes >= MAX_CONSECUTIVE_CRASHES:
            print(f"\n  ✗ ABORTED: {consecutive_crashes} consecutive crashes. Check API keys, etc.")
            break
        time.sleep(min(2 ** consecutive_crashes, 30))
        continue

    # Check for flag
    found = FLAG_REGEX.search(summary)
    if found:
        elapsed = time.time() - start_time

        print()
        print("════════════════════════════════════════════════════════════════")
        print("  ✓ FLAG FOUND")
        print("════════════════════════════════════════════════════════════════")
        print()
        print(f"  {found.group(0)}")
        print()
        print(
            f"  Completed in {step} steps"
            f"  •  {int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
        )
        break

# Stop sandbox if needed
if not args.keep_running:
    container.stop()