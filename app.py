import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
app = Flask(__name__)

# Configuration
app.secret_key = os.environ.get("SESSION_SECRET")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///complaints.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database
logger.info("Initializing database...")
db.init_app(app)

# Import models after db initialization
from models import BankAuthority, Account, AccountBlockHistory, Complaint


# Bank authority login requirement decorator
def bank_authority_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'bank_authority_id' not in session:
            flash('Please login as bank authority first', 'error')
            return redirect(url_for('bank_authority_login'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/health')
def health_check():
    """Health check endpoint to verify server is running."""
    logger.info("Health check endpoint accessed")
    return "OK", 200


@app.route('/')
def index():
    """Root route redirects to dashboard if logged in, otherwise shows complaint form."""
    if 'bank_authority_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('complaint_view.html')


@app.route('/dashboard')
@bank_authority_required
def dashboard():
    """Render main dashboard with blocked accounts and complaints."""
    # Get blocked accounts with their history
    blocked_accounts = db.session.query(Account, AccountBlockHistory).join(
        AccountBlockHistory,
        Account.id == AccountBlockHistory.account_id).filter(
            Account.is_blocked == True).all()

    # Get recent complaints
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()

    logger.info(
        f"Found {len(blocked_accounts)} blocked accounts and {len(complaints)} complaints"
    )
    return render_template('dashboard.html',
                           blocked_accounts=blocked_accounts,
                           complaints=complaints)


@app.route('/configure-bank-api', methods=['POST'])
@bank_authority_required
def configure_bank_api():
    """Configure bank API credentials."""
    from models import BankAPICredential
    try:
        bank_code = request.form.get('bank_code')
        api_key = request.form.get('api_key')
        api_secret = request.form.get('api_secret')
        environment = request.form.get('environment', 'test')

        if not all([bank_code, api_key, api_secret]):
            flash('All fields are required', 'error')
            return redirect(url_for('dashboard'))

        # Check if credentials already exist for this bank
        existing_cred = BankAPICredential.query.filter_by(
            bank_code=bank_code).first()
        if existing_cred:
            # Update existing credentials
            existing_cred.api_key = api_key
            existing_cred.api_secret = api_secret
            existing_cred.environment = environment
            existing_cred.is_active = True
            db.session.commit()
            logger.info(f"Updated API credentials for bank {bank_code}")
        else:
            # Create new credentials
            cred = BankAPICredential(bank_code=bank_code,
                                     api_key=api_key,
                                     api_secret=api_secret,
                                     environment=environment)
            db.session.add(cred)
            db.session.commit()
            logger.info(f"Added new API credentials for bank {bank_code}")

        flash('Bank API configuration saved successfully', 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        logger.error(f"Error configuring bank API: {str(e)}")
        flash('Error saving bank API configuration', 'error')
        return redirect(url_for('dashboard'))


@app.route('/blocked-accounts')
def get_blocked_accounts():
    """Get list of blocked accounts for the dashboard table."""
    try:
        blocked = db.session.query(Account, AccountBlockHistory).join(
            AccountBlockHistory,
            Account.id == AccountBlockHistory.account_id).filter(
                Account.is_blocked == True).all()

        accounts = [{
            'account_number': acc.account_number,
            'bank_code': acc.bank_identifier,
            'blocked_at': hist.blocked_at.isoformat(),
            'reason': hist.reason,
            'status': hist.status
        } for acc, hist in blocked]

        return jsonify({'accounts': accounts})

    except Exception as e:
        logger.error(f"Error fetching blocked accounts: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/bank-authority/login', methods=['GET', 'POST'])
def bank_authority_login():
    """Bank authority login page."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        bank_code = request.form.get('bank_code')

        authority = BankAuthority.query.filter_by(username=username,
                                                  bank_code=bank_code,
                                                  is_active=True).first()

        if authority and check_password_hash(authority.password_hash,
                                             password):
            session['bank_authority_id'] = authority.id
            flash('Logged in successfully', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid credentials', 'error')

    return render_template('bank_authority_login.html')


@app.route('/bank-authority/logout')
def bank_authority_logout():
    """Bank authority logout."""
    session.pop('bank_authority_id', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))


@app.route('/unblock-account/<account_number>', methods=['POST'])
@bank_authority_required
def unblock_account(account_number):
    """Unblock an account (requires bank authority authentication)."""
    try:
        # Get current bank authority
        authority = BankAuthority.query.get(session['bank_authority_id'])
        if not authority:
            flash('Bank authority not found', 'error')
            return redirect(url_for('dashboard'))

        # Find account
        account = Account.query.filter_by(
            account_number=account_number).first()
        if not account:
            flash('Account not found', 'error')
            return redirect(url_for('dashboard'))

        # Attempt to unblock
        account.is_blocked = False
        db.session.commit()
        flash('Account unblocked successfully', 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        logger.error(f"Error unblocking account: {str(e)}")
        flash('Error unblocking account', 'error')
        return redirect(url_for('dashboard'))


@app.route('/process-complaint', methods=['POST'])
def process_complaint():
    """Handle complaint form submission with fraud detection."""
    try:
        content = request.form.get('content')
        if not content:
            flash('Please provide complaint details', 'error')
            return redirect(url_for('index'))

        # Initialize TransactionAI for fraud detection
        from transaction_ai import TransactionAI
        ai_system = TransactionAI()

        # Analyze complaint for fraud indicators
        analysis = ai_system.analyze_text_content(content)
        is_fraudulent = analysis.get('is_fraudulent', False)
        fraud_indicators = analysis.get('fraud_indicators', [])

        # Create complaint record
        complaint = Complaint(
            content=content,
            source='web',
            classification='FRAUD' if is_fraudulent else 'NORMAL',
            fraud_indicators=fraud_indicators,
            created_at=datetime.utcnow())
        db.session.add(complaint)
        db.session.commit()  # Commit to get complaint.id

        # Extract account numbers and block accounts if fraud is detected
        if is_fraudulent:
            account_numbers = ai_system.extract_account_numbers(content)

            if not account_numbers:
                # If no account numbers found using patterns, try simple digit extraction
                account_numbers = re.findall(r'\b\d{6,12}\b', content)

            for acc_num in account_numbers:
                # Find or create account
                account = Account.query.filter_by(
                    account_number=acc_num).first()
                if not account:
                    account = Account(
                        account_number=acc_num,
                        account_holder="Unknown",  # Will be updated by bank
                        bank_identifier="AUTO",  # Will be updated by bank
                        is_blocked=False)
                    db.session.add(account)
                    db.session.commit()

                # Block account if not already blocked
                if not account.is_blocked:
                    if account.block_account():
                        logger.info(
                            f"Account {acc_num} blocked due to fraud detection in complaint {complaint.id}"
                        )
                    else:
                        logger.error(f"Failed to block account {acc_num}")

        flash('Complaint submitted successfully', 'success')
        return redirect(url_for('index'))

    except Exception as e:
        logger.error(f"Error processing complaint: {str(e)}")
        flash('Error submitting complaint', 'error')
        return redirect(url_for('index'))


# Add security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers[
        'Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


# Update the logging configuration for production
if not app.debug:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

# Create database tables
with app.app_context():
    logger.info("Creating database tables...")
    db.create_all()
    logger.info("Database tables created successfully")

logger.info("Flask application initialization complete")
