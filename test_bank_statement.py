import logging
from text_processing import TextProcessor
from text_extractor import TextExtractor

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_bank_statement():
    """Test extraction and matching of bank statement transactions."""
    try:
        pdf_path = "attached_assets/1658603571698VPRlXJHTHVrmjZMq.pdf"
        processor = TextProcessor()
        extractor = TextExtractor()

        logger.info(f"\nProcessing bank statement: {pdf_path}")
        text = extractor.extract_text_from_pdf(pdf_path)

        # Test specific transaction patterns
        test_cases = [
            # UPI transactions with split IDs
            {
                "debit": "21 Apr 2021 21 Apr 2021UPI/DR/111121066801/003001 5.00 51,947.00",
                "credit": "21 Apr 2021 21 Apr 2021UPI/CR/1111210/66801/PRADIP 5.00 51,947.00",
                "expected_id": "111121066801",
                "expected_amount": 5.00,
                "expected_date": "21-Apr-2021"
            },
            # NEFT transactions
            {
                "debit": "17 Jun 2021 17 Jun 2021 NEFTIBKL0O000136ICMS210617000AI5 1,74,545.00 2,13,666.00",
                "credit": "17 Jun 2021 17 Jun 2021 NEFTIBKL0O000136ICMS210617000AI5 1,74,545.00 2,13,666.00",
                "expected_id": "ICMS210617000AI5",
                "expected_amount": 174545.00,
                "expected_date": "17-Jun-2021"
            },
            # Regular UPI transactions
            {
                "debit": "27 May 2021 27 MayTO TRANSFER- TRANSFER TO 706.00 39,360.00 UPI/DR/114714183538/Xpress",
                "credit": "27 May 2021 27 MayBY TRANSFER UPI/CR/1147141/83538/PRADIP 706.00 39,360.00",
                "expected_id": "114714183538",
                "expected_amount": 706.00,
                "expected_date": "27-May-2021"
            }
        ]

        logger.info("\nTesting Transaction Pattern Matching:")
        successes = []
        failures = []

        for i, case in enumerate(test_cases, 1):
            logger.info(f"\nTest Case {i}:")
            logger.info(f"Debit Line: {case['debit']}")
            logger.info(f"Credit Line: {case['credit']}")

            # Test debit transaction extraction
            debit_details = processor.extract_transaction_details(case['debit'])
            logger.info("\nDebit Transaction Details:")
            if debit_details:
                for key, value in debit_details.items():
                    logger.info(f"  {key}: {value}")

            # Test credit transaction extraction
            credit_details = processor.extract_transaction_details(case['credit'])
            logger.info("\nCredit Transaction Details:")
            if credit_details:
                for key, value in credit_details.items():
                    logger.info(f"  {key}: {value}")

            # Test transaction matching
            match_result = processor.match_transactions(case['debit'], case['credit'])
            logger.info(f"\nMatch Result: {match_result}")

            # Verify expected values
            test_passed = True
            if debit_details:
                if debit_details['transaction_id'] != case['expected_id']:
                    logger.error(f"✗ Transaction ID mismatch. Expected: {case['expected_id']}, Got: {debit_details['transaction_id']}")
                    test_passed = False
                if abs(debit_details['amount'] - case['expected_amount']) > 0.01:
                    logger.error(f"✗ Amount mismatch. Expected: {case['expected_amount']}, Got: {debit_details['amount']}")
                    test_passed = False
                if debit_details['date'] != case['expected_date']:
                    logger.error(f"✗ Date mismatch. Expected: {case['expected_date']}, Got: {debit_details['date']}")
                    test_passed = False
            else:
                logger.error("✗ Failed to extract debit transaction details")
                test_passed = False

            if test_passed:
                successes.append(i)
                logger.info("✓ Test case passed")
            else:
                failures.append(i)
                logger.error("✗ Test case failed")

        logger.info("\nTest Summary:")
        logger.info(f"Total test cases: {len(test_cases)}")
        logger.info(f"Passed: {len(successes)} - Cases: {successes}")
        logger.info(f"Failed: {len(failures)} - Cases: {failures}")

        return {
            'test_cases': len(test_cases),
            'successes': len(successes),
            'failures': len(failures),
            'success_rate': len(successes) / len(test_cases) if test_cases else 0
        }

    except Exception as e:
        logger.error(f"Error testing bank statement: {str(e)}", exc_info=True)
        return {
            'test_cases': 0,
            'success': False,
            'error': str(e)
        }

if __name__ == "__main__":
    test_bank_statement()