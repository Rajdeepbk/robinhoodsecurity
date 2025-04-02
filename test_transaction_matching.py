import logging
import unittest
from datetime import datetime
from text_processing import TextProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestTransactionMatching(unittest.TestCase):
    def setUp(self):
        self.processor = TextProcessor()

    def test_exact_match_upi(self):
        """Test matching of UPI transactions with exact ID match."""
        debit = "21 Apr 2021 10:15 UPI/DR/114714183538/Rajdeep/SBIN/3726267244/UPI- 300.00"
        credit = "21 Apr 2021 10:15 UPI/CR/114714183538/PRADIP K/SBIN/94356457795/UPI 300.00"

        result = self.processor.match_transactions(debit, credit)
        self.assertTrue(result['match'])
        self.assertEqual(result['confidence'], 1.0)
        self.assertEqual(result['details']['transaction_id'], "114714183538")
        self.assertEqual(result['details']['amount'], 300.00)

    def test_fuzzy_match_upi(self):
        """Test fuzzy matching of slightly mismatched UPI IDs."""
        # Same transaction with slightly different ID formatting
        debit = "21 Apr 2021 10:15 UPI/DR/114714183538/Rajdeep 300.00"
        credit = "21 Apr 2021 10:16 UPI/CR/114714183538/PRADIP 300.00"

        result = self.processor.match_transactions(debit, credit)
        self.assertTrue(result['match'])
        self.assertGreaterEqual(result['confidence'], 0.85)

    def test_time_based_matching(self):
        """Test matching transactions within the same time window."""
        # Same transaction recorded few minutes apart
        debit = "21 Apr 2021 10:15:00 NEFTIBKL0000012345678 Transfer To 5000.00"
        credit = "21 Apr 2021 10:20:00 NEFTIBKL0000012345678 Credit 5000.00"

        result = self.processor.match_transactions(debit, credit)
        self.assertTrue(result['match'])
        self.assertTrue(result['details']['time'] is not None)

    def test_no_match_different_amounts(self):
        """Test rejection of transactions with different amounts."""
        debit = "21 Apr 2021 UPI/DR/114714183538/Transfer 300.00"
        credit = "21 Apr 2021 UPI/CR/114714183538/Received 301.00"

        result = self.processor.match_transactions(debit, credit)
        self.assertFalse(result['match'])
        self.assertEqual(result['reason'], "Transactions don't match")

    def test_neft_transaction_match(self):
        """Test matching of NEFT transactions."""
        debit = "17 Jun 2021 NEFTIBKL0O000136ICMS210617000AI5 Transfer To 174545.00"
        credit = "17 Jun 2021 NEFTIBKL0O000136ICMS210617000AI5 Credit 174545.00"

        result = self.processor.match_transactions(debit, credit)
        self.assertTrue(result['match'])
        self.assertEqual(result['details']['transaction_id'], "ICMS210617000AI5")

    def test_imps_transaction_match(self):
        """Test matching of IMPS transactions."""
        debit = "15 May 2021 IMPS/P2A/UA0392811991M/Transfer 1000.00"
        credit = "15 May 2021 IMPS/P2A/UA0392811991M/Received 1000.00"

        result = self.processor.match_transactions(debit, credit)
        self.assertTrue(result['match'])
        self.assertEqual(result['details']['transaction_id'], "UA0392811991M")

    def test_different_day_no_match(self):
        """Test rejection of similar transactions on different days."""
        debit = "21 Apr 2021 UPI/DR/114714183538/Transfer 300.00"
        credit = "22 Apr 2021 UPI/CR/114714183538/Received 300.00"

        result = self.processor.match_transactions(debit, credit)
        self.assertFalse(result['match'])

if __name__ == '__main__':
    unittest.main(verbosity=2)