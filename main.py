"""
OSINT Bot Admin Panel
A separate Telegram bot for managing OSINT bot subscriptions
Admin: @ded_xdk
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
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

# Import our existing database
import sys
sys.path.append('.')
from database import DatabaseManager
from health_check import HealthCheckServer

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO'))
)
logger = logging.getLogger(__name__)


class OSINTAdminBot:
    """Admin bot for managing OSINT subscriptions"""
    
    def __init__(self):
        self.bot_token = os.getenv('ADMIN_BOT_TOKEN')  # New admin bot token
        self.admin_user_id = int(os.getenv('ADMIN_USER_ID', '0'))
        self.osint_bot_username = os.getenv('BOT_USERNAME', 'reosintbot')
        self.admin_bot_username = os.getenv('ADMIN_BOT_USERNAME', 'subscriptionOSINTbot')
        
        # Multiple admin support
        self.admin_user_ids = [
            self.admin_user_id,  # Primary admin (@boyonthegrid)
            1844138085,  # Secondary admin (@ded_xdk)
        ]
        
        # Initialize database connection
        self.db = DatabaseManager()
        
        # Subscription settings
        self.subscription_price = 399.0
        self.subscription_days = 21
        self.start_time = datetime.now()
        self.is_healthy = True
        
        # Health check setup
        self.health_server = HealthCheckServer(
            port=int(os.getenv('PORT', '8001')),  # Different port for admin bot
            bot_status_func=self.get_health_status
        )
        
        if not self.bot_token:
            raise ValueError("ADMIN_BOT_TOKEN not found in environment variables")
        
        if not self.admin_user_id:
            raise ValueError("ADMIN_USER_ID not found in environment variables")
    
    def get_health_status(self):
        """Get admin bot health status for monitoring"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            'healthy': self.is_healthy,
            'uptime': uptime,
            'name': f'OSINT Admin Bot (@{self.admin_bot_username})',
            'database': self.db is not None,
            'admins': len(self.admin_user_ids)
        }
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors in the admin bot"""
        logger.error(f"Admin bot exception while handling an update: {context.error}")
        
        # Handle specific Telegram conflicts
        if "Conflict" in str(context.error):
            logger.error("Admin bot conflict detected - another instance may be running with the same token")
            self.is_healthy = False
            # Don't retry on conflicts - let it fail
            return
        
        # Handle other errors gracefully
        if update and hasattr(update, 'effective_message') and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ An error occurred while processing your admin request. Please try again later."
                )
            except Exception as e:
                logger.error(f"Failed to send admin error message: {e}")
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is authorized admin"""
        return user_id in self.admin_user_ids
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command"""
        user = update.effective_user
        
        if not self.is_admin(user.id):
            await update.message.reply_text(
                "🚫 **Access Denied**\n\n"
                "This is an admin-only bot for managing OSINT subscriptions.\n"
                "Only @boyonthegrid and @ded_xdk can use this bot.",
                parse_mode='Markdown'
            )
            return
        
        welcome_message = f"""
🔧 **OSINT Admin Panel** (@{self.admin_bot_username})

Welcome {user.first_name}! 👋

This is your admin control panel for managing @{self.osint_bot_username} subscriptions.

� **Authorized Admins:**
• @boyonthegrid (Primary Admin)
• @ded_xdk (Secondary Admin)

�💳 **Subscription Details:**
• Price: ₹{self.subscription_price}
• Duration: {self.subscription_days} days
• Features: Unlimited OSINT queries

🎛️ **Available Commands:**
/grant <user_id> [payment_ref] - Grant subscription
/revoke <user_id> - Revoke subscription
/userinfo <user_id> - Get user details
/stats - View bot statistics
/users - List all users
/active - List active subscribers
/help - Show detailed help

📊 **Quick Actions:**
        """
        
        # Create quick action buttons
        keyboard = [
            [InlineKeyboardButton("📊 Bot Statistics", callback_data="stats")],
            [InlineKeyboardButton("👥 Active Users", callback_data="active_users")],
            [InlineKeyboardButton("📋 All Users", callback_data="all_users")],
            [InlineKeyboardButton("💰 Revenue Report", callback_data="revenue")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def grant_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Grant subscription to a user"""
        user = update.effective_user
        
        if not self.is_admin(user.id):
            await update.message.reply_text("🚫 Access denied.")
            return
        
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "**Usage:** `/grant <user_id> [payment_reference]`\n\n"
                "**Examples:**\n"
                "`/grant 123456789` - Grant subscription\n"
                "`/grant 123456789 UPI_REF_001` - Grant with payment reference\n"
                "`/grant 123456789 CASH_DELHI_15SEP` - Grant with custom reference",
                parse_mode='Markdown'
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            payment_ref = context.args[1] if len(context.args) > 1 else f"ADMIN_GRANT_{datetime.now().strftime('%d%m%Y_%H%M')}"
            
            # Check if user exists in database, create if not
            user_data = self.db.get_user(target_user_id)
            if not user_data:
                # Try to get user info from Telegram API
                try:
                    telegram_user = await context.bot.get_chat(target_user_id)
                    first_name = telegram_user.first_name or "Unknown User"
                    last_name = telegram_user.last_name
                    username = telegram_user.username
                    
                    await update.message.reply_text(
                        f"ℹ️ <b>Found user on Telegram</b>\n\n"
                        f"👤 <b>Name:</b> {first_name}{' ' + last_name if last_name else ''}\n"
                        f"🆔 <b>Username:</b> @{username if username else 'None'}\n"
                        f"🔢 <b>User ID:</b> <code>{target_user_id}</code>\n\n"
                        f"Adding to database...",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    # Couldn't get user from Telegram, use placeholder
                    first_name = "Unknown User"
                    last_name = None
                    username = None
                    
                    await update.message.reply_text(
                        f"⚠️ <b>Could not fetch user details from Telegram</b>\n\n"
                        f"User ID <code>{target_user_id}</code> will be added with placeholder data.\n"
                        f"Details will be updated when they interact with @{self.osint_bot_username}",
                        parse_mode='HTML'
                    )
                
                # Create user entry in database for subscription management
                self.db.add_user(
                    user_id=target_user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                user_data = self.db.get_user(target_user_id)
            
            # Grant subscription
            success = self.db.grant_subscription(
                user_id=target_user_id,
                days=self.subscription_days,
                amount=self.subscription_price,
                admin_id=user.id,
                payment_ref=payment_ref
            )
            
            if success:
                user_stats = self.db.get_user_stats(target_user_id)
                username_display = user_data['username'] or 'N/A'
                await update.message.reply_text(
                    f"✅ <b>Subscription Granted Successfully!</b>\n\n"
                    f"<b>User:</b> @{username_display} ({user_data['first_name']})\n"
                    f"<b>User ID:</b> <code>{target_user_id}</code>\n"
                    f"<b>Duration:</b> {self.subscription_days} days\n"
                    f"<b>Amount:</b> ₹{self.subscription_price}\n"
                    f"<b>Payment Ref:</b> <code>{payment_ref}</code>\n"
                    f"<b>Valid Until:</b> {user_stats['subscription_end'][:10] if user_stats['subscription_end'] else 'N/A'}\n"
                    f"<b>Granted by:</b> {user.first_name} (<code>{user.id}</code>)\n\n"
                    f"💡 User can now use @{self.osint_bot_username} for {self.subscription_days} days!",
                    parse_mode='HTML'
                )
                
                # Log the action
                logger.info(f"Admin {user.id} granted subscription to user {target_user_id} with reference {payment_ref}")
            else:
                await update.message.reply_text(
                    "❌ <b>Failed to grant subscription</b>\n\nDatabase error occurred. Please try again.",
                    parse_mode='HTML'
                )
                
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Invalid user ID</b>\n\nPlease provide a valid numeric user ID.",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error in grant command: {e}")
            await update.message.reply_text(
                "❌ <b>Error occurred</b>\n\nPlease try again or check the logs.",
                parse_mode='HTML'
            )
    
    async def revoke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Revoke user subscription"""
        user = update.effective_user
        
        if not self.is_admin(user.id):
            await update.message.reply_text("🚫 Access denied.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "<b>Usage:</b> <code>/revoke &lt;user_id&gt;</code>\n\n"
                "<b>Example:</b> <code>/revoke 123456789</code>",
                parse_mode='HTML'
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            
            # Check if user exists
            user_data = self.db.get_user(target_user_id)
            if not user_data:
                await update.message.reply_text(
                    f"❌ <b>User not found</b>\n\n"
                    f"User ID <code>{target_user_id}</code> doesn't exist in the database.\n"
                    f"Cannot revoke subscription for non-existent user.",
                    parse_mode='HTML'
                )
                return
            
            # Revoke subscription
            success = self.db.expire_subscription(target_user_id)
            
            if success:
                username_display = user_data['username'] or 'N/A'
                await update.message.reply_text(
                    f"🚫 <b>Subscription Revoked</b>\n\n"
                    f"<b>User:</b> @{username_display} ({user_data['first_name']})\n"
                    f"<b>User ID:</b> <code>{target_user_id}</code>\n"
                    f"<b>Status:</b> Expired\n"
                    f"<b>Revoked by:</b> {user.first_name}\n\n"
                    f"User can no longer access @{self.osint_bot_username}.",
                    parse_mode='HTML'
                )
                logger.info(f"Admin {user.id} revoked subscription for user {target_user_id}")
            else:
                await update.message.reply_text(
                    "❌ <b>Failed to revoke subscription</b>\n\nDatabase error occurred.",
                    parse_mode='HTML'
                )
                
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Invalid user ID</b>\n\nPlease provide a valid numeric user ID.",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error in revoke command: {e}")
            await update.message.reply_text(
                "❌ <b>Error occurred</b>\n\nPlease try again.",
                parse_mode='HTML'
            )
    
    async def userinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Get detailed user information"""
        user = update.effective_user
        
        if not self.is_admin(user.id):
            await update.message.reply_text("🚫 Access denied.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "**Usage:** `/userinfo <user_id>`\n\n"
                "**Example:** `/userinfo 123456789`",
                parse_mode='Markdown'
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            
            user_data = self.db.get_user(target_user_id)
            user_stats = self.db.get_user_stats(target_user_id)
            
            if not user_data:
                await update.message.reply_text(
                    f"❌ **User not found**\n\nUser ID `{target_user_id}` doesn't exist.",
                    parse_mode='Markdown'
                )
                return
            
            status_emoji = {
                'active': '✅',
                'expired': '⏰',
                'inactive': '🔒'
            }
            
            status = user_stats.get('subscription_status', 'inactive')
            
            message = f"""
📋 **Detailed User Information**

**👤 User Profile:**
• **ID:** `{user_data['user_id']}`
• **Username:** @{user_data['username'] or 'Not set'}
• **Name:** {user_data['first_name']} {user_data['last_name'] or ''}
• **Joined:** {user_data['created_at'][:10]}

**💳 Subscription Status:** {status_emoji.get(status, '❓')} {status.title()}
• **Start Date:** {user_stats['subscription_start'][:10] if user_stats['subscription_start'] else 'Never'}
• **End Date:** {user_stats['subscription_end'][:10] if user_stats['subscription_end'] else 'N/A'}
• **Days Remaining:** {user_stats['days_remaining']} days
• **Amount Paid:** ₹{user_stats['payment_amount'] or 0}

**📊 Usage Statistics:**
• **Total Queries:** {user_stats['queries_used']}
• **Payment Reference:** `{user_data['payment_reference'] or 'None'}`
• **Last Updated:** {user_data['updated_at'][:10]}

**🔧 Quick Actions:**
            """
            
            # Add action buttons
            keyboard = []
            if status == 'active':
                keyboard.append([InlineKeyboardButton("🚫 Revoke Access", callback_data=f"revoke_{target_user_id}")])
            elif status in ['expired', 'inactive']:
                keyboard.append([InlineKeyboardButton("✅ Grant Access", callback_data=f"grant_{target_user_id}")])
            
            keyboard.append([InlineKeyboardButton("🔄 Refresh Info", callback_data=f"userinfo_{target_user_id}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            
        except ValueError:
            await update.message.reply_text(
                "❌ **Invalid user ID**\n\nPlease provide a valid numeric user ID.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error in userinfo command: {e}")
            await update.message.reply_text(
                "❌ **Error occurred**\n\nPlease try again.",
                parse_mode='Markdown'
            )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show bot statistics"""
        user = update.effective_user
        
        if not self.is_admin(user.id):
            await update.message.reply_text("🚫 Access denied.")
            return
        
        try:
            active_users = self.db.get_all_active_users()
            total_revenue = len(active_users) * self.subscription_price
            
            # Get additional stats from database
            with self.db.db_path and open(self.db.db_path, 'r') if os.path.exists(self.db.db_path) else None:
                pass  # Database exists
            
            message = f"""
📊 **OSINT Bot Statistics**

**💰 Revenue & Subscriptions:**
• **Active Subscriptions:** {len(active_users)}
• **Total Revenue:** ₹{total_revenue:,.0f}
• **Average per User:** ₹{self.subscription_price}

**📈 Performance:**
• **Subscription Price:** ₹{self.subscription_price}
• **Subscription Duration:** {self.subscription_days} days
• **Bot:** @{self.osint_bot_username}

**📅 Report Generated:** {datetime.now().strftime('%d %b %Y at %H:%M')}

🎯 **Today's Focus:** Maintain quality service and user satisfaction!
            """
            
            keyboard = [
                [InlineKeyboardButton("👥 View Active Users", callback_data="active_users")],
                [InlineKeyboardButton("🔄 Refresh Stats", callback_data="stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text(
                "❌ **Error getting statistics**\n\nPlease try again.",
                parse_mode='Markdown'
            )
    
    async def callback_query_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        user = query.from_user
        
        if not self.is_admin(user.id):
            await query.answer("🚫 Access denied", show_alert=True)
            return
        
        await query.answer()
        
        data = query.data
        
        if data == "stats":
            await self.stats_command(update, context)
        elif data == "active_users":
            await self.show_active_users(query)
        elif data == "all_users":
            await self.show_all_users(query)
        elif data == "revenue":
            await self.show_revenue_report(query)
        elif data.startswith("grant_"):
            user_id = int(data.split("_")[1])
            await self.quick_grant(query, user_id)
        elif data.startswith("revoke_"):
            user_id = int(data.split("_")[1])
            await self.quick_revoke(query, user_id)
        elif data.startswith("userinfo_"):
            user_id = int(data.split("_")[1])
            await self.refresh_userinfo(query, user_id)
    
    async def show_active_users(self, query):
        """Show active users list"""
        try:
            active_users = self.db.get_all_active_users()
            
            if not active_users:
                text = "📭 <b>No Active Users</b>\n\nNo users currently have active subscriptions."
            else:
                text = f"👥 <b>Active Subscribers ({len(active_users)})</b>\n\n"
                
                for i, user in enumerate(active_users[:10], 1):  # Show first 10
                    end_date = user['subscription_end_date'][:10] if user['subscription_end_date'] else 'N/A'
                    created_date = user['created_at'][:10] if user['created_at'] else 'N/A'
                    
                    # Status emoji (all active users get the active emoji)
                    status_emoji = '✅'
                    
                    # User display logic for username
                    username_display = f"@{user['username']}" if user['username'] else '@N/A'
                    
                    # Name display logic
                    if user['first_name'] and user['first_name'] != 'Unknown User':
                        name_display = user['first_name']
                        if user['last_name']:
                            name_display += f" {user['last_name']}"
                    else:
                        name_display = 'N/A'
                    
                    text += f"{i}. {status_emoji} {username_display} ({name_display})\n"
                    text += f"   ID: <code>{user['user_id']}</code> | Joined: {created_date} | Expires: {end_date}\n\n"
                
                if len(active_users) > 10:
                    text += f"... and {len(active_users) - 10} more users\n\n"
                
                text += f"💰 <b>Total Revenue:</b> ₹{len(active_users) * self.subscription_price:,.0f}"
            
            await query.edit_message_text(text, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Error showing active users: {e}")
            await query.edit_message_text("❌ Error loading active users")
    
    async def show_all_users(self, query):
        """Show all users list"""
        try:
            # Get all users from database
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, username, first_name, subscription_status, created_at
                    FROM users 
                    ORDER BY created_at DESC
                    LIMIT 15
                ''')
                users = cursor.fetchall()
            
            if not users:
                text = "📭 <b>No Users Found</b>\n\nNo users in the database yet."
            else:
                text = f"📋 <b>All Users ({len(users)} shown)</b>\n\n"
                
                for i, user in enumerate(users, 1):
                    user_id, username, first_name, status, created = user
                    status_emoji = {'active': '✅', 'expired': '⏰', 'inactive': '🔒'}.get(status, '❓')
                    
                    # Better user display logic
                    if username:
                        user_display = f"@{username}"
                    elif first_name and first_name != 'Unknown User':
                        user_display = first_name
                    else:
                        user_display = f"User {user_id}"
                    
                    text += f"{i}. {status_emoji} {user_display}\n"
                    text += f"   ID: <code>{user_id}</code> | Joined: {created[:10]}\n\n"
            
            await query.edit_message_text(text, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Error showing all users: {e}")
            await query.edit_message_text("❌ Error loading users")
    
    async def show_revenue_report(self, query):
        """Show revenue report"""
        try:
            active_users = self.db.get_all_active_users()
            
            # Get payment statistics
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                # Get total payments
                cursor.execute('SELECT COUNT(*), SUM(amount) FROM payment_logs')
                total_payments, total_revenue = cursor.fetchone()
                
                # Get today's payments
                cursor.execute('''
                    SELECT COUNT(*), SUM(amount) 
                    FROM payment_logs 
                    WHERE date(created_at) = date('now')
                ''')
                today_payments, today_revenue = cursor.fetchone()
                
                # Get this month's payments
                cursor.execute('''
                    SELECT COUNT(*), SUM(amount) 
                    FROM payment_logs 
                    WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
                ''')
                month_payments, month_revenue = cursor.fetchone()
            
            text = f"""
💰 <b>Revenue Report</b>

<b>📊 Current Status:</b>
• Active Subscriptions: {len(active_users)}
• Active Revenue: ₹{len(active_users) * self.subscription_price:,.0f}

<b>💳 Payment Statistics:</b>
• Total Payments: {total_payments or 0}
• Total Revenue: ₹{total_revenue or 0:,.0f}

<b>📅 Today:</b>
• New Payments: {today_payments or 0}
• Today's Revenue: ₹{today_revenue or 0:,.0f}

<b>🗓️ This Month:</b>
• Monthly Payments: {month_payments or 0}
• Monthly Revenue: ₹{month_revenue or 0:,.0f}

<b>📈 Metrics:</b>
• Price per Subscription: ₹{self.subscription_price}
• Subscription Duration: {self.subscription_days} days
• Average Daily Revenue: ₹{(month_revenue or 0) / 30:,.0f}

<b>Generated:</b> {datetime.now().strftime('%d %b %Y at %H:%M')}
            """
            
            await query.edit_message_text(text, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Error showing revenue report: {e}")
            await query.edit_message_text("❌ Error loading revenue report")
    
    async def refresh_userinfo(self, query, user_id):
        """Refresh user information"""
        try:
            user_data = self.db.get_user(user_id)
            user_stats = self.db.get_user_stats(user_id)
            
            if not user_data:
                await query.edit_message_text(f"❌ User {user_id} not found")
                return
            
            status_emoji = {
                'active': '✅',
                'expired': '⏰', 
                'inactive': '🔒'
            }
            
            status = user_stats.get('subscription_status', 'inactive')
            username_display = user_data['username'] or 'N/A'
            
            text = f"""
📋 <b>User Information (Refreshed)</b>

<b>👤 User:</b> @{username_display} ({user_data['first_name']})
<b>ID:</b> <code>{user_id}</code>

<b>💳 Status:</b> {status_emoji.get(status, '❓')} {status.title()}
<b>Days Remaining:</b> {user_stats['days_remaining']}
<b>Queries Used:</b> {user_stats['queries_used']}
<b>Amount Paid:</b> ₹{user_stats['payment_amount'] or 0}

<b>Updated:</b> {datetime.now().strftime('%H:%M:%S')}
            """
            
            # Add action buttons
            keyboard = []
            if status == 'active':
                keyboard.append([InlineKeyboardButton("🚫 Revoke Access", callback_data=f"revoke_{user_id}")])
            elif status in ['expired', 'inactive']:
                keyboard.append([InlineKeyboardButton("✅ Grant Access", callback_data=f"grant_{user_id}")])
            
            keyboard.append([InlineKeyboardButton("🔄 Refresh Again", callback_data=f"userinfo_{user_id}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error refreshing user info: {e}")
            await query.edit_message_text("❌ Error refreshing user information")
    
    async def quick_grant(self, query, user_id):
        """Quick grant subscription via callback"""
        try:
            payment_ref = f"QUICK_GRANT_{datetime.now().strftime('%d%m%Y_%H%M')}"
            
            success = self.db.grant_subscription(
                user_id=user_id,
                days=self.subscription_days,
                amount=self.subscription_price,
                admin_id=query.from_user.id,
                payment_ref=payment_ref
            )
            
            if success:
                await query.edit_message_text(
                    f"✅ **Subscription Granted**\n\n"
                    f"User `{user_id}` now has {self.subscription_days} days access!\n"
                    f"Reference: `{payment_ref}`",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text("❌ Failed to grant subscription")
                
        except Exception as e:
            logger.error(f"Error in quick grant: {e}")
            await query.edit_message_text("❌ Error granting subscription")
    
    async def quick_revoke(self, query, user_id):
        """Quick revoke subscription via callback"""
        try:
            success = self.db.expire_subscription(user_id)
            
            if success:
                await query.edit_message_text(
                    f"🚫 **Subscription Revoked**\n\n"
                    f"User `{user_id}` no longer has access.\n"
                    f"Status updated to expired.",
                    parse_mode='Markdown'
                )
                logger.info(f"Admin {query.from_user.id} revoked subscription for user {user_id}")
            else:
                await query.edit_message_text("❌ Failed to revoke subscription")
                
        except Exception as e:
            logger.error(f"Error in quick revoke: {e}")
            await query.edit_message_text("❌ Error revoking subscription")
    
    def run(self):
        """Start the admin bot with health monitoring"""
        try:
            # Start health check server
            self.health_server.start()
            logger.info(f"Health check server started on port {self.health_server.port}")
            
            # Create the Application
            application = Application.builder().token(self.bot_token).build()
            
            # Add command handlers
            application.add_handler(CommandHandler("start", self.start_command))
            application.add_handler(CommandHandler("grant", self.grant_command))
            application.add_handler(CommandHandler("revoke", self.revoke_command))
            application.add_handler(CommandHandler("userinfo", self.userinfo_command))
            application.add_handler(CommandHandler("stats", self.stats_command))
            
            # Add callback query handler
            application.add_handler(CallbackQueryHandler(self.callback_query_handler))
            
            # Add error handler
            application.add_error_handler(self.error_handler)
            
            logger.info("Starting OSINT Admin Bot...")
            self.is_healthy = True
            
            # Run the bot
            application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            logger.error(f"Error starting admin bot: {e}")
            self.is_healthy = False
            raise
        finally:
            # Cleanup health server
            try:
                self.health_server.stop()
                logger.info("Health check server stopped")
            except Exception as e:
                logger.error(f"Error stopping health server: {e}")


def main():
    """Main function to run the admin bot"""
    try:
        admin_bot = OSINTAdminBot()
        admin_bot.run()
    except KeyboardInterrupt:
        logger.info("Admin bot stopped by user")
    except Exception as e:
        logger.error(f"Admin bot crashed: {e}")
        raise


if __name__ == '__main__':
    main()