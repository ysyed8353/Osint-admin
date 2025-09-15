"""
OSINT Bot Admin Client (Telegram Bot)
This bot runs locally and communicates with the Flask API server
"""

import os
import logging
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

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
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5000')
ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', 'osint-admin-secret-key-2025')

if not ADMIN_BOT_TOKEN:
    logger.error("ADMIN_BOT_TOKEN not found in environment variables!")
    exit(1)

class APIClient:
    """Client for communicating with Flask API"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    async def request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make HTTP request to API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    result = await response.json()
                    
                    if response.status >= 400:
                        logger.error(f"API Error {response.status}: {result}")
                        return {'error': result.get('error', 'Unknown error'), 'status': response.status}
                    
                    return result
        except aiohttp.ClientError as e:
            logger.error(f"HTTP Client Error: {e}")
            return {'error': f'Connection failed: {str(e)}'}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {'error': f'Unexpected error: {str(e)}'}
    
    async def verify_admin(self, user_id: int) -> bool:
        """Verify if user is admin"""
        result = await self.request('POST', '/api/telegram/verify-admin', {'user_id': user_id})
        return result.get('is_admin', False) if 'error' not in result else False
    
    async def get_stats(self, admin_user_id: int) -> dict:
        """Get bot statistics"""
        return await self.request('POST', '/api/telegram/stats', {'admin_user_id': admin_user_id})
    
    async def get_users(self, admin_user_id: int, page: int = 1, limit: int = 10) -> dict:
        """Get paginated user list"""
        return await self.request('POST', '/api/telegram/users', {
            'admin_user_id': admin_user_id,
            'page': page,
            'limit': limit
        })
    
    async def get_user_info(self, admin_user_id: int, target_user_id: int) -> dict:
        """Get specific user information"""
        return await self.request('POST', '/api/telegram/user-info', {
            'admin_user_id': admin_user_id,
            'target_user_id': target_user_id
        })
    
    async def grant_subscription(self, admin_user_id: int, target_user_id: int, days: int = 21, amount: float = 399.0) -> dict:
        """Grant subscription to user"""
        return await self.request('POST', '/api/telegram/grant-subscription', {
            'admin_user_id': admin_user_id,
            'target_user_id': target_user_id,
            'days': days,
            'amount': amount
        })
    
    async def revoke_subscription(self, admin_user_id: int, target_user_id: int) -> dict:
        """Revoke user subscription"""
        return await self.request('POST', '/api/telegram/revoke-subscription', {
            'admin_user_id': admin_user_id,
            'target_user_id': target_user_id
        })

# Initialize API client
api_client = APIClient(API_BASE_URL, ADMIN_API_KEY)

async def is_admin(user_id: int) -> bool:
    """Check if user is admin via API"""
    return await api_client.verify_admin(user_id)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Access denied. This bot is for administrators only.")
        return
    
    welcome_text = f"""
🔧 **OSINT Bot Admin Panel**

🌐 **Connected to API:** `{API_BASE_URL}`

**Available commands:**
• `/stats` - View bot statistics
• `/users [page]` - Show users (paginated)
• `/grant <user_id> [days]` - Grant subscription
• `/revoke <user_id>` - Revoke subscription
• `/info <user_id>` - Get user information
• `/health` - Check API connection

**Examples:**
• `/grant 123456789 21` - Grant 21 days
• `/users 2` - Show page 2 of users
• `/info 123456789` - Get user details

👨‍💼 **Admin:** @ded_xdk
🤖 **Bot:** Local client + API server
    """
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check API health"""
    user_id = update.effective_user.id
    
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return
    
    try:
        result = await api_client.request('GET', '/api/health')
        
        if 'error' in result:
            await update.message.reply_text(f"❌ **API Connection Failed**\n\nError: {result['error']}")
        else:
            health_text = f"""
✅ **API Health Check**

🌐 **Status:** {result.get('status', 'unknown')}
📊 **Database:** {result.get('database', 'unknown')}
👥 **Active Users:** {result.get('active_users_count', 'N/A')}
🕐 **Timestamp:** {result.get('timestamp', 'N/A')}
🔗 **API URL:** `{API_BASE_URL}`
            """
            await update.message.reply_text(health_text, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ **Connection Error**\n\n{str(e)}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    user_id = update.effective_user.id
    
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return
    
    try:
        result = await api_client.get_stats(user_id)
        
        if 'error' in result:
            await update.message.reply_text(f"❌ Error getting statistics: {result['error']}")
            return
        
        stats_text = f"""
📊 **Bot Statistics**

👥 **Users:**
• Total Users: {result['total_users']:,}
• Active Subscriptions: {result['active_subscriptions']:,}
• Conversion Rate: {result['conversion_rate']:.1f}%

💰 **Revenue:**
• Estimated Monthly: ₹{result['total_revenue']:,.2f}
• Per Subscription: ₹{result['subscription_price']:,.2f}
• Estimated Daily: ₹{result['estimated_daily_revenue']:,.2f}

🕐 **Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🌐 **Source:** API Server
        """
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await update.message.reply_text(f"❌ Error getting statistics: {str(e)}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show users with pagination"""
    user_id = update.effective_user.id
    
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return
    
    try:
        page = 1
        if context.args and context.args[0].isdigit():
            page = int(context.args[0])
        
        result = await api_client.get_users(user_id, page=page, limit=10)
        
        if 'error' in result:
            await update.message.reply_text(f"❌ Error getting users: {result['error']}")
            return
        
        users = result['users']
        pagination = result['pagination']
        
        if not users:
            await update.message.reply_text("📭 No users found.")
            return
        
        users_text = f"👥 **Users (Page {pagination['current_page']}/{pagination['total_pages']})**\n\n"
        
        for user in users:
            username = user.get('username', 'N/A')
            first_name = user.get('first_name', 'N/A')
            status = "🟢 Active" if user.get('subscription_status') == 'active' else "🔴 Inactive"
            
            users_text += f"**{user['user_id']}** - @{username} ({first_name})\n"
            users_text += f"Status: {status}\n"
            users_text += f"Joined: {user.get('created_at', 'N/A')[:10]}\n\n"
        
        users_text += f"📄 **Total:** {pagination['total_users']} users"
        
        # Add navigation buttons
        keyboard = []
        if pagination['has_prev']:
            keyboard.append(InlineKeyboardButton(f"⬅️ Page {page-1}", callback_data=f"users_page_{page-1}"))
        if pagination['has_next']:
            keyboard.append(InlineKeyboardButton(f"Page {page+1} ➡️", callback_data=f"users_page_{page+1}"))
        
        reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
        
        await update.message.reply_text(users_text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in users command: {e}")
        await update.message.reply_text(f"❌ Error getting users: {str(e)}")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user information"""
    user_id = update.effective_user.id
    
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/info <user_id>`\nExample: `/info 123456789`", parse_mode='Markdown')
        return
    
    try:
        target_user_id = int(context.args[0])
        result = await api_client.get_user_info(user_id, target_user_id)
        
        if 'error' in result:
            await update.message.reply_text(f"❌ Error: {result['error']}")
            return
        
        user_data = result['user']
        is_subscribed = result.get('is_subscribed', False)
        
        info_text = f"""
👤 **User Information**

**ID:** `{user_data['user_id']}`
**Username:** @{user_data.get('username', 'N/A')}
**Name:** {user_data.get('first_name', 'N/A')} {user_data.get('last_name', '')}
**Subscription:** {'🟢 Active' if is_subscribed else '🔴 Inactive'}
**Status:** {user_data.get('subscription_status', 'unknown')}
**Joined:** {user_data.get('created_at', 'N/A')[:10]}

**Actions:**
• `/grant {target_user_id} 21` - Grant 21 days
• `/revoke {target_user_id}` - Revoke subscription
        """
        
        await update.message.reply_text(info_text, parse_mode='Markdown')
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Use numbers only.")
    except Exception as e:
        logger.error(f"Error in info command: {e}")
        await update.message.reply_text(f"❌ Error getting user info: {str(e)}")

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
        
        result = await api_client.grant_subscription(user_id, target_user_id, days)
        
        if 'error' in result:
            await update.message.reply_text(f"❌ Error: {result['error']}")
            return
        
        if result.get('success'):
            details = result['details']
            await update.message.reply_text(
                f"✅ **Subscription Granted**\n\n"
                f"**User:** `{details['user_id']}`\n"
                f"**Duration:** {details['days']} days\n"
                f"**Amount:** ₹{details['amount']}\n"
                f"**Expires:** {details['expiry_date'][:10]}\n\n"
                f"🌐 *Updated via API*"
            )
        else:
            await update.message.reply_text("❌ Failed to grant subscription.")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or days. Use numbers only.")
    except Exception as e:
        logger.error(f"Error in grant command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Revoke user subscription"""
    user_id = update.effective_user.id
    
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/revoke <user_id>`\nExample: `/revoke 123456789`", parse_mode='Markdown')
        return
    
    try:
        target_user_id = int(context.args[0])
        
        result = await api_client.revoke_subscription(user_id, target_user_id)
        
        if 'error' in result:
            await update.message.reply_text(f"❌ Error: {result['error']}")
            return
        
        if result.get('success'):
            await update.message.reply_text(
                f"✅ **Subscription Revoked**\n\n"
                f"**User:** `{target_user_id}`\n"
                f"**Status:** Subscription expired\n\n"
                f"🌐 *Updated via API*"
            )
        else:
            await update.message.reply_text("❌ Failed to revoke subscription.")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Use numbers only.")
    except Exception as e:
        logger.error(f"Error in revoke command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not await is_admin(user_id):
        await query.edit_message_text("❌ Access denied.")
        return
    
    if query.data.startswith('users_page_'):
        page = int(query.data.split('_')[-1])
        
        result = await api_client.get_users(user_id, page=page, limit=10)
        
        if 'error' in result:
            await query.edit_message_text(f"❌ Error: {result['error']}")
            return
        
        users = result['users']
        pagination = result['pagination']
        
        users_text = f"👥 **Users (Page {pagination['current_page']}/{pagination['total_pages']})**\n\n"
        
        for user in users:
            username = user.get('username', 'N/A')
            first_name = user.get('first_name', 'N/A')
            status = "🟢 Active" if user.get('subscription_status') == 'active' else "🔴 Inactive"
            
            users_text += f"**{user['user_id']}** - @{username} ({first_name})\n"
            users_text += f"Status: {status}\n"
            users_text += f"Joined: {user.get('created_at', 'N/A')[:10]}\n\n"
        
        users_text += f"📄 **Total:** {pagination['total_users']} users"
        
        # Update navigation buttons
        keyboard = []
        if pagination['has_prev']:
            keyboard.append(InlineKeyboardButton(f"⬅️ Page {page-1}", callback_data=f"users_page_{page-1}"))
        if pagination['has_next']:
            keyboard.append(InlineKeyboardButton(f"Page {page+1} ➡️", callback_data=f"users_page_{page+1}"))
        
        reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
        
        await query.edit_message_text(users_text, parse_mode='Markdown', reply_markup=reply_markup)

def main():
    """Main function"""
    if not ADMIN_BOT_TOKEN:
        logger.error("ADMIN_BOT_TOKEN not found!")
        return
    
    logger.info(f"Starting Telegram Admin Bot...")
    logger.info(f"API URL: {API_BASE_URL}")
    
    # Create application
    application = Application.builder().token(ADMIN_BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("grant", grant_command))
    application.add_handler(CommandHandler("revoke", revoke_command))
    
    # Add callback handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start the bot
    logger.info("Bot started! Send /start to begin.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()