# Phase Evaluation Plan (eval.md)

> **Reference**: [Implementation Plan](./implementation_plan.md) · [Architecture](./Architecture.md)  
> **Purpose**: Defines the testing strategy, manual test cases, and success criteria for each of the 6 phases of the Mutual Fund FAQ Assistant project.

---

## Table of Contents
1. [Phase 1: Project Scaffolding & Configuration](#phase-1-project-scaffolding--configuration)
2. [Phase 2: Data Ingestion Pipeline](#phase-2-data-ingestion-pipeline)
3. [Phase 3: Vector Store & Retrieval](#phase-3-vector-store--retrieval)
4. [Phase 4: Guardrails & LLM Generation](#phase-4-guardrails--llm-generation)
5. [Phase 5: API Server](#phase-5-api-server)
6. [Phase 6: Frontend UI & Documentation](#phase-6-frontend-ui--documentation)

---

## Phase 1: Project Scaffolding & Configuration

**Objective**: Ensure the foundational folder structure, configuration management, and environment setup are robust and repeatable.

### Automated Checks
- `python -c "from src.config import *"` executes without any import or syntax errors.
- `pip install -r requirements.txt` executes cleanly in an isolated virtual environment.

### Manual Verification
1. Verify directory tree matches `Architecture.md` §2.
2. Check that `.env.example` contains all expected keys (e.g., `GROQ_API_KEY`, `EMBEDDING_MODEL`).
3. Verify `data/sources.json` contains exactly 5 valid Groww scheme URLs.

### Success Criteria
- [ ] Folder structure is completely scaffolded.
- [ ] Dependencies install cleanly.
- [ ] Configuration loads successfully from environment and constants.

---

## Phase 2: Data Ingestion Pipeline

**Objective**: Verify the offline pipeline successfully extracts, cleans, chunks, and embeds data from Groww.in.

### Automated Checks
Run the ingestion script step-by-step:
```bash
python scripts/ingest.py --scrape-only
python scripts/ingest.py --parse-only
python scripts/ingest.py --chunk-only
```

### Manual Verification
1. **Scraper**: Inspect `data/raw/*.html`. Ensure files are >50KB and contain visible HTML, not just JS bundles.
2. **Parser**: Inspect `data/processed/*.txt`. Ensure no `<nav>`, `<footer>`, or `<script>` tags remain. Check that tabular data is readable.
3. **Chunker**: Inspect `*_chunks.json`. 
   - Token counts should predominantly be between 300-500.
   - Metadata (`chunk_id`, `scheme_name`, `section_title`, `source_url`, `last_updated`) must be present for every chunk.
4. **Embedder**: Verify the resulting output contains a 384-dimensional float array for the `embedding` key.

### Success Criteria
- [ ] 5 HTML files downloaded to `data/raw/`.
- [ ] Clean text files generated in `data/processed/`.
- [ ] Chunk JSON files have correct metadata and adhere to token limits.
- [ ] Embeddings generated without API dependency (runs locally).

---

## Phase 3: Vector Store & Retrieval

**Objective**: Validate ChromaDB initialization, chunk loading, and similarity search accuracy.

### Automated Checks
```bash
# Run full ingest to load DB
python scripts/ingest.py --full
```
Run `vector_store.get_collection_stats()` to assert chunk count is >0.

### Manual Verification
1. **Basic Retrieval**: Query "expense ratio HDFC Small Cap" via Python script/CLI. Ensure returned chunks actually contain expense ratio data.
2. **Threshold Test**: Query an unrelated topic (e.g., "Apple stock price"). Ensure 0 chunks are returned because no chunks pass the `0.65` threshold.
3. **Filter Test**: Query "exit load" while passing `scheme_name="HDFC Mid Cap Fund"` as a filter. Verify all returned chunks belong only to that scheme.
4. **Idempotency**: Run the ingest script twice. Ensure the total chunk count does not duplicate (upsert behavior works).

### Success Criteria
- [ ] ChromaDB collection successfully created and populated (~200-500 chunks).
- [ ] Similarity threshold strictly filters out irrelevant matches.
- [ ] Metadata filtering successfully isolates specific schemes.

---

## Phase 4: Guardrails & LLM Generation

**Objective**: Ensure PII is blocked, advisory queries are refused, and factual queries are correctly synthesized by the LLM.

### Automated Checks
Run unit test suites:
```bash
pytest tests/test_guardrails.py -v
pytest tests/test_generation.py -v
```

### Manual / Unit Test Coverage Requirements
1. **Intent Classifier**:
   - `FACTUAL`: "What is the NAV of HDFC Silver ETF?" -> Pass
   - `ADVISORY`: "Which fund is best for long term?" -> Block (Route to Refusal)
   - `OUT_OF_SCOPE`: "How do I open an SBI account?" -> Block (Route to Refusal)
2. **PII Filter**:
   - Input containing `ABCDE1234F` (PAN) -> Block
   - Input containing `9876543210` (Phone) -> Strip & Pass
3. **LLM Formatting**:
   - Verify prompt templates inject context properly.
   - Force the LLM to output a 5-sentence response; verify `formatter.py` truncates it to 3 sentences.
   - Ensure `formatter.py` injects `Source: [...]` if omitted by the LLM.

### Success Criteria
- [ ] Guardrails unit tests achieve >90% coverage for regex and logic paths.
- [ ] LLM respects strict limits (3 sentences, facts only).
- [ ] Citations and sanitization are consistently enforced.

---

## Phase 5: API Server

**Objective**: Validate the FastAPI application, endpoints, request schema validation, and middleware.

### Automated Checks
Run end-to-end and API integration tests:
```bash
pytest tests/test_e2e.py -v
```

### Manual Verification
Use `curl` or Postman to test live endpoints:
1. **Health Check**: `GET /api/health` -> `200 OK {"status": "ok"}`
2. **Factual Query**: `POST /api/chat` with valid query.
   - Expect: `200 OK`, `refused: false`, valid `answer` and `source_url`.
3. **Advisory Query**: `POST /api/chat` with advisory query.
   - Expect: `200 OK`, `refused: true`, AMFI link as source.
4. **Malformed Request**: `POST /api/chat` with empty query string.
   - Expect: Refusal or `422 Unprocessable Entity`.
5. **Rate Limiting**: Trigger 35 rapid requests to `/api/chat`. 
   - Expect: `429 Too Many Requests` on the 31st request.

### Success Criteria
- [ ] Server starts cleanly via `uvicorn`.
- [ ] Request/Response schemas strictly match specifications.
- [ ] Rate limiting (`slowapi`) and CORS middleware function correctly.

---

## Phase 6: Frontend UI & Documentation

**Objective**: Verify the web interface provides a resilient, responsive, and seamless user experience.

### Automated / Browser Checks
Launch the server and open `http://localhost:8000` in a browser.

### Manual Verification
1. **UI Elements**: Verify the "Facts-only. No investment advice." disclaimer is clearly visible.
2. **Interactivity**: 
   - Click an "Example Question" chip. Verify it triggers an API call and renders the response.
   - Type a query and press Enter. Verify the loading animation (typing indicator) appears.
3. **Rendering & Escaping**:
   - Submit `<script>alert('test')</script>`. Verify it is rendered safely as text without executing.
   - Ensure the markdown citation link is rendered as a clickable anchor tag (`<a>`).
4. **Resilience**: 
   - Disconnect the network (or stop the API server) and send a query. Verify the frontend displays a graceful "Network Error" message bubble.
5. **Responsive Design**: Resize the browser down to mobile width (<640px). Ensure the chat layout and input bar remain usable.

### Success Criteria
- [ ] UI accurately manages states: Welcome -> Typing -> Loading -> Display.
- [ ] XSS prevention is active on chat rendering.
- [ ] README.md contains complete setup instructions and meets requirements.

---

> **Note on Execution**: Evaluation should happen iteratively at the end of each phase before moving on to the next dependent phase (e.g., do not build Phase 5 without passing all Phase 4 checks).
