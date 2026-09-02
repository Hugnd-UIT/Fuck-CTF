<div align="center">

<pre>
╔══════════════════════════════════════════════════════════════════════════════════╗
║                                                                                  ║
║          ███████╗██╗   ██╗ ██████╗██╗  ██╗     ██████╗████████╗███████╗          ║
║          ██╔════╝██║   ██║██╔════╝██║ ██╔╝    ██╔════╝╚══██╔══╝██╔════╝          ║
║          █████╗  ██║   ██║██║     █████╔╝     ██║        ██║   █████╗            ║
║          ██╔══╝  ██║   ██║██║     ██╔═██╗     ██║        ██║   ██╔══╝            ║
║          ██║     ╚██████╔╝╚██████╗██║  ██╗    ╚██████╗   ██║   ██║               ║
║          ╚═╝      ╚═════╝  ╚═════╝╚═╝  ╚═╝     ╚═════╝   ╚═╝   ╚═╝               ║
║                                                                                  ║
╚══════════════════════════════════════════════════════════════════════════════════╝
</pre>

### Fuck CTF
**An autonomous LLM agent that solves CTF challenges end to end**

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-required-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?logo=github&logoColor=white)](https://github.com/Hugnd-UIT)
[![Firecrawl](https://img.shields.io/badge/Firecrawl-FF5C00?logo=firefox&logoColor=white)](https://www.firecrawl.dev/)
[![License](https://img.shields.io/badge/License-AGPLv3-blue)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen)](#)

</div>

<br>

## 📌 Introduction

**Fuck CTF** is an autonomous LLM-based agent that solves Capture The Flag challenges from start to finish — reading the challenge description, working the problem, and submitting the flag — without human intervention.

The framework orchestrates six specialized AI modules in a closed loop:

> **Planner → Executor → Verifier → Refiner → Summarizer → Reflector**

It dynamically switches between reasoning, web searching, sandboxed code execution, output verification, iterative self-correction, and high-level strategy reflection until the flag is captured.

<br>

## 🧩 Core Capabilities

| Module | Role |
|:---|:---|
| 🐳 Docker | Provides a disposable, isolated environment to safely interact with targets |
| 🧠 Planner | Analyzes the challenge and decomposes it into a prioritized Attack tree of subtasks |
| 🛠️ Executor | Generates and runs terminal commands, compiled binaries, and Python scripts |
| 🔍 Verifier | Evaluates raw command output against the Planner's hypothesis to classify success or failure |
| ♻️ Refiner | Diagnoses errors and rewrites broken commands or scripts to fix failures iteratively |
| 📊 Summarizer | Distills execution logs into structured observations and updates the Attack tree |
| 🪞 Reflector | Intervenes when the agent is stuck for multiple cycles to backtrack and rethink strategy |
| 🌐 RAG | Searches GitHub repos and web pages via Firecrawl when the agent hits an unfamiliar vulnerability |

<br>

## 🏴 Supported Categories
 
| Category | Description |
|:---|:---|
| 🔐 Crypto | Breaking or exploiting classical and modern cryptographic schemes |
| ⚙️ Reverse | Disassembling and analyzing binaries to recover logic or hidden data |
| 💥 Pwn | Exploiting memory corruption and binary vulnerabilities to gain control |
| 🕵️ Forensics | Digging through files, memory dumps, and network captures for hidden clues |
 
<br>

## 📂 Repo Structure

```text
.
├── agent/               Core orchestrator loop and all agent modules
│   ├── planner/         Planner — subtask generation and Attack Tree management
│   ├── executor/        Executor — command generation
│   ├── verifier/        Verifier — result evaluation
│   ├── refiner/         Refiner — error correction
│   ├── summarizer/      Summarizer — observation synthesis
│   ├── reflector/       Reflector — strategy backtracking
│   └── core/            Memory via ChromaDB, state, and shared utilities
├── benchmark/           Challenge JSON configs organized by platform and category
├── cli/                 Terminal UI rendering — ASCII art, panels, progress
├── db/                  Persistent ChromaDB vector store for RAG context
├── docs/                Documentation
├── rag/                 Retrieval-Augmented Generation — GitHub + Firecrawl
├── workspace/           Place challenge files here — mounted to /data in Docker
├── config.example.json  Config template
├── run.py               Main entry point
└── sandbox.py           Docker sandbox lifecycle manager
```

<br>

## ⚙️ Workflow

```mermaid
graph TD
    classDef start_end fill:#f8d7da,stroke:#f5c6cb,stroke-width:2px,color:#721c24,shape:circle;
    classDef action fill:#fff3cd,stroke:#ffeeba,stroke-width:2px,color:#856404;
    classDef sandbox fill:#d4edda,stroke:#c3e6cb,stroke-width:2px,color:#155724;
    classDef db fill:#e2e3e5,stroke:#d6d8db,stroke-width:2px,color:#383d41;
    classDef decision fill:#cce5ff,stroke:#b8daff,stroke-width:2px,color:#004085;

    Start((🏁 Start — Load json)):::start_end

    DB[(Vector database — Query context)]:::db
    Plan[📝 Planner — Analyze and plan]:::action

    CheckGoal{Goal<br/>achieved?}:::decision
    EndGoal((🚩 Captured the flag!)):::start_end
    CheckRAG1{RAG?}:::decision

    RAG[🌐 RAG — Search and scrape web with GitHub and Firecrawl]:::action

    Exec[🛠️ Executor — Generate and run commands]:::action

    CheckRAG2{RAG?}:::decision
    Docker[🐳 Docker]:::sandbox

    Verif[🔍 Verifier — Evaluate results]:::action

    CheckRAG3{Needs<br/>RAG?}:::decision
    CheckFlag{Goal<br/>achieved?}:::decision

    EndFlag((🚩 Captured the flag!)):::start_end
    CheckFail{Result<br/>failed?}:::decision

    Ref[♻️ Refiner — Fix and rerun commands]:::action

    Sum[📊 Summarizer — Update attack tree and history]:::db

    Next((🔄 Loop)):::start_end

    Start ==> DB
    DB ==> Plan

    Plan ==> CheckGoal
    CheckGoal == Yes ==> EndGoal
    CheckGoal == No ==> CheckRAG1

    CheckRAG1 == Yes ==> RAG
    CheckRAG1 == No ==> Exec

    Exec ==> CheckRAG2
    CheckRAG2 == Yes ==> RAG
    CheckRAG2 == No ==> Docker

    Docker ==> Verif

    Verif ==> CheckRAG3
    CheckRAG3 == Yes ==> RAG
    CheckRAG3 == No ==> CheckFlag

    CheckFlag == Yes ==> EndFlag
    CheckFlag == No ==> CheckFail

    CheckFail == Yes ==> Ref
    Ref ==> Docker

    CheckFail == No ==> Sum

    RAG ==> Next
    Sum ==> Next
    Next -.->|Loop back| DB

    Plan -.->|Hypothesis| Verif
    Docker -.-> Verif

    Docker -.->|Error logs| Ref

    Verif -.->|Status| Sum
    Docker -.->|Logs| Sum

    RAG -.->|Web data| DB
```

<br>

## 🚀 Installation

> **Requirements:** Python 3.9+, Docker running

**1. Clone the repository**

```bash
git clone https://github.com/Hugnd-UIT/Fuck-CTF.git
cd Fuck-CTF
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
.\venv\Scripts\activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

<br>

## 🔑 Setup

Copy the environment file and fill in your API keys:

```bash
cp .env_example .env
```

| Variable | Description | Required |
|:---|:---|:---:|
| `OPENAI_API_KEY` | OpenAI key, or an OpenRouter / DeepSeek proxy key | ✅ |
| `OPENAI_BASE_URL` | API base URL, needed for proxy providers | ✅ |
| `GITHUB_API_KEY` | GitHub Personal Access Token for RAG search | ✅ |
| `FIRECRAWL_API_KEY` | Firecrawl API key for web scraping | ✅ |
| `HF_TOKEN` | Hugging Face token, local models only | Optional |
| `CUDA_VISIBLE_DEVICES` | GPU IDs for local model inference, e.g. `0,1` | Optional |

<br>

## 🎯 Run a challenge

**1. Drop challenge files into `workspace/`**

If the challenge provides downloadable files — source code, pcap, zip, binary — place them in the `workspace/` directory. This folder is automatically mounted to `/data` inside the Docker container.

> [!WARNING]
> Always **clear `workspace/`** before starting a new challenge. Leftover files from previous runs will confuse the agent.

**2. Create a `config.json`**

Use any file in `benchmark/` as a template, or create one from scratch:

```json
{
    "planner": {
        "model": "openai/gpt-4o",
        "local": false,
        "temperature": 0.7,
        "top": 0.9,
        "sample": true,
        "tokens": 4096
    },
    "executor": {
        "model": "openai/gpt-4o-mini",
        "local": false,
        "temperature": 0.2,
        "top": 1.0,
        "sample": false,
        "tokens": 4096
    },
    "verifier": {
        "model": "openai/gpt-4o-mini",
        "local": false,
        "temperature": 0.1,
        "top": 1.0,
        "sample": false,
        "tokens": 4096
    },
    "refiner": {
        "model": "openai/gpt-4o-mini",
        "local": false,
        "temperature": 0.2,
        "top": 1.0,
        "sample": false,
        "tokens": 4096
    },
    "summarizer": {
        "model": "openai/gpt-4o",
        "local": false,
        "temperature": 0.3,
        "top": 1.0,
        "sample": false,
        "tokens": 4096
    },
    "reflector": {
        "model": "openai/gpt-4o",
        "local": false,
        "temperature": 0.7,
        "top": 1.0,
        "sample": false,
        "tokens": 4096
    },
    "sandbox": "ctf",
    "timeout": 15,
    "limit": 2000,
    "cmd_time": 30,
    "max_time": 600,
    "flag": "flag{FORMAT}",
    "target": {
        "category": "challenge-category",
        "desc": "Description of the challenge...",
        "dir": "/data",
        "host": "target-host-or-ip",
        "port": 1337
    }
}
```

**Config field reference:**

| Field | Type | Description |
|:---|:---|:---|
| `sandbox` | string | Docker image tag for the ephemeral sandbox |
| `timeout` | int, minutes | Total time limit for the entire agent run |
| `cmd_time` | int, seconds | Max execution time for a single command in sandbox |
| `max_time` | int, seconds | Max cumulative sandbox runtime before forced reflection |
| `limit` | int, chars | Max length for truncating long command outputs |
| `flag` | string | Expected flag format to help Verifier detect success |
| `target.dir` | string | Path inside Docker where `workspace/` is mounted — default `/data` |
| `target.host` | string | Challenge host or URL |
| `target.port` | int | Challenge port — leave `""` for web-only challenges |

**3. Run**

```bash
python run.py -c config.json -k
```

The `-k` flag keeps the Docker container alive between runs, significantly speeding up subsequent attempts on the same challenge.

<br>

## 👤 Author

Made by **Hugnd-UIT**

[![GitHub](https://img.shields.io/badge/GitHub-Hugnd--UIT-181717?logo=github&logoColor=white)](https://github.com/Hugnd-UIT)

<br>

## 📜 License

This project is licensed under the **GNU Affero General Public License v3.0**. See [LICENSE](LICENSE) for the full text.

<br>

<div align="center">

© 2026 Hugnd-UIT — All rights reserved under AGPLv3

</div>
