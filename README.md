# FuckCTF: LLM Agent and Evaluation Framework for Autonomous CTF Solving

## Introduction

We introduce FuckCTF, a novel Large Language Model (LLM)-based agent capable of autonomously solving Capture The Flag (CTF) challenges. 
FuckCTF's multi-module architecture includes a Planner, Executor, Verifier, Refiner, Summarizer, and Reflector, which enable it to generate commands and process feedback iteratively in an isolated Docker sandbox. It utilizes Retrieval-Augmented Generation (RAG) to search for advanced exploits and optimal algorithms, ensuring it solves challenges without hopelessly brute-forcing everything.

<br>

## Using the repository
- You will have to install Python 3.9+ and Docker (must be running to create the sandbox container)
- Set up your Environment Variables (`.env`)
  - Copy the example environment file to create your own:
    ```bash
    cp .env_example .env
    ```
  - Open the `.env` file and insert your API keys. You will need:
    - **OPENAI_API_KEY / OPENAI_BASE_URL**: Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys) (or your preferred proxy like DeepSeek/OpenRouter).
    - **HF_TOKEN** *(for local models)*: Get your access token from [Hugging Face Settings](https://huggingface.co/settings/tokens).
    - **GITHUB_API_KEY**: Generate a personal access token at [GitHub Developer Settings](https://github.com/settings/tokens).
    - **FIRECRAWL_API_KEY**: Sign up and get your key at [Firecrawl](https://www.firecrawl.dev/).
- Create a workspace for the challenge
  - Create a new directory named `workspace` in the root of the repository.
  - Whenever you have a new challenge with downloadable files (like source code, a zip file, or a compiled binary), place them inside this `workspace/` directory.
  - **⚠️ IMPORTANT:** When moving to a new challenge, clear the `workspace/` directory of old files so the AI doesn't get confused by leftover files from previous runs!
- Configure the challenge parameters
  - Open or create a `config.json` file (you can use one of the files in the `benchmark/` folder as a template).
  - Update the `target` section with the details of your current challenge:
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
- Start the FuckCTF Agent
  - Install the environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use: .\venv\Scripts\activate
    pip install -r requirements.txt
    ```
  - Run the agent with your configuration file:
    ```bash
    python run.py -c config.json -k
    ```
    *(The `-k` flag tells the framework to keep the Docker container running after the challenge ends, which speeds up subsequent runs).*
