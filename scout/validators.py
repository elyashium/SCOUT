from pydantic import BaseModel
from typing import List

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str]

def validate_email(email: str, signals: List[str]) -> ValidationResult:
    errors = []
    
    # 1. Under 100 words
    word_count = len(email.split())
    if word_count > 100:
        errors.append(f"Email is too long ({word_count} words). Must be under 100 words.")
        
    # 2. No banned phrases
    email_lower = email.lower()
    if "passionate about" in email_lower:
        errors.append("Contains banned phrase: 'passionate about'.")
    if "excited to" in email_lower:
        errors.append("Contains banned phrase: 'excited to'.")
    
    # 3. No em dashes
    if "—" in email or "--" in email:
        errors.append("Contains banned em dashes ('—' or '--').")
        
    # 4. No exclamation marks
    if "!" in email:
        errors.append("Contains exclamation mark '!'.")
        
    # 5. All lowercase
    if any(c.isupper() for c in email):
        errors.append("Contains uppercase letters. Must be entirely lowercase.")
        
    # 6. Must reference a signal
    signal_referenced = False
    if not signals:
        # If no signals were found during research, we skip this check
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
            errors.append("Email does not seem to explicitly reference any of the provided signals.")
            
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
