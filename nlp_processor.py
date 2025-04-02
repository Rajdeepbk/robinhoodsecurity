import spacy
import re
from typing import Dict, Any, List, Tuple

class NLPProcessor:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")

    def process_text(self, text: str) -> Dict[str, Any]:
        doc = self.nlp(text.lower())

        # Extract all transaction details
        transactions = self._extract_all_transactions(text)

        # Extract key entities
        entities = {ent.label_: ent.text for ent in doc.ents}

        return {
            'transactions': transactions,
            'entities': entities,
            'processed_text': ' '.join([token.lemma_ for token in doc])
        }

    def _extract_all_transactions(self, text: str) -> List[Dict[str, Any]]:
        transactions = []
        # Find each transaction segment
        transaction_segments = []

        # First split by explicit transaction markers
        patterns = [
            r'first\s+transaction.*?(?=second\s+transaction|$)',
            r'second\s+transaction.*?(?=third\s+transaction|$)',
            r'third\s+transaction.*?(?=fourth\s+transaction|$)',
            r'(?:tx|transaction\s+(?:id|#|:)?\s*tx?)\d+.*?(?=(?:tx|transaction\s+(?:id|#|:)?\s*tx?)\d+|$)'
        ]

        last_end = 0
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                segment = text[match.start():match.end()].strip()
                if segment and len(segment.split()) >= 3:  # Minimum words for a valid segment
                    transaction_segments.append(segment)
                    last_end = match.end()

        # Process each transaction segment
        for segment in transaction_segments:
            # Extract transaction ID
            tx_id_match = re.search(r'\b(?:tx|transaction\s+(?:id|#|:)?\s*tx?)(\d+)\b', segment, re.IGNORECASE)
            if not tx_id_match:
                continue

            tx_id = f"TX{tx_id_match.group(1)}"

            # Extract amount
            amount_match = re.search(r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', segment)
            if not amount_match:
                continue

            amount = float(amount_match.group(1).replace(',', ''))

            # Extract reference ID
            ref_id = ""
            ref_match = re.search(r'ref(?:erence)?\s*(?:id|number|#)?\s*[:#]?\s*(\w+)', segment, re.IGNORECASE)
            if ref_match:
                ref_id = ref_match.group(1)

            # Extract parties
            parties = self._extract_transaction_parties(segment)

            if tx_id and amount > 0:
                transaction = {
                    'transaction_id': tx_id,
                    'reference_id': ref_id,
                    'amount': amount,
                    'parties': parties
                }
                transactions.append(transaction)

        return transactions

    def _extract_reference_id(self, text: str) -> str:
        patterns = [
            r'ref(?:erence)?\s*(?:id|number|#)?\s*[:#]?\s*(\w+)',
            r'confirmation\s*(?:id|number|#)?\s*[:#]?\s*(\w+)',
            r'tracking\s*(?:id|number|#)?\s*[:#]?\s*(\w+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def _extract_amount(self, text: str) -> float:
        # Match currency amounts with $ symbol
        pattern = r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        matches = re.finditer(pattern, text)
        for match in matches:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                continue
        return 0.0

    def _extract_transaction_parties(self, text: str) -> List[Dict[str, str]]:
        parties = []

        # Patterns for identifying senders and receivers
        sender_patterns = [
            r'from\s+(?:account\s+)?(\d{8,12})',
            r'(?:sender|from):\s*(\d{8,12})',
        ]

        receiver_patterns = [
            r'to\s+(?:account\s+)?(\d{8,12})',
            r'(?:receiver|to):\s*(\d{8,12})',
        ]

        # Extract sender information
        for pattern in sender_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                account_number = match.group(1)
                parties.append({
                    'type': 'sender',
                    'name': f'Account {account_number}',
                    'account_number': account_number
                })
                break

        # Extract receiver information
        for pattern in receiver_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                account_number = match.group(1)
                parties.append({
                    'type': 'receiver',
                    'name': f'Account {account_number}',
                    'account_number': account_number
                })
                break

        return parties