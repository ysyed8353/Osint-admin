# 🤖 Telegram Bot + Flask API Architecture

## 🏗️ Architecture Overview

```
┌─────────────────┐    HTTP/JSON     ┌─────────────────┐
│  Telegram Bot   │ ──────────────► │   Flask API     │
│  (Local Client) │                 │ (Render Server) │ 
│                 │ ◄────────────── │                 │
└─────────────────┘                 └─────────────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │ Supabase Database│
                                    └─────────────────┘
```

## 🎯 Benefits of This Setup

✅ **Free Tier Compatible** - Flask API runs as web service on Render free tier  
✅ **Best User Experience** - Telegram bot provides familiar interface  
✅ **Scalable** - API can handle multiple clients  
✅ **Secure** - API key authentication + admin user validation  
✅ **Reliable** - No bot conflicts or deployment issues  
✅ **Flexible** - Can add web dashboard, mobile app, or other clients later  

## 📁 File Structure

```
osint-admin-bot/
├── app.py                    # Flask API server (deploys to Render)
├── telegram_client.py        # Telegram bot client (runs locally)
├── requirements.txt          # API server dependencies
├── requirements.client.txt   # Telegram client dependencies
├── .env.example             # API server environment template
├── .env.client.example      # Telegram client environment template
└── Procfile                 # Render deployment config
```

## 🚀 Deployment Steps

### 1. Deploy Flask API to Render

1. **Commit and push** your changes to GitHub
2. In Render dashboard, deploy `osint-admin-api` service
3. **Set environment variables** in Render:
   - `ADMIN_API_KEY` - Generate a strong secret key
   - `SUPABASE_URL` - Your Supabase project URL
   - `SUPABASE_KEY` - Your Supabase anon key
   - `ADMIN_USER_ID` - Your admin user ID

4. **Get the API URL** from Render (e.g., `https://osint-admin-api.onrender.com`)

### 2. Set up Local Telegram Bot

1. **Install dependencies:**
   ```bash
   pip install -r requirements.client.txt
   ```

2. **Create `.env` file** (copy from `.env.client.example`):
   ```bash
   ADMIN_BOT_TOKEN=your_admin_bot_token_here
   API_BASE_URL=https://osint-admin-api.onrender.com
   ADMIN_API_KEY=same-key-you-set-in-render
   ```

3. **Run the Telegram bot locally:**
   ```bash
   python telegram_client.py
   ```

### 3. Test the System

1. **Check API health:** Visit your Render URL in browser
2. **Test bot:** Send `/start` to your admin bot
3. **Verify connection:** Use `/health` command in bot

## 🔧 API Endpoints

The Flask API provides these endpoints for the Telegram bot:

| Endpoint | Purpose | Bot Command |
|----------|---------|-------------|
| `POST /api/telegram/verify-admin` | Verify admin access | Automatic |
| `POST /api/telegram/stats` | Get statistics | `/stats` |
| `POST /api/telegram/users` | List users | `/users [page]` |
| `POST /api/telegram/user-info` | Get user details | `/info <user_id>` |
| `POST /api/telegram/grant-subscription` | Grant subscription | `/grant <user_id> [days]` |
| `POST /api/telegram/revoke-subscription` | Revoke subscription | `/revoke <user_id>` |

## 🛠️ Bot Commands

Once running, your admin bot supports:

- `/start` - Welcome message and help
- `/health` - Check API connection
- `/stats` - View bot statistics  
- `/users [page]` - List users with pagination
- `/info <user_id>` - Get user information
- `/grant <user_id> [days]` - Grant subscription (default 21 days)
- `/revoke <user_id>` - Revoke user subscription

## 🔒 Security Features

- **API Key Authentication** - All requests require valid API key
- **Admin User Validation** - Only authorized user IDs can access
- **HTTPS Communication** - Secure API communication
- **Environment Variables** - Sensitive data protected

## 🐛 Troubleshooting

### Bot Not Responding
1. Check if `telegram_client.py` is running locally
2. Verify `.env` file has correct `ADMIN_BOT_TOKEN`
3. Test API connection with `/health` command

### API Connection Failed
1. Check if Render service is running
2. Verify `API_BASE_URL` in client `.env`
3. Ensure `ADMIN_API_KEY` matches between client and server
4. Check Render logs for errors

### Database Errors
1. Run the SQL fix in Supabase:
   ```sql
   ALTER TABLE users DISABLE ROW LEVEL SECURITY;
   ALTER TABLE payments DISABLE ROW LEVEL SECURITY;
   ```
2. Verify Supabase credentials in Render environment variables

## 💡 Future Enhancements

This architecture supports easy additions:
- **Web Dashboard** - Add HTML interface to Flask API
- **Mobile App** - Create mobile client using same API
- **Webhooks** - Add webhook endpoints for external integrations
- **Multiple Bots** - Multiple Telegram bots can use same API
- **Analytics** - Add usage tracking and reporting

## 📊 Example Usage

```bash
# Terminal 1: Run API (or deploy to Render)
python app.py

# Terminal 2: Run Telegram bot
python telegram_client.py

# Telegram chat:
/start
/stats
/users 1
/grant 123456789 21
/info 123456789
```

This setup gives you the best of both worlds - a reliable, scalable API backend with an intuitive Telegram bot interface!