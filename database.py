import aiosqlite
import logging

logger = logging.getLogger(__name__)
DB_NAME = "casino_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0 NOT NULL,
                games_played INTEGER DEFAULT 0 NOT NULL,
                games_won INTEGER DEFAULT 0 NOT NULL,
                total_wagered INTEGER DEFAULT 0 NOT NULL,
                net_profit INTEGER DEFAULT 0 NOT NULL,
                nickname TEXT
            )
        ''')
        await db.commit()
        logger.info("База данных и таблица 'users' успешно проверены/созданы.")

async def add_user_if_not_exists(user_id: int, username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if not await cursor.fetchone():
            await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        else:
            await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        await db.commit()

async def get_user_balance(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def update_user_balance(user_id: int, amount: int, relative: bool = False):
    async with aiosqlite.connect(DB_NAME) as db:
        if relative:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        else:
            await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def update_user_stats(user_id: int, bet: int, win_amount: int):
    is_win = 1 if win_amount > 0 else 0
    profit = win_amount - bet
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE users 
            SET games_played = games_played + 1,
                games_won = games_won + ?,
                total_wagered = total_wagered + ?,
                net_profit = net_profit + ?
            WHERE user_id = ?
        """, (is_win, bet, profit, user_id))
        await db.commit()

async def get_top_users(limit: int = 10) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT user_id, username, nickname, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
        return await cursor.fetchall()

async def set_user_nickname(user_id: int, nickname: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET nickname = ? WHERE user_id = ?", (nickname, user_id))
        await db.commit()

async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_global_stats() -> dict | None:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT 
                COUNT(user_id) as total_users,
                SUM(balance) as total_balance,
                SUM(games_played) as total_games,
                SUM(total_wagered) as total_wager,
                SUM(net_profit) as casino_profit
            FROM users
        """)
        row = await cursor.fetchone()
        return dict(row) if row else None