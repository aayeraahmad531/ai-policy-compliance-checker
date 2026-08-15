from typing import List, Dict, Any, Tuple

# Severity-based penalties
# TODO: Move these values to a separate config file or env variables for greater customization
PENALTIES = {
    "high": 50,
    "medium": 20,
    "low": 5
}

def calculate_score_and_outcome(
    violations: List[Dict[str, Any]], 
    has_insufficient_info: bool
) -> Tuple[bool, int, str]:
    """
    Deterministically calculates compliance status, score, and outcome based on violations.
    
    Rules:
    - Base score is 100.
    - Each violation deducts points based on its severity:
        - HIGH severity violation: 40 points
        - MEDIUM severity violation: 20 points
        - LOW severity violation: 5 points
    - The score is clamped between 0 and 100.
    - If there is any HIGH or MEDIUM severity violation, compliant is False and the outcome is NON_COMPLIANT.
    - If there are no HIGH/MEDIUM violations but the LLM flags that information was insufficient, 
      compliant is True and the outcome is INSUFFICIENT_INFORMATION.
    - Otherwise, compliant is True and the outcome is COMPLIANT.
    
    Args:
        violations: List of violation dicts, where each dict has a 'severity' key.
        has_insufficient_info: Boolean indicating if there is insufficient information.
        
    Returns:
        Tuple[bool, int, str]: (compliant, score, outcome)
    """
    score = 100
    has_high_or_medium = False
    
    for v in violations:
        severity = v.get("severity", "").lower()
        penalty = PENALTIES.get(severity, 0)
        score -= penalty
        if severity in ("high", "medium"):
            has_high_or_medium = True
            
    # Clamp score to a minimum of 0
    score = max(0, score)
    
    if has_high_or_medium:
        compliant = False
        outcome = "NON_COMPLIANT"
    elif has_insufficient_info:
        compliant = True
        # For insufficient information, we keep compliant=True but reflect status in the outcome
        outcome = "INSUFFICIENT_INFORMATION"
    else:
        compliant = True
        outcome = "COMPLIANT"
        
    return compliant, score, outcome
