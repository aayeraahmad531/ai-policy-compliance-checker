# AI Policy Compliance Checker (EU AI Act)

I built this project after spending way too many hours manually reading through EU AI Act compliance PDFs while reviewing AI features for work. I wanted a quick, automated way to check AI outputs or system prompts against EU AI Act rules (like human oversight, transparency, non-discrimination, etc.) without having to look up article numbers every single time.

This repo exposes a small FastAPI service that takes any AI content or feature description, runs it through OpenAI GPT via LangChain, and returns a clear compliance verdict with score, article references, and suggested fixes.

---

## 🛠️ Tech Stack

- **Language:** Python 3.11+
- **API Framework:** FastAPI
- **LLM Orchestration:** LangChain (`langchain-openai`)
- **AI Model:** OpenAI (`gpt-4o-mini` by default, configurable)
- **Containerization:** Docker & Docker Compose
- **Deployment:** GCP Cloud Run ready

---

## ⚙️ Environment Variables

Create a `.env` file in the root folder (or copy from `.env.example`):

```bash
cp .env.example .env
```

Set the following variables inside `.env`:

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** | None | Your OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model to use for audits |

---

## 🚀 Running Locally

### 1. Setup virtual environment & dependencies

```bash
# Create and activate virtualenv
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Start the API server

```bash
python main.py
```
*(Or run directly with uvicorn: `uvicorn main:app --reload --port 8000`)*

The server will start at `http://127.0.0.1:8000`. You can test endpoints via Swagger docs at `http://127.0.0.1:8000/docs`.

---

## 🐳 Running with Docker

If you don't want to mess with local Python environments, use Docker:

```bash
# Build the image
docker build -t ai-compliance-checker .

# Run container (passing your env file)
docker run -p 8000:8000 --env-file .env ai-compliance-checker
```

Now access `http://localhost:8000/health` to verify it's up.

---

## 📡 API Endpoints & Example Usage

### 1. `GET /health`
Quick health check endpoint to confirm the service is alive.

### 2. `GET /principles`
Returns a quick summary of the 6 EU AI Act principles evaluated by this tool (Transparency, Human Oversight, Accuracy & Robustness, Non-Discrimination, Privacy, Accountability).

### 3. `POST /compliance-check`
Audits content against EU AI Act rules.

#### Example Request:
```bash
curl -X POST http://localhost:8000/compliance-check \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Our AI model automatically rejects credit applications for applicants living in specific postal codes without human intervention.",
    "context": "Fintech automated lending system"
  }'
```

#### Example Response:
```json
{
  "compliant": false,
  "score": 50,
  "summary": "The described fintech lending system violates core EU AI Act requirements. Automatic denial without human review breaches Article 14, and using postal code as a decision variable creates serious proxy discrimination risk under Article 10.",
  "violations": [
    {
      "principle": "Human Oversight",
      "severity": "high",
      "article_reference": "Art. 14",
      "description": "Fully automated credit denial without a human review or appeal pathway violates human oversight rules for high-risk AI decisions."
    },
    {
      "principle": "Non-Discrimination",
      "severity": "high",
      "article_reference": "Art. 10",
      "description": "Postal code is a known proxy for race and income, creating indirect discriminatory impact."
    }
  ],
  "recommendations": [
    {
      "principle": "Human Oversight",
      "action": "Add a mandatory human review step before issuing final loan rejections.",
      "priority": "high"
    },
    {
      "principle": "Non-Discrimination",
      "action": "Remove geographic zip/postal code features from decision inputs and run demographic parity tests.",
      "priority": "high"
    }
  ],
  "eu_ai_act_articles": [
    "Art. 10",
    "Art. 14"
  ]
}
```

---

## 📌 Known Limitations & Future Improvements

- **Current Limitations:** Right now it works best on short to medium text descriptions (system prompts, feature descriptions, policy drafts). It doesn't parse full PDF policy uploads directly yet.
- **Future Plans:**
  - Add optional support for NIST AI Risk Management Framework rules alongside the EU AI Act.
  - Add response caching to cut down on OpenAI tokens for repeated audits.
  - Build a simple Streamlit / React frontend so non-technical team members can run checks easily.

---

## 📄 License

MIT - feel free to use and modify for your own projects!
