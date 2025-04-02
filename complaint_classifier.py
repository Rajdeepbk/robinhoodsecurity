from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import numpy as np
import logging

class ComplaintClassifier:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()
        self.classifier = MultinomialNB()
        self.categories = ['account_issue', 'transaction_fraud', 'identity_theft', 'card_fraud', 'other']

        # Initialize with comprehensive training data
        self._initialize_classifier()

    def _initialize_classifier(self):
        # Extended training data covering various fraud scenarios
        training_data = [
            # Transaction Fraud
            "unauthorized transaction on my account",
            "strange transactions I didn't make",
            "someone made purchases without my permission",
            "unexpected withdrawals from my account",
            "transactions I never authorized",

            # Card Fraud
            "someone stole my card and made purchases",
            "lost my credit card and see suspicious charges",
            "card was cloned and used at multiple locations",
            "found duplicate charges on my card",
            "my card was used online without permission",

            # Identity Theft
            "someone opened accounts in my name",
            "accounts I never created appearing on my credit report",
            "my personal information was used to open credit cards",
            "identity stolen and multiple accounts opened",
            "someone is using my SSN to open accounts",

            # Account Issues
            "can't access my online banking",
            "login credentials not working",
            "account showing wrong balance",
            "statement shows incorrect transactions",
            "account access blocked after suspicious activity",

            # Mixed/Other
            "received spam emails asking for bank details",
            "phishing attempt from fake bank website",
            "suspicious phone call claiming to be bank representative",
            "someone trying to change my account password",
            "email saying my account was compromised"
        ]

        # Labels corresponding to the training data
        labels = [
            # Transaction Fraud cases
            'transaction_fraud', 'transaction_fraud', 'transaction_fraud', 
            'transaction_fraud', 'transaction_fraud',

            # Card Fraud cases
            'card_fraud', 'card_fraud', 'card_fraud', 'card_fraud', 'card_fraud',

            # Identity Theft cases
            'identity_theft', 'identity_theft', 'identity_theft', 
            'identity_theft', 'identity_theft',

            # Account Issue cases
            'account_issue', 'account_issue', 'account_issue', 
            'account_issue', 'account_issue',

            # Other/Mixed cases
            'other', 'other', 'other', 'other', 'other'
        ]

        # Fit vectorizer and classifier
        X = self.vectorizer.fit_transform(training_data)
        self.classifier.fit(X, labels)
        logging.info(f"Classifier trained with {len(training_data)} examples across {len(set(labels))} categories")

    def classify_complaint(self, text: str) -> str:
        """Classify the complaint text into predefined categories."""
        X = self.vectorizer.transform([text])
        prediction = self.classifier.predict(X)
        logging.debug(f"Classified text as: {prediction[0]}")
        return prediction[0]