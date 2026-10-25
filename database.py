import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(__file__))
DB_PATH = os.path.join(DATA_DIR, 'sportcards.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            player TEXT NOT NULL,
            year INTEGER,
            sport TEXT,
            team TEXT,
            set_name TEXT,
            variant TEXT,
            card_number TEXT,
            numbering TEXT,
            graded INTEGER DEFAULT 0,
            grading_company TEXT,
            grade TEXT,
            photo_front TEXT,
            photo_back TEXT,
            purchase_price REAL,
            purchase_date TEXT,
            sale_price REAL,
            sale_date TEXT,
            status TEXT DEFAULT 'owned',
            market_price REAL,
            market_price_updated TEXT,
            qr_code TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            gemini_raw TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER NOT NULL,
            price REAL,
            source TEXT,
            recorded_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (card_id) REFERENCES cards(id)
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            trade_date TEXT,
            notes TEXT,
            counterpart TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS trade_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            card_id INTEGER,
            direction TEXT NOT NULL,
            player TEXT,
            description TEXT,
            value REAL,
            FOREIGN KEY (trade_id) REFERENCES trades(id),
            FOREIGN KEY (card_id) REFERENCES cards(id)
        );
    ''')
    # Migraciones para bases de datos antiguas
    migrations = [
        'ALTER TABLE cards ADD COLUMN user_id INTEGER DEFAULT 1',
        'ALTER TABLE cards ADD COLUMN personal_collection INTEGER DEFAULT 0',
        'ALTER TABLE cards ADD COLUMN traded_in_trade_id INTEGER',
    ]
    for sql in migrations:
        try:
            c.execute(sql)
            conn.commit()
        except Exception:
            pass
    conn.commit()
    conn.close()

# --- Usuarios ---

def create_user(username, password):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                  (username.strip().lower(), generate_password_hash(password)))
        user_id = c.lastrowid
        conn.commit()
        conn.close()
        return user_id, None
    except sqlite3.IntegrityError:
        conn.close()
        return None, 'El usuario ya existe'

def get_user_by_username(username):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username.strip().lower(),))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def verify_user(username, password):
    user = get_user_by_username(username)
    if not user:
        return None
    if check_password_hash(user['password_hash'], password):
        return user
    return None

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, username, created_at FROM users WHERE id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, username, created_at FROM users ORDER BY id')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Cartas ---

def get_stats(user_id=None):
    conn = get_db()
    c = conn.cursor()
    where = 'WHERE user_id = ?' if user_id else ''
    params = (user_id,) if user_id else ()
    c.execute(f'''
        SELECT
            COUNT(*) as total_cards,
            SUM(CASE WHEN status='owned' THEN 1 ELSE 0 END) as owned,
            SUM(CASE WHEN status='sold' THEN 1 ELSE 0 END) as sold,
            SUM(CASE WHEN status='owned' THEN COALESCE(purchase_price, 0) ELSE 0 END) as total_invested,
            SUM(CASE WHEN status='owned' THEN COALESCE(market_price, purchase_price, 0) ELSE 0 END) as current_value,
            SUM(CASE WHEN status='sold' AND purchase_price IS NOT NULL THEN (sale_price - purchase_price) ELSE 0 END) as total_profit
        FROM cards {where}
    ''', params)
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}

def get_all_cards(status=None, search=None, sport=None, year=None, set_name=None, user_id=None):
    conn = get_db()
    c = conn.cursor()
    query = 'SELECT * FROM cards WHERE 1=1'
    params = []
    if user_id:
        query += ' AND user_id = ?'
        params.append(user_id)
    if status:
        query += ' AND status = ?'
        params.append(status)
    if search:
        query += ' AND (player LIKE ? OR set_name LIKE ? OR team LIKE ? OR variant LIKE ?)'
        like = f'%{search}%'
        params.extend([like, like, like, like])
    if sport:
        query += ' AND sport = ?'
        params.append(sport)
    if year:
        query += ' AND year = ?'
        params.append(int(year))
    if set_name:
        query += ' AND set_name = ?'
        params.append(set_name)
    query += ' ORDER BY created_at DESC'
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_filter_options(user_id=None):
    conn = get_db()
    c = conn.cursor()
    if user_id:
        c.execute('SELECT DISTINCT sport FROM cards WHERE user_id=? AND sport IS NOT NULL ORDER BY sport', (user_id,))
        sports = [r[0] for r in c.fetchall()]
        c.execute('SELECT DISTINCT year FROM cards WHERE user_id=? AND year IS NOT NULL ORDER BY year DESC', (user_id,))
        years = [r[0] for r in c.fetchall()]
        c.execute('SELECT DISTINCT set_name FROM cards WHERE user_id=? AND set_name IS NOT NULL ORDER BY set_name', (user_id,))
        sets = [r[0] for r in c.fetchall()]
    else:
        c.execute('SELECT DISTINCT sport FROM cards WHERE sport IS NOT NULL ORDER BY sport')
        sports = [r[0] for r in c.fetchall()]
        c.execute('SELECT DISTINCT year FROM cards WHERE year IS NOT NULL ORDER BY year DESC')
        years = [r[0] for r in c.fetchall()]
        c.execute('SELECT DISTINCT set_name FROM cards WHERE set_name IS NOT NULL ORDER BY set_name')
        sets = [r[0] for r in c.fetchall()]
    conn.close()
    return {'sports': sports, 'years': years, 'sets': sets}

def get_card(card_id, user_id=None):
    conn = get_db()
    c = conn.cursor()
    if user_id:
        c.execute('SELECT * FROM cards WHERE id = ? AND user_id = ?', (card_id, user_id))
    else:
        c.execute('SELECT * FROM cards WHERE id = ?', (card_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def create_card(data, user_id=1):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO cards
        (user_id, player, year, sport, team, set_name, variant, card_number, numbering,
         graded, grading_company, grade, photo_front, photo_back,
         purchase_price, purchase_date, market_price, market_price_updated, notes, gemini_raw,
         personal_collection)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        user_id,
        data.get('player'), data.get('year'), data.get('sport'), data.get('team'),
        data.get('set_name'), data.get('variant'), data.get('card_number'),
        data.get('numbering'), data.get('graded', 0), data.get('grading_company'),
        data.get('grade'), data.get('photo_front'), data.get('photo_back'),
        data.get('purchase_price'), data.get('purchase_date'),
        data.get('market_price'), data.get('market_price_updated'),
        data.get('notes'), data.get('gemini_raw'),
        1 if data.get('personal_collection') else 0
    ))
    card_id = c.lastrowid
    conn.commit()
    conn.close()
    return card_id

def update_card(card_id, data):
    conn = get_db()
    c = conn.cursor()
    fields = []
    params = []
    allowed = ['player','year','sport','team','set_name','variant','card_number',
               'numbering','graded','grading_company','grade','purchase_price',
               'purchase_date','sale_price','sale_date','status','market_price',
               'market_price_updated','qr_code','notes','personal_collection',
               'traded_in_trade_id']
    for field in allowed:
        if field in data:
            fields.append(f'{field} = ?')
            params.append(data[field])
    if not fields:
        return
    params.append(card_id)
    c.execute(f'UPDATE cards SET {", ".join(fields)} WHERE id = ?', params)
    conn.commit()
    conn.close()

def add_price_history(card_id, price, source):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO price_history (card_id, price, source) VALUES (?,?,?)',
              (card_id, price, source))
    conn.commit()
    conn.close()

def get_price_history(card_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM price_history WHERE card_id = ? ORDER BY recorded_at DESC LIMIT 20',
              (card_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats_by_sport(user_id=None):
    conn = get_db()
    c = conn.cursor()
    where = 'AND user_id = ?' if user_id else ''
    params = (user_id,) if user_id else ()
    c.execute(f'''
        SELECT sport,
            COUNT(*) as total,
            SUM(CASE WHEN status='owned' THEN 1 ELSE 0 END) as owned,
            SUM(CASE WHEN status='sold' THEN 1 ELSE 0 END) as sold,
            SUM(COALESCE(purchase_price, 0)) as invested
        FROM cards WHERE sport IS NOT NULL {where}
        GROUP BY sport ORDER BY total DESC
    ''', params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_top_cards(user_id=None, limit=5):
    conn = get_db()
    c = conn.cursor()
    where = 'AND user_id = ?' if user_id else ''
    params = (user_id,) if user_id else ()
    c.execute(f'''
        SELECT *, (COALESCE(market_price, purchase_price, 0) - COALESCE(purchase_price, 0)) as gain
        FROM cards WHERE status='owned' AND purchase_price IS NOT NULL {where}
        ORDER BY gain DESC LIMIT ?
    ''', (*params, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats_by_player(user_id=None, limit=20):
    conn = get_db()
    c = conn.cursor()
    where = 'WHERE user_id = ?' if user_id else ''
    params = (user_id,) if user_id else ()
    c.execute(f'''
        SELECT player,
               COUNT(*) as total,
               SUM(CASE WHEN status='owned' THEN 1 ELSE 0 END) as owned,
               SUM(CASE WHEN status='sold' THEN 1 ELSE 0 END) as sold,
               SUM(COALESCE(purchase_price, 0)) as total_invested,
               SUM(CASE WHEN status='sold' THEN COALESCE(sale_price,0) - COALESCE(purchase_price,0) ELSE 0 END) as profit
        FROM cards {where}
        GROUP BY player
        ORDER BY total DESC
        LIMIT ?
    ''', (*params, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_alerts(user_id=None):
    conn = get_db()
    c = conn.cursor()
    where = 'AND user_id = ?' if user_id else ''
    params = (user_id,) if user_id else ()
    c.execute(f'''
        SELECT COUNT(*) as count FROM cards
        WHERE status='owned'
        AND personal_collection = 0
        AND purchase_date IS NOT NULL
        AND purchase_date <= date('now', '-6 months')
        {where}
    ''', params)
    old_cards = c.fetchone()['count']

    c.execute(f'''
        SELECT id, player, purchase_date FROM cards
        WHERE status='owned'
        AND personal_collection = 0
        AND purchase_date IS NOT NULL
        AND purchase_date <= date('now', '-6 months')
        {where}
        ORDER BY purchase_date ASC
        LIMIT 10
    ''', params)
    old_cards_list = [dict(r) for r in c.fetchall()]
    conn.close()
    return {'old_cards_count': old_cards, 'old_cards': old_cards_list}

def get_profit_by_period(user_id=None):
    conn = get_db()
    c = conn.cursor()
    where = 'AND user_id = ?' if user_id else ''
    params = (user_id,) if user_id else ()

    def query(period_filter):
        c.execute(f'''
            SELECT
                COUNT(*) as sold_count,
                COALESCE(SUM(sale_price - COALESCE(purchase_price, 0)), 0) as profit
            FROM cards
            WHERE status='sold' AND sale_date IS NOT NULL
            AND sale_date >= {period_filter}
            {where}
        ''', params)
        return dict(c.fetchone())

    result = {
        'today':   query("date('now')"),
        'week':    query("date('now', '-7 days')"),
        'month':   query("date('now', '-30 days')"),
        'quarter': query("date('now', '-90 days')"),
        'year':    query("date('now', '-365 days')"),
        'all':     query("'1900-01-01'"),
    }

    c.execute(f'''
        SELECT
            strftime('%Y-%m', sale_date) as month,
            COUNT(*) as sold_count,
            COALESCE(SUM(sale_price - COALESCE(purchase_price, 0)), 0) as profit
        FROM cards
        WHERE status='sold' AND sale_date IS NOT NULL
        AND sale_date >= date('now', '-12 months')
        {where}
        GROUP BY month ORDER BY month ASC
    ''', params)
    result['by_month'] = [dict(r) for r in c.fetchall()]

    conn.close()
    return result

# --- Trades ---

def create_trade(data, user_id=1):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO trades (user_id, trade_date, notes, counterpart)
        VALUES (?, ?, ?, ?)
    ''', (user_id, data.get('trade_date'), data.get('notes'), data.get('counterpart')))
    trade_id = c.lastrowid

    for card in data.get('give', []):
        card_id = card.get('card_id')
        value = card.get('value')
        c.execute('''
            INSERT INTO trade_cards (trade_id, card_id, direction, player, description, value)
            VALUES (?, ?, 'give', ?, ?, ?)
        ''', (trade_id, card_id, card.get('player'), card.get('description'), value))
        if card_id:
            c.execute("UPDATE cards SET status='traded', traded_in_trade_id=? WHERE id=?",
                      (trade_id, card_id))

    for card in data.get('receive', []):
        card_id = card.get('card_id')
        c.execute('''
            INSERT INTO trade_cards (trade_id, card_id, direction, player, description, value)
            VALUES (?, ?, 'receive', ?, ?, ?)
        ''', (trade_id, card_id, card.get('player'), card.get('description'), card.get('value')))

    conn.commit()
    conn.close()
    return trade_id

def get_trades(user_id=None):
    conn = get_db()
    c = conn.cursor()
    where = 'WHERE t.user_id = ?' if user_id else ''
    params = (user_id,) if user_id else ()
    c.execute(f'''
        SELECT t.*,
            (SELECT COALESCE(SUM(tc.value),0) FROM trade_cards tc WHERE tc.trade_id=t.id AND tc.direction='give') as give_value,
            (SELECT COALESCE(SUM(tc.value),0) FROM trade_cards tc WHERE tc.trade_id=t.id AND tc.direction='receive') as receive_value
        FROM trades t {where}
        ORDER BY t.trade_date DESC, t.created_at DESC
    ''', params)
    trades = [dict(r) for r in c.fetchall()]
    for trade in trades:
        c.execute("SELECT * FROM trade_cards WHERE trade_id=?", (trade['id'],))
        trade['cards'] = [dict(r) for r in c.fetchall()]
    conn.close()
    return trades

def get_trade(trade_id, user_id=None):
    conn = get_db()
    c = conn.cursor()
    if user_id:
        c.execute('SELECT * FROM trades WHERE id=? AND user_id=?', (trade_id, user_id))
    else:
        c.execute('SELECT * FROM trades WHERE id=?', (trade_id,))
    trade = c.fetchone()
    if not trade:
        conn.close()
        return None
    trade = dict(trade)
    c.execute("SELECT * FROM trade_cards WHERE trade_id=?", (trade_id,))
    trade['cards'] = [dict(r) for r in c.fetchall()]
    conn.close()
    return trade
