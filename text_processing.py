import re
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher

class TextProcessor:
    # Class-level regex patterns
    PATTERNS = {
        # Transaction ID patterns with improved validation
        'upi_debit': re.compile(r'UPI/DR/(\d{9,12})/'),  # UPI debit with 9-12 digits
        'upi_credit': re.compile(r'UPI/CR/(\d{9,12})'),  # Credit ID as one continuous number
        'neft': re.compile(r'NEFT[A-Z0-9]*?([A-Z]{4}\d{9,}[A-Z0-9]*)'),  # NEFT with bank prefix and ID
        'imps': re.compile(r'IMPS/P2A/([A-Z0-9]{12,})/'),  # IMPS reference

        # Date and amount patterns
        'date': re.compile(r'(?:^|\s)(\d{1,2})\s*([A-Za-z]{3})(?:[\s-]*(\d{4}))'),
        'time': re.compile(r'(\d{2}):(\d{2})(?::(\d{2}))?'),  # Optional seconds
        'amount': re.compile(r'(?<![.\d])(\d+(?:,\d{2,3})*\.\d{2})(?![.\d])'),
    }

    # Match confidence thresholds
    MATCH_THRESHOLDS = {
        'id_similarity': 0.85,  # Minimum similarity ratio for fuzzy ID matching
        'amount_tolerance': 0.01,  # Maximum difference in amounts
        'time_window_minutes': 60  # Maximum time difference for same-day transactions
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.DEBUG)

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity ratio between two strings."""
        return SequenceMatcher(None, str1, str2).ratio()

    def _match_transaction_ids(self, id1: str, id2: str) -> Tuple[bool, float]:
        """Match transaction IDs with fuzzy matching support."""
        # Try exact match first
        if id1 == id2:
            return True, 1.0

        # Try fuzzy match if exact match fails
        similarity = self._calculate_similarity(id1, id2)
        is_match = similarity >= self.MATCH_THRESHOLDS['id_similarity']
        return is_match, similarity

    def _parse_transaction_time(self, text: str) -> Optional[datetime]:
        """Extract transaction time from text."""
        try:
            # Extract date first
            date_match = self.PATTERNS['date'].search(text)
            if not date_match:
                return None

            # Try to find time
            time_match = self.PATTERNS['time'].search(text)
            if not time_match:
                return None

            # Combine date and time
            day = int(date_match.group(1))
            month = date_match.group(2)
            year = int(date_match.group(3))

            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            second = int(time_match.group(3)) if time_match.group(3) else 0

            # Convert month name to number
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 
                'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            month_num = month_map.get(month.lower()[:3])

            if month_num:
                return datetime(year, month_num, day, hour, minute, second)
            return None

        except (ValueError, AttributeError) as e:
            self.logger.debug(f"Error parsing transaction time: {e}")
            return None

    def match_transactions(self, text1: str, text2: str) -> Dict[str, Any]:
        """Match transactions between two entries with enhanced matching logic."""
        self.logger.info("Starting transaction matching")
        try:
            details1 = self.extract_transaction_details(text1)
            details2 = self.extract_transaction_details(text2)

            if not details1 or not details2:
                self.logger.debug("Could not extract details from one or both transactions")
                return {
                    "match": False,
                    "reason": "Could not extract details from one or both transactions"
                }

            # Compare transaction IDs with fuzzy matching
            ids_match, similarity = self._match_transaction_ids(
                details1['transaction_id'],
                details2['transaction_id']
            )
            self.logger.debug(f"Transaction IDs similarity: {similarity:.2f}")

            # Compare amounts with tolerance
            amount_diff = abs(details1['amount'] - details2['amount'])
            amounts_match = amount_diff <= self.MATCH_THRESHOLDS['amount_tolerance']
            self.logger.debug(f"Amount difference: {amount_diff:.2f}")

            # Compare dates first
            date1 = datetime.strptime(details1['date'], '%d-%b-%Y')
            date2 = datetime.strptime(details2['date'], '%d-%b-%Y')
            dates_match = date1.date() == date2.date()
            self.logger.debug(f"Dates match: {dates_match}")

            # If dates don't match, return no match immediately
            if not dates_match:
                return {
                    "match": False,
                    "reason": "Transactions are on different days",
                    "details": {
                        "date1": details1['date'],
                        "date2": details2['date']
                    }
                }

            # Compare transaction times if available
            time1 = self._parse_transaction_time(text1)
            time2 = self._parse_transaction_time(text2)

            time_match = True
            if time1 and time2:
                time_diff = abs((time1 - time2).total_seconds()) / 60  # Convert to minutes
                time_match = time_diff <= self.MATCH_THRESHOLDS['time_window_minutes']
                self.logger.debug(f"Time difference (minutes): {time_diff:.2f}")
                self.logger.debug(f"Time match: {time_match}")

            if ids_match and amounts_match and time_match:
                # Determine debit and credit entries
                if details1['transaction_type'] == 'DEBIT':
                    debit_entry, credit_entry = details1, details2
                else:
                    debit_entry, credit_entry = details2, details1

                match_details = {
                    "match": True,
                    "confidence": similarity,
                    "details": {
                        "transaction_id": debit_entry['transaction_id'],
                        "amount": debit_entry['amount'],
                        "date": debit_entry['date'],
                        "time": time1.strftime('%H:%M:%S') if time1 else None,
                        "debit_type": debit_entry['transaction_type'],
                        "credit_type": credit_entry['transaction_type'],
                        "description": debit_entry['description']
                    }
                }
                self.logger.info(f"Found matching transaction with confidence: {similarity:.2f}")
                return match_details

            return {
                "match": False,
                "reason": "Transactions don't match",
                "details": {
                    "id_similarity": similarity,
                    "amount_diff": amount_diff,
                    "time_match": time_match,
                    "id1": details1['transaction_id'],
                    "id2": details2['transaction_id'],
                    "amount1": details1['amount'],
                    "amount2": details2['amount']
                }
            }

        except Exception as e:
            self.logger.error(f"Error matching transactions: {str(e)}")
            return {"match": False, "reason": str(e)}

    def extract_transaction_details(self, text: str) -> Dict[str, Any]:
        """Extract transaction details from text with enhanced bank format support."""
        self.logger.info("Starting transaction detail extraction")
        self.logger.debug(f"Processing text: {text}")

        try:
            if not isinstance(text, str) or not text.strip():
                self.logger.debug("Invalid or empty text input")
                return {}

            # Skip header lines
            if any(header in text.upper() for header in ["BRANCH DETAILS", "CUSTOMER DETAILS", "STATEMENT OF ACCOUNT"]):
                self.logger.debug("Skipping header line")
                return {}

            # Parse date first
            date = self._parse_date(text)
            if not date:
                self.logger.debug("No valid date found")
                return {}

            # Parse amount and balance
            amount, _ = self._parse_amount(text)
            if amount <= 0:
                self.logger.debug("No valid amount found")
                return {}

            # Extract transaction ID and type
            transaction_id, transaction_type = self._extract_transaction_id(text)
            if not transaction_id:
                self.logger.debug("No valid transaction ID found")
                return {}

            # Normalize description by removing extra whitespace
            description = ' '.join(text.strip().split())
            self.logger.debug(f"Final description ({len(description)}): {repr(description)}")

            details = {
                "transaction_type": transaction_type,
                "transaction_id": transaction_id,
                "amount": amount,
                "date": date,
                "description": description
            }

            self.logger.info("Successfully extracted transaction details")
            self.logger.debug(f"Final transaction details: {repr(details)}")
            return details

        except Exception as e:
            self.logger.error(f"Error in transaction detail extraction: {str(e)}")
            return {}

    def _parse_amount(self, text: str) -> Tuple[float, Optional[float]]:
        """Parse amount and balance from text."""
        self.logger.debug(f"Parsing amount from text: {text[:100]}...")
        try:
            # Try single amount pattern
            match = self.PATTERNS['amount'].search(text)
            if match:
                self.logger.debug(f"Found raw single amount: {match.group(1)}")
                amount = float(match.group(1).replace(',', ''))
                self.logger.debug(f"Converted single amount: {amount:.2f}")
                return amount, None

            self.logger.debug("No valid amount pattern found in text")
            return 0.0, None

        except ValueError as e:
            self.logger.error(f"Error parsing amount: {str(e)}")
            return 0.0, None

    def _parse_date(self, text: str) -> Optional[str]:
        """Parse date from text."""
        self.logger.debug(f"Parsing date from text: {text[:100]}...")
        try:
            # Try to match date pattern
            match = self.PATTERNS['date'].search(text)
            if match:
                self.logger.debug(f"Found date components: day={match.group(1)}, month={match.group(2)}, year={match.group(3)}")
                day = match.group(1).strip().zfill(2)
                month = match.group(2).strip().title()
                year = match.group(3).strip()

                # Fix common OCR errors in month names
                month_fixes = {
                    'lun': 'Jun',
                    'jul': 'Jul',
                    'lan': 'Jan',
                    '0ct': 'Oct',
                    'Nov': 'Nov',
                    'Dec': 'Dec'
                }
                original_month = month
                month = month_fixes.get(month.lower(), month)
                if month != original_month:
                    self.logger.debug(f"Fixed month: {original_month} -> {month}")

                # Validate month
                if month.lower()[:3] in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                                       'jul', 'aug', 'sep', 'oct', 'nov', 'dec']:
                    date_str = f"{day}-{month}-{year}"
                    self.logger.debug(f"Successfully parsed date: {date_str}")
                    return date_str

            self.logger.debug("No valid date pattern found in text")
            return None

        except Exception as e:
            self.logger.error(f"Error parsing date: {str(e)}")
            return None

    def _extract_transaction_id(self, text: str) -> Tuple[str, str]:
        """Extract transaction ID and type."""
        self.logger.debug(f"Extracting transaction ID from text: {text}")
        try:
            text_upper = text.upper()

            # Check UPI debit first
            debit_match = self.PATTERNS['upi_debit'].search(text)
            if debit_match:
                tx_id = debit_match.group(1)
                self.logger.debug(f"Found UPI debit match: {debit_match.group(0)}")
                if len(tx_id) >= 9:  # Validate ID length
                    self.logger.debug(f"Valid UPI debit ID found: {tx_id}")
                    return tx_id, "DEBIT"

            # Check UPI credit
            credit_match = self.PATTERNS['upi_credit'].search(text)
            if credit_match:
                # Handle both continuous and split formats
                tx_id = credit_match.group(1)  # Remove any slashes
                self.logger.debug(f"Found UPI credit match: {credit_match.group(0)}, ID after joining: {tx_id}")
                if len(tx_id) >= 9:  # Validate ID length
                    self.logger.debug(f"Valid UPI credit ID found: {tx_id}")
                    return tx_id, "CREDIT"

            # Check NEFT
            neft_match = self.PATTERNS['neft'].search(text)
            if neft_match:
                tx_id = neft_match.group(1)
                self.logger.debug(f"Found NEFT match: {neft_match.group(0)}")
                if len(tx_id) >= 12:  # Validate NEFT ID length
                    # Determine transaction type based on indicators
                    is_debit = any(x in text_upper for x in self.debit_indicators)
                    is_credit = any(x in text_upper for x in self.credit_indicators)
                    tx_type = "DEBIT" if is_debit and not is_credit else "CREDIT"
                    self.logger.debug(f"Valid NEFT {tx_type} ID found: {tx_id}, Indicators - Debit: {is_debit}, Credit: {is_credit}")
                    return tx_id, tx_type

            # Check IMPS
            imps_match = self.PATTERNS['imps'].search(text)
            if imps_match:
                tx_id = imps_match.group(1)
                self.logger.debug(f"Found IMPS match: {imps_match.group(0)}")
                if len(tx_id) >= 12:  # Validate IMPS ID length
                    # Use same indicator logic as NEFT
                    is_debit = any(x in text_upper for x in self.debit_indicators)
                    is_credit = any(x in text_upper for x in self.credit_indicators)
                    tx_type = "DEBIT" if is_debit and not is_credit else "CREDIT"
                    self.logger.debug(f"Valid IMPS {tx_type} ID found: {tx_id}, Indicators - Debit: {is_debit}, Credit: {is_credit}")
                    return tx_id, tx_type

            self.logger.debug("No valid transaction ID pattern found in text")
            return "", ""

        except Exception as e:
            self.logger.error(f"Error extracting transaction ID: {str(e)}")
            return "", ""

    debit_indicators = [
        "TRANSFER TO",
        "TO TRANSFER",
        "DEBIT",
        "PAID",
        "WITHDRAWAL",
        "UPI/DR/"
    ]
    credit_indicators = [
        "BY TRANSFER",
        "TRANSFER BY",
        "CREDIT",
        "RECEIVED",
        "UPI/CR/"
    ]