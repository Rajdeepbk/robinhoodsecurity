from datetime import datetime
from app import db
from typing import Dict, Any, List, Tuple
from sqlalchemy import func, distinct
from services.notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)


class BankAuthority(db.Model):
    """Store bank authority credentials."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    bank_code = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'bank_code': self.bank_code,
            'is_active': self.is_active
        }


class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(50), unique=True, nullable=False)
    account_holder = db.Column(db.String(100), nullable=False)
    is_blocked = db.Column(db.Boolean, default=False)  # For fraud prevention
    bank_identifier = db.Column(db.String(20))  # Bank specific identifier
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship with TransactionParty
    transaction_parties = db.relationship('TransactionParty',
                                          backref='linked_account',
                                          lazy=True)

    def block_account(self) -> bool:
        """Block this account and record the action."""
        try:
            if not self.is_blocked:
                self.is_blocked = True
                # Create block history record
                block_history = AccountBlockHistory(
                    account_id=self.id,
                    reason="Fraud detected - Account blocked automatically",
                    block_type="FRAUD",
                    status="COMPLETED",
                    api_response={
                        'timestamp': datetime.utcnow().isoformat(),
                        'action': 'block_account',
                        'type': 'automatic_fraud_detection'
                    })
                db.session.add(block_history)
                db.session.commit()
                logger.info(
                    f"Account {self.account_number} blocked successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Error blocking account: {str(e)}")
            db.session.rollback()
            return False

    def unblock_account(self,
                        bank_authority: 'BankAuthority') -> Dict[str, Any]:
        """Unblock this account, only accessible by bank authorities."""
        try:
            # Verify bank authority matches the account's bank
            if not bank_authority.is_active or bank_authority.bank_code != self.bank_identifier:
                return {
                    'success': False,
                    'message': 'Unauthorized bank authority'
                }

            if self.is_blocked:
                self.is_blocked = False

                # Record unblock action in history
                unblock_history = AccountBlockHistory(
                    account_id=self.id,
                    reason=
                    f"Account unblocked by bank authority: {bank_authority.username}",
                    block_type="UNBLOCK",
                    status="COMPLETED",
                    api_response={
                        'success': True,
                        'timestamp': datetime.utcnow().isoformat(),
                        'action': 'unblock_account',
                        'authority': bank_authority.username
                    })
                db.session.add(unblock_history)
                db.session.commit()

                # Send notification to bank
                notification_service = NotificationService()
                notification_result = notification_service.send_unblock_notification(
                    bank_code=self.bank_identifier,
                    account_data={
                        'account_number': self.account_number,
                        'bank_identifier': self.bank_identifier,
                        'reason': unblock_history.reason,
                        'unblocked_by': bank_authority.username,
                        'block_history_id': unblock_history.id
                    })

                if not notification_result['success']:
                    logger.warning(
                        f"Failed to send unblock notification: {notification_result['message']}"
                    )

                return {
                    'success': True,
                    'message': 'Account unblocked successfully',
                    'unblock_history_id': unblock_history.id
                }

            return {'success': False, 'message': 'Account is not blocked'}

        except Exception as e:
            logger.error(f"Error unblocking account: {str(e)}")
            return {'success': False, 'message': str(e)}

    def check_block_status(self) -> Dict[str, Any]:
        """Check if this account is blocked."""
        return {
            'is_blocked': self.is_blocked,
            'account_number': self.account_number,
            'bank_identifier': self.bank_identifier,
            'last_updated': self.created_at.isoformat()
        }


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer,
                             db.ForeignKey('complaint.id'),
                             nullable=True)
    transaction_id = db.Column(db.String(100))  # Original bank transaction ID
    reference_id = db.Column(db.String(100))
    amount = db.Column(db.Float)
    transaction_date = db.Column(db.DateTime)
    is_reversed = db.Column(db.Boolean, default=False)
    reversal_transaction_id = db.Column(db.String(100), nullable=True)
    bank_response_code = db.Column(db.String(20),
                                   nullable=True)  # Bank API response code
    reversal_status = db.Column(
        db.String(20),
        default='PENDING')  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Bank API related fields
    bank_api_reference = db.Column(
        db.String(100))  # Bank's API transaction reference
    bank_status = db.Column(db.String(50))  # Status from bank's system
    reversal_attempts = db.Column(
        db.Integer, default=0)  # Track number of reversal attempts
    last_reversal_attempt = db.Column(
        db.DateTime)  # Timestamp of last reversal attempt

    # Relationships
    transaction_parties = db.relationship('TransactionParty',
                                          backref='transaction',
                                          lazy=True)

    def initiate_reversal(self) -> bool:
        """
        Initiate a reversal for this transaction.
        Returns True if reversal was initiated successfully.
        """
        if self.is_reversed:
            return False

        sender, receiver = self.get_sender_receiver()
        if not sender or not receiver:
            return False

        try:
            # Attempt to reverse via bank API (to be implemented)
            # bank_api.reverse_transaction(self.transaction_id)

            # Mark original transaction as reversed
            self.is_reversed = True
            self.reversal_transaction_id = f"REV-{self.transaction_id}"
            self.reversal_status = 'IN_PROGRESS'
            self.reversal_attempts += 1
            self.last_reversal_attempt = datetime.utcnow()

            # Create reversal transaction record
            reversal = Transaction(
                complaint_id=self.complaint_id,
                transaction_id=self.reversal_transaction_id,
                reference_id=f"REV-{self.reference_id}"
                if self.reference_id else None,
                amount=self.amount,
                transaction_date=datetime.utcnow(),
                is_reversed=False,  # This is the reversal transaction itself
                reversal_status='IN_PROGRESS')
            db.session.add(reversal)

            # Create transaction parties for reversal (swap sender and receiver)
            TransactionParty(
                transaction=reversal,
                complaint_id=self.complaint_id,
                account_id=receiver.account_id,
                party_type='sender',  # Original receiver becomes sender
                identified_name=receiver.identified_name,
                account_number=receiver.account_number)

            TransactionParty(
                transaction=reversal,
                complaint_id=self.complaint_id,
                account_id=sender.account_id,
                party_type='receiver',  # Original sender becomes receiver
                identified_name=sender.identified_name,
                account_number=sender.account_number)

            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            self.reversal_status = 'FAILED'
            self.bank_status = str(e)
            db.session.commit()
            return False

    def get_sender_receiver(
            self) -> Tuple["TransactionParty", "TransactionParty"]:
        """Get the sender and receiver for this transaction."""
        sender = next(
            (p for p in self.transaction_parties if p.party_type == 'sender'),
            None)
        receiver = next(
            (p
             for p in self.transaction_parties if p.party_type == 'receiver'),
            None)
        return sender, receiver

    @classmethod
    def find_matching_transactions(
            cls, transaction_data: Dict[str, Any]) -> List["Transaction"]:
        """Find transactions matching the given criteria."""
        query = cls.query

        if transaction_data.get('transaction_id'):
            query = query.filter_by(
                transaction_id=transaction_data['transaction_id'])

        if transaction_data.get('reference_id'):
            query = query.filter_by(
                reference_id=transaction_data['reference_id'])

        if transaction_data.get('amount'):
            query = query.filter_by(amount=transaction_data['amount'])

        if transaction_data.get('transaction_date'):
            # Match transactions within the same day
            date = transaction_data['transaction_date']
            query = query.filter(
                func.date(cls.transaction_date) == func.date(date))

        return query.all()


class TransactionParty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer,
                             db.ForeignKey('complaint.id'),
                             nullable=False)
    transaction_id = db.Column(db.Integer,
                               db.ForeignKey('transaction.id'),
                               nullable=True)
    account_id = db.Column(db.Integer,
                           db.ForeignKey('account.id'),
                           nullable=True)
    party_type = db.Column(db.String(20),
                           nullable=False)  # 'sender' or 'receiver'
    identified_name = db.Column(
        db.String(100))  # Name extracted from complaint
    account_number = db.Column(db.String(50))  # Account number if found
    bank_code = db.Column(db.String(20))  # Bank identifier code
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Complaint(db.Model):
    """Store complaint information with fraud analysis."""
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(50), nullable=False)  # email, web, phone
    content = db.Column(db.Text, nullable=False)
    fraud_score = db.Column(db.Float,
                            default=0.0)  # Set default to 0.0 instead of None
    classification = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    fraud_indicators = db.Column(db.JSON)  # Store detected fraud indicators

    # Relationships
    transactions = db.relationship('Transaction',
                                   backref='complaint',
                                   lazy=True)
    transaction_parties = db.relationship('TransactionParty',
                                          backref='complaint',
                                          lazy=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'source': self.source,
            'content': self.content,
            'fraud_score': self.fraud_score or 0.0,  # Default to 0.0 if None
            'classification': self.classification,
            'created_at': self.created_at.isoformat(),
            'fraud_indicators': self.fraud_indicators or []
        }


class BankAPICredential(db.Model):
    """Store bank API credentials safely."""
    id = db.Column(db.Integer, primary_key=True)
    bank_code = db.Column(db.String(20), unique=True, nullable=False)
    api_key = db.Column(db.String(500))  # Encrypted API key
    api_secret = db.Column(db.String(500))  # Encrypted API secret
    environment = db.Column(db.String(20), default='test')  # test/production
    is_active = db.Column(db.Boolean, default=True)
    last_used = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AccountBlockHistory(db.Model):
    """Track history of account blocks."""
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer,
                           db.ForeignKey('account.id'),
                           nullable=False)
    blocked_at = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(200))  # Reason for blocking
    transaction_id = db.Column(
        db.String(100))  # Related fraudulent transaction
    block_type = db.Column(
        db.String(50))  # 'FRAUD', 'SUSPICIOUS_ACTIVITY', etc.
    status = db.Column(db.String(20))  # 'PENDING', 'COMPLETED', 'FAILED'
    api_response = db.Column(db.JSON)  # Store API response details

    # Relationship with Account
    account = db.relationship('Account', backref='block_history', lazy=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'account_id': self.account_id,
            'blocked_at': self.blocked_at.isoformat(),
            'reason': self.reason,
            'transaction_id': self.transaction_id,
            'block_type': self.block_type,
            'status': self.status,
            'api_response': self.api_response
        }
