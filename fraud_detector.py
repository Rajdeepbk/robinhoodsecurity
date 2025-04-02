from typing import Dict, Any, List, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

class FraudDetector:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()
        # Fraud-related keywords with weights
        self.fraud_keywords = {
            # Transaction fraud indicators
            'unauthorized': 1.5,
            'fraud': 2.0,
            'fraudulent': 2.0,
            'stolen': 1.8,
            'theft': 1.8,
            'hack': 1.8,
            'hacked': 1.8,
            'compromised': 1.6,

            # Scam indicators
            'scam': 1.7,
            'scammed': 1.7,
            'fake': 1.5,
            'phishing': 1.9,
            'impersonation': 1.7,
            'impostor': 1.7,

            # Suspicious activity
            'suspicious': 1.3,
            'unknown': 1.2,
            'unrecognized': 1.3,
            'unfamiliar': 1.2,
            'strange': 1.2,
            'unexpected': 1.2,

            # Identity theft
            'identity': 1.4,
            'impersonate': 1.6,
            'stole': 1.6,
            'forged': 1.7,
            'forgery': 1.7,

            # Account compromise
            'compromise': 1.6,
            'breached': 1.5,
            'hijacked': 1.7,
            'takeover': 1.6,

            # Payment fraud
            'duplicate': 1.4,
            'overcharge': 1.5,
            'overcharged': 1.5,
            'double-charged': 1.5,

            # Spam indicators
            'spam': 1.3,
            'unsolicited': 1.2,
            'unwanted': 1.1,

            # Social engineering
            'pretending': 1.4,
            'claiming': 1.3,
            'pressured': 1.4,
            'urgent': 1.3,
            'emergency': 1.3,

            # Money laundering
            'shell': 1.6,
            'mule': 1.7,
            'laundering': 1.8,
            'structured': 1.4,

            # Generic warning signs
            'mistake': 1.1,
            'error': 1.1,
            'wrong': 1.1,
            'incorrect': 1.1
        }

    def calculate_fraud_score(self, processed_text: str) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Calculate fraud score and return detected indicators with their weights.
        Returns a tuple of (fraud_score, list of detected indicators)
        """
        words = processed_text.lower().split()
        score = 0.0
        detected_indicators = []

        # Calculate weighted score and collect matched terms
        for word in words:
            if word in self.fraud_keywords:
                weight = self.fraud_keywords[word]
                score += weight
                detected_indicators.append({
                    'term': word,
                    'weight': weight,
                    'category': self._get_category(word)
                })

        # Normalize score between 0 and 1
        if score > 0:
            score = min(score / 10.0, 1.0)

        return float(score), detected_indicators

    def _get_category(self, word: str) -> str:
        """Determine the fraud category for a given keyword."""
        categories = {
            'transaction_fraud': ['unauthorized', 'fraud', 'fraudulent', 'stolen'],
            'scam': ['scam', 'scammed', 'fake', 'phishing', 'impersonation', 'impostor'],
            'suspicious_activity': ['suspicious', 'unknown', 'unrecognized', 'unfamiliar', 'strange', 'unexpected'],
            'identity_theft': ['identity', 'impersonate', 'stole', 'forged', 'forgery'],
            'account_compromise': ['compromise', 'breached', 'hijacked', 'takeover', 'compromised'],
            'payment_fraud': ['duplicate', 'overcharge', 'overcharged', 'double-charged'],
            'spam': ['spam', 'unsolicited', 'unwanted'],
            'social_engineering': ['pretending', 'claiming', 'pressured', 'urgent', 'emergency'],
            'money_laundering': ['shell', 'mule', 'laundering', 'structured'],
            'generic_warning': ['mistake', 'error', 'wrong', 'incorrect']
        }

        for category, keywords in categories.items():
            if word in keywords:
                return category
        return 'other'