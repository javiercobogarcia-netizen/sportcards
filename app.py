import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps

load_dotenv()

from database import (init_db as _init_db, get_stats, get_all_cards, get_card, create_card, update_card,
                      add_price_history, get_price_history, get_filter_options,
                      create_user, verify_user, get_user, get_all_users,
                      get_stats_by_sport, get_top_cards)
from gemini_service import identify_card
from ebay_service import search_card_price
from qr_service import generate_qr
from excel_service import export_collection

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('SECRET_KEY', 'sportcards-2024')

# Inicializar BD siempre (también con gunicorn en producción)
_init_db()

DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'heic', 'heif'}

def allowed_file(filename, content_type=None):
    if content_type and content_type.startswith('image/'):
        return True
    if not filename or '.' not in filename:
        return bool(content_type and content_type.startswith('image/'))
    return filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

def current_user_id():
    return session.get('user_id', 1)

def save_photo(file, subfolder):
    from PIL import Image
    dest_dir = os.path.join(UPLOAD_DIR, subfolder)
    os.makedirs(dest_dir, exist_ok=True)
    filename = f'{uuid.uuid4().hex}.jpg'
    path = os.path.join(dest_dir, filename)
    img = Image.open(file.stream)
    img = img.convert('RGB')
    img.thumbnail((1200, 1200), Image.LANCZOS)
    img.save(path, 'JPEG', quality=75, optimize=True)
    return path, f'uploads/{subfolder}/{filename}'

# --- Páginas ---

@app.route('/login', methods=['GET'])
def login_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'error': 'Usuario y contraseña requeridos'}), 400
    user = verify_user(username, password)
    if not user:
        return jsonify({'error': 'Usuario o contraseña incorrectos'}), 401
    session['user_id'] = user['id']
    session['username'] = user['username']
    return jsonify({'ok': True, 'username': user['username']})

@app.route('/register', methods=['POST'])
def do_register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'error': 'Usuario y contraseña requeridos'}), 400
    if len(password) < 4:
        return jsonify({'error': 'La contraseña debe tener al menos 4 caracteres'}), 400
    user_id, error = create_user(username, password)
    if error:
        return jsonify({'error': error}), 400
    session['user_id'] = user_id
    session['username'] = username.lower()
    return jsonify({'ok': True, 'username': username.lower()})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', username=session.get('username'))

@app.route('/add')
@login_required
def add_page():
    return render_template('add_card.html')

@app.route('/collection')
@login_required
def collection_page():
    return render_template('collection.html')

@app.route('/card/<int:card_id>')
@login_required
def card_detail(card_id):
    return render_template('card_detail.html', card_id=card_id)

@app.route('/stats')
@login_required
def stats_page():
    return render_template('stats.html', username=session.get('username'))

@app.route('/user/<username>')
@login_required
def user_collection(username):
    from database import get_user_by_username
    target = get_user_by_username(username)
    if not target:
        return 'Usuario no encontrado', 404
    if target['id'] == session.get('user_id'):
        return redirect(url_for('collection_page'))
    return render_template('collection_readonly.html',
                           target_username=target['username'],
                           viewer_username=session.get('username'))

# --- API ---

@app.route('/api/users')
@login_required
def api_users():
    users = get_all_users()
    me = session.get('user_id')
    return jsonify([u for u in users if u['id'] != me])

@app.route('/api/user/<username>/cards')
@login_required
def api_user_cards(username):
    from database import get_user_by_username
    target = get_user_by_username(username)
    if not target:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    status = request.args.get('status')
    search = request.args.get('q')
    sport = request.args.get('sport')
    year = request.args.get('year')
    set_name = request.args.get('set')
    cards = get_all_cards(status=status, search=search, sport=sport, year=year,
                          set_name=set_name, user_id=target['id'])
    return jsonify(cards)

@app.route('/api/user/<username>/filter-options')
@login_required
def api_user_filter_options(username):
    from database import get_user_by_username
    target = get_user_by_username(username)
    if not target:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    return jsonify(get_filter_options(user_id=target['id']))

@app.route('/api/stats')
@login_required
def api_stats():
    return jsonify(get_stats(user_id=current_user_id()))

@app.route('/api/stats/detail')
@login_required
def api_stats_detail():
    uid = current_user_id()
    return jsonify({
        'by_sport': get_stats_by_sport(user_id=uid),
        'top_cards': get_top_cards(user_id=uid),
        'general': get_stats(user_id=uid)
    })

@app.route('/api/cards')
@login_required
def api_cards():
    status = request.args.get('status')
    search = request.args.get('q')
    sport = request.args.get('sport')
    year = request.args.get('year')
    set_name = request.args.get('set')
    cards = get_all_cards(status=status, search=search, sport=sport, year=year, set_name=set_name, user_id=current_user_id())
    return jsonify(cards)

@app.route('/api/filter-options')
@login_required
def api_filter_options():
    return jsonify(get_filter_options(user_id=current_user_id()))

@app.route('/api/card/<int:card_id>')
@login_required
def api_card(card_id):
    card = get_card(card_id, user_id=current_user_id())
    if not card:
        return jsonify({'error': 'Carta no encontrada'}), 404
    card['price_history'] = get_price_history(card_id)
    return jsonify(card)

@app.route('/api/identify', methods=['POST'])
@login_required
def api_identify():
    front_file = request.files.get('front')
    back_file = request.files.get('back')

    if not front_file:
        return jsonify({'error': 'Foto delantera requerida'}), 400

    try:
        front_path, front_rel = save_photo(front_file, 'fronts')
    except Exception as e:
        return jsonify({'error': f'Error procesando foto delantera: {str(e)} (filename={front_file.filename}, ct={front_file.content_type})'}), 400
    back_path = None
    back_rel = None
    if back_file:
        try:
            back_path, back_rel = save_photo(back_file, 'backs')
        except Exception:
            pass

    data, error = identify_card(front_path, back_path)
    if error:
        return jsonify({'error': error}), 500

    data['photo_front'] = front_rel
    data['photo_back'] = back_rel

    # Precio de eBay automático (si está configurado)
    if data.get('player') and data.get('sport') != 'pokemon':
        result, _ = search_card_price(
            data.get('player'), data.get('year'), data.get('set_name'),
            data.get('numbering'), None, None
        )
        if result:
            data['market_price'] = result['average']
            data['market_price_updated'] = result['updated']
            data['ebay_result'] = result

    return jsonify(data)

@app.route('/api/cards', methods=['POST'])
@login_required
def api_create_card():
    data = request.get_json()
    if not data or not data.get('player'):
        return jsonify({'error': 'El nombre del jugador es requerido'}), 400

    card_id = create_card(data, user_id=current_user_id())

    qr_path = generate_qr(card_id)
    update_card(card_id, {'qr_code': qr_path})

    if data.get('purchase_price'):
        add_price_history(card_id, data['purchase_price'], 'compra')
    if data.get('market_price'):
        add_price_history(card_id, data['market_price'], 'ebay')

    return jsonify({'id': card_id, 'qr_code': qr_path}), 201

@app.route('/api/card/<int:card_id>', methods=['PUT'])
@login_required
def api_update_card(card_id):
    card = get_card(card_id, user_id=current_user_id())
    if not card:
        return jsonify({'error': 'No autorizado'}), 403
    data = request.get_json()
    update_card(card_id, data)
    if data.get('market_price'):
        add_price_history(card_id, data['market_price'], 'mercado')
    if data.get('sale_price'):
        add_price_history(card_id, data['sale_price'], 'venta')
    return jsonify({'ok': True})

@app.route('/api/card/<int:card_id>/sell', methods=['POST'])
@login_required
def api_sell_card(card_id):
    card = get_card(card_id, user_id=current_user_id())
    if not card:
        return jsonify({'error': 'No autorizado'}), 403
    data = request.get_json()
    sale_price = data.get('sale_price')
    if not sale_price:
        return jsonify({'error': 'Precio de venta requerido'}), 400
    update_card(card_id, {
        'sale_price': sale_price,
        'sale_date': data.get('sale_date', datetime.now().strftime('%Y-%m-%d')),
        'status': 'sold'
    })
    add_price_history(card_id, sale_price, 'venta')
    card = get_card(card_id)
    purchase = card.get('purchase_price') or 0
    profit = round(float(sale_price) - purchase, 2)
    roi = round((profit / purchase) * 100, 1) if purchase else 0
    return jsonify({'profit': profit, 'roi': roi})

@app.route('/api/card/<int:card_id>/market-price', methods=['POST'])
@login_required
def api_market_price(card_id):
    card = get_card(card_id, user_id=current_user_id())
    if not card:
        return jsonify({'error': 'Carta no encontrada'}), 404

    if card.get('sport') == 'pokemon':
        result, error = search_pokemon_price(card.get('player'), card.get('set_name'), card.get('card_number'))
    else:
        result, error = search_card_price(
            card.get('player'), card.get('year'), card.get('set_name'),
            card.get('numbering'), card.get('grading_company'), card.get('grade')
        )

    if error:
        return jsonify({'error': error}), 500

    update_card(card_id, {
        'market_price': result['average'],
        'market_price_updated': result['updated']
    })
    add_price_history(card_id, result['average'], 'mercado')
    return jsonify(result)

@app.route('/api/export')
@login_required
def api_export():
    status = request.args.get('status')
    cards = get_all_cards(status=status, user_id=current_user_id())
    path, filename = export_collection(cards)
    return send_file(path, as_attachment=True, download_name=filename)

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route('/qrcodes/<path:filename>')
def serve_qr(filename):
    from qr_service import QR_DIR
    return send_from_directory(QR_DIR, filename)

@app.route('/static/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js')

def search_pokemon_price(name, set_name, card_number):
    """Busca precio en eBay para cartas Pokémon."""
    return search_card_price(name, None, set_name, None, None, None)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5052, debug=True)
