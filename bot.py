"""
Hua Bot - Secure Telegram Protection Bot
Features: User management, rate limiting, spam protection, security checks
"""

import sqlite3
import random
import time
from datetime import datetime, timedelta
import logging
import hashlib
import hmac

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

# ============ LOGGING SETUP ============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
BOT_TOKEN = "PUT_Your_Bot_Token"
OPENAI_KEY = "PUT_OPENAI_KEY"
OWNER_ID = 6085226440
OWNER_USERNAME = "Y_O_0_1"
CHANNEL = "@Libya0005"

# Security Configuration
MAX_MESSAGE_LENGTH = 4096
MAX_COMMAND_ARGS = 10
SPAM_THRESHOLD = 10  # messages
SPAM_WINDOW = 60  # seconds
BAN_DURATION = 3600  # 1 hour
RATE_LIMIT_WINDOW = 60  # seconds

# ============ DATABASE SETUP ============
db = sqlite3.connect("bot.db", check_same_thread=False)
c = db.cursor()

c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        money INTEGER DEFAULT 0,
        bank INTEGER DEFAULT 0,
        xp INTEGER DEFAULT 0,
        rank TEXT DEFAULT 'Bronze',
        warn_count INTEGER DEFAULT 0,
        clan TEXT,
        last_daily TEXT,
        last_command TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_banned INTEGER DEFAULT 0,
        ban_reason TEXT,
        ban_expires TIMESTAMP
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS security_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS spam_tracker (
        user_id INTEGER PRIMARY KEY,
        message_count INTEGER DEFAULT 0,
        first_message_time TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
""")

db.commit()

# ============ SYSTEM DATA ============
RANKS = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "GrandMaster"]
COOLDOWNS = {}
SPAM_TRACKER = {}
BLOCKED_WORDS = ["spam", "scam", "hack"]  # Expandable list

# ============ SECURITY FUNCTIONS ============

def log_security_event(user_id: int, action: str, details: str = ""):
    """Log security events to database"""
    try:
        c.execute(
            "INSERT INTO security_logs (user_id, action, details) VALUES (?, ?, ?)",
            (user_id, action, details)
        )
        db.commit()
        logger.info(f"Security Log - User: {user_id}, Action: {action}, Details: {details}")
    except Exception as e:
        logger.error(f"Error logging security event: {e}")

def is_user_banned(user_id: int) -> bool:
    """Check if user is banned and if ban has expired"""
    try:
        c.execute(
            "SELECT is_banned, ban_expires FROM users WHERE id = ?",
            (user_id,)
        )
        result = c.fetchone()
        
        if not result:
            return False
            
        is_banned, ban_expires = result
        
        if is_banned and ban_expires:
            if datetime.now() > datetime.fromisoformat(ban_expires):
                # Ban has expired, unban user
                c.execute(
                    "UPDATE users SET is_banned = 0, ban_expires = NULL WHERE id = ?",
                    (user_id,)
                )
                db.commit()
                log_security_event(user_id, "BAN_EXPIRED", "User ban automatically lifted")
                return False
            return True
        
        return False
    except Exception as e:
        logger.error(f"Error checking ban status: {e}")
        return False

def ban_user(user_id: int, reason: str = "", duration_hours: int = 1):
    """Ban a user for specified duration"""
    try:
        ban_expires = (datetime.now() + timedelta(hours=duration_hours)).isoformat()
        c.execute(
            "UPDATE users SET is_banned = 1, ban_reason = ?, ban_expires = ? WHERE id = ?",
            (reason, ban_expires, user_id)
        )
        db.commit()
        log_security_event(user_id, "BANNED", f"Reason: {reason}, Duration: {duration_hours}h")
        logger.warning(f"User {user_id} banned for {duration_hours} hours. Reason: {reason}")
    except Exception as e:
        logger.error(f"Error banning user: {e}")

def check_message_safety(text: str) -> tuple[bool, str]:
    """Check message for spam/malicious content"""
    if not text:
        return True, ""
    
    # Check length
    if len(text) > MAX_MESSAGE_LENGTH:
        return False, "Message too long"
    
    # Check for blocked words
    text_lower = text.lower()
    for word in BLOCKED_WORDS:
        if word in text_lower:
            return False, f"Blocked content detected: {word}"
    
    # Check for excessive capitalization (spam indicator)
    if len(text) > 10 and sum(1 for c in text if c.isupper()) / len(text) > 0.8:
        return False, "Excessive capitalization"
    
    # Check for repeated characters (spam indicator)
    for i in range(len(text) - 4):
        if len(set(text[i:i+5])) == 1:
            return False, "Repeated characters detected"
    
    return True, ""

def check_spam(user_id: int) -> bool:
    """Check if user is spamming"""
    now = time.time()
    
    if user_id not in SPAM_TRACKER:
        SPAM_TRACKER[user_id] = {"count": 0, "start_time": now}
        return False
    
    tracker = SPAM_TRACKER[user_id]
    
    # Reset if window expired
    if now - tracker["start_time"] > SPAM_WINDOW:
        SPAM_TRACKER[user_id] = {"count": 0, "start_time": now}
        return False
    
    tracker["count"] += 1
    
    if tracker["count"] > SPAM_THRESHOLD:
        log_security_event(user_id, "SPAM_DETECTED", f"Sent {tracker['count']} messages in {SPAM_WINDOW}s")
        return True
    
    return False

def check_cooldown(user_id: int, command: str, seconds: int) -> bool:
    """Check if user is on cooldown for a command"""
    now = time.time()
    key = f"{user_id}_{command}"
    
    if key in COOLDOWNS and now - COOLDOWNS[key] < seconds:
        return False
    
    COOLDOWNS[key] = now
    return True

def ensure_user(user_id: int, first_name: str = "", username: str = ""):
    """Ensure user exists in database"""
    try:
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        if not c.fetchone():
            c.execute(
                """INSERT INTO users 
                (id, first_name, username, money, bank, xp, rank, warn_count, clan, last_daily) 
                VALUES (?, ?, ?, 0, 0, 0, 'Bronze', 0, NULL, '')""",
                (user_id, first_name, username)
            )
            db.commit()
            log_security_event(user_id, "USER_CREATED", f"Username: {username}")
            logger.info(f"New user created: {user_id} (@{username})")
    except Exception as e:
        logger.error(f"Error ensuring user exists: {e}")

def get_rank(xp: int) -> str:
    """Get user rank based on XP"""
    rank_index = min(xp // 100, len(RANKS) - 1)
    return RANKS[rank_index]

def add_warn(user_id: int, reason: str = ""):
    """Add warning to user, ban after 3 warnings"""
    try:
        c.execute("SELECT warn_count FROM users WHERE id = ?", (user_id,))
        result = c.fetchone()
        
        if not result:
            return
        
        warn_count = result[0] + 1
        c.execute("UPDATE users SET warn_count = ? WHERE id = ?", (warn_count, user_id))
        db.commit()
        
        log_security_event(user_id, "WARNING_ADDED", f"Reason: {reason}, Total: {warn_count}")
        
        if warn_count >= 3:
            ban_user(user_id, f"Auto-ban: 3 warnings - {reason}", duration_hours=24)
            return "BANNED"
        
        return warn_count
    except Exception as e:
        logger.error(f"Error adding warning: {e}")
        return 0

# ============ COMMAND HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    try:
        user = update.effective_user
        
        # Security checks
        if is_user_banned(user.id):
            await update.message.reply_text("❌ You are banned from using this bot.")
            return
        
        ensure_user(user.id, user.first_name, user.username)
        
        # Notify owner
        try:
            await context.bot.send_message(
                OWNER_ID,
                f"🔔 New user started bot\n"
                f"👤 Name: {user.first_name}\n"
                f"🆔 ID: {user.id}\n"
                f"📱 Username: @{user.username}\n"
                f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except Exception as e:
            logger.error(f"Error notifying owner: {e}")
        
        # Welcome message with keyboard
        keyboard = [
            [InlineKeyboardButton("💰 Balance", callback_data='balance')],
            [InlineKeyboardButton("⚒️ Work", callback_data='work')],
            [InlineKeyboardButton("📊 Profile", callback_data='profile')],
            [InlineKeyboardButton("❓ Help", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎉 Welcome {user.first_name}!\n\n"
            f"I'm Hua Bot - your secure Telegram companion.\n"
            f"Use /help for available commands.",
            reply_markup=reply_markup
        )
        
        log_security_event(user.id, "BOT_START", "User started bot session")
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    try:
        user = update.effective_user
        
        if is_user_banned(user.id):
            await update.message.reply_text("❌ You are banned from using this bot.")
            return
        
        help_text = """
🤖 **Hua Bot Commands:**

💰 **Economy:**
/balance - Check your balance
/work - Earn money (cooldown: 3s)
/daily - Claim daily reward
/gamble <amount> - Gamble your money

🧠 **AI:**
/ai <prompt> - Ask AI questions (GPT-4o-mini)

👤 **Profile:**
/profile - View your profile
/rank - Check your rank

⚙️ **Moderator Commands:**
/warn <user_id> - Warn a user
/ban <user_id> - Ban a user
/unban <user_id> - Unban a user

🔒 **Security Features:**
- Spam protection
- Rate limiting
- Content filtering
- User authentication
- Automatic ban system
- Security logging

Use commands carefully. Abuse may result in ban.
"""
        await update.message.reply_text(help_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in help handler: {e}")

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ai command with OpenAI"""
    try:
        user = update.effective_user
        user_id = user.id
        
        # Security checks
        if is_user_banned(user_id):
            await update.message.reply_text("❌ You are banned from using this bot.")
            return
        
        if check_spam(user_id):
            await update.message.reply_text("⚠️ You're sending messages too fast. Please slow down.")
            ban_user(user_id, "Spam detected", duration_hours=1)
            return
        
        ensure_user(user_id, user.first_name, user.username)
        
        if not context.args or len(context.args) > MAX_COMMAND_ARGS:
            await update.message.reply_text("❌ Usage: /ai <your question>")
            return
        
        if not check_cooldown(user_id, "ai", 5):
            await update.message.reply_text("⏱️ Please wait 5 seconds before using AI again.")
            return
        
        prompt = " ".join(context.args[:MAX_COMMAND_ARGS])
        is_safe, safety_msg = check_message_safety(prompt)
        
        if not is_safe:
            log_security_event(user_id, "UNSAFE_CONTENT_DETECTED", safety_msg)
            await update.message.reply_text(f"⚠️ Message rejected: {safety_msg}")
            add_warn(user_id, f"Unsafe content in AI prompt: {safety_msg}")
            return
        
        await update.message.reply_text("🤔 Thinking...")
        
        try:
            client = OpenAI(api_key=OPENAI_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content
            
            # Ensure response isn't too long
            if len(answer) > MAX_MESSAGE_LENGTH:
                answer = answer[:MAX_MESSAGE_LENGTH] + "...\n\n(Response truncated)"
            
            await update.message.reply_text(f"🤖 **AI Response:**\n\n{answer}", parse_mode='Markdown')
            log_security_event(user_id, "AI_COMMAND_EXECUTED", f"Prompt: {prompt[:50]}...")
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            await update.message.reply_text("❌ Error connecting to AI. Please try again later.")
            add_warn(user_id, "AI API error")
    
    except Exception as e:
        logger.error(f"Error in ai_command: {e}")
        await update.message.reply_text("❌ An error occurred.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command"""
    try:
        user = update.effective_user
        user_id = user.id
        
        if is_user_banned(user_id):
            await update.message.reply_text("❌ You are banned.")
            return
        
        ensure_user(user_id, user.first_name, user.username)
        
        c.execute("SELECT money, bank, xp, rank FROM users WHERE id = ?", (user_id,))
        result = c.fetchone()
        
        if result:
            money, bank, xp, rank = result
            total = money + bank
            
            balance_text = f"""
💰 **Balance:**
👛 Wallet: ${money:,}
🏦 Bank: ${bank:,}
💵 Total: ${total:,}

📊 **Stats:**
⭐ XP: {xp}
🏆 Rank: {rank}
            """
            await update.message.reply_text(balance_text, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ User not found.")
    
    except Exception as e:
        logger.error(f"Error in balance: {e}")
        await update.message.reply_text("❌ Error retrieving balance.")

async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /work command"""
    try:
        user = update.effective_user
        user_id = user.id
        
        if is_user_banned(user_id):
            await update.message.reply_text("❌ You are banned.")
            return
        
        ensure_user(user_id, user.first_name, user.username)
        
        if not check_cooldown(user_id, "work", 3):
            await update.message.reply_text("⏱️ You need to wait 3 seconds before working again.")
            return
        
        earn = random.randint(10, 50)
        xp_gain = random.randint(5, 15)
        
        c.execute(
            "UPDATE users SET money = money + ?, xp = xp + ? WHERE id = ?",
            (earn, xp_gain, user_id)
        )
        db.commit()
        
        new_rank = get_rank(xp_gain)
        await update.message.reply_text(
            f"✅ Work complete!\n"
            f"💵 Earned: ${earn}\n"
            f"⭐ XP gained: {xp_gain}"
        )
        log_security_event(user_id, "WORK_COMPLETED", f"Earned: ${earn}, XP: {xp_gain}")
    
    except Exception as e:
        logger.error(f"Error in work: {e}")
        await update.message.reply_text("❌ Error processing work.")

async def daily_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /daily command"""
    try:
        user = update.effective_user
        user_id = user.id
        
        if is_user_banned(user_id):
            await update.message.reply_text("❌ You are banned.")
            return
        
        ensure_user(user_id, user.first_name, user.username)
        
        c.execute("SELECT last_daily FROM users WHERE id = ?", (user_id,))
        result = c.fetchone()
        
        today = str(datetime.now().date())
        last_daily = result[0] if result else ""
        
        if last_daily == today:
            await update.message.reply_text("📅 You've already claimed your daily reward today!")
            return
        
        reward = random.randint(200, 500)
        
        c.execute(
            "UPDATE users SET money = money + ?, last_daily = ? WHERE id = ?",
            (reward, today, user_id)
        )
        db.commit()
        
        await update.message.reply_text(
            f"🎁 Daily Reward Claimed!\n"
            f"💵 Reward: ${reward}"
        )
        log_security_event(user_id, "DAILY_CLAIMED", f"Amount: ${reward}")
    
    except Exception as e:
        logger.error(f"Error in daily_reward: {e}")
        await update.message.reply_text("❌ Error claiming daily reward.")

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /warn command (Admin only)"""
    try:
        user = update.effective_user
        
        # Check if user is owner
        if user.id != OWNER_ID:
            await update.message.reply_text("❌ Only the bot owner can use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /warn <user_id> [reason]")
            return
        
        try:
            target_id = int(context.args[0])
            reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
            return
        
        result = add_warn(target_id, reason)
        
        if result == "BANNED":
            await update.message.reply_text(
                f"⛔ User {target_id} has been automatically banned (3 warnings).\n"
                f"Reason: {reason}"
            )
        else:
            await update.message.reply_text(
                f"⚠️ User {target_id} warned ({result}/3).\n"
                f"Reason: {reason}"
            )
    
    except Exception as e:
        logger.error(f"Error in warn_user: {e}")
        await update.message.reply_text("❌ Error warning user.")

async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ban command (Admin only)"""
    try:
        user = update.effective_user
        
        if user.id != OWNER_ID:
            await update.message.reply_text("❌ Only the bot owner can use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /ban <user_id> [duration_hours] [reason]")
            return
        
        try:
            target_id = int(context.args[0])
            duration = int(context.args[1]) if len(context.args) > 1 else 24
            reason = " ".join(context.args[2:]) if len(context.args) > 2 else "No reason provided"
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID or duration.")
            return
        
        ban_user(target_id, reason, duration)
        await update.message.reply_text(
            f"🚫 User {target_id} banned for {duration} hour(s).\n"
            f"Reason: {reason}"
        )
    
    except Exception as e:
        logger.error(f"Error in ban_user_command: {e}")
        await update.message.reply_text("❌ Error banning user.")

async def unban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unban command (Admin only)"""
    try:
        user = update.effective_user
        
        if user.id != OWNER_ID:
            await update.message.reply_text("❌ Only the bot owner can use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /unban <user_id>")
            return
        
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
            return
        
        c.execute(
            "UPDATE users SET is_banned = 0, ban_reason = NULL, ban_expires = NULL WHERE id = ?",
            (target_id,)
        )
        db.commit()
        
        log_security_event(target_id, "UNBANNED", f"By: {user.id}")
        await update.message.reply_text(f"✅ User {target_id} has been unbanned.")
    
    except Exception as e:
        logger.error(f"Error in unban_user_command: {e}")
        await update.message.reply_text("❌ Error unbanning user.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages with security checks"""
    try:
        user = update.effective_user
        user_id = user.id
        
        if is_user_banned(user_id):
            return
        
        ensure_user(user_id, user.first_name, user.username)
        
        message_text = update.message.text or ""
        
        # Check spam
        if check_spam(user_id):
            log_security_event(user_id, "SPAM_VIOLATION", message_text[:50])
            add_warn(user_id, "Spamming messages")
            await update.message.reply_text("⚠️ Please don't spam messages.")
            return
        
        # Check message safety
        is_safe, safety_msg = check_message_safety(message_text)
        if not is_safe:
            log_security_event(user_id, "UNSAFE_MESSAGE", safety_msg)
            await update.message.reply_text(f"⚠️ Your message was rejected: {safety_msg}")
            add_warn(user_id, f"Unsafe message: {safety_msg}")
            return
    
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    try:
        query = update.callback_query
        user = query.from_user
        
        if is_user_banned(user.id):
            await query.answer("❌ You are banned.", show_alert=True)
            return
        
        await query.answer()
        
        if query.data == 'balance':
            ensure_user(user.id, user.first_name, user.username)
            c.execute("SELECT money, bank, xp, rank FROM users WHERE id = ?", (user.id,))
            result = c.fetchone()
            
            if result:
                money, bank, xp, rank = result
                total = money + bank
                
                await query.edit_message_text(
                    f"💰 **Balance:**\n"
                    f"👛 Wallet: ${money:,}\n"
                    f"🏦 Bank: ${bank:,}\n"
                    f"💵 Total: ${total:,}\n\n"
                    f"⭐ XP: {xp}\n"
                    f"🏆 Rank: {rank}",
                    parse_mode='Markdown'
                )
        
        elif query.data == 'work':
            if not check_cooldown(user.id, "work", 3):
                await query.answer("⏱️ Please wait 3 seconds.", show_alert=True)
                return
            
            earn = random.randint(10, 50)
            xp_gain = random.randint(5, 15)
            
            c.execute(
                "UPDATE users SET money = money + ?, xp = xp + ? WHERE id = ?",
                (earn, xp_gain, user.id)
            )
            db.commit()
            
            await query.edit_message_text(
                f"✅ **Work Complete!**\n"
                f"💵 Earned: ${earn}\n"
                f"⭐ XP: {xp_gain}"
            )
    
    except Exception as e:
        logger.error(f"Error in button_callback: {e}")

# ============ MAIN APPLICATION ============

def main():
    """Start the bot"""
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("work", work))
    app.add_handler(CommandHandler("daily", daily_reward))
    app.add_handler(CommandHandler("warn", warn_user))
    app.add_handler(CommandHandler("ban", ban_user_command))
    app.add_handler(CommandHandler("unban", unban_user_command))
    
    # Message and callback handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("🤖 Hua Bot is starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
