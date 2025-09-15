# Admin/Subscription Bot Deployment Guide

## 🚀 Render.com Deployment

### Prerequisites
1. GitHub repository with this folder's code
2. **NEW** Telegram bot token from @BotFather for @subscriptionOSINTbot
3. Main bot token (for database access)

### Step 1: Create Admin Bot Token
1. Message @BotFather on Telegram
2. Send `/newbot`
3. Bot Name: `OSINT Subscription Manager`
4. Username: `subscriptionOSINTbot`
5. **Copy the token** - this is your `ADMIN_BOT_TOKEN`

### Step 2: Create Render Service
1. Go to Render.com dashboard
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. **Important**: Select this folder (`osint-admin-bot`) as the root directory

### Step 3: Service Configuration
- **Name**: `osint-admin-bot`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python main.py`
- **Plan**: Free
- **Health Check Path**: `/health`

### Step 4: Environment Variables
Set these in Render dashboard:
```
PYTHONUNBUFFERED=1
PORT=8001
ADMIN_BOT_TOKEN=your_admin_bot_token
ADMIN_BOT_USERNAME=subscriptionOSINTbot
ADMIN_USER_ID=5682019164
TELEGRAM_BOT_TOKEN=your_main_bot_token
BOT_USERNAME=reosintbot
LOG_LEVEL=INFO
```

**Critical**: 
- `ADMIN_BOT_TOKEN` = New token for @subscriptionOSINTbot
- `TELEGRAM_BOT_TOKEN` = Same as main bot (for database only)

### Step 5: Deploy
1. Click "Create Web Service"
2. Wait for deployment
3. Check health: `https://your-admin-service.onrender.com/health`

## ✅ Success Indicators
- Service shows "Live" status
- Health endpoint returns JSON with "healthy": true
- No "Conflict" errors in logs
- Admin bot responds to /start command

## 👥 Admin Access
Only these users can use the admin bot:
- @boyonthegrid (ID: 5682019164)
- @ded_xdk (ID: 1844138085)

## 🔧 Local Testing
```bash
# Copy environment file
cp .env.example .env
# Edit .env with your tokens (BOTH tokens needed!)

# Install dependencies
pip install -r requirements.txt

# Run bot
python main.py
```