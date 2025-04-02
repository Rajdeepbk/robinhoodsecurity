import logging
import os
from datetime import datetime
from text_processing import TextProcessor
from text_extractor import TextExtractor
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def store_transaction(conn, transaction: dict):
    """Store a transaction in the database."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO transactions (
                    transaction_id, transaction_type, amount, date, 
                    category, bank, account_number, account_name, 
                    reference_number
                ) VALUES (
                    %(transaction_id)s, %(transaction_type)s, %(amount)s, 
                    %(date)s, %(category)s, %(bank)s, %(account_number)s, 
                    %(account_name)s, %(reference_number)s
                )
            """, {
                'transaction_id': transaction.get('transaction_id'),
                'transaction_type': transaction.get('transaction_type'),
                'amount': transaction.get('amount'),
                'date': transaction.get('date'),
                'category': transaction.get('category', 'OTHER'),
                'bank': transaction.get('bank', 'Unknown'),
                'account_number': transaction.get('account'),
                'account_name': transaction.get('name'),
                'reference_number': transaction.get('reference', '')
            })
        conn.commit()
    except Exception as e:
        logger.error(f"Error storing transaction: {e}")
        conn.rollback()

def analyze_bank_statement(pdf_path: str):
    """Analyze transactions from a bank statement PDF."""
    try:
        processor = TextProcessor()
        extractor = TextExtractor()

        # Extract text from PDF
        logger.info(f"Processing PDF: {pdf_path}")
        text = extractor.extract_text_from_pdf(pdf_path)

        # Process each line
        transactions = []
        transaction_types = set()
        amounts = []
        categories = set()

        # Process transactions
        for line in text.split('\n'):
            if line.strip():
                details = processor.extract_transaction_details(line)
                if details:
                    transactions.append(details)
                    transaction_types.add(details['transaction_type'])
                    amounts.append(details['amount'])
                    if 'category' in details:
                        categories.add(details['category'])

        # Analysis summary
        logger.info("\nBank Statement Analysis:")
        logger.info(f"Total Transactions Found: {len(transactions)}")
        logger.info(f"Transaction Types: {sorted(list(transaction_types))}")
        logger.info(f"Transaction Categories: {sorted(list(categories))}")

        if amounts:
            logger.info(f"Amount Range: ₹{min(amounts):,.2f} to ₹{max(amounts):,.2f}")
            logger.info(f"Total Volume: ₹{sum(amounts):,.2f}")

        # Store transactions in database
        try:
            conn = psycopg2.connect(os.environ['DATABASE_URL'])
            for tx in transactions:
                store_transaction(conn, tx)
            logger.info(f"Stored {len(transactions)} transactions in database")
        except Exception as e:
            logger.error(f"Database error: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

        # Sample transactions by category
        logger.info("\nSample Transactions by Category:")
        for category in sorted(categories):
            samples = [t for t in transactions if t.get('category') == category][:2]
            logger.info(f"\n{category} Transactions:")
            for sample in samples:
                logger.info(f"  - Amount: ₹{sample['amount']:,.2f}")
                logger.info(f"    ID: {sample['transaction_id']}")
                logger.info(f"    Type: {sample['transaction_type']}")
                if sample.get('date'):
                    logger.info(f"    Date: {sample['date']}")

        return {
            'total_transactions': len(transactions),
            'transaction_types': sorted(list(transaction_types)),
            'categories': sorted(list(categories)),
            'amount_range': {'min': min(amounts), 'max': max(amounts)} if amounts else None,
            'total_volume': sum(amounts) if amounts else 0
        }

    except Exception as e:
        logger.error(f"Error analyzing bank statement: {str(e)}")
        return None

if __name__ == "__main__":
    # Analyze the bank statement
    pdf_path = "attached_assets/1658603571698VPRlXJHTHVrmjZMq.pdf" 
    result = analyze_bank_statement(pdf_path)
    if result:
        logger.info("\nAnalysis Summary:")
        for key, value in result.items():
            logger.info(f"{key}: {value}")