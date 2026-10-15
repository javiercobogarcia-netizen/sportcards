import google.generativeai as genai
import os
import json
import base64
from PIL import Image

def identify_card(front_path, back_path=None):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key or api_key == 'TU_CLAVE_AQUI':
        return None, 'API key de Gemini no configurada'

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-3.8-flash')

    parts = []

    try:
        img_front = Image.open(front_path)
        parts.append(img_front)
    except Exception as e:
        return None, f'Error leyendo foto delantera: {e}'

    if back_path and os.path.exists(back_path):
        try:
            img_back = Image.open(back_path)
            parts.append(img_back)
        except Exception:
            pass

    prompt = """Eres un experto en cartas de deporte (sport cards), especialmente de Panini, Topps, Upper Deck, Prizm, Select, Immaculate, Impeccable, National Treasures, Optic, Chronicles y otras colecciones.

Analiza DETENIDAMENTE estas imágenes e identifica todos los datos. Presta especial atención a:
- El nombre del INSERT o VARIANTE que aparece en la carta (ej: Watercolors, Shimmer, Gold Vinyl, Refractor, Prizm, Holo, Silver, Base, Rookie, Auto, Patch, Logoman, etc.)
- Si hay autógrafo (firma) visible → indica "Autograph" o "Auto" en la variante
- Si hay pieza de jersey/parche → indica "Patch" o "Memorabilia"
- La numeración exacta que aparece impresa (ej: 05/25, 12/99, 1/1)
- El año de la temporada (puede aparecer como "2024-25", "Season 2024-25", etc.)

Devuelve SOLO un JSON válido con esta estructura exacta (sin texto adicional, sin markdown):
{
  "player": "nombre completo del jugador",
  "year": 2024,
  "sport": "fútbol|baloncesto|béisbol|fútbol americano|hockey|otro",
  "team": "nombre del equipo",
  "set_name": "nombre COMPLETO del set incluyendo la marca (ej: Panini Prizm EuroLeague, Topps Chrome, Panini Impeccable EuroLeague)",
  "variant": "nombre del insert/variante/parallel (ej: Watercolors Signatures, Gold Refractor, Silver Prizm, Base, Rookie Auto Patch). Si tiene autógrafo incluye 'Auto' o 'Signatures'. NUNCA pongas null si hay alguna variante visible.",
  "card_number": "número de carta si aparece en la carta (ej: WCS-GON, #123)",
  "numbering": "solo el número máximo de la tirada SIN barra (ej: si pone 05/25 escribe 25, si pone /99 escribe 99, si es 1/1 escribe 1). null si no está numerada.",
  "graded": 0,
  "grading_company": null,
  "grade": null,
  "notes": "detalle adicional: si está numerada indica el número específico (ej: 05/25), si tiene autógrafo menciónalo, cualquier dato relevante"
}

Si la carta está en un estuche de gradeo (PSA, BGS, SGC, CGC): graded=1, rellena grading_company y grade.
Responde ÚNICAMENTE con el JSON, sin explicaciones, sin bloques de código."""

    try:
        response = model.generate_content([prompt] + parts)
        raw = response.text.strip()

        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]

        data = json.loads(raw)
        data['gemini_raw'] = response.text
        return data, None

    except json.JSONDecodeError:
        return {'gemini_raw': response.text, 'player': '', 'year': None,
                'sport': None, 'team': None, 'set_name': None, 'variant': None,
                'card_number': None, 'numbering': None, 'graded': 0,
                'grading_company': None, 'grade': None, 'notes': None}, None
    except Exception as e:
        return None, str(e)
