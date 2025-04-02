import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
from text_processing import TextProcessor
import re

class TransactionAI(TextProcessor):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Common fraud-related keywords
        self.fraud_keywords = [
            'unauthorized', 'fraud', 'scam', 'fake', 'stolen', 'suspicious',
            'unknown transaction', 'not recognize', 'didn\'t authorize',
            'wrong transaction', 'theft', 'fraudulent'
        ]
        super().__init__()

    def learn_from_pdf_statements(self, pdf_paths: List[str]) -> Dict[str, Any]:
        """Learn transaction patterns from bank statements in PDF format."""
        try:
            from text_extractor import TextExtractor
            extractor = TextExtractor()
            all_transactions = []

            for pdf_path in pdf_paths:
                # Extract text from PDF
                text = extractor.extract_text_from_pdf(pdf_path)
                # Extract transaction details
                details = self.extract_transaction_details(text)
                if details:
                    all_transactions.append(details)

            # Analyze transaction patterns
            if all_transactions:
                # Amount patterns
                amounts = [tx['amount'] for tx in all_transactions if 'amount' in tx]
                if amounts:
                    self.transaction_patterns['amount_thresholds'].update({
                        'pdf_mean': np.mean(amounts),
                        'pdf_std': np.std(amounts),
                        'pdf_max': max(amounts),
                        'pdf_min': min(amounts)
                    })

                # Transaction ID patterns
                transaction_ids = [tx['transaction_id'] for tx in all_transactions if 'transaction_id' in tx]
                self.transaction_patterns['upi_patterns'].update({
                    'id_length': len(transaction_ids[0]) if transaction_ids else 0,
                    'common_prefixes': self._find_common_prefixes(transaction_ids)
                })

                # Time patterns from dates
                dates = [tx['date'] for tx in all_transactions if 'date' in tx]
                if dates:
                    date_objects = [datetime.strptime(d, '%d-%b-%Y') for d in dates if d]
                    hours = [d.hour for d in date_objects]
                    self.transaction_patterns['time_patterns'].update({
                        'pdf_peak_hours': self._find_peak_hours(hours)
                    })

                return {
                    'patterns_learned': True,
                    'total_pdf_transactions': len(all_transactions),
                    'transaction_patterns': self.transaction_patterns
                }

            return {'patterns_learned': False, 'reason': 'No transactions found in PDFs'}

        except Exception as e:
            self.logger.error(f"Error learning from PDF statements: {str(e)}")
            return {'patterns_learned': False, 'error': str(e)}

    def learn_from_dataset(self, csv_path: str) -> Dict[str, Any]:
        """Learn transaction patterns from historical dataset."""
        try:
            df = pd.read_csv(csv_path)
            self.logger.info(f"Learning from dataset with {len(df)} transactions")

            # Learn amount patterns
            amount_stats = df['TransactionAmount'].agg(['mean', 'std', 'min', 'max'])
            self.transaction_patterns['amount_thresholds'].update({
                'mean': amount_stats['mean'],
                'std': amount_stats['std'],
                'min': amount_stats['min'],
                'max': amount_stats['max'],
                'q1': df['TransactionAmount'].quantile(0.25),
                'q3': df['TransactionAmount'].quantile(0.75),
                'max_normal': df['TransactionAmount'].quantile(0.95)
            })

            # Learn time patterns
            df['Hour'] = pd.to_datetime(df['TransactionDate']).dt.hour
            df['DayOfWeek'] = pd.to_datetime(df['TransactionDate']).dt.dayofweek
            self.transaction_patterns['time_patterns'].update({
                'peak_hours': df['Hour'].value_counts().nlargest(3).index.tolist(),
                'quiet_hours': df['Hour'].value_counts().nsmallest(3).index.tolist(),
                'weekday_patterns': df.groupby('DayOfWeek')['TransactionAmount'].agg(['mean', 'count']).to_dict()
            })

            # Learn velocity patterns
            df['TransactionDate'] = pd.to_datetime(df['TransactionDate'])
            velocity_patterns = {}
            for account in df['AccountID'].unique():
                account_txns = df[df['AccountID'] == account]
                if len(account_txns) > 1:
                    time_diffs = account_txns['TransactionDate'].diff()
                    velocity_patterns[account] = {
                        'avg_time_between_txns': time_diffs.mean().total_seconds(),
                        'min_time_between_txns': time_diffs.min().total_seconds() if not pd.isna(time_diffs.min()) else None,
                        'max_daily_txns': account_txns.groupby(account_txns['TransactionDate'].dt.date)['TransactionID'].count().max()
                    }
            self.transaction_patterns['velocity_checks'] = velocity_patterns

            # Learn customer behavior patterns
            customer_patterns = df.groupby('AccountID').agg({
                'TransactionAmount': ['mean', 'std', 'count', 'max'],
                'LoginAttempts': ['max', 'mean'],
                'TransactionDuration': ['mean', 'std'],
                'AccountBalance': ['mean', 'min']
            }).to_dict()
            self.transaction_patterns['customer_behavior'] = customer_patterns

            return {
                'patterns_learned': True,
                'total_csv_transactions': len(df),
                'transaction_patterns': self.transaction_patterns
            }

        except Exception as e:
            self.logger.error(f"Error learning from dataset: {str(e)}")
            return {'patterns_learned': False, 'error': str(e)}

    def analyze_transaction_risk(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze transaction risk based on learned patterns."""
        try:
            risk_factors = []
            risk_score = 0.0
            account_id = transaction.get('account_id')

            # Amount risk analysis
            amount = transaction.get('amount', 0)
            if amount > self.transaction_patterns['amount_thresholds'].get('max_normal', float('inf')):
                risk_score += 0.3
                risk_factors.append({
                    'type': 'amount',
                    'severity': 'high',
                    'detail': 'Transaction amount exceeds 95th percentile'
                })

            # Velocity check
            if account_id and account_id in self.transaction_patterns['velocity_checks']:
                velocity_pattern = self.transaction_patterns['velocity_checks'][account_id]
                if transaction.get('time_since_last_txn', float('inf')) < velocity_pattern['min_time_between_txns'] / 2:
                    risk_score += 0.2
                    risk_factors.append({
                        'type': 'velocity',
                        'severity': 'medium',
                        'detail': 'Unusually quick transaction after previous one'
                    })

            # Time pattern risk
            hour = transaction.get('hour', 0)
            if hour in self.transaction_patterns['time_patterns'].get('quiet_hours', []):
                risk_score += 0.1
                risk_factors.append({
                    'type': 'time',
                    'severity': 'low',
                    'detail': 'Transaction during unusual hours'
                })

            # UPI pattern check
            transaction_id = transaction.get('transaction_id', '')
            expected_length = self.transaction_patterns['upi_patterns'].get('id_length', 0)
            if expected_length and len(transaction_id) != expected_length:
                risk_score += 0.3
                risk_factors.append({
                    'type': 'upi_format',
                    'severity': 'high',
                    'detail': 'Unusual UPI transaction ID format'
                })

            risk_level = 'High' if risk_score > 0.7 else 'Medium' if risk_score > 0.3 else 'Low'

            return {
                'risk_score': min(risk_score, 1.0),
                'risk_level': risk_level,
                'risk_factors': risk_factors,
                'timestamp': datetime.now().isoformat(),
                'analysis_version': '2.1'
            }

        except Exception as e:
            self.logger.error(f"Error analyzing transaction risk: {str(e)}")
            return {
                'risk_score': 0.0,
                'risk_level': 'Unknown',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def _find_common_prefixes(self, transaction_ids: List[str]) -> Dict[str, int]:
        """Find common prefixes in transaction IDs."""
        prefixes = {}
        for tx_id in transaction_ids:
            if len(tx_id) >= 4:
                prefix = tx_id[:4]
                prefixes[prefix] = prefixes.get(prefix, 0) + 1
        return prefixes

    def _find_peak_hours(self, hours: List[int]) -> List[int]:
        """Find peak transaction hours."""
        if not hours:
            return []
        hour_counts = pd.Series(hours).value_counts()
        return hour_counts.nlargest(3).index.tolist()

    def analyze_pattern_significance(self, transaction: Dict[str, Any]) -> Dict[str, float]:
        """Analyze the significance of transaction patterns."""
        try:
            significance = {}

            # Amount significance
            if 'amount' in transaction:
                amount = transaction['amount']
                mean = self.transaction_patterns['amount_thresholds'].get('mean', 0)
                std = self.transaction_patterns['amount_thresholds'].get('std', 1)
                if std > 0:
                    z_score = abs(amount - mean) / std
                    significance['amount'] = min(1.0, z_score / 3.0)  # Cap at 1.0

            # Time significance
            if 'hour' in transaction:
                hour = transaction['hour']
                quiet_hours = self.transaction_patterns['time_patterns'].get('quiet_hours', [])
                significance['time'] = 1.0 if hour in quiet_hours else 0.0

            # Velocity significance
            if 'time_since_last_txn' in transaction:
                time_since_last = transaction['time_since_last_txn']
                min_time = self.transaction_patterns['velocity_checks'].get('min_time_between_txns', 300)
                if min_time > 0:
                    significance['velocity'] = min(1.0, min_time / time_since_last if time_since_last > 0 else 1.0)

            return significance

        except Exception as e:
            self.logger.error(f"Error analyzing pattern significance: {str(e)}")
            return {}

    def extract_transaction_details(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract transaction details using learned patterns."""
        try:
            # Check for debit transaction pattern
            debit_match = re.search(self.patterns['debit'], text)
            if debit_match:
                transaction_id = debit_match.group(1)
                transaction_type = "DEBIT"
            else:
                # Check for credit transaction pattern
                credit_match = re.search(self.patterns['credit'], text)
                if credit_match:
                    transaction_id = credit_match.group(1) + credit_match.group(2)
                    transaction_type = "CREDIT"
                else:
                    return None

            # Extract amount
            amount_match = re.search(self.patterns['amount'], text)
            amount = float(amount_match.group(1)) if amount_match else None

            # Try both date formats
            date = None
            date_match1 = re.search(self.patterns['date_format1'], text)
            date_match2 = re.search(self.patterns['date_format2'], text)
            if date_match1:
                date = f"{date_match1.group(1)}-{date_match1.group(2)}-{date_match1.group(3)}"
            elif date_match2:
                date = f"{date_match2.group(1)}-{date_match2.group(2)}-{date_match2.group(3)}"

            # Extract account number and name
            account_match = re.search(self.patterns['account'], text)
            name_match = re.search(self.patterns['name'], text)

            return {
                "transaction_type": transaction_type,
                "transaction_id": transaction_id,
                "amount": amount,
                "date": date,
                "account": f"SBIN{account_match.group(1)}" if account_match else None,
                "name": name_match.group(1) if name_match else None
            }

        except Exception as e:
            self.logger.error(f"Error extracting transaction details: {str(e)}")
            return None

    def match_transactions(self, text1: str, text2: str) -> Dict[str, Any]:
        """Match transactions between two entries using learned patterns."""
        try:
            # Extract details from both texts
            details1 = self.extract_transaction_details(text1)
            details2 = self.extract_transaction_details(text2)

            if not details1 or not details2:
                return {
                    "match": False,
                    "reason": "Could not extract details from one or both transactions"
                }

            # Compare transaction IDs
            ids_match = details1['transaction_id'] == details2['transaction_id']

            # Compare amounts (if both exist)
            amounts_match = (details1['amount'] is not None and
                           details2['amount'] is not None and
                           abs(details1['amount'] - details2['amount']) < 0.01)  # Handle floating point comparison

            # Determine which is debit and which is credit
            if details1['transaction_type'] == 'DEBIT':
                debit_entry, credit_entry = details1, details2
            else:
                debit_entry, credit_entry = details2, details1

            if ids_match and amounts_match:
                return {
                    "match": True,
                    "confidence": 1.0,
                    "details": {
                        "transaction_id": debit_entry['transaction_id'],
                        "amount": debit_entry['amount'],
                        "date": debit_entry['date'] or credit_entry['date'],
                        "debit_account": debit_entry['account'],
                        "debit_name": debit_entry['name'],
                        "credit_account": credit_entry['account'],
                        "credit_name": credit_entry['name']
                    },
                    "risk_analysis": self.analyze_transaction_risk({
                        "amount": debit_entry['amount'],
                        "date": debit_entry['date']
                    })
                }
            else:
                return {
                    "match": False,
                    "reason": "Transaction IDs or amounts don't match",
                    "details": {
                        "ids_match": ids_match,
                        "amounts_match": amounts_match,
                        "debit_amount": debit_entry.get('amount'),
                        "credit_amount": credit_entry.get('amount')
                    }
                }

        except Exception as e:
            self.logger.error(f"Error matching transactions: {str(e)}")
            return {"match": False, "reason": str(e)}

    def learn_from_example(self, debit_text: str, credit_text: str) -> bool:
        """Learn patterns from a matched transaction pair."""
        try:
            # Extract and validate transaction ID patterns
            debit_match = re.search(self.patterns['debit'], debit_text)
            credit_match = re.search(self.patterns['credit'], credit_text)

            if debit_match and credit_match:
                debit_id = debit_match.group(1)
                credit_id = credit_match.group(1) + credit_match.group(2)

                # Verify the pattern matches
                if debit_id == credit_id:
                    self.logger.info(f"Successfully learned transaction ID pattern: {debit_id}")
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error learning from example: {str(e)}")
            return False

    def analyze_text_content(self, text: str) -> Dict[str, Any]:
        """Analyze text content for fraud indicators."""
        try:
            text = text.lower()
            fraud_indicators = []

            # Check for fraud keywords
            for keyword in self.fraud_keywords:
                if keyword in text:
                    fraud_indicators.append(f"Found suspicious keyword: {keyword}")

            return {
                'is_fraudulent': len(fraud_indicators) > 0,
                'fraud_indicators': fraud_indicators,
                'analysis_timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error analyzing text content: {str(e)}")
            return {
                'is_fraudulent': False,
                'fraud_indicators': [],
                'error': str(e)
            }

    def extract_account_numbers(self, text: str) -> List[str]:
        """Extract potential account numbers from text."""
        try:
            # Common account number patterns
            patterns = [
                r'\b\d{6,12}\b',  # 6-12 digit numbers
                r'\b[A-Z]{2}\d{6,}\b',  # Bank code followed by numbers
                r'\bACCT\s*[:/#]?\s*\d+\b'  # ACCT followed by numbers
            ]

            account_numbers = []
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                account_numbers.extend(matches)

            return list(set(account_numbers))  # Remove duplicates

        except Exception as e:
            self.logger.error(f"Error extracting account numbers: {str(e)}")
            return []