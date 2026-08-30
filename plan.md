# 🔧 Implementation Plan — Fix 6 Bugs cho FuckCTF Agent

> Đọc kỹ từng STEP trước khi làm. Mỗi STEP có: mô tả vấn đề → file cần mở → code cần thay → cách kiểm tra.

> [!IMPORTANT]
> **Thứ tự quan trọng!** Làm đúng thứ tự từ Step 1 đến Step 6. Mỗi step fix 1 bug.

---

## ✅ STEP 1 — Fix Bug #3: Verifier Không Biết Thành Công Hay Thất Bại (ĐÃ XỬ LÝ)

**Bug**: Verifier chỉ kiểm tra có flag không. Mọi bước `checksec`, `gdb`, `offset discovery` đều bị mark "fail" vì chưa có flag → Refiner loop mãi.

**File cần mở**: [`agent/verifier/prompt.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\verifier\prompt.py)

### Việc cần làm:

Tìm đoạn code này (dòng 50–88):

```python
SYSTEM_PROMPT = f"""
You are the Verifier module of an autonomous CTF penetration-testing agent.
Your job is to read the output of a recently executed command, compare it
against the expected success criteria, and extract useful knowledge for the
Planner.

RULES OF EVALUATION

1. Ground Truth
...
4. Flag Check
   - If the output contains a CTF flag [e.g., CTF{{...}}, flag{{...}}],
     set flag to true.
```

**Thêm đoạn sau vào CUỐI của `RULES OF EVALUATION` (trước dòng `OUTPUT FORMAT`)**:

```python
5. Tactic-Aware Success (CRITICAL FOR PWN CHALLENGES)
   - For "Static-Analysis" tactic: result is "success" if the output
     contains ANY of: checksec output, file type info, strings output,
     function names from objdump, or binary architecture info.
     Do NOT require a flag to mark this as success.
   - For "Dynamic-Analysis" tactic: result is "success" if gdb/pwndbg
     ran and produced register values, backtrace, or crash information.
     Do NOT require a flag to mark this as success.
   - For "Offset-Discovery" tactic: result is "success" if output
     contains a specific numeric offset value (e.g., "offset = 44",
     "cyclic_find" result, or "EIP offset: 44").
     Do NOT require a flag to mark this as success.
   - For "Protection-Bypass" tactic: result is "success" if a canary
     value, leak address, or bypass technique was identified.
   - For "Payload-Crafting" tactic: result is "success" if a python
     script was written/run WITHOUT SyntaxError or ImportError.
   - For "Exploitation" tactic: result is "success" ONLY if the output
     contains a flag pattern matching 247CTF{{...}} or similar.

   IMPORTANT: "partial" is better than "fail". Use "partial" when the
   command ran successfully but found less than expected. Reserve "fail"
   ONLY for: command not found, crash before producing any output,
   or explicit error that proves the hypothesis completely wrong.
```

### Kết quả sau khi thay:

File `agent/verifier/prompt.py` phần `SYSTEM_PROMPT` sẽ có 5 rules thay vì 4.

### Kiểm tra:

Chạy lại bot. Trong output bạn sẽ thấy:
```
[VERIFIER] Evaluating results...
  ✓ Verifier   : success   ← thay vì "fail" cho bước checksec
```

---

## ✅ STEP 2 — Fix Bug #2: Planner Không Thấy Raw Output (Mất Offset, Address) (ĐÃ XỬ LÝ)

**Bug**: Planner chỉ đọc `attack_tree` đã được tóm tắt. Mất số offset, địa chỉ canary, crash addr.

**Có 3 file cần sửa** (làm tuần tự):

### 2A — Sửa `agent/__init__.py`: Lưu raw output vào history_log

**File cần mở**: [`agent/__init__.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\__init__.py)

Tìm đoạn này (khoảng dòng 730–778):

```python
        latest_step = {
            "subtask": subtask,
            "commands": commands,
            "summary": full_output[:500],
            "verification": verify_json
        }
```

**Không sửa `latest_step`**. Tìm đoạn `self.history_log.append(...)` ở dưới (dòng 755–778):

```python
        self.history_log.append(
            {
                "step_id": step_id,
                "tactic": plan_json.get(
                    "reason",
                    {}
                ).get(
                    "hypothesis",
                    {}
                ).get(
                    "tactic",
                    "Unknown"
                ),
                "plan": subtask,
                "observation": summary_json.get(
                    "summary",
                    ""
                ),
                "result": verify_json.get(
                    "result",
                    "unknown"
                )
            }
        )
```

**Thêm field `raw_output`** vào dict trên:

```python
        self.history_log.append(
            {
                "step_id": step_id,
                "tactic": plan_json.get(
                    "reason",
                    {}
                ).get(
                    "hypothesis",
                    {}
                ).get(
                    "tactic",
                    "Unknown"
                ),
                "plan": subtask,
                "observation": summary_json.get(
                    "summary",
                    ""
                ),
                "result": verify_json.get(
                    "result",
                    "unknown"
                ),
                "raw_output": full_output[:1500]
            }
        )
```

> [!NOTE]
> Chỉ thêm 1 dòng: `"raw_output": full_output[:1500]` — giữ 1500 ký tự đầu tiên của output thô.

### 2B — Sửa `agent/planner/prompt.py`: Hiển thị raw output trong USER_PROMPT

**File cần mở**: [`agent/planner/prompt.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\planner\prompt.py)

Tìm `USER_PROMPT` (dòng 112–130):

```python
USER_PROMPT = """
TARGET:
{target}

TOOLS AVAILABLE TO EXECUTOR:
{tool_list}

ATTACK TREE [validated paths so far]:
{attack_tree}

MEMORY [Vector DB retrieved memories and external knowledge]:
{memory}

HISTORY [JSON list of prior steps]:
{history}

Output exactly one JSON object following the schema in the system prompt.
No markdown, no comments.
"""
```

**Thay bằng** (thêm section `LAST STEP RAW OUTPUT`):

```python
USER_PROMPT = """
TARGET:
{target}

TOOLS AVAILABLE TO EXECUTOR:
{tool_list}

ATTACK TREE [validated paths so far]:
{attack_tree}

LAST STEP RAW OUTPUT [Read carefully for exact numbers, addresses, offsets]:
{last_output}

MEMORY [Vector DB retrieved memories and external knowledge]:
{memory}

HISTORY [JSON list of prior steps]:
{history}

Output exactly one JSON object following the schema in the system prompt.
No markdown, no comments.
"""
```

### 2C — Sửa `agent/planner/engine.py`: Truyền last_output vào prompt

**File cần mở**: [`agent/planner/engine.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\planner\engine.py)

Tìm hàm `plan(...)`:

```python
    def plan(
        self,
        history,
        target,
        attack_tree,
        tool_list,
        playbook,
        memory_context
    ):
```

**Bước 1**: Thêm parameter `last_output=""` vào signature:

```python
    def plan(
        self,
        history,
        target,
        attack_tree,
        tool_list,
        playbook,
        memory_context,
        last_output=""
    ):
```

**Bước 2**: Tìm chỗ format `user_content` (chỗ gọi `USER_PROMPT.format(...)`):

Thêm `last_output=last_output` vào đó. Tìm đoạn như:

```python
        user_content = USER_PROMPT.format(
            target=target,
            tool_list=tool_list_str,
            attack_tree=attack_tree,
            memory=memory_context,
            history=history_str
        )
```

**Sửa thành**:

```python
        user_content = USER_PROMPT.format(
            target=target,
            tool_list=tool_list_str,
            attack_tree=attack_tree,
            last_output=last_output or "No previous command output.",
            memory=memory_context,
            history=history_str
        )
```

### 2D — Sửa `agent/__init__.py`: Truyền raw output khi gọi planner

**Quay lại file** [`agent/__init__.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\__init__.py)

Tìm đoạn gọi `self.planner.plan(...)` (khoảng dòng 241–248):

```python
        plan_result = self.planner.plan(
            history=self.build_history_for_planner(),
            target=target_str,
            attack_tree=tree_str,
            tool_list=self.tool_list,
            playbook=self.active_playbook,
            memory_context=memory_context
        )
```

**Sửa thành** (thêm `last_output`):

```python
        # Lấy raw output của bước cuối cùng trong history_log
        last_raw = ""
        if self.history_log:
            last_raw = self.history_log[-1].get("raw_output_preview", "")

        plan_result = self.planner.plan(
            history=self.build_history_for_planner(),
            target=target_str,
            attack_tree=tree_str,
            tool_list=self.tool_list,
            playbook=self.active_playbook,
            memory_context=memory_context,
            last_output=last_raw
        )
```

---

## ⚡ STEP 3 — Fix Bug #1: Planner Không Biết Binary Là x86, Có Canary

**Bug**: Planner lên kế hoạch chung chung vì không biết architecture và protections của binary.

**File cần mở**: [`agent/planner/prompt.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\planner\prompt.py)

Tìm trong `SYSTEM_PROMPT` phần `4. Tooling`:

```
4. Tooling
   - The Executor initially has these tools available: <TOOL_LIST>
   - You have root privileges in the sandbox. If you need a standard Kali tool
     that is not installed, you CAN propose a subtask to install it
     (e.g., via `apt-get update && apt-get install -y <package>`).
```

**Thêm rule `5.` mới ngay sau phần Tooling** (trước `LOOP DISCIPLINE`):

```
5. PWN Challenge Awareness
   - For pwn/binary challenges, ALWAYS check architecture BEFORE crafting
     exploits:
     * If binary is ELF 32-bit (x86): use 4-byte addresses, p32() in pwntools,
       function arguments go on STACK after return address.
     * If binary is ELF 64-bit (x86-64): use 8-byte addresses, p64() in pwntools,
       function arguments go in registers (RDI, RSI, RDX...).
   - If the attack_tree findings mention "canary" or "stack smashing protection":
     you MUST propose canary brute-force OR canary leak before stack overflow.
   - If PIE is disabled (no-PIE): function addresses are static, use objdump -d
     to find win functions directly.
   - NEVER craft an exploit payload until you have confirmed: (1) binary arch,
     (2) exact overflow offset, (3) canary handling strategy.
```

---

## ⚡ STEP 4 — Fix Bug #4: Refiner Không Biết Gì Về Binary

**Bug**: Refiner không biết offset, arch, protections → đề xuất payload sai.

**Có 2 file cần sửa**:

### 4A — Sửa `agent/refiner/prompt.py`: Thêm `binary_facts` vào USER_PROMPT

**File cần mở**: [`agent/refiner/prompt.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\refiner\prompt.py)

Tìm `USER_PROMPT` (dòng 81–98):

```python
USER_PROMPT = """
TARGET ENVIRONMENT:
{target}

INTENDED SUBTASK:
{subtask}

FAILED COMMAND[S]:
{failed_command}

ERROR OUTPUT:
{error_output}

HISTORY SUMMARY:
{history}

Analyze the error and return the refined command[s] in the JSON format.
"""
```

**Thay bằng**:

```python
USER_PROMPT = """
TARGET ENVIRONMENT:
{target}

BINARY FACTS COLLECTED SO FAR [Use these to avoid wrong assumptions]:
{binary_facts}

INTENDED SUBTASK:
{subtask}

FAILED COMMAND[S]:
{failed_command}

ERROR OUTPUT:
{error_output}

HISTORY SUMMARY:
{history}

Analyze the error and return the refined command[s] in the JSON format.
"""
```

### 4B — Sửa `agent/refiner/engine.py`: Thêm parameter `binary_facts`

**File cần mở**: [`agent/refiner/engine.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\refiner\engine.py)

Tìm hàm `refine(...)` (dòng 28–35):

```python
    def refine(
        self,
        target,
        subtask,
        failed_command,
        error_output,
        history
    ):
```

**Sửa thành** (thêm `binary_facts=""`):

```python
    def refine(
        self,
        target,
        subtask,
        failed_command,
        error_output,
        history,
        binary_facts=""
    ):
```

Tìm chỗ format `user_content` (dòng 50–56):

```python
        user_content = USER_PROMPT.format(
            target=target,
            subtask=subtask,
            failed_command=failed_command_str,
            error_output=error_output,
            history=history_str
        )
```

**Sửa thành**:

```python
        user_content = USER_PROMPT.format(
            target=target,
            binary_facts=binary_facts or "Not yet collected.",
            subtask=subtask,
            failed_command=failed_command_str,
            error_output=error_output,
            history=history_str
        )
```

### 4C — Sửa `agent/__init__.py`: Truyền binary_facts khi gọi refiner

**Quay lại file** [`agent/__init__.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\__init__.py)

Tìm đoạn gọi `self.refiner.refine(...)` (khoảng dòng 572–578):

```python
                refine_result = self.refiner.refine(
                    target=target_str,
                    subtask=subtask,
                    failed_command=commands,
                    error_output=full_output,
                    history=self.compressed_history
                )
```

**Sửa thành**:

```python
                refine_result = self.refiner.refine(
                    target=target_str,
                    subtask=subtask,
                    failed_command=commands,
                    error_output=full_output,
                    history=self.compressed_history,
                    binary_facts="\n".join(
                        self.attack_tree.get("findings", [])
                    )
                )
```

---

## ⚡ STEP 5 — Fix Bug #5: RAG Query Không Match Knowledge Liên Quan

**Bug**: ChromaDB được query bằng generic text từ attack tree → không lấy được chunks về canary bypass cụ thể.

**File cần mở**: [`agent/__init__.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\__init__.py)

Tìm phần `MEMORY RETRIEVAL` (khoảng dòng 180–234):

```python
        # MEMORY RETRIEVAL
        retrieved_memory = []

        try:
            query_text = (
                str(self.attack_tree.get("next", ""))
                or "Initial recon"
            )

            # Query memory collection
            mem_res = self.memory.query(
                query_texts=[query_text],
                n_results=3
            )
```

**Sửa phần tính `query_text`** thành:

```python
        # MEMORY RETRIEVAL
        retrieved_memory = []

        try:
            # Build a richer query using target description + current stage
            # so ChromaDB can find relevant knowledge chunks
            target_desc = (
                target.get("description", "")
                if isinstance(target, dict)
                else str(target)
            )
            current_stage = self.attack_tree.get("stage", "")
            next_tasks = " ".join(
                self.attack_tree.get("next", [])
            ) if isinstance(
                self.attack_tree.get("next", []), list
            ) else str(self.attack_tree.get("next", ""))

            # Combine for a more specific query
            query_text = " ".join(filter(None, [
                target_desc[:200],
                current_stage,
                next_tasks[:200]
            ])) or "binary exploitation pwn"

            # Query memory collection
            mem_res = self.memory.query(
                query_texts=[query_text],
                n_results=3
            )
```

> [!NOTE]
> Thay đổi này giúp query ChromaDB với text cụ thể hơn: bao gồm mô tả challenge (e.g., "cookie monster canary") + stage hiện tại + việc cần làm tiếp. Kết quả: chunks về canary bypass sẽ được pull ra đúng lúc.

---

## ⚡ STEP 6 — Fix Bug #6: Summarizer Phải Lưu Technical Facts (Offset, Arch)

**Bug**: Summarizer tóm tắt "Found overflow" nhưng mất số offset cụ thể. Attack tree `findings` chỉ có text prose, không có structured facts.

**Có 2 file cần sửa**:

### 6A — Sửa `agent/summarizer/prompt.py`: Yêu cầu extract technical numbers

**File cần mở**: [`agent/summarizer/prompt.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\summarizer\prompt.py)

Tìm phần `RULES OF SUMMARIZATION` (dòng 75–106):

```
RULES OF SUMMARIZATION

1. Attack Tree Format
   - Maintain a highly structured JSON object tracking the state of the attack.
   - Keep findings concise and actionable.
   - Update `done` and `failed` lists to prevent the Planner from repeating
     mistakes.

2. Summary Constraint
   - The `summary` field should be a very brief 1-2 sentence description of
     what happened. It will be added to the history log.

3. No Hallucinations
   - Only add information to the Attack Tree that has been explicitly
     confirmed by the latest step or was already in the previous tree.
```

**Thêm Rule 4** ngay sau Rule 3:

```
4. Technical Fact Preservation (CRITICAL)
   - When adding to `findings`, you MUST preserve EXACT technical values.
     Do NOT summarize them. Examples:
     * WRONG: "Found the overflow offset"
     * CORRECT: "overflow_offset=44"
     * WRONG: "Binary has stack protection"
     * CORRECT: "checksec: canary=yes, NX=yes, PIE=no, RELRO=partial"
     * WRONG: "Found a win function"
     * CORRECT: "win_function=0x08049236 (from objdump)"
   - For pwn challenges, `findings` MUST include these when discovered:
     * Binary architecture: "arch=ELF32" or "arch=ELF64"
     * Protections: "canary=yes/no, NX=yes/no, PIE=yes/no"
     * Overflow offset: "offset=<exact number>"
     * Win function or libc gadget addresses if found
   - These exact facts will be passed to the Refiner to avoid wrong payloads.
```

### 6B — Thêm `required_data` field vào attack tree schema

Trong cùng file `agent/summarizer/prompt.py`, tìm `_schema` (dòng 4–38):

```python
_schema = json.dumps(
    {
        ...
        "attack_tree": {
            "stage": ...,
            "done": [...],
            "findings": [...],
            "next": [...],
            "failed": [...],
        },
        ...
    },
    ...
)
```

**Thêm field `required_data`** vào `attack_tree` trong schema:

```python
_schema = json.dumps(
    {
        "reason": {
            "analysis": (
                "Identify key facts from the latest step and how they "
                "affect the attack tree"
            ),
        },
        "attack_tree": {
            "stage": (
                "The current stage of the attack "
                "(e.g. reconnaissance, binary_analysis, "
                "vulnerability_discovery, exploit)"
            ),
            "done": [
                "List of subtasks that have been successfully completed"
            ],
            "findings": [
                "List of EXACT technical facts: arch=ELF32, offset=44, "
                "canary=yes, win=0x08049236, etc."
            ],
            "required_data": {
                "arch": "ELF32 or ELF64 — fill when known",
                "offset": "exact number or null",
                "canary": "yes/no or null",
                "nx": "yes/no or null",
                "pie": "yes/no or null",
                "win_function": "address or null"
            },
            "next": [
                "List of prioritized subtasks to try next"
            ],
            "failed": [
                "List of subtasks or approaches that failed "
                "and should not be retried"
            ],
        },
        "summary": (
            "A 1-2 sentence summary of what was achieved in this step "
            "to be appended to the history."
        ),
    },
    indent=2,
)
```

---

## ✅ Kiểm Tra Sau Khi Fix Xong

### Chạy lại bot:

```powershell
python run.py -c config.json -k
```

### Dấu hiệu các bug đã được fix:

| Bug đã fix | Dấu hiệu trong output |
|---|---|
| Bug #3 Verifier | `✓ Verifier   : success` sau bước `checksec` |
| Bug #2 Raw output | Planner mention offset numbers cụ thể trong reasoning |
| Bug #1 Binary context | Planner nói "x86 32-bit" hoặc "p32()" trong subtask |
| Bug #4 Refiner facts | Refiner không propose x64 payload khi binary là x86 |
| Bug #5 RAG query | `Memory: X chunks injected` tăng lên (không còn 0) |
| Bug #6 Summarizer | `attack_tree.findings` chứa `"offset=44"` thay vì prose |

### Nếu vẫn không chạy sau khi fix:

1. Kiểm tra có lỗi Python syntax không: `python -c "import agent"`
2. Nếu Verifier vẫn fail: đọc log `[VERIFIER] Evaluating...` và xem raw output có gì
3. Nếu RAG vẫn 0 chunks: kiểm tra `GITHUB_API_KEY` đã set chưa

---

## 📌 Tóm Tắt Thay Đổi Theo File

| File | Loại thay đổi | Step |
|---|---|---|
| [`agent/verifier/prompt.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\verifier\prompt.py) | Thêm Rule 5 (tactic-aware success) | Step 1 |
| [`agent/__init__.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\__init__.py) | Thêm `raw_output_preview` vào history_log | Step 2A |
| [`agent/planner/prompt.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\planner\prompt.py) | Thêm `{last_output}` vào USER_PROMPT | Step 2B |
| [`agent/planner/engine.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\planner\engine.py) | Thêm param `last_output` vào `plan()` | Step 2C |
| [`agent/__init__.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\__init__.py) | Truyền `last_raw` khi gọi `planner.plan()` | Step 2D |
| [`agent/planner/prompt.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\planner\prompt.py) | Thêm Rule 5 (PWN awareness) | Step 3 |
| [`agent/refiner/prompt.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\refiner\prompt.py) | Thêm `{binary_facts}` vào USER_PROMPT | Step 4A |
| [`agent/refiner/engine.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\refiner\engine.py) | Thêm param `binary_facts` vào `refine()` | Step 4B |
| [`agent/__init__.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\__init__.py) | Truyền `binary_facts` khi gọi `refiner.refine()` | Step 4C |
| [`agent/__init__.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\__init__.py) | Fix `query_text` để RAG query specific hơn | Step 5 |
| [`agent/summarizer/prompt.py`](file:///c:\Users\ASUS\Documents\FuckCTF\agent\summarizer\prompt.py) | Thêm Rule 4 + `required_data` vào schema | Step 6 |
