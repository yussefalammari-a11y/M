# Hua Bot - Secure Telegram Protection Bot

🤖 A comprehensive Telegram bot with advanced security features, economy system, and AI integration.

## Features

### 🔒 Security Features
- **Spam Protection**: Real-time detection of message flooding
- **Content Filtering**: Blocks harmful keywords and malicious patterns
- **Rate Limiting**: Cooldown system for all commands
- **User Ban System**: Temporary and permanent bans with auto-expiration
- **3-Strike Warning System**: Automatic ban after 3 warnings
- **Security Logging**: Complete audit trail of all actions
- **Message Validation**: Length checks and pattern detection

### 💰 Economy System
- **Wallet & Bank**: Manage money across accounts
- **/work**: Earn money (3-second cooldown)
- **/daily**: Claim daily rewards
- **XP & Ranks**: Level up through activities
  - Bronze → Silver → Gold → Platinum → Diamond → Master → GrandMaster

### 🧠 AI Integration
- **/ai <prompt>**: Ask questions to GPT-4o-mini
- Safe prompt validation
- Rate-limited to prevent abuse
- Response truncation for Telegram limits

### ⚙️ Admin Commands
- **/warn <user_id>**: Issue warnings (3 warnings = auto-ban)
- **/ban <user_id> [hours] [reason]**: Ban users temporarily or permanently
- **/unban <user_id>**: Lift user bans

### 📊 User Management
- Automatic user registration
- Profile tracking (money, XP, rank, warnings)
- Session logging
- User activity monitoring

## Installation

### Prerequisites
- Python 3.8+
- Telegram Bot Token
- OpenAI API Key

### Setup Steps

1. **Clone the repository**
```bash
git clone https://github.com/yussefalammari-a11y/M.git
cd M
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
cp .env.example .env
```

4. **Edit .env file with your credentials**
```env
BOT_TOKEN=8403529159:AAFV6IZff9znjQO-5y1j7lOnsmf-Qq3zGVU
OPENAI_KEY=your_openai_api_key_here
OWNER_ID=6085226440
OWNER_USERNAME=Y_O_0_1
CHANNEL=@Libya0005
```

5. **Run the bot**
```bash
python bot.py
```

## Configuration

### Environment Variables (`.env`)

```env
# Telegram Bot Token
BOT_TOKEN=8403529159:AAFV6IZff9znjQO-5y1j7lOnsmf-Qq3zGVU

# OpenAI API Key
OPENAI_KEY=your_openai_key_here

# Bot Owner Details
OWNER_ID=6085226440
OWNER_USERNAME=Y_O_0_1
CHANNEL=@Libya0005

# Security Settings (optional)
MAX_MESSAGE_LENGTH=4096
SPAM_THRESHOLD=10
SPAM_WINDOW=60
```

### Security Configuration

Edit `bot.py` to customize:

```python
# Security Configuration
MAX_MESSAGE_LENGTH = 4096      # Max message length
MAX_COMMAND_ARGS = 10          # Max command arguments
SPAM_THRESHOLD = 10            # Messages before spam trigger
SPAM_WINDOW = 60               # Spam detection window (seconds)
BAN_DURATION = 3600            # Default ban duration (seconds)

# Blocked Words
BLOCKED_WORDS = ["spam", "scam", "hack"]  # Add more as needed
```

## Commands

### User Commands

| Command | Description | Cooldown |
|---------|-------------|----------|
| `/start` | Start the bot | None |
| `/help` | Show all commands | None |
| `/balance` | Check your balance | None |
| `/work` | Earn money | 3 seconds |
| `/daily` | Claim daily reward | 24 hours |
| `/ai <prompt>` | Ask AI a question | 5 seconds |

### Admin Commands (Owner Only)

| Command | Description |
|---------|-------------|
| `/warn <user_id> [reason]` | Warn a user |
| `/ban <user_id> [hours] [reason]` | Ban a user |
| `/unban <user_id>` | Unban a user |

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    money INTEGER,
    bank INTEGER,
    xp INTEGER,
    rank TEXT,
    warn_count INTEGER,
    clan TEXT,
    last_daily TEXT,
    created_at TIMESTAMP,
    is_banned INTEGER,
    ban_reason TEXT,
    ban_expires TIMESTAMP
)
```

### Security Logs Table
```sql
CREATE TABLE security_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    action TEXT,
    details TEXT,
    timestamp TIMESTAMP
)
```

## Security Features in Detail

### Spam Detection
- Monitors messages per user
- Resets counter every 60 seconds
- Auto-bans user after 10 messages in 60 seconds
- Logs all spam violations

### Content Filtering
- **Blocked Keywords**: Customizable list
- **Capitalization Check**: Detects excessive caps (>80%)
- **Repeated Characters**: Detects patterns like "AAAAAAA"
- **Length Validation**: Enforces message length limits

### Warning System
1️⃣ First warning → User notified
2️⃣ Second warning → User warned
3️⃣ Third warning → **Auto-ban for 24 hours**

Auto-ban can be lifted with `/unban` command by owner.

### Ban System
- **Temporary Bans**: Auto-expire after set duration
- **Permanent Bans**: Manual unban required
- **Ban Tracking**: All bans logged with reason and expiry
- **Auto-Expiration**: System checks and lifts expired bans automatically

## Usage Examples

### Start the Bot
```bash
python bot.py
```

### Use /ai Command
```
User: /ai What is Python?
Bot: 🤔 Thinking...
Bot: 🤖 AI Response: Python is a high-level programming language...
```

### Check Balance
```
User: /balance
Bot: 💰 Balance:
     👛 Wallet: $500
     🏦 Bank: $1,000
     💵 Total: $1,500
     
     📊 Stats:
     ⭐ XP: 250
     🏆 Rank: Silver
```

### Work Command
```
User: /work
Bot: ✅ Work complete!
     💵 Earned: $35
     ⭐ XP gained: 12
```

### Admin: Ban User
```
Owner: /ban 123456789 24 Spamming messages
Bot: 🚫 User 123456789 banned for 24 hour(s).
     Reason: Spamming messages
```

## Error Handling

The bot includes comprehensive error handling:
- ✅ Try-except blocks in all handlers
- ✅ Graceful degradation on API failures
- ✅ Detailed logging for debugging
- ✅ User-friendly error messages

## Logging

All events are logged to:
- **Console**: Real-time output
- **Database**: Security logs table
- **Files**: Check logs with `logging` module

### Log Levels
- `INFO`: Normal operations
- `WARNING`: Ban actions, security violations
- `ERROR`: API errors, exceptions

## API Integration

### OpenAI GPT-4o-mini
- Model: `gpt-4o-mini`
- Max tokens: 1024
- Temperature: 0.7
- Safe prompts: Validated before sending

## Performance

- **Database**: SQLite (lightweight, local)
- **Threading**: Non-blocking async handlers
- **Memory**: Efficient spam tracking
- **Scalability**: Built for multiple users

## Troubleshooting

### Bot not responding
1. Check bot token in `.env`
2. Verify internet connection
3. Check logs: `python bot.py 2>&1 | tee bot.log`

### AI commands not working
1. Verify OpenAI API key
2. Check API quota/billing
3. Ensure prompt is under 10 arguments

### Database errors
1. Delete `bot.db` to reset
2. Restart bot (will recreate schema)
3. Check file permissions

### Spam detection too aggressive
Adjust in `bot.py`:
```python
SPAM_THRESHOLD = 15  # Increase this
SPAM_WINDOW = 120    # Increase this
```

## Security Best Practices

✅ **Do:**
- Keep tokens in `.env` (never commit)
- Regularly update dependencies
- Monitor security logs
- Use strong passwords for accounts
- Test commands before deploying

❌ **Don't:**
- Share bot tokens publicly
- Store credentials in code
- Run with elevated permissions unnecessarily
- Disable security features
- Add untrusted code

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Contact: [@Y_O_0_1](https://t.me/Y_O_0_1)

## Changelog

### Version 1.0.0 (2026-05-08)
- ✅ Initial release
- ✅ Core bot functionality
- ✅ Security features
- ✅ Economy system
- ✅ AI integration
- ✅ Admin commands

---

**Made with ❤️ by Yussef Al-Ammari**

🚀 **Status**: Active & Maintained
