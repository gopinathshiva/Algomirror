from flask import jsonify, request
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import TradingAccount
from app.utils.rate_limiter import api_rate_limit
from app.utils.ping_monitor import ping_monitor

@api_bp.route('/accounts')
@login_required
@api_rate_limit()
def get_accounts():
    """Get user's trading accounts"""
    accounts = current_user.get_active_accounts()
    
    accounts_data = []
    for account in accounts:
        accounts_data.append({
            'id': account.id,
            'name': account.account_name,
            'broker': account.broker_name,
            'status': account.connection_status,
            'is_primary': account.is_primary,
            'last_connected': account.last_connected.isoformat() if account.last_connected else None
        })
    
    return jsonify({
        'status': 'success',
        'data': accounts_data
    })

@api_bp.route('/ping-status')
@login_required
@api_rate_limit()
def get_ping_status():
    """Get ping status summary for user's accounts"""
    try:
        status_summary = ping_monitor.get_account_status_summary(current_user.id)
        return jsonify({
            'status': 'success',
            **status_summary  # Spread the summary directly into the response
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get ping status: {str(e)}'
        }), 500

@api_bp.route('/accounts/<int:account_id>/ping', methods=['POST'])
@login_required
@api_rate_limit()
def force_ping_check(account_id):
    """Force immediate ping check for specific account"""
    try:
        # Verify account belongs to current user
        account = TradingAccount.query.filter_by(
            id=account_id, 
            user_id=current_user.id
        ).first()
        
        if not account:
            return jsonify({
                'status': 'error',
                'message': 'Account not found'
            }), 404
        
        result = ping_monitor.force_check_account(account_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to check account: {str(e)}'
        }), 500