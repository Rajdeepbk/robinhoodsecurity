import re
import logging
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from typing import Dict, Any, List, Optional, Tuple
from text_processing import TextProcessor

class TextExtractor(TextProcessor):
    def __init__(self):
        super().__init__()
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)

    def _combine_transaction_lines(self, lines: List[str]) -> List[str]:
        """Combine multi-line transactions into single lines."""
        combined_lines = []
        current_line = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line starts with a date pattern
            if self.PATTERNS['transaction_line'].match(line):
                if current_line:
                    combined_lines.append(current_line)
                current_line = line
            elif current_line:
                # Only append if line contains relevant transaction info
                if any(key in line for key in ['TRANSFER', 'UPI', 'NEFT', 'ATM', 'IMPS']):
                    current_line += " " + line

        if current_line:
            combined_lines.append(current_line)

        return combined_lines

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from a PDF file using OCR."""
        try:
            self.logger.info(f"Converting PDF to images: {pdf_path}")
            images = convert_from_path(
                pdf_path,
                dpi=300,
                grayscale=True,
                thread_count=2
            )

            pages_text = []
            for i, image in enumerate(images):
                self.logger.info(f"Processing page {i+1}")
                image = image.convert('L')  # Convert to grayscale

                # Configure tesseract for better accuracy with numbers
                custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz/-.,:() "'
                text = pytesseract.image_to_string(image, config=custom_config)

                # Process each line for transactions
                if text.strip():
                    self.logger.debug(f"Page {i+1} raw text: {text[:500]}")

                    # Combine multi-line transactions
                    lines = text.split('\n')
                    transaction_lines = self._combine_transaction_lines(lines)

                    # Process each transaction
                    for line in transaction_lines:
                        details = self.extract_transaction_details(line)
                        if details:
                            self.logger.debug(f"Found transaction: {details}")
                else:
                    self.logger.warning(f"No text extracted from page {i+1}")

                pages_text.append(text)

            complete_text = "\n".join(pages_text)
            return complete_text

        except Exception as e:
            self.logger.error(f"Error extracting text from PDF: {str(e)}")
            raise

    def process_transactions(self, text: str) -> List[Dict[str, Any]]:
        """Process extracted text to identify and analyze transactions."""
        transactions = []
        try:
            # Split and combine transaction lines
            lines = text.split('\n')
            transaction_lines = self._combine_transaction_lines(lines)

            # Process each transaction line
            for line in transaction_lines:
                details = self.extract_transaction_details(line)
                if details:
                    transactions.append(details)
                    self.logger.debug(f"Processed transaction: {details}")

            # Log summary
            if transactions:
                self.logger.info(f"Total transactions identified: {len(transactions)}")
                amounts = [t['amount'] for t in transactions if 'amount' in t]
                if amounts:
                    self.logger.info(f"Amount range: {min(amounts)} to {max(amounts)}")
            else:
                self.logger.warning("No transactions found in text")

            return transactions

        except Exception as e:
            self.logger.error(f"Error processing transactions: {str(e)}")
            return []

    def match_transactions_from_files(self, image1_path: str, image2_path: str) -> Dict[str, Any]:
        """Match transactions between two bank statement images/PDFs."""
        try:
            # Extract text from both files
            text1 = self.extract_text_from_pdf(image1_path) if image1_path.lower().endswith('.pdf') else self.extract_text_from_image(image1_path)
            text2 = self.extract_text_from_pdf(image2_path) if image2_path.lower().endswith('.pdf') else self.extract_text_from_image(image2_path)

            # Process transactions from both texts
            transactions1 = self.process_transactions(text1)
            transactions2 = self.process_transactions(text2)

            matches = []
            for tx1 in transactions1:
                for tx2 in transactions2:
                    match_result = self.match_transactions(tx1.get('description', ''), tx2.get('description', ''))
                    if match_result.get('match'):
                        matches.append({
                            'tx1': tx1,
                            'tx2': tx2,
                            'match_details': match_result
                        })

            return {
                "match": bool(matches),
                "matches": matches,
                "total_transactions1": len(transactions1),
                "total_transactions2": len(transactions2)
            }

        except Exception as e:
            self.logger.error(f"Error matching transactions from files: {str(e)}")
            raise

    def extract_text_from_image(self, image_path: str) -> str:
        """Extract text from a single image file."""
        try:
            self.logger.info(f"Processing image: {image_path}")
            image = Image.open(image_path)
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(image, config=custom_config)

            # Log sample of extracted text
            if text.strip():
                sample = text[:200].replace('\n', ' ')
                self.logger.debug(f"Extracted text sample: {sample}...")
            else:
                self.logger.warning("No text extracted from image")

            return text
        except Exception as e:
            self.logger.error(f"Error extracting text from image: {str(e)}")
            raise

    def match_transactions(self, text1: str, text2: str) -> Dict[str, Any]:
        """Match transactions between two bank statements."""
        try:
            details1 = self.extract_transaction_details(text1)
            details2 = self.extract_transaction_details(text2)

            if not details1 or not details2:
                return {
                    "match": False,
                    "reason": "Could not extract details from one or both transactions"
                }

            # Compare transaction IDs and amounts
            ids_match = details1['transaction_id'] == details2['transaction_id']
            amounts_match = (details1['amount'] is not None and
                           details2['amount'] is not None and
                           abs(details1['amount'] - details2['amount']) < 0.01)

            if ids_match and amounts_match:
                # Determine debit and credit entries
                if details1['transaction_type'] == 'DEBIT':
                    debit_tx, credit_tx = details1, details2
                else:
                    debit_tx, credit_tx = details2, details1

                return {
                    "match": True,
                    "confidence": 1.0,
                    "details": {
                        "transaction_id": debit_tx['transaction_id'],
                        "amount": debit_tx['amount'],
                        "date": debit_tx['date'] or credit_tx['date'],
                        "debit_account": debit_tx['account'],
                        "debit_name": debit_tx['name'],
                        "credit_account": credit_tx['account'],
                        "credit_name": credit_tx['name']
                    }
                }
            else:
                return {
                    "match": False,
                    "reason": "Transaction IDs or amounts don't match",
                    "details": {
                        "ids_match": ids_match,
                        "amounts_match": amounts_match
                    }
                }

        except Exception as e:
            self.logger.error(f"Error matching transactions: {str(e)}")
            raise

    def extract_transaction_details(self, text: str) -> Dict[str, Any]:
        """Extract transaction details from bank statement."""
        try:
            #Simplified extraction for demonstration
            amount_match = re.search(r'(\d+(?:\.\d{2})?)', text)
            id_match = re.search(r'(\d+)', text) #Simplified ID extraction

            if amount_match and id_match:
                amount = float(amount_match.group(1))
                transaction_id = id_match.group(1)
                return {
                    'transaction_type': 'DEBIT', #Simplified type
                    'transaction_id': transaction_id,
                    'amount': amount,
                    'date': None,
                    'account': None,
                    'name': None,
                    'description': text #Added description field
                }
            else:
                return {}

        except Exception as e:
            self.logger.error(f"Error extracting transaction details: {str(e)}")
            raise
    def _log_transaction_patterns_in_page(self, text: str, page_num: int):
        """Log transaction patterns found in a specific page."""
        try:
            # Regular expressions for various patterns
            patterns = {
                'dates': r'\d{2}(?:-|\s+)[A-Za-z]{3}(?:-|\s+)\d{4}',
                'amounts': r'(?:Rs\.|\$|₹)?\s*\d+(?:,\d{3})*(?:\.\d{2})?',
                'upi_refs': r'(?:UPI/[DR][DR]/\d+|UPI[/-][A-Z]+)',
                'account_refs': r'SBIN\d+',
                'transfer_refs': r'(?:TO|BY)\s+TRANSFER',
            }

            for pattern_name, pattern in patterns.items():
                matches = re.findall(pattern, text)
                if matches:
                    self.logger.debug(f"Page {page_num} - Found {pattern_name}: {matches[:3]}")

            # Look for specific transaction lines
            transaction_lines = [line for line in text.split('\n')
                                  if any(key in line for key in ['TRANSFER', 'UPI', 'NEFT', 'ATM'])]
            if transaction_lines:
                self.logger.debug(f"Page {page_num} - Transaction lines found: {len(transaction_lines)}")
                for line in transaction_lines[:3]:  # Log first 3 transaction lines
                    self.logger.debug(f"Sample transaction: {line}")

        except Exception as e:
            self.logger.error(f"Error analyzing patterns on page {page_num}: {str(e)}")