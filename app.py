import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps

load_dotenv()

from database import (init_db as _init_db, get_stats, get_all_cards, get_card, create_card, update_card,
                      add_price_history, get_price_history, get_filter_options,
                      create_user, verify_user, get_user, get_all_users,
                      get_stats_by_sport, get_top_cards, get_stats_by_player)
from gemini_service import identify_card
from ebay_service import search_card_price
from qr_service import generate_qr
from excel_service import export_collection

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('SECRET_KEY', 'sportcards-2024')
app.permanent_session_lifetime = timedelta(days=365)

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
