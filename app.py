import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from datetime import datetime

load_dotenv()

from database import init_db, get_stats, get_all_cards, get_card, create_card, update_card, add_price_history, get_price_history, get_filter_options
from gemini_service import identify_card
from ebay_service import search_card_price
from qr_service import generate_qr
from excel_service import export_collection

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('SECRET_KEY', 'sportcards-2024')

# En Render DATA_DIR=/data (disco persistente). En local, carpeta del proyecto.
DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'heic', 'heif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_photo(file, subfolder):
    from PIL import Image
    import io
    dest_dir = os.path.join(UPLOAD_DIR, subfolder)
    os.makedirs(dest_dir, exist_ok=True)
    filename = f'{uuid.uuid4().hex}.jpg'
    path = os.path.join(dest_dir, filename)
    # Comprimir: máx 1200px, calidad 75% → ~150KB por foto
    img = Image.open(file.stream)
    img = img.convert('RGB')
    img.thumbnail((1200, 1200), Image.LANCZOS)
    img.save(path, 'JPEG', quality=75, optimize=True)
    return path, f'uploads/{subfolder}/{filename}'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add')
def add_page():
    return render_template('add_card.html')

@app.route('/collection')
def collection_page():
    return render_template('collection.html')

@app.route('/card/<int:card_id>')
def card_detail(card_id):
    return render_template('card_detail.html', card_id=card_id)

# --- API ---

@app.route('/api/stats')
def api_stats():
    return jsonify(get_stats())

@app.route('/api/cards')
def api_cards():
    status = request.args.get('status')
    search = request.args.get('q')
    sport = request.args.get('sport')
    year = request.args.get('year')
    set_name = request.args.get('set')
    cards = get_all_cards(status=status, search=search, sport=sport, year=year, set_name=set_name)
    return jsonify(cards)

@app.route('/api/filter-options')
def api_filter_options():
    return jsonify(get_filter_options())

@app.route('/api/card/<int:card_id>')
def api_card(card_id):
    card = get_card(card_id)
    if not card:
        return jsonify({'error': 'Carta no encontrada'}), 404
    card['price_history'] = get_price_history(card_id)
    return jsonify(card)

@app.route('/api/identify', methods=['POST'])
def api_identify():
    front_file = request.files.get('front')
    back_file = request.files.get('back')

    if not front_file or not allowed_file(front_file.filename):
        return jsonify({'error': 'Foto delantera requerida'}), 400

    front_path, front_rel = save_photo(front_file, 'fronts')
    back_path = None
    back_rel = None
    if back_file and allowed_file(back_file.filename):
        back_path, back_rel = save_photo(back_file, 'backs')

    data, error = identify_card(front_path, back_path)
    if error:
        return jsonify({'error': error}), 500

    data['photo_front'] = front_rel
    data['photo_back'] = back_rel
    return jsonify(data)

@app.route('/api/cards', methods=['POST'])
def api_create_card():
    data = request.get_json()
    if not data or not data.get('player'):
        return jsonify({'error': 'El nombre del jugador es requerido'}), 400

    card_id = create_card(data)

    qr_path = generate_qr(card_id)
    update_card(card_id, {'qr_code': qr_path})

    if data.get('purchase_price'):
        add_price_history(card_id, data['purchase_price'], 'compra')

    return jsonify({'id': card_id, 'qr_code': qr_path}), 201

@app.route('/api/card/<int:card_id>', methods=['PUT'])
def api_update_card(card_id):
    data = request.get_json()
    update_card(card_id, data)

    if data.get('market_price'):
        add_price_history(card_id, data['market_price'], 'mercado')
    if data.get('sale_price'):
        add_price_history(card_id, data['sale_price'], 'venta')

    return jsonify({'ok': True})

@app.route('/api/card/<int:card_id>/sell', methods=['POST'])
def api_sell_card(card_id):
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
def api_market_price(card_id):
    card = get_card(card_id)
    if not card:
        return jsonify({'error': 'Carta no encontrada'}), 404

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
    add_price_history(card_id, result['average'], 'ebay')
    return jsonify(result)

@app.route('/api/export')
def api_export():
    status = request.args.get('status')
    cards = get_all_cards(status=status)
    path, filename = export_collection(cards)
    return send_file(path, as_attachment=True, download_name=filename)

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route('/qrcodes/<path:filename>')
def serve_qr(filename):
    qr_dir = os.path.join(os.path.dirname(__file__), 'qrcodes')
    return send_from_directory(qr_dir, filename)

@app.route('/static/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5052, debug=True)
