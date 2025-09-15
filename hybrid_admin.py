"""
Hybrid Admin System - Both Telegram Bot AND Flask API
This gives you both options in one application
"""

import os
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string

# Telegram bot imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# Import database
import sys
sys.path.append('.')
from database import DatabaseManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN')
ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', 'your-secret-api-key-here')
ADMIN_USER_IDS = [
    int(os.getenv('ADMIN_USER_ID', '5682019164')),
    1844138085,  # @ded_xdk
]

# Initialize database
db = DatabaseManager()

# Flask App for API
app = Flask(__name__)

# API endpoints (same as before)
def require_api_key(f):
    """Decorator to require API key for protected endpoints"""
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if api_key != ADMIN_API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
def index():
    """Dashboard showing both bot and API status"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OSINT Admin Hub</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .status { padding: 20px; margin: 20px 0; border-radius: 10px; }
            .online { background: #d4edda; border: 1px solid #c3e6cb; }
            .offline { background: #f8d7da; border: 1px solid #f5c6cb; }
            .endpoint { background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 5px; }
            .method { font-weight: bold; color: #007acc; }
        </style>
    </head>
    <body>
        <h1>🤖 OSINT Admin Hub</h1>
        <p>Hybrid system with both Telegram bot and Flask API</p>
        
        <div class="status online">
            <h3>📱 Telegram Bot Status</h3>
            <p><strong>Bot:</strong> @subscriptionOSINTbot</p>
            <p><strong>Status:</strong> <span style="color: green;">✅ Running</span></p>
            <p><strong>Commands:</strong> /start, /stats, /users, /grant, /revoke</p>
        </div>
        
        <div class="status online">
            <h3>🌐 Flask API Status</h3>
            <p><strong>Status:</strong> <span style="color: green;">✅ Active</span></p>
            <p><strong>Authentication:</strong> API Key required</p>
        </div>
        
        <h2>API Endpoints:</h2>
        
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/health</code><br>
            Health check endpoint
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/stats</code><br>
            Get bot statistics (requires API key)
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/users</code><br>
            List all users (requires API key)
        </div>
        
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/users/{user_id}/grant</code><br>
            Grant subscription to user (requires API key)<br>
            Body: <code>{"days": 21, "price": 399}</code>
        </div>
        
        <h3>How to Use:</h3>
        <ul>
            <li><strong>Telegram:</strong> Message @subscriptionOSINTbot directly</li>
            <li><strong>API:</strong> Include header <code>X-API-Key: your-secret-key</code></li>
        </ul>
        
        <p><strong>Timestamp:</strong> {{ timestamp }}</p>
    </body>
    </html>
    """
    return render_template_string(html, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/health')
@app.route('/api/health')
def health():
    """Health check endpoint"""
    try:
        active_users = db.get_all_active_users()
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'telegram_bot': 'running' if ADMIN_BOT_TOKEN else 'not_configured',
            'database': 'connected',
            'active_users': len(active_users)
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/stats')
@require_api_key
def get_stats():
    """Get bot statistics"""
    try:
        active_users = db.get_all_active_users()
        
        if hasattr(db, 'use_sqlite') and db.use_sqlite:
            import sqlite3
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
        else:
            all_users = db.supabase.table('users').select('user_id').execute()
            total_users = len(all_users.data) if all_users.data else 0
        
        subscription_price = 399.0
        total_revenue = len(active_users) * subscription_price
        
        return jsonify({
            'active_subscriptions': len(active_users),
            'total_users': total_users,
            'total_revenue': total_revenue,
            'subscription_price': subscription_price,
            'conversion_rate': round((len(active_users)/total_users*100 if total_users > 0 else 0), 2),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>/grant', methods=['POST'])
@require_api_key
def grant_subscription(user_id):
    """Grant subscription to user"""
    try:
        data = request.get_json() or {}
        days = data.get('days', 21)
        price = data.get('price', 399.0)
        
        # Check if user exists, create if not
        user_data = db.get_user(user_id)
        if not user_data:
            db.add_user(
                user_id=user_id,
                username=data.get('username', f'user_{user_id}'),
                first_name=data.get('first_name', 'Admin Created'),
                last_name=data.get('last_name', '')
            )
        
        # Grant subscription
        success = db.grant_subscription(
            user_id=user_id,
            days=days,
            amount=price
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Subscription granted to user {user_id}',
                'days': days,
                'price': price,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': 'Failed to grant subscription'}), 500
            
    except Exception as e:
        logger.error(f"Error granting subscription to {user_id}: {e}")
        return jsonify({'error': str(e)}), 500

# Telegram Bot Functions
async def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_USER_IDS

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Access denied. This bot is for administrators only.")
        return
    
    welcome_text = """
🔧 **OSINT Bot Admin Panel**

Available commands:
• `/stats` - View bot statistics
• `/users` - Show all users (paginated)
• `/grant <user_id> [days]` - Grant subscription
• `/revoke <user_id>` - Revoke subscription
• `/info <user_id>` - Get user information

🌐 **Also available as API:**
Access the same features via REST API at the web interface.

👨‍💼 Admin: @ded_xdk
    """
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    user_id = update.effective_user.id
    
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return
    
    try:
        active_users = db.get_all_active_users()
        
        if hasattr(db, 'use_sqlite') and db.use_sqlite:
            import sqlite3
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
        else:
            all_users = db.supabase.table('users').select('*').execute()
            total_users = len(all_users.data) if all_users.data else 0
        
        subscription_price = 399.0
        estimated_revenue = len(active_users) * subscription_price
        
        stats_text = f"""
📊 **Bot Statistics**

👥 **Users:**
• Total Users: {total_users:,}
• Active Subscriptions: {len(active_users):,}
• Conversion Rate: {(len(active_users)/total_users*100 if total_users > 0 else 0):.1f}%

💰 **Revenue:**
• Estimated Monthly: ₹{estimated_revenue:,.2f}
• Per Subscription: ₹{subscription_price:,.2f}
• Estimated Daily: ₹{estimated_revenue/30:,.2f}

🕐 Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await update.message.reply_text(f"❌ Error getting statistics: {str(e)}")

async def grant_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grant subscription to user"""
    user_id = update.effective_user.id
    
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Usage: `/grant <user_id> [days]`\nExample: `/grant 123456789 21`", parse_mode='Markdown')
        return
    
    try:
        target_user_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 21
        
        # Check if user exists
        user_data = db.get_user(target_user_id)
        if not user_data:
            await update.message.reply_text(f"❌ User {target_user_id} not found in database.")
            return
        
        # Grant subscription
        success = db.grant_subscription(target_user_id, days, 399.0)
        
        if success:
            await update.message.reply_text(
                f"✅ **Subscription Granted**\n\n"
                f"User: {target_user_id}\n"
                f"Duration: {days} days\n"
                f"Amount: ₹399"
            )
        else:
            await update.message.reply_text("❌ Failed to grant subscription.")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or days. Use numbers only.")
    except Exception as e:
        logger.error(f"Error in grant command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

def run_flask():
    """Run Flask app in a separate thread"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

async def main():
    """Main function to run both Telegram bot and Flask API"""
    
    # Start Flask API in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Only start Telegram bot if token is provided
    if ADMIN_BOT_TOKEN:
        logger.info("Starting Telegram bot...")
        
        # Create application
        application = Application.builder().token(ADMIN_BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("grant", grant_command))
        
        # Start the bot
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info("Both Telegram bot and Flask API are running!")
        
        # Keep running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
    else:
        logger.warning("No ADMIN_BOT_TOKEN provided. Running Flask API only.")
        # Keep Flask running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Shutting down Flask API...")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")