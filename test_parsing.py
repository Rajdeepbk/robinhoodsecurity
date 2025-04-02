import logging
import unittest
from text_processing import TextProcessor

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestTransactionParsing(unittest.TestCase):
    def setUp(self):
        self.processor = TextProcessor()

    def test_upi_transaction(self):
        """Test UPI transaction extraction."""
        test_case = {
            "input": "21 Apr 2021 21 Apr 2021UPI/DR/111121066801/003001 5.00 51,947.00",
            "expected": {
                "date": "21-Apr-2021",
                "transaction_id": "111121066801",
                "amount": 5.00,
                "transaction_type": "DEBIT",
                "description": "21 Apr 2021 21 Apr 2021UPI/DR/111121066801/003001 5.00 51,947.00"
            }
        }
        self._verify_transaction_extraction(test_case)

    def test_upi_transfer_transaction(self):
        """Test UPI transfer transaction extraction."""
        test_case = {
            "input": "27 May 2021 27 MayTO TRANSFER- TRANSFER TO 706.00 39,360.00 UPI/DR/114714183538/Xpress",
            "expected": {
                "date": "27-May-2021",
                "transaction_id": "114714183538",
                "amount": 706.00,
                "transaction_type": "DEBIT",
                "description": "27 May 2021 27 MayTO TRANSFER- TRANSFER TO 706.00 39,360.00 UPI/DR/114714183538/Xpress"
            }
        }
        self._verify_transaction_extraction(test_case)

    def test_neft_transaction(self):
        """Test NEFT transaction extraction."""
        test_case = {
            "input": "17 Jun 2021 17 Jun 2021 TRANSFER TO NEFTIBKL0O000136ICMS210617000AI5 1,74,545.00 2,13,666.00",
            "expected": {
                "date": "17-Jun-2021",
                "transaction_id": "ICMS210617000AI5",
                "amount": 174545.00,
                "transaction_type": "DEBIT",
                "description": "17 Jun 2021 17 Jun 2021 TRANSFER TO NEFTIBKL0O000136ICMS210617000AI5 1,74,545.00 2,13,666.00"
            }
        }

        logger.info("\n" + "="*80)
        logger.info(f"Testing NEFT transaction extraction for:\n{test_case['input']}")
        details = self.processor.extract_transaction_details(test_case['input'])

        self.assertIsNotNone(details, f"Failed to extract details from: {test_case['input']}")
        self.assertIsInstance(details, dict, "Extracted details should be a dictionary")

        # Log full description comparison
        logger.info("\n=== Description Comparison ===")
        logger.info(f"Expected: ({len(test_case['expected']['description'])})")
        logger.info(test_case['expected']['description'])
        logger.info("\nGot: ({len(details['description'])})")
        logger.info(details['description'])
        logger.info("\nExpected repr:")
        logger.info(repr(test_case['expected']['description']))
        logger.info("\nGot repr:")
        logger.info(repr(details['description']))
        logger.info("=" * 40)

        # Check each field separately for better error reporting
        for field in ["date", "transaction_id", "amount", "transaction_type", "description"]:
            self.assertIn(field, details, f"Missing field {field} in extracted details")

            if field == "amount":
                self.assertAlmostEqual(
                    details[field],
                    test_case['expected'][field],
                    places=2,
                    msg=f"Amount mismatch. Expected: {test_case['expected'][field]}, Got: {details[field]}"
                )
            else:
                # Compare normalized strings
                self.assertEqual(
                    str(details[field]).strip(),
                    str(test_case['expected'][field]).strip(),
                    f"{field} mismatch.\nExpected: {test_case['expected'][field]}\nGot: {details[field]}"
                )

    def _verify_transaction_extraction(self, test_case):
        """Helper method to verify transaction extraction."""
        logger.info("\n" + "="*80)
        logger.info(f"Testing transaction extraction for:\n{test_case['input']}")
        details = self.processor.extract_transaction_details(test_case['input'])

        self.assertIsNotNone(details, f"Failed to extract details from: {test_case['input']}")
        self.assertIsInstance(details, dict, "Extracted details should be a dictionary")

        # Check each field separately for better error reporting
        for field in ["date", "transaction_id", "amount", "transaction_type", "description"]:
            self.assertIn(field, details, f"Missing field {field} in extracted details")

            logger.info(f"\nComparing {field}:")
            logger.info(f"  Expected ({len(str(test_case['expected'][field]))}): {repr(str(test_case['expected'][field]))}")
            logger.info(f"  Got      ({len(str(details[field]))}): {repr(str(details[field]))}")

            if field == "amount":
                self.assertAlmostEqual(
                    details[field],
                    test_case['expected'][field],
                    places=2,
                    msg=f"Amount mismatch. Expected: {test_case['expected'][field]}, Got: {details[field]}"
                )
            else:
                self.assertEqual(
                    str(details[field]).strip(),
                    str(test_case['expected'][field]).strip(),
                    f"{field} mismatch.\nExpected: {test_case['expected'][field]}\nGot: {details[field]}"
                )
        logger.info("="*80 + "\n")

    def test_parse_date(self):
        """Test date parsing with various formats."""
        test_cases = [
            {
                "input": "21 Apr 2021 21 Apr 2021UPI/DR/111121066801/003001",
                "expected": "21-Apr-2021"
            },
            {
                "input": "1 Apr2021 BY TRANSFER-INB",
                "expected": "01-Apr-2021"
            },
            {
                "input": "7)un2021( BY TRANSFER",
                "expected": "07-Jun-2021"
            },
            {
                "input": "27 May    2021",
                "expected": "27-May-2021"
            }
        ]

        for case in test_cases:
            logger.info(f"\nTesting date parsing for: {case['input']}")
            result = self.processor._parse_date(case['input'])
            self.assertEqual(
                result,
                case['expected'],
                f"Date parsing failed. Expected: {case['expected']}, Got: {result}"
            )

    def test_extract_transaction_id(self):
        """Test transaction ID extraction with various formats."""
        test_cases = [
            {
                "input": "UPI/DR/111121066801/003001",
                "expected_id": "111121066801",
                "expected_type": "DEBIT"
            },
            {
                "input": "UPI/CR/1111210/66801/PRADIP",
                "expected_id": "111121066801",
                "expected_type": "CREDIT"
            },
            {
                "input": "NEFTIBKL0O000136ICMS210617000AI5",
                "expected_id": "ICMS210617000AI5",
                "expected_type": "CREDIT"
            },
            {
                "input": "IMPS/P2A/UA0392811991M/XXX",
                "expected_id": "UA0392811991M",
                "expected_type": "CREDIT"
            }
        ]

        for case in test_cases:
            logger.info(f"\nTesting transaction ID extraction for: {case['input']}")
            tx_id, tx_type = self.processor._extract_transaction_id(case['input'])
            self.assertEqual(
                tx_id,
                case['expected_id'],
                f"Transaction ID extraction failed. Expected: {case['expected_id']}, Got: {tx_id}"
            )
            self.assertEqual(
                tx_type,
                case['expected_type'],
                f"Transaction type extraction failed. Expected: {case['expected_type']}, Got: {tx_type}"
            )

    def test_upi_credit_id_formats(self):
        """Test UPI credit ID extraction with different formats."""
        test_cases = [
            {
                "input": "UPI/CR/114714183538/PRADIP",  # Standard format
                "expected_id": "114714183538",
                "expected_type": "CREDIT"
            },
            {
                "input": "UPI/CR/1147141/83538/PRADIP",  # Split number format
                "expected_id": "114714183538",
                "expected_type": "CREDIT"
            }
        ]

        for case in test_cases:
            logger.info(f"\nTesting UPI credit ID extraction for: {case['input']}")
            logger.info(f"Expected ID: {case['expected_id']}, Type: {case['expected_type']}")
            tx_id, tx_type = self.processor._extract_transaction_id(case['input'])

            self.assertEqual(
                tx_id,
                case['expected_id'],
                f"Transaction ID mismatch.\nExpected: {case['expected_id']}\nGot: {tx_id}"
            )
            self.assertEqual(
                tx_type,
                case['expected_type'],
                f"Transaction type mismatch.\nExpected: {case['expected_type']}\nGot: {tx_type}"
            )

if __name__ == '__main__':
    unittest.main(verbosity=2)