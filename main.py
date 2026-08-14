import os
import json
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# Basic logger set up
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_compliance_checker")

app = FastAPI(
    title="EU AI Act Compliance Checker",
    description="API that checks AI text outputs against key EU AI Act regulatory principles.",
    version="1.0.0"
)

# TODO: Cache repeated content checks to save on API usage costs
# TODO: Add customizable compliance rule packs for NIST or ISO standards

class ComplianceRequest(BaseModel):
    content: str = Field(..., min_length=10, description="The AI text output or system description to evaluate")
    context: Optional[str] = Field(None, description="Optional context about how the AI is used (e.g. hiring, loan approvals)")

class Violation(BaseModel):
    principle: str
    severity: str  # low, medium, high
    article_reference: str
    description: str

class Recommendation(BaseModel):
    principle: str
    action: str
    priority: str

class ComplianceResponse(BaseModel):
    compliant: bool
    score: int
    summary: str
    violations: List[Violation] = []
    recommendations: List[Recommendation] = []
    eu_ai_act_articles: List[str] = []


EU_PRINCIPLES_SUMMARY = [
    {"principle": "Transparency", "article": "Art. 13", "description": "Users must know they are interacting with AI, and outputs must be explainable."},
    {"principle": "Human Oversight", "article": "Art. 14", "description": "High-stakes automated decisions must have human review or override options."},
    {"principle": "Accuracy & Robustness", "article": "Art. 15", "description": "Outputs must be factual, qualified, and resilient to malicious inputs."},
    {"principle": "Non-Discrimination", "article": "Art. 10", "description": "AI outputs must not create or perpetuate bias against protected groups."},
    {"principle": "Privacy", "article": "Art. 10 + GDPR", "description": "Personal data collection must be minimized and lawfully handled."},
    {"principle": "Accountability", "article": "Art. 9", "description": "Requires audit trails, risk management, and clear owner responsibility."}
]

SYSTEM_PROMPT = """You are a regulatory auditor specializing in the EU Artificial Intelligence Act (Regulation (EU) 2024/1689).
Your job is to audit the provided AI text output or system description against these 6 principles:
1. Transparency (Art. 13)
2. Human Oversight (Art. 14)
3. Accuracy & Robustness (Art. 15)
4. Non-Discrimination (Art. 10)
5. Privacy (Art. 10 + GDPR)
6. Accountability (Art. 9)

Evaluate the text carefully. Return ONLY a JSON object matching this structure:
{{
  "compliant": true/false (false if any high or medium severity violation is found),
  "score": integer between 0 and 100,
  "summary": "2-3 sentence executive summary of compliance status",
  "violations": [
    {{
      "principle": "Principle Name",
      "severity": "low/medium/high",
      "article_reference": "Art. X",
      "description": "Specific reason why this violates the rule"
    }}
  ],
  "recommendations": [
    {{
      "principle": "Principle Name",
      "action": "Practical fix step",
      "priority": "low/medium/high"
    }}
  ],
  "eu_ai_act_articles": ["Art. 9", "Art. 14"]
}}
"""


@app.get("/health")
def health():
    return {"status": "ok", "service": "EU AI Act Compliance Checker", "version": "1.0.0"}


@app.get("/principles")
def principles():
    return {"principles": EU_PRINCIPLES_SUMMARY}


@app.post("/compliance-check", response_model=ComplianceResponse)
async def check_compliance(req: ComplianceRequest):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.strip() == "" or api_key == "your_openai_api_key_here":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OPENAI_API_KEY is not set. Please update your .env file with a valid key."
        )

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    try:
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            temperature=0.0
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "Use-Case Context: {context}\n\nContent to Audit:\n{content}")
        ])

        chain = prompt | llm | StrOutputParser()

        context_val = req.context if req.context else "No extra context provided."
        raw_output = await chain.ainvoke({"content": req.content, "context": context_val})

        # Strip markdown fences if GPT wraps response in backticks
        text = raw_output.strip()
        if "```" in text:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start:end+1]

        data = json.loads(text)
        return ComplianceResponse(**data)

    except json.JSONDecodeError as err:
        logger.error(f"Failed to parse LLM JSON output: {err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The AI model returned output that could not be parsed as valid JSON. Please try again."
        )
    except Exception as err:
        logger.error(f"Error during compliance check: {err}")
        err_msg = str(err)
        if "api_key" in err_msg.lower() or "authentication" in err_msg.lower() or "401" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid OPENAI_API_KEY provided. Check your key and try again."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compliance check failed: {err_msg}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
