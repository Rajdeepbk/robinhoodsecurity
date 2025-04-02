import logging
from transaction_ai import TransactionAI
import pandas as pd
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_fraud_detection():
    """Test the AI's transaction analysis and fraud detection capabilities."""
    try:
        # Initialize AI
        ai = TransactionAI()

        # Learn from CSV dataset first
        csv_path = 'attached_assets/bank_transactions_data_2 (1).csv'
        csv_learning_results = ai.learn_from_dataset(csv_path)

        logger.info("\nCSV Learning Results:")
        logger.info(f"Total Transactions Analyzed: {csv_learning_results.get('total_csv_transactions', 0)}")

        # Learn from PDF statements
        pdf_paths = [
            'attached_assets/1627730510979F1GHiZKAdcMiPmn1.pdf',
            'attached_assets/1631124804933aED6HNlmmjcabJ4Q.pdf'
        ]
        pdf_learning_results = ai.learn_from_pdf_statements(pdf_paths)

        logger.info("\nPDF Learning Results:")
        logger.info(f"Total PDF Transactions: {pdf_learning_results.get('total_pdf_transactions', 0)}")

        # Test pattern recognition
        if csv_learning_results.get('patterns_learned'):
            patterns = csv_learning_results['transaction_patterns']

            logger.info("\nLearned Patterns:")
            logger.info(f"Amount Thresholds: {patterns['amount_thresholds']}")
            logger.info(f"Peak Transaction Hours: {patterns['time_patterns']['peak_hours']}")
            logger.info(f"UPI Patterns: {patterns.get('upi_patterns', {})}")

            # Test risk analysis with various scenarios
            test_cases = [
                {
                    'name': 'High Amount Late Night Transaction',
                    'transaction': {
                        'amount': 5000.0,
                        'hour': 2,
                        'location': 'Unknown Location',
                        'device_id': 'NEW_DEVICE_123',
                        'login_attempts': 3,
                        'channel': 'Online',
                        'customer_age': 65,
                        'transaction_id': '207823693675'
                    }
                },
                {
                    'name': 'Unusual UPI Format Transaction',
                    'transaction': {
                        'amount': 1000.0,
                        'hour': 14,
                        'location': 'Mumbai',
                        'device_id': 'D000123',
                        'login_attempts': 1,
                        'channel': 'UPI',
                        'customer_age': 25,
                        'transaction_id': '12345'  # Incorrect format
                    }
                },
                {
                    'name': 'Quick Successive Transactions',
                    'transaction': {
                        'amount': 750.0,
                        'hour': 15,
                        'location': 'Los Angeles',
                        'device_id': 'D000456',
                        'login_attempts': 1,
                        'channel': 'Online',
                        'customer_age': 30,
                        'account_id': 'AC00123',
                        'time_since_last_txn': 60,  # seconds
                        'transaction_id': '207823693999'
                    }
                }
            ]

            logger.info("\nRisk Analysis Tests:")
            for test_case in test_cases:
                logger.info(f"\nTesting: {test_case['name']}")
                risk_analysis = ai.analyze_transaction_risk(test_case['transaction'])
                logger.info(f"Risk Score: {risk_analysis['risk_score']}")
                logger.info(f"Risk Level: {risk_analysis['risk_level']}")
                logger.info("Risk Factors:")
                for factor in risk_analysis['risk_factors']:
                    logger.info(f"- {factor['type']} (Severity: {factor['severity']}): {factor['detail']}")

                # Analyze pattern significance
                significance = ai.analyze_pattern_significance(test_case['transaction'])
                logger.info("\nPattern Significance:")
                for pattern, score in significance.items():
                    logger.info(f"- {pattern}: {score:.2f}")

        return {
            'csv_learning': csv_learning_results,
            'pdf_learning': pdf_learning_results
        }

    except Exception as e:
        logger.error(f"Error testing fraud detection: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    test_fraud_detection()