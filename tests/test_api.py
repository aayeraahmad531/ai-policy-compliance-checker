"""
Automated unit tests for EU AI Act Compliance Checker API.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from main import app, ComplianceResponse, Violation, Recommendation, LLMAnalysisOutput, LLMViolation, LLMRecommendation
from app.scoring import calculate_score_and_outcome

client = TestClient(app)


def test_health_endpoint():
    """Test GET /health returns 200 and expected status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_principles_endpoint():
    """Test GET /principles returns 200 and 6 EU AI Act principles."""
    response = client.get("/principles")
    assert response.status_code == 200
    data = response.json()
    assert "principles" in data
    assert len(data["principles"]) == 6
    principles_names = [p["principle"] for p in data["principles"]]
    assert "Transparency" in principles_names
    assert "Human Oversight" in principles_names
    assert "Non-Discrimination" in principles_names


def test_compliance_check_validation_error():
    """Test POST /compliance-check rejects content shorter than 10 characters."""
    response = client.post("/compliance-check", json={"content": "short"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Newly Added Tests
# ---------------------------------------------------------------------------

def test_empty_input_validation():
    """Test POST /compliance-check rejects empty or whitespace-only inputs."""
    # Empty content
    response = client.post("/compliance-check", json={"content": ""})
    assert response.status_code == 422
    assert "Content cannot be empty" in response.json()["detail"][0]["msg"]

    # Whitespace content
    response = client.post("/compliance-check", json={"content": "         "})
    assert response.status_code == 422


def test_excessively_long_input_validation():
    """Test POST /compliance-check rejects inputs exceeding 50,000 characters."""
    long_content = "a" * 50001
    response = client.post("/compliance-check", json={"content": long_content})
    assert response.status_code == 422
    assert "exceeds maximum allowed length" in response.json()["detail"][0]["msg"]


def test_scoring_module_directly():
    """Test the deterministic scoring logic in app/scoring.py directly."""
    # 1. Compliant, no violations
    compliant, score, outcome = calculate_score_and_outcome([], False)
    assert compliant is True
    assert score == 100
    assert outcome == "COMPLIANT"

    # 2. Non-compliant, one high violation (100 - 50 = 50)
    violations = [{"severity": "high"}]
    compliant, score, outcome = calculate_score_and_outcome(violations, False)
    assert compliant is False
    assert score == 50
    assert outcome == "NON_COMPLIANT"

    # 3. Non-compliant, one medium and one low violation (100 - 20 - 5 = 75)
    violations = [{"severity": "medium"}, {"severity": "low"}]
    compliant, score, outcome = calculate_score_and_outcome(violations, False)
    # Medium severity violation results in non-compliant state
    assert compliant is False
    assert score == 75
    assert outcome == "NON_COMPLIANT"

    # 4. Compliant with low violation (100 - 5 = 95)
    violations = [{"severity": "low"}]
    compliant, score, outcome = calculate_score_and_outcome(violations, False)
    assert compliant is True
    assert score == 95
    assert outcome == "COMPLIANT"

    # 5. Insufficient information (no violations)
    compliant, score, outcome = calculate_score_and_outcome([], True)
    assert compliant is True
    assert score == 100
    assert outcome == "INSUFFICIENT_INFORMATION"


@patch("main.ChatOpenAI")
def test_compliance_check_compliant_result(mock_chat_openai):
    """Test POST /compliance-check with a fully compliant mock response."""
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance
    
    mock_structured_llm = AsyncMock()
    mock_instance.with_structured_output.return_value = mock_structured_llm

    expected_output = LLMAnalysisOutput(
        has_insufficient_information=False,
        summary="The AI system complies fully with all rules.",
        violations=[],
        recommendations=[]
    )
    # Mock both call and ainvoke to support piping and direct call
    mock_structured_llm.return_value = expected_output
    mock_structured_llm.ainvoke.return_value = expected_output

    payload = {
        "content": "This is a standard compliant AI system text output.",
        "context": "General recommendation chatbot"
    }

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test1234567890"}):
        response = client.post("/compliance-check", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["compliant"] is True
        assert data["score"] == 100
        assert data["outcome"] == "COMPLIANT"
        assert len(data["violations"]) == 0
        assert "analysis_id" in data
        assert "timestamp" in data
        assert data["model_used"] == "gpt-4o-mini"


@patch("main.ChatOpenAI")
def test_compliance_check_insufficient_information(mock_chat_openai):
    """Test POST /compliance-check returning an INSUFFICIENT_INFORMATION outcome."""
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance
    
    mock_structured_llm = AsyncMock()
    mock_instance.with_structured_output.return_value = mock_structured_llm

    expected_output = LLMAnalysisOutput(
        has_insufficient_information=True,
        insufficient_information_explanation="The text fails to describe the human review process.",
        summary="Insufficient information to determine compliance.",
        violations=[],
        recommendations=[]
    )
    mock_structured_llm.return_value = expected_output
    mock_structured_llm.ainvoke.return_value = expected_output

    payload = {
        "content": "Our AI classifies customer support emails.",
        "context": "Support routing"
    }

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test1234567890"}):
        response = client.post("/compliance-check", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["compliant"] is True
        assert data["score"] == 100
        assert data["outcome"] == "INSUFFICIENT_INFORMATION"
        assert "fails to describe" in data["summary"]


@patch("main.ChatOpenAI")
def test_compliance_check_malformed_llm_output_handling(mock_chat_openai):
    """Test POST /compliance-check returns 422 when the LLM returns malformed, unparseable JSON."""
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance
    
    # Force structured output to throw exception to trigger fallback
    mock_instance.with_structured_output.side_effect = Exception("Structured output disabled")

    # Mock the fallback raw parser chain to return completely invalid JSON
    with patch("langchain_core.runnables.RunnableSequence.ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = "This is not JSON at all!"

        payload = {
            "content": "Evaluate this text against the EU AI Act regulations.",
            "context": "Testing"
        }
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test1234567890"}):
            response = client.post("/compliance-check", json=payload)
            assert response.status_code == 422
            assert "could not be parsed as valid JSON" in response.json()["detail"]


@patch("main.ChatOpenAI")
def test_compliance_check_llm_failure_handling(mock_chat_openai):
    """Test POST /compliance-check returns 500 when LLM raises a generic exception."""
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance
    
    mock_structured_llm = AsyncMock()
    mock_instance.with_structured_output.return_value = mock_structured_llm
    
    # Mock exceptions on both call and ainvoke
    mock_structured_llm.side_effect = Exception("API connection dropped")
    mock_structured_llm.ainvoke.side_effect = Exception("API connection dropped")

    payload = {
        "content": "Evaluate this text against the EU AI Act regulations.",
        "context": "Testing"
    }
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test1234567890"}):
        response = client.post("/compliance-check", json=payload)
        assert response.status_code == 500
        assert "internal error occurred" in response.json()["detail"]


@patch("main.ChatOpenAI")
def test_compliance_check_timeout_handling(mock_chat_openai):
    """Test POST /compliance-check returns 504 when LLM request times out."""
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance
    
    mock_structured_llm = AsyncMock()
    mock_instance.with_structured_output.return_value = mock_structured_llm
    
    # Mock exceptions on both call and ainvoke
    mock_structured_llm.side_effect = Exception("Request timed out after 30 seconds")
    mock_structured_llm.ainvoke.side_effect = Exception("Request timed out after 30 seconds")

    payload = {
        "content": "Evaluate this text against the EU AI Act regulations.",
        "context": "Testing"
    }
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test1234567890"}):
        response = client.post("/compliance-check", json=payload)
        assert response.status_code == 504
        assert "request to the AI model timed out" in response.json()["detail"]


@patch("main.ChatOpenAI")
def test_compliance_check_rate_limit_handling(mock_chat_openai):
    """Test POST /compliance-check returns 429 when LLM rate limit is reached."""
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance
    
    mock_structured_llm = AsyncMock()
    mock_instance.with_structured_output.return_value = mock_structured_llm
    
    # Mock exceptions on both call and ainvoke
    mock_structured_llm.side_effect = Exception("Rate limit exceeded 429")
    mock_structured_llm.ainvoke.side_effect = Exception("Rate limit exceeded 429")

    payload = {
        "content": "Evaluate this text against the EU AI Act regulations.",
        "context": "Testing"
    }
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test1234567890"}):
        response = client.post("/compliance-check", json=payload)
        assert response.status_code == 429
        assert "rate limit was exceeded" in response.json()["detail"]


# Keep original success test so it continues to pass
@patch("main.ChatOpenAI")
def test_compliance_check_success(mock_chat_openai):
    """Test POST /compliance-check returns structured response when OpenAI chain succeeds (legacy check)."""
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance
    mock_instance.with_structured_output.side_effect = Exception("Fallback mock trigger")

    fake_json_output = """{
      "compliant": false,
      "score": 50,
      "summary": "High risk violation detected due to automated lending decisions.",
      "violations": [
        {
          "principle": "Human Oversight",
          "severity": "high",
          "article_reference": "Art. 14",
          "description": "Automated loan denials without human review."
        }
      ],
      "recommendations": [
        {
          "principle": "Human Oversight",
          "action": "Add human review step.",
          "priority": "high"
        }
      ],
      "eu_ai_act_articles": ["Art. 14"]
    }"""

    with patch("langchain_core.runnables.RunnableSequence.ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = fake_json_output

        payload = {
            "content": "Our AI system automatically scores loan applicants without human oversight.",
            "context": "Fintech lending",
        }
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test1234567890"}):
            response = client.post("/compliance-check", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["compliant"] is False
            assert data["score"] == 50
            assert len(data["violations"]) == 1
            assert data["violations"][0]["principle"] == "Human Oversight"


def test_compliance_check_missing_api_key():
    """Test POST /compliance-check returns 401 when OPENAI_API_KEY is not set."""
    payload = {
        "content": "Our AI system automatically scores loan applicants without human oversight.",
        "context": "Fintech credit decisioning engine",
    }
    with patch.dict("os.environ", {"OPENAI_API_KEY": "your_openai_api_key_here"}):
        response = client.post("/compliance-check", json=payload)
        assert response.status_code == 401
        assert "OPENAI_API_KEY" in response.json()["detail"]
