# Admin/Subscription Bot
Telegram bot for managing OSINT bot subscriptions

## Features
- User subscription management
- Grant/revoke access
- User statistics and analytics
- Admin-only access (@boyonthegrid, @ded_xdk)

## Deployment
- Deploy this folder as a separate Render service
- Uses @subscriptionOSINTbot token (different from main bot!)
- Health check on port 8001

## Environment Variables
```
ADMIN_BOT_TOKEN=your_admin_bot_token
ADMIN_BOT_USERNAME=subscriptionOSINTbot
ADMIN_USER_ID=5682019164
TELEGRAM_BOT_TOKEN=your_main_bot_token
BOT_USERNAME=reosintbot
PORT=8001
LOG_LEVEL=INFO
```

**Note**: Uses main bot token for database access only!