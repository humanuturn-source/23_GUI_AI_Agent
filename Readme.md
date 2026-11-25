# Install Instructions - AI GUI Agent

## Step 1: Install Ollama & Pull Local Models

Install Ollama to host your models locally, then pull Google DeepMind’s Gemma 4 (or any preferred multimodal vision model, like LLaVA or MiniCPM).

1.	Install Ollama:
⚬	macOS / Linux: Download from ollama.com or run:

    ```bash
    brew install ollama
    ```
⚬	Windows: Download and run the setup installer from ollama.com.

2.	Pull the Local Gemma 4 & 2 Models:
Open your terminal and run:

    ```bash
    ollama pull gemma4
    ollama pull gemma2

    ```

## Step 2: Create a Python Virtual Environment

Keep your dependencies isolated by creating a clean virtual environment:

    ```bash
    # 1. Navigate to your project folder
    cd ai_app

    # 2. Create the virtual environment
    python3 -m venv venv

    # 3. Activate the virtual environment
    # macOS / Linux:
    source venv/bin/activate

    ```

## Step 3: Install dependencies

    ```text
    ollama>=0.4.0
    pydantic>=2.10.0
    fastapi>=0.115.5
    uvicorn>=0.32.1
    chromadb>=0.5.0
    langgraph>=0.2.0
    langchain-text-splitters>=0.3.0
    playwright>=1.49.0

    ```

    ```bash
    pip install -r requirements.txt
    ```

    ```bash
    pip install python-multipart
    playwright install    
    ```

# 4. Run Open WebUI in Docker connected to host Ollama & FastAPI server

```bash
    docker run -d --name open-webui \
    -p 3000:8080 \
    --add-host=host.docker.internal:host-gateway \
    -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
    -e OPENAI_API_BASE_URL=http://host.docker.internal:8000/v1 \
    -e OPENAI_API_KEY=local-no-key-needed \
    -v open-webui:/app/backend/data \
    ghcr.io/open-webui/open-webui:main

```

## Step 5: Source documents pip 

    Copy source documents and Python scripts from the GitHub repositoey

## Step 6: Load Docuemnts

    Run  ingest_graph.py and load all the source docuemnts


## Step 7: Run Test application

    Run test_invntory_app.py from the commandline

## Step 8: Run server wrapper

    Run server.py from the commandline

## Step 9: Run OpenWebUI as a Docker container 

    Verify Open WebUI in Docker Desktop

## Step 10: Connect Open WebUI to Your Local Agent and give a Prompt

To connect and include your custom serengeti-browser-agent
in Open WebUI, you need to link your running FastAPI wrapper (server.py) as an OpenAI-compatible API connection.

Since Open WebUI is running inside a Docker container and your FastAPI server is running on your host machine, follow these step-by-step instructions to configure it properly:

1. Ensure Your FastAPI Server is Running on the Host

    Open a terminal on your Mac, navigate to your project directory, activate your virtual environment, and start your wrapper server on port 8000:

    ```bash
        python3 serer.py

    ```

    Your server exposes serengeti-browser-agent through the OpenAI-compatible endpoint at http://localhost:8000/v1

2. Configure the Connections Settings in Open WebUI

    a. Open your browser at http://localhost:3000 (where Open WebUI is running).

    b. Click on your Profile icon (bottom left corner) and select Admin Panel (or Settings).

    c. Navigate to Settings -> Connections (or General depending on your Open WebUI version).

    d. Look for the OpenAI API section.

    e. Add a new connection with the following details:
        API Base URL: [http://host.docker.internal:8000/v1](http://host.docker.internal:8000/v1)
        (Note: host.docker.internal allows the Docker container to talk to your host machine's port 8000).
        API Key: not-needed (or any dummy string like 12345).

    f. Click the Save button (or refresh the connection). Open WebUI will automatically query /v1/models and register graphrag-router-agent.

3.  Select and Test Your Agent in Chat

    a. Go back to the main chat screen.

    b. Click the model dropdown selector at the top (as shown in your screenshot).

    c. Choose serengeti-browser-agent.

    d. Type any of your sample prompts.

    e. Example:

    Open http://localhost:5000/inventory, fill out #item_name with "Serengeti Lion Toy" and #quantity with "10", click #submit_btn, verify "Item added successfully!


====
