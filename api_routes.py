from flask import Blueprint, request, jsonify
from models import Complaint, Transaction, TransactionParty, Account, db
from nlp_processor import NLPProcessor
from fraud_detector import FraudDetector
from email_parser import EmailParser
from complaint_classifier import ComplaintClassifier
from text_extractor import TextExtractor  # Add this import
import logging
import traceback
from datetime import datetime
import os

api_bp = Blueprint('api', __name__)

# Initialize components
nlp_processor = NLPProcessor()
fraud_detector = FraudDetector()
email_parser = EmailParser()
complaint_classifier = ComplaintClassifier()

@api_bp.route('/api/complaints', methods=['POST'])
def create_complaint():
    try:
        data = request.get_json()
        logging.info(f"Received complaint data: {data}")

        # Handle different sources
        if data.get('source') == 'email':
            parsed_data = email_parser.parse_email(data['content'])
            content = parsed_data['content']
        else:
            content = data['content']

        logging.info(f"Processing complaint content: {content}")

        # Process complaint text
        processed_data = nlp_processor.process_text(content)
        logging.info(f"Extracted data from complaint: {processed_data}")

        # Calculate fraud score and get indicators
        fraud_score, fraud_indicators = fraud_detector.calculate_fraud_score(processed_data['processed_text'])
        logging.info(f"Calculated fraud score: {fraud_score}")
        logging.info(f"Detected fraud indicators: {fraud_indicators}")

        # Classify complaint
        classification = complaint_classifier.classify_complaint(content)
        logging.info(f"Complaint classification: {classification}")

        # Create complaint record
        complaint = Complaint(
            source=data.get('source', 'web'),
            content=content,
            fraud_score=fraud_score,
            classification=classification,
            fraud_indicators=fraud_indicators
        )
        db.session.add(complaint)

        # Process all transactions found in the complaint
        for transaction_data in processed_data.get('transactions', []):
            logging.info(f"Processing transaction: {transaction_data}")

            # Create transaction record
            transaction = Transaction(
                complaint=complaint,
                transaction_id=transaction_data.get('transaction_id'),
                reference_id=transaction_data.get('reference_id'),
                amount=transaction_data.get('amount')
            )
            db.session.add(transaction)
            logging.info(f"Created transaction record: {transaction.transaction_id}")

            # Add transaction parties
            for party_info in transaction_data.get('parties', []):
                logging.info(f"Processing transaction party: {party_info}")

                # Check if account exists
                account = None
                if party_info.get('account_number'):
                    account = Account.query.filter_by(
                        account_number=party_info['account_number']
                    ).first()

                    # Create account if it doesn't exist
                    if not account and party_info.get('name'):
                        account = Account(
                            account_number=party_info['account_number'],
                            account_holder=party_info['name']
                        )
                        db.session.add(account)
                    logging.info(f"Found/Created account: {account.account_number if account else 'None'}")

                # Create transaction party record
                try:
                    party = TransactionParty(
                        complaint=complaint,
                        transaction=transaction,
                        account_id=account.id if account else None,
                        party_type=party_info['type'],
                        identified_name=party_info.get('name'),
                        account_number=party_info.get('account_number')
                    )
                    db.session.add(party)
                    logging.info(f"Created transaction party: {party.party_type} - {party.identified_name}")
                except Exception as party_error:
                    logging.error(f"Error creating transaction party: {str(party_error)}")
                    raise

        db.session.commit()
        logging.info(f"Successfully created complaint with ID: {complaint.id}")

        return jsonify(complaint.to_dict()), 201

    except Exception as e:
        error_details = traceback.format_exc()
        logging.error(f"Error processing complaint: {str(e)}\nTraceback:\n{error_details}")
        db.session.rollback()
        return jsonify({'error': 'Failed to process complaint', 'details': str(e)}), 500

@api_bp.route('/api/complaints', methods=['GET'])
def get_complaints():
    try:
        complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
        return jsonify([complaint.to_dict() for complaint in complaints])
    except Exception as e:
        logging.error(f"Error fetching complaints: {str(e)}")
        return jsonify({'error': 'Failed to fetch complaints'}), 500

@api_bp.route('/api/complaints/<int:complaint_id>', methods=['GET'])
def get_complaint(complaint_id):
    try:
        complaint = Complaint.query.get_or_404(complaint_id)
        return jsonify(complaint.to_dict())
    except Exception as e:
        logging.error(f"Error fetching complaint {complaint_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch complaint'}), 500

@api_bp.route('/api/sender-stats', methods=['GET'])
def get_sender_stats():
    """Get statistics about complaints per sender."""
    try:
        stats = TransactionParty.get_sender_complaint_stats()
        return jsonify([{
            'account_number': stat[0],
            'identified_name': stat[1],
            'complaint_count': stat[2]
        } for stat in stats])
    except Exception as e:
        logging.error(f"Error fetching sender stats: {str(e)}")
        return jsonify({'error': 'Failed to fetch sender statistics'}), 500

@api_bp.route('/api/accounts/<account_number>/complaints', methods=['GET'])
def get_account_complaints(account_number):
    """Get complaint history for a specific account."""
    try:
        account = Account.query.filter_by(account_number=account_number).first_or_404()
        history = account.get_complaint_history()
        stats = {
            'account_number': account_number,
            'account_holder': account.account_holder,
            'total_complaints': account.get_complaints_count(),
            'complaints': history
        }
        return jsonify(stats)
    except Exception as e:
        logging.error(f"Error fetching account complaints: {str(e)}")
        return jsonify({'error': 'Failed to fetch account complaints'}), 500

@api_bp.route('/api/fraud-patterns', methods=['GET'])
def get_fraud_patterns():
    """Get analysis of suspicious relationships and fraud patterns."""
    try:
        # Get suspicious sender-receiver relationships
        suspicious_relationships = TransactionParty.get_suspicious_relationships()

        # Get receivers with multiple fraud complaints
        fraud_patterns = TransactionParty.get_receiver_fraud_patterns()

        results = {
            'suspicious_relationships': [{
                'receiver_account': rel['receiver_account'],
                'complaint_count': rel['complaint_count'],
                'sender_accounts': rel['sender_accounts']
            } for rel in suspicious_relationships],
            'fraud_patterns': [{
                'account_number': pattern[0],
                'identified_name': pattern[1],
                'complaint_count': pattern[2],
                'average_fraud_score': float(pattern[3])
            } for pattern in fraud_patterns]
        }

        return jsonify(results)
    except Exception as e:
        logging.error(f"Error analyzing fraud patterns: {str(e)}")
        return jsonify({'error': 'Failed to analyze fraud patterns'}), 500

@api_bp.route('/api/transactions/match', methods=['POST'])
def match_transactions():
    """Find matching transactions based on provided criteria."""
    try:
        data = request.get_json()
        logging.info(f"Received transaction matching request with data: {data}")

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        required_fields = ['transaction_id', 'reference_id', 'amount']
        if not any(field in data for field in required_fields):
            return jsonify({
                'error': 'At least one of transaction_id, reference_id, or amount must be provided'
            }), 400

        # Convert date string to datetime if provided
        if 'transaction_date' in data:
            try:
                data['transaction_date'] = datetime.fromisoformat(data['transaction_date'])
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400

        matching_transactions = Transaction.find_matching_transactions(data)
        logging.info(f"Found {len(matching_transactions)} matching transactions")

        response_data = {
            'matches': [{
                'transaction_id': tx.transaction_id,
                'reference_id': tx.reference_id,
                'amount': tx.amount,
                'transaction_date': tx.transaction_date.isoformat() if tx.transaction_date else None,
                'is_reversed': tx.is_reversed,
                'reversal_transaction_id': tx.reversal_transaction_id,
                'parties': [{
                    'type': party.party_type,
                    'account_number': party.account_number,
                    'name': party.identified_name
                } for party in tx.transaction_parties]
            } for tx in matching_transactions]
        }

        logging.info(f"Returning matched transactions: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Error matching transactions: {str(e)}")
        return jsonify({'error': 'Failed to match transactions'}), 500

@api_bp.route('/api/transactions/<transaction_id>/reverse', methods=['POST'])
def reverse_transaction(transaction_id):
    """Initiate a reversal for the specified transaction."""
    try:
        logging.info(f"Attempting to reverse transaction: {transaction_id}")
        transaction = Transaction.query.filter_by(transaction_id=transaction_id).first_or_404()

        if transaction.is_reversed:
            logging.warning(f"Transaction {transaction_id} is already reversed")
            return jsonify({'error': 'Transaction is already reversed'}), 400

        logging.info("Initiating transaction reversal")
        if transaction.initiate_reversal():
            db.session.commit()
            logging.info(f"Successfully reversed transaction {transaction_id}")
            return jsonify({
                'message': 'Transaction reversal initiated successfully',
                'reversal_transaction_id': transaction.reversal_transaction_id
            })
        else:
            logging.error(f"Failed to initiate reversal for transaction {transaction_id}")
            return jsonify({'error': 'Failed to initiate transaction reversal'}), 400

    except Exception as e:
        logging.error(f"Error reversing transaction: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to reverse transaction'}), 500

@api_bp.route('/api/transactions/match-images', methods=['POST'])
def match_transaction_images():
    """Match transactions from two bank statement images."""
    try:
        if 'image1' not in request.files or 'image2' not in request.files:
            return jsonify({'error': 'Two images are required'}), 400

        image1 = request.files['image1']
        image2 = request.files['image2']

        logging.info(f"Processing bank statement images for matching")

        # Save images temporarily
        image1_path = os.path.join('attached_assets', 'temp_image1.png')
        image2_path = os.path.join('attached_assets', 'temp_image2.png')

        image1.save(image1_path)
        image2.save(image2_path)

        # Process images
        extractor = TextExtractor()
        results = extractor.match_transactions(image1_path, image2_path)

        logging.info(f"Raw extraction results: {results}")

        # Format the response with detailed matching information
        matched_transactions = []
        for match in results['matches']:
            transaction = {
                'date': match['date'],
                'amount': match['amount'],
                'debit_details': {
                    'reference': match['debit_refs'][0] if match['debit_refs'] else None,
                    'account_info': results['image1_details'].get('account_numbers', [])
                },
                'credit_details': {
                    'reference': match['credit_refs'][0] if match['credit_refs'] else None,
                    'account_info': results['image2_details'].get('account_numbers', [])
                },
                'confidence_score': 1.0 if (match['debit_refs'] and match['credit_refs']) else 0.8,
                'transaction_type': 'UPI' if any('UPI' in ref for ref in match['debit_refs'] + match['credit_refs']) else 'TRANSFER'
            }
            matched_transactions.append(transaction)
            logging.info(f"Found matching transaction: {transaction}")

        # Clean up temporary files
        try:
            os.remove(image1_path)
            os.remove(image2_path)
        except Exception as e:
            logging.warning(f"Error cleaning up temporary files: {str(e)}")

        response_data = {
            'matched_transactions': matched_transactions,
            'match_count': len(matched_transactions),
            'analysis_summary': {
                'total_amounts_analyzed': len(results['image1_details']['amounts'] + results['image2_details']['amounts']),
                'matching_confidence': 'HIGH' if all(t['confidence_score'] > 0.9 for t in matched_transactions) else 'MEDIUM',
                'transaction_types_found': list(set(t['transaction_type'] for t in matched_transactions))
            }
        }

        logging.info(f"Returning match results: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Error matching transaction images: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to match transactions', 'details': str(e)}), 500