"""
Automated unit tests for EU AI Act Compliance Checker API.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from main import app, ComplianceResponse, Violation, Recommendation

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


@patch("main.ChatOpenAI")
def test_compliance_check_success(mock_chat_openai):
    """Test POST /compliance-check returns structured response when OpenAI chain succeeds."""
    mock_instance = AsyncMock()
    mock_chat_openai.return_value = mock_instance

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
