from pydantic import BaseModel
from typing import List

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str]

def validate_email(email: str, signals: List[str]) -> ValidationResult:
    errors = []
    
    # 1. Reasonable length — max 250 words
    word_count = len(email.split())
    if word_count > 250:
        errors.append(f"Email is too long ({word_count} words). Must be under 250 words.")
        
    # 2. No banned fluff phrases
    email_lower = email.lower()
    if "passionate about" in email_lower:
        errors.append("Contains banned phrase: 'passionate about'.")
    if "excited to" in email_lower:
        errors.append("Contains banned phrase: 'excited to'.")
    if "hope this finds you" in email_lower:
        errors.append("Contains banned phrase: 'hope this finds you'.")
        
    # 3. No exclamation marks
    if "!" in email:
        errors.append("Contains exclamation mark '!'.")
        
    # 4. Must have a Subject line
    if not email.lower().startswith("subject:"):
        errors.append("Email must begin with 'Subject: <subject line>'.")
        
    # 5. Must reference a signal (if signals exist)
    signal_referenced = False
    if not signals:
        signal_referenced = True
    else:
        for signal in signals:
            signal_words = signal.lower().split()
            if len(signal_words) < 2:
                if signal.lower() in email_lower:
                    signal_referenced = True
                    break
            else:
                for i in range(len(signal_words) - 1):
                    bigram = f"{signal_words[i]} {signal_words[i+1]}"
                    if bigram in email_lower:
                        signal_referenced = True
                        break
                if signal_referenced:
                    break
                    
        if not signal_referenced:
            errors.append("Email does not reference any of the research signals.")
            
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
