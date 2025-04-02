import pandas as pd
import logging
from typing import Dict, List, Any
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TransactionAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_transaction_data(self, csv_path: str) -> Dict[str, Any]:
        """Analyze transaction patterns from CSV data."""
        try:
            # Read CSV file
            df = pd.read_csv(csv_path)
            self.logger.info(f"Successfully read CSV file with columns: {df.columns.tolist()}")

            # Extract unique patterns
            patterns = {
                'transaction_types': set(),
                'channels': set(),
                'merchant_ids': set(),
                'device_ids': set()
            }

            # Analyze patterns
            patterns['transaction_types'] = df['TransactionType'].unique().tolist()
            patterns['channels'] = df['Channel'].unique().tolist()
            patterns['merchant_ids'] = df['MerchantID'].unique().tolist()
            patterns['device_ids'] = df['DeviceID'].unique().tolist()

            # Analyze transaction characteristics
            transactions = []
            for _, row in df.iterrows():
                tx = {
                    'transaction_id': row['TransactionID'],
                    'account_id': row['AccountID'],
                    'amount': row['TransactionAmount'],
                    'date': row['TransactionDate'],
                    'type': row['TransactionType'],
                    'channel': row['Channel'],
                    'location': row['Location'],
                    'merchant_id': row['MerchantID']
                }
                transactions.append(tx)

            # Log summary statistics
            self.logger.info(f"Found {len(transactions)} transactions")
            self.logger.info(f"Transaction types: {patterns['transaction_types']}")
            self.logger.info(f"Channels: {patterns['channels']}")

            return {
                'patterns': patterns,
                'transactions': transactions[:10]  # Return first 10 transactions for testing
            }

        except Exception as e:
            self.logger.error(f"Error analyzing transaction data: {str(e)}")
            raise

    def extract_transaction_details(self, text: str) -> Dict[str, Any]:
        """Extract transaction details from bank statement text."""
        details = {
            'debited_details': None,
            'credited_details': None,
            'transaction_id': None,
            'reference': None,
            'amount': None,
            'date': None
        }

        try:
            # Extract debit transaction (TO TRANSFER-UPI/DR)
            debit_pattern = r'TO TRANSFER-UPI/DR/(\d+)/([^/]+)/SBIN/([^/]+)/UPI'
            debit_match = re.search(debit_pattern, text)
            if debit_match:
                details['debited_details'] = {
                    'transaction_id': debit_match.group(1),
                    'reference': debit_match.group(2),
                    'account': f"SBIN{debit_match.group(3)}",
                    'type': 'Debit'
                }

            # Extract credit transaction (BY TRANSFER UPI/CR)
            credit_pattern = r'BY TRANSFER UPI/CR/(\d+)/(\d+)/([^/]+)/SBIN/(\d+)'
            credit_match = re.search(credit_pattern, text)
            if credit_match:
                details['credited_details'] = {
                    'transaction_id': credit_match.group(1),
                    'reference': credit_match.group(2),
                    'name': credit_match.group(3),
                    'account': f"SBIN{credit_match.group(4)}",
                    'type': 'Credit'
                }

            # Extract amount and date
            amount_pattern = r'(\d+\.\d{2})'
            date_pattern = r'(\d{2}-Mar-2022)'

            amount_match = re.search(amount_pattern, text)
            if amount_match:
                details['amount'] = float(amount_match.group(1))

            date_match = re.search(date_pattern, text)
            if date_match:
                details['date'] = date_match.group(1)

            return details

        except Exception as e:
            self.logger.error(f"Error extracting transaction details: {str(e)}")
            raise

if __name__ == "__main__":
    analyzer = TransactionAnalyzer()
    # Analyze CSV data
    patterns = analyzer.analyze_transaction_data("attached_assets/bank_transactions_data_2.csv")
    logger.info(f"Analyzed patterns: {patterns}")