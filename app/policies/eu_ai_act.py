from pydantic import BaseModel

class PolicyPrinciple(BaseModel):
    id: str
    name: str
    description: str
    article_reference: str
    guidance: str

# Existing six principles structured cleanly
EU_AI_ACT_PRINCIPLES = [
    PolicyPrinciple(
        id="transparency",
        name="Transparency",
        description="Users must know they are interacting with AI, and outputs must be explainable.",
        article_reference="Art. 13",
        guidance="Ensure the system explicitly discloses that content is AI-generated, and provides understandable explanations of how decisions are reached."
    ),
    PolicyPrinciple(
        id="human_oversight",
        name="Human Oversight",
        description="High-stakes automated decisions must have human review or override options.",
        article_reference="Art. 14",
        guidance="Implement mechanisms for human review, intervention, and override of AI-driven outcomes, especially in high-risk areas."
    ),
    PolicyPrinciple(
        id="accuracy_robustness",
        name="Accuracy & Robustness",
        description="Outputs must be factual, qualified, and resilient to malicious inputs.",
        article_reference="Art. 15",
        guidance="Validate output accuracy, set confidence thresholds, and test resilience against adversarial inputs or manipulation."
    ),
    PolicyPrinciple(
        id="non_discrimination",
        name="Non-Discrimination",
        description="AI outputs must not create or perpetuate bias against protected groups.",
        article_reference="Art. 10",
        guidance="Audit training data and model outputs for bias or discriminatory patterns based on gender, race, age, or other protected characteristics."
    ),
    PolicyPrinciple(
        id="privacy",
        name="Privacy",
        description="Personal data collection must be minimized and lawfully handled.",
        article_reference="Art. 10 + GDPR",
        guidance="Enforce data minimization, secure user consent, and ensure full compliance with GDPR requirements for personal data processing."
    ),
    PolicyPrinciple(
        id="accountability",
        name="Accountability",
        description="Requires audit trails, risk management, and clear owner responsibility.",
        article_reference="Art. 9",
        guidance="Establish risk management systems, maintain detailed logs (audit trails), and assign clear operational responsibility for the AI system."
    )
]

# Backward-compatible summary format for principles endpoint
EU_PRINCIPLES_SUMMARY = [
    {
        "principle": p.name,
        "article": p.article_reference,
        "description": p.description
    }
    for p in EU_AI_ACT_PRINCIPLES
]
