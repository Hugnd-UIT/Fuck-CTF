# F*ck CTF 🚩🤖

An autonomous, LLM-powered AI agent designed to automatically solve Capture The Flag (CTF) challenges. 

F*ck CTF spins up an isolated Docker sandbox, analyzes the challenge (binary, source code, or black-box network service), and dynamically plans its attacks. It utilizes **Retrieval-Augmented Generation (RAG)** to search for advanced exploits and optimal algorithms, ensuring it solves challenges without hopelessly brute-forcing everything.

## ✨ Features
- **Isolated Sandbox Execution:** All agent operations and attack scripts are run safely inside a Kali Linux Docker container.
- **RAG-Enabled Tactics:** Automatically searches the web (via DuckDuckGo and Firecrawl) for vulnerability classes, mathematical shortcuts, and CTF writeups to build budget-optimal exploits.
- **Specialized Playbooks:** Built-in strategies tailored for `pwn`, `crypto`, and `reverse` challenges.
- **Stateful Intelligence:** Remembers what it has done, detects when a server resets its connection, and adjusts its attack tree dynamically.

---

## 🛠️ Prerequisites
- **Python 3.9+**
- **Docker** (must be running to create the sandbox container)
- API keys for your preferred LLM providers (e.g., DeepSeek, OpenAI, Anthropic, Gemini).
- *(Optional)* [Firecrawl](https://firecrawl.dev/) API Key for advanced web scraping.

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/fuck-ctf.git
   cd fuck-ctf
   ```

2. **Set up the virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/Mac:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your API keys:**
   Copy the example environment file and add your keys:
   ```bash
   cp .env_example .env
   ```
   Open `.env` and fill in your API keys (e.g., `DEEPSEEK_API_KEY`, `FIRECRAWL_API_KEY`, etc.).

---

## 🎮 Usage

### 1. Prepare the Challenge
Whenever you have a new challenge with downloadable files (like source code or a compiled binary), place them inside the `workspace/` directory.

> **⚠️ IMPORTANT:** When moving to a new challenge, **clear the `workspace/` directory** of old files so the AI doesn't get confused by leftover files from previous runs!

### 2. Update the Configuration
Open `config.json` and update the `target` section with the details of your current challenge:

```json
"target": {
    "category": "crypto",
    "desc": "Alice and Bob are using legacy codebases and need to negotiate parameters...",
    "dir": "/data",
    "host": "socket.cryptohack.org",
    "port": 13379
}
```
*Note: The `workspace/` folder on your machine is automatically mounted to `/data` inside the Docker container.*

### 3. Run the Agent
Execute the agent using the runner script:

```bash
python run.py -c config.json -k
```
*(The `-k` flag tells the framework to keep the Docker container running after the challenge ends, which speeds up subsequent runs).*

Sit back and watch the AI plan its attack, write scripts, interact with the target, and capture the flag!

---

## 🧠 How it works

The framework is driven by a multi-agent architecture:
- **Planner:** Decides the next logical step based on the challenge category and current progress.
- **Executor:** Translates the plan into concrete bash/python commands.
- **Sandbox:** A sandboxed `kalilinux/kali-rolling` container that executes the commands and captures the standard output.
- **Verifier & Summarizer:** Analyzes the output, determines if the step succeeded, and updates the global memory (Attack Tree) to guide the next move.
