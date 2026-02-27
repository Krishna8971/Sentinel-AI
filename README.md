# Sentinel AI

Sentinel AI is a multi-agent continuous security platform designed to natively model backend authorization logic as an active system. It prevents BOLA, privilege escalation, and refactor-induced permission drift using context-aware AI models rather than simplistic pattern scaling.

This repository powers the Sentinel AI MVP (Minimum Viable Product).

## Platform Components

1.  **AI Consensus Engine (Worker/Runner)**:
    Extracted Python code structures are sent into local AI inference models. It connects to **External LM Studio Instances** running **Qwen 2.5 Coder 7B and Mistral 7B in parallel**. A Judge agent reviews their responses and creates a definitive vulnerability recommendation.

### The 6 Docker Containers

When you run `docker-compose up -d --build`, Sentinel AI launches a specialized microservices architecture consisting of exactly 6 containers:

**Infrastructure:**
1. **`sentinel_postgres`**: Stores the historical scan results, computed Auth Integrity Scores, and application state.
2. **`sentinel_redis`**: Message broker handling the queue for asynchronous Celery tasks between the backend and worker.
3. **`sentinel_neo4j`**: Graph database dynamically mapping out the `Role` → `Route` → `Resource` relationships extracted from the code.

**Core Application:**
4. **`sentinel_backend`**: The Python FastAPI service. Listens for external events (like GitHub PR webhooks), serves the API to the dashboard, and orchestrates scans.
5. **`sentinel_worker`**: The Python Celery service. Does the heavy lifting of AST parsing the target source code, extracting routes, and communicating with the external LM Studio nodes.
6. **`sentinel_frontend`**: The UI React Dashboard served to the user on port 80 to visualize the Auth integrity.

## Technology Stack

### Services & Logic
*   **Backend Validation API**: Python (FastAPI)
*   **Background Jobs**: Celery + Redis
*   **LLM Inference API**: OpenAI-compatible Endpoints (provided by LM Studio)

### Databases
*   **Relational**: PostgreSQL 15
*   **Graph Model**: Neo4j 5

### Frontend UI
*   **Architecture**: React + Vite + TypeScript
*   **Styling**: TailwindCSS
*   **Icons**: Lucide React

---

## 🚀 How to Run the Project Locally

The entire core architecture is containerized and orchestrated via `docker-compose`. 

### Prerequisites
- Docker & Docker Compose installed and running on your host machine.
- **LM Studio** installed on your host (or network) running two distinct Local Servers.

### 1. Configure LM Studio Inference
Sentinel AI expects two API endpoints that follow the OpenAI `/v1/chat/completions` schema:
1. Open LM Studio and load the **Mistral 7B** model. Start a local server on port `1234`.
2. Open another instance of LM Studio (or a separate machine) and load the **Qwen 2.5 Coder 7B** model. Start a local server on port `1235`.

*Note: If you run LM Studio on a different machine than docker, update the `MISTRAL_API_BASE_URL` and `QWEN_API_BASE_URL` inside the `docker-compose.yml` file to exactly match those IP addresses.*

### 2. Build and Start all Services
In your terminal, navigate to the root directory `Sentinal AI` (where `docker-compose.yml` lives) and run:
```bash
docker-compose up -d --build
```

**What happens during the build?**
- It will pull the base images for PostgreSQL, Redis, and Neo4j.
- It will build the `backend/Dockerfile` and `worker/Dockerfile` Python environments.
- It will build the `frontend/Dockerfile` React dashboard.

### 3. Verify Services
Once the containers are up, use `docker ps` to verify the 6 containers are running (`sentinel_frontend`, `sentinel_backend`, `sentinel_worker`, PostgreSQL, Redis, Neo4j).

### 4. Access the Application
- **Dashboard UI**: Navigate your browser to [http://localhost](http://localhost) (React Dashboard via Nginx port 80).
- **Backend API**: Navigate your browser to [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI for the Webhook receiver).
- **Neo4j Browser**: Navigate your browser to [http://localhost:7474](http://localhost:7474)

---

## Modifying the App

- **Frontend**: The React source files live in `/frontend/src`.
- **Backend API**: The FastAPI source files and webhooks live in `/backend/app`.
- **Worker & Intelligence**: The core AST parsing and AI Consensus engine live in `/worker`. Changes here require rebuilding the container (e.g., `docker-compose build worker && docker-compose up -d worker`).
