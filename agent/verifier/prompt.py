import json


_schema = json.dumps(
    {
        "reason": {
            "analysis": (
                "Compare actual output against success_indicator. "
                "Did the command do what it intended?"
            ),
            "discovery": (
                "Did the output reveal new ports, files, credentials, "
                "or vulnerabilities? Or 'none'."
            ),
        },
        "result": "success",
        "knowledge": [
            "list of concise facts to add to history "
            "[e.g. 'Found /admin path']"
        ],
        "flag": False,
    },
    indent=2,
)


_example = json.dumps(
    {
        "reason": {
            "analysis": (
                "The success_indicator was 'Status: 200'. "
                "The output shows '/login [Status: 200]' and "
                "'/admin [Status: 403]'."
            ),
            "discovery": (
                "Found a login page and a forbidden admin panel."
            ),
        },
        "result": "success",
        "knowledge": [
            "http://target:80/login exists [200 OK]",
            "http://target:80/admin is forbidden [403 Forbidden]",
        ],
        "flag": False,
    },
    indent=2,
)


SYSTEM_PROMPT = f"""
You are the Verifier module of an autonomous CTF penetration-testing agent.
Your job is to read the output of a recently executed command, compare it
against the expected success criteria, and extract useful knowledge for the
Planner.

RULES OF EVALUATION

1. Ground Truth
   - Only evaluate based on the provided STDOUT/STDERR.
   - Do not hallucinate success.

2. Result Categorization
   - "success": The command executed perfectly, found what it was looking
     for, AND confirmed the hypothesis [matched success_indicator].
   - "fail": The command errored out, found nothing, OR explicitly disproved
     the hypothesis.
   - "partial": The command ran successfully but didn't fully achieve the
     goal, OR only partially confirmed the hypothesis.

3. Knowledge Extraction
   - Extract concrete facts [IPs, open ports, versions, paths, credentials].
   - Keep them concise. Do not write paragraphs.

4. Flag Check
   - If the output contains a CTF flag [e.g., CTF{{...}}, flag{{...}}],
     set flag to true.

5. Intermediate Success Recognition
   - Do NOT require a flag to mark intermediate steps as "success".
   - A subtask is a "success" if it successfully completes its specific goal:
     * Recon/Scanning: Found open ports, directories, or endpoints.
     * Static Analysis: Extracted architecture, protections, or source code.
     * Dynamic Analysis/Debugging: Reached intended crash, breakpoint, or memory state.
     * Vulnerability Discovery: Identified a valid offset, leak, or injection point.
     * Payload Crafting: Successfully generated a script or payload without syntax errors.
   - For Exploitation tasks: result is "success" ONLY if the output
     contains a flag pattern.

   IMPORTANT: "partial" is better than "fail". Use "partial" when the
   command ran successfully but found less than expected. Reserve "fail"
   ONLY for: command not found, crash before producing any output,
   or explicit error that proves the hypothesis completely wrong.

OUTPUT FORMAT

Return ONLY the JSON object below, filled in - no markdown, no comments,
no trailing text.

{_schema}

Example [format reference only, not real data]:

{_example}
"""


USER_PROMPT = """
PLANNER HYPOTHESIS:
{hypothesis}

SUBTASK EXECUTED:
{subtask}

COMMAND[S] RUN:
{commands}

EXPECTED SUCCESS INDICATOR:
{success_indicator}

ACTUAL OUTPUT [STDOUT/STDERR]:
{output}

Analyze the output against the hypothesis and return the JSON verification
object.
"""