import os
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.policies.eu_ai_act import EU_AI_ACT_PRINCIPLES, EU_PRINCIPLES_SUMMARY
from app.scoring import calculate_score_and_outcome
from app.prompts import AUDIT_SYSTEM_PROMPT

load_dotenv()

# Basic logger set up
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_compliance_checker")

app = FastAPI(
    title="EU AI Act Compliance Checker",
    description="API that checks AI text outputs against key EU AI Act regulatory principles.",
    version="1.0.0"
)

# Configurable CORS middleware based on env variables
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "*")
if allowed_origins_str == "*":
    origins = ["*"]
else:
    origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if "*" not in origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TODO: Cache repeated content checks to save on API usage costs
# TODO: Add customizable compliance rule packs for NIST or ISO standards

class ComplianceRequest(BaseModel):
    content: str = Field(..., description="The AI text output or system description to evaluate")
    context: Optional[str] = Field(None, description="Optional context about how the AI is used (e.g. hiring, loan approvals)")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Content cannot be empty or whitespace only.")
        if len(v_stripped) < 10:
            raise ValueError("Content must be at least 10 characters long.")
        if len(v) > 50000:
            raise ValueError("Content exceeds maximum allowed length of 50000 characters.")
        return v

    @field_validator("context")
    @classmethod
    def validate_context(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if len(v) > 10000:
                raise ValueError("Context exceeds maximum allowed length of 10000 characters.")
        return v

class Violation(BaseModel):
    principle: str
    severity: str  # low, medium, high
    article_reference: str
    description: str
    evidence: str = ""
    explanation: str = ""
    recommendation: str = ""

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
    outcome: str = "COMPLIANT"  # COMPLIANT, NON_COMPLIANT, INSUFFICIENT_INFORMATION
    analysis_id: str
    timestamp: str
    model_used: str

# Pydantic schemas for LLM structured output
class LLMViolation(BaseModel):
    principle: str = Field(description="The name of the EU AI Act principle violated. Must be one of the 6 principles.")
    severity: str = Field(description="Severity of the violation: 'low', 'medium', or 'high'")
    article_reference: str = Field(description="Relevant article reference (e.g., 'Art. 13', 'Art. 14')")
    evidence: str = Field(default="", description="Direct quotation or evidence from the provided text showing the violation. MUST be from the provided text only.")
    explanation: str = Field(default="", description="Detailed explanation of why the text violates the principle.")
    recommendation: str = Field(default="", description="Actionable fix to resolve this violation.")

class LLMRecommendation(BaseModel):
    principle: str = Field(description="The principle this recommendation applies to")
    action: str = Field(description="Actionable remediation step")
    priority: str = Field(default="low", description="Priority of the recommendation: 'low', 'medium', or 'high'")

class LLMAnalysisOutput(BaseModel):
    has_insufficient_information: bool = Field(default=False, description="True if the text lacks sufficient information to evaluate compliance properly.")
    insufficient_information_explanation: Optional[str] = Field(None, description="Explanation of what information is missing to make a compliance determination.")
    violations: List[LLMViolation] = Field(default=[], description="List of identified violations.")
    recommendations: List[LLMRecommendation] = Field(default=[], description="List of general recommendations.")
    summary: str = Field(default="", description="A concise summary of the analysis.")


def parse_fallback_json(text: str) -> LLMAnalysisOutput:
    """Safe fallback parser to parse raw JSON text and validate it against the LLMAnalysisOutput schema."""
    text = text.strip()
    if "```" in text:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]
    
    data = json.loads(text)
    return LLMAnalysisOutput(**data)


@app.get("/health")
def health():
    return {"status": "ok", "service": "EU AI Act Compliance Checker", "version": "1.0.0"}


@app.get("/principles")
def principles():
    return {"principles": EU_PRINCIPLES_SUMMARY}


@app.post("/compliance-check", response_model=ComplianceResponse)
async def check_compliance(req: ComplianceRequest):
    start_time = time.time()
    analysis_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.strip() == "" or api_key == "your_openai_api_key_here":
        duration = time.time() - start_time
        logger.error(f"Compliance check {analysis_id} failed in {duration:.3f}s: OPENAI_API_KEY not configured.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OPENAI_API_KEY is not set. Please update your .env file with a valid key."
        )

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    context_val = req.context if req.context else "No extra context provided."

    try:
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            temperature=0.0,
            timeout=30.0
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", AUDIT_SYSTEM_PROMPT),
            ("human", "Use-Case Context: {context}\n\nContent to Audit:\n{content}")
        ])

        # Try structured output using with_structured_output
        try:
            structured_llm = llm.with_structured_output(LLMAnalysisOutput)
            chain = prompt | structured_llm
            result = await chain.ainvoke({"content": req.content, "context": context_val})
            
            # Handle mock string output if running in legacy test cases
            if isinstance(result, str):
                llm_output = parse_fallback_json(result)
            elif isinstance(result, dict):
                llm_output = LLMAnalysisOutput(**result)
            else:
                llm_output = result
        except Exception as str_err:
            # Propagate API errors directly so they are handled with correct status codes
            str_err_msg = str(str_err).lower()
            if any(kw in str_err_msg for kw in ("timeout", "timed out", "time out", "rate_limit", "429", "auth", "api_key", "401")):
                raise str_err

            logger.warning(f"Structured output method failed: {str_err}. Falling back to manual JSON parsing.")
            # Fallback to string-based output and manual parsing
            fallback_chain = prompt | llm | StrOutputParser()
            raw_output = await fallback_chain.ainvoke({"content": req.content, "context": context_val})
            llm_output = parse_fallback_json(raw_output)

        # Convert LLM output violations to response format
        violations_list = []
        for lv in llm_output.violations:
            violations_list.append(Violation(
                principle=lv.principle,
                severity=lv.severity,
                article_reference=lv.article_reference,
                description=lv.explanation,  # description maps to explanation
                evidence=lv.evidence,
                explanation=lv.explanation,
                recommendation=lv.recommendation
            ))

        # Convert LLM output recommendations to response format
        recommendations_list = []
        for lr in llm_output.recommendations:
            recommendations_list.append(Recommendation(
                principle=lr.principle,
                action=lr.action,
                priority=lr.priority
            ))
            
        # Collect EU AI Act article references
        articles_set = set()
        for lv in llm_output.violations:
            articles_set.add(lv.article_reference)
            # Add corresponding recommendation priority violation details
            if not any(r.action == lv.recommendation for r in recommendations_list):
                recommendations_list.append(Recommendation(
                    principle=lv.principle,
                    action=lv.recommendation,
                    priority=lv.severity
                ))

        # Calculate compliance status and score deterministically in Python
        violations_dict_list = [v.model_dump() for v in violations_list]
        compliant, score, outcome = calculate_score_and_outcome(
            violations_dict_list, 
            llm_output.has_insufficient_information
        )

        response_data = ComplianceResponse(
            compliant=compliant,
            score=score,
            summary=llm_output.insufficient_information_explanation if (
                llm_output.has_insufficient_information and llm_output.insufficient_information_explanation
            ) else llm_output.summary,
            violations=violations_list,
            recommendations=recommendations_list,
            eu_ai_act_articles=list(articles_set),
            outcome=outcome,
            analysis_id=analysis_id,
            timestamp=timestamp,
            model_used=model_name
        )

        duration = time.time() - start_time
        logger.info(
            f"Compliance check {analysis_id} succeeded using model {model_name} in {duration:.3f}s. "
            f"Outcome: {outcome}, Violations count: {len(violations_list)}, Score: {score}"
        )
        return response_data

    except json.JSONDecodeError as err:
        duration = time.time() - start_time
        logger.error(f"Compliance check {analysis_id} failed in {duration:.3f}s: Failed to parse JSON from LLM: {err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The AI model returned output that could not be parsed as valid JSON. Please try again."
        )
    except Exception as err:
        duration = time.time() - start_time
        logger.error(f"Compliance check {analysis_id} failed in {duration:.3f}s due to error: {err}")
        err_msg = str(err).lower()
        if "api_key" in err_msg or "auth" in err_msg or "401" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed. Please check your OPENAI_API_KEY."
            )
        elif "timeout" in err_msg or "timed out" in err_msg or "time out" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="The request to the AI model timed out. Please try again."
            )
        elif "rate_limit" in err_msg or "429" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="The AI model API rate limit was exceeded. Please try again later."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal error occurred during the compliance check."
            )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
