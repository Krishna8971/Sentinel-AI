# Sentinel AI Platform: Usage & Testing Guide

This guide explains how to actively test and use the Sentinel AI platform now that the architecture is running.

## 1. Starting the Environment

Before proceeding, ensure your environment is running:

1. **Start LM Studio**: 
   - Start **Mistral 7B** on port `1234`
   - Start **Qwen 2.5 Coder 7B** on port `1235`
   - Ensure the URLs in your `.env` file match these instances.
2. **Start the Sentinel Backend**:
   - Run `docker-compose up -d --build` from the project root.
   - Wait for the 6 containers (`sentinel_frontend`, `sentinel_backend`, `sentinel_worker`, PostgreSQL, Redis, Neo4j) to become healthy.

## 2. Platform Access Points

- **The Continuous Validation Dashboard**: http://localhost
  Use this to view the Auth Graph and recent findings visually.
- **The Graph Database (Neo4j)**: http://localhost:7474
  Use this to query the Raw Authorization Graph (Login: `neo4j` / Password: `sentinel_neo4j_password`).
- **The API / Webhook Endpoint**: http://localhost:8000/docs
  Use this to manually trigger scans or view the API spec.

---

## 3. Real-World Use Case: Detecting "BOLA" (Broken Object Level Authorization)

To truly test Sentinel AI, we need to simulate what happens when a developer accidentally introduces a vulnerability in a Python FastAPI application.

### The Scenario
Imagine a developer is working on a PR for an e-commerce backend. They add a new endpoint to fetch order details:

```python
# The vulnerable code being committed:
@app.get("/api/orders/{order_id}")
async def get_order_details(order_id: int):
    # DANGER: The developer forgot to add a `depends(get_current_user)` guard!
    order = db.query(Order).filter(Order.id == order_id).first()
    return order
```

### How Sentinel AI Intercepts This (The Test Flow)

1. **The Webhook Trigger**: 
   The developer opens the Pull Request on GitHub. GitHub fires a JSON Webhook to Sentinel's `http://localhost:8000/webhook` endpoint.
   
2. **Surface Intelligence Extraction**:
   The `sentinel_worker` receives the PR diff. The AST Parser reads the Python code and extracts the structural relationships:
   - **Route:** `GET /api/orders/{order_id}`
   - **Arguments:** `order_id`
   - **Guards:** `[]` (Empty! No authentication dependency is present on this route).

3. **Graph Mapping (Neo4j)**:
   The worker immediately updates the Neo4j Graph Database. If you look at `http://localhost:7474`, you'll see a node for `/api/orders/{order_id}` completely detached from any `UserRole` nodes, indicating it's floating freely on the public internet.

4. **The AI Consensus Engine Kicks In**:
   The worker sends this extracted structure simultaneously to your LM Studio instances:
   - **To Mistral 7B (Port 1234)**: "Analyze this endpoint schema..."
   - **To Qwen 2.5 7B (Port 1235)**: "Analyze this endpoint schema..."
   
   Both models independently reason about the code. They will notice that an endpoint returning sensitive PII (`order_id`) has no `Depends(verify_token)` attached to it. They format their responses into JSON indicating a **BOLA** vulnerability with High Confidence.

5. **The Verdict**:
   The Consensus Engine agrees that both models found a critical vulnerability. It downgrades the application's "Auth Integrity Score" by 25 points.

6. **The Output**:
   - The React Dashboard (`http://localhost`) flashes red, showing the Auth Integrity has dropped and logging the specific BOLA vulnerability.
   - The backend automatically posts a comment on the GitHub PR: *"Warning: Sentinel AI detected a Missing Authentication Guard on `get_order_details`. This allows unauthorized access to all orders."*

---

## 4. How to Trigger a Manual Test (Without a real GitHub Repo)

Since the frontend is a mock representation for the MVP, you can simulate a GitHub Webhook firing by sending a direct `POST` request to the backend.

Open a terminal and run the following curl command:

```bash
curl -X POST http://localhost:8000/api/github/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: sha256=PLACEHOLDER_MAC" \
  -d '{
    "action": "opened",
    "pull_request": {
      "number": 42,
      "head": {
        "sha": "abc123fed"
      },
      "base": {
        "repo": {
          "full_name": "my-company/demo-api"
        }
      }
    }
  }'
```

Watch the Docker terminal (`docker-compose logs -f worker`). You will see the Celery worker pick up the task and attempt to run the analysis!
