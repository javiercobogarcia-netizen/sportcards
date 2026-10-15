import sqlite3
import os

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
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            gemini_raw TEXT
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER NOT NULL,
            price REAL,
            source TEXT,
            recorded_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (card_id) REFERENCES cards(id)
        );
    ''')
    conn.commit()
    conn.close()

def get_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT
            COUNT(*) as total_cards,
            SUM(CASE WHEN status='owned' THEN 1 ELSE 0 END) as owned,
            SUM(CASE WHEN status='sold' THEN 1 ELSE 0 END) as sold,
            SUM(CASE WHEN status='owned' THEN purchase_price ELSE 0 END) as total_invested,
            SUM(CASE WHEN status='owned' THEN COALESCE(market_price, purchase_price) ELSE 0 END) as current_value,
            SUM(CASE WHEN status='sold' THEN (sale_price - purchase_price) ELSE 0 END) as total_profit
        FROM cards
    ''')
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}

def get_all_cards(status=None, search=None, sport=None, year=None, set_name=None):
    conn = get_db()
    c = conn.cursor()
    query = 'SELECT * FROM cards WHERE 1=1'
    params = []
    if status:
        query += ' AND status = ?'
        params.append(status)
    if search:
        query += ' AND (player LIKE ? OR set_name LIKE ? OR team LIKE ?)'
        like = f'%{search}%'
        params.extend([like, like, like])
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

def get_filter_options():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT DISTINCT sport FROM cards WHERE sport IS NOT NULL ORDER BY sport')
    sports = [r[0] for r in c.fetchall()]
    c.execute('SELECT DISTINCT year FROM cards WHERE year IS NOT NULL ORDER BY year DESC')
    years = [r[0] for r in c.fetchall()]
    c.execute('SELECT DISTINCT set_name FROM cards WHERE set_name IS NOT NULL ORDER BY set_name')
    sets = [r[0] for r in c.fetchall()]
    conn.close()
    return {'sports': sports, 'years': years, 'sets': sets}

def get_card(card_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM cards WHERE id = ?', (card_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def create_card(data):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO cards
        (player, year, sport, team, set_name, variant, card_number, numbering,
         graded, grading_company, grade, photo_front, photo_back,
         purchase_price, purchase_date, market_price, market_price_updated, notes, gemini_raw)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        data.get('player'), data.get('year'), data.get('sport'), data.get('team'),
        data.get('set_name'), data.get('variant'), data.get('card_number'),
        data.get('numbering'), data.get('graded', 0), data.get('grading_company'),
        data.get('grade'), data.get('photo_front'), data.get('photo_back'),
        data.get('purchase_price'), data.get('purchase_date'),
        data.get('market_price'), data.get('market_price_updated'),
        data.get('notes'), data.get('gemini_raw')
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
               'market_price_updated','qr_code','notes']
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
