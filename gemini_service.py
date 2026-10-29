import os
import json
import time
from google import genai
from google.genai import types

def identify_card(front_path, back_path=None):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key or api_key == 'TU_CLAVE_AQUI':
        return None, 'API key de Gemini no configurada'

    client = genai.Client(api_key=api_key)

    prompt = """Eres un experto en cartas coleccionables: sport cards (Panini, Topps, Upper Deck, Prizm, Select, Immaculate, Optic, Chronicles, Bowman, Fleer, Donruss) Y cartas Pokémon (Base Set, Jungle, Fossil, Neo, EX, Diamond & Pearl, Black & White, XY, Sun & Moon, Sword & Shield, Scarlet & Violet, y todas las expansiones).

Analiza DETENIDAMENTE estas imágenes e identifica la carta. Determina PRIMERO si es una carta Pokémon o una sport card.

Para SPORT CARDS presta atención a:
- Nombre completo del jugador
- Variante/insert: Watercolors, Shimmer, Gold Vinyl, Refractor, Prizm, Holo, Silver, Base, Rookie (RC), Auto (Autograph/firma), Patch, Logoman, Signatures, RPA (Rookie Patch Auto)
- Si hay firma visible → variante incluye "Auto" o "Signatures"
- Si hay pieza de jersey/parche tela → variante incluye "Patch" o "Memorabilia"
- Numeración exacta impresa (ej: 05/25 → numbering: "25", número específico en notes)
- Rookie Card: si hay etiqueta RC o es primera carta del jugador → variant incluye "Rookie" o "RC"

Para CARTAS POKÉMON:
- Nombre del Pokémon en campo "player"
- Expansión completa en "set_name" (ej: "Pokémon Scarlet & Violet — Obsidian Flames", "Pokémon Base Set")
- Variante: Holo, Reverse Holo, Full Art, Secret Rare, Ultra Rare, Gold, Rainbow, VMAX, VSTAR, ex, EX, GX, V, Amazing Rare, Illustration Rare, Special Illustration Rare
- Número de carta (ej: "025/198") en card_number
- sport: "pokemon"
- team: tipo del Pokémon (ej: "Fire", "Water", "Psychic")
- Si está en estuche de gradeo (PSA, CGC, BGS): graded=1

Devuelve SOLO un JSON válido (sin texto, sin markdown):
{
  "player": "nombre del jugador o Pokémon",
  "year": 2024,
  "sport": "fútbol|baloncesto|béisbol|fútbol americano|hockey|golf|pokemon|otro",
  "team": "equipo del jugador o tipo del Pokémon",
  "set_name": "nombre COMPLETO del set incluyendo marca",
  "variant": "variante/parallel/insert. Nunca null si hay alguna. Para Pokémon incluir rareza.",
  "card_number": "número de carta (ej: WCS-GON, #123, 025/198)",
  "numbering": "solo el número máximo SIN barra (ej: 25 para /25, 1 para 1/1). null si no está numerada.",
  "graded": 0,
  "grading_company": null,
  "grade": null,
  "notes": "detalles: número específico si numerada (ej: carta 05 de 25), autógrafo, RC, cualquier dato relevante"
}

Si está en estuche de gradeo: graded=1, rellena grading_company y grade.
Responde ÚNICAMENTE con el JSON."""

    contents = [prompt]

    try:
        with open(front_path, 'rb') as f:
            front_bytes = f.read()
        contents.append(types.Part.from_bytes(data=front_bytes, mime_type='image/jpeg'))
    except Exception as e:
        return None, f'Error leyendo foto delantera: {e}'

    if back_path and os.path.exists(back_path):
        try:
            with open(back_path, 'rb') as f:
                back_bytes = f.read()
            contents.append(types.Part.from_bytes(data=back_bytes, mime_type='image/jpeg'))
        except Exception:
            pass

    last_error = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=contents,
            )
            raw = response.text.strip()

            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
                raw = raw.strip()

            data = json.loads(raw)
            data['gemini_raw'] = response.text
            return data, None

        except json.JSONDecodeError:
            return {'gemini_raw': response.text, 'player': '', 'year': None,
                    'sport': None, 'team': None, 'set_name': None, 'variant': None,
                    'card_number': None, 'numbering': None, 'graded': 0,
                    'grading_company': None, 'grade': None, 'notes': None}, None
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(5)

    return None, str(last_error)


def identify_sealed(photo_path):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key or api_key == 'TU_CLAVE_AQUI':
        return None, 'API key de Gemini no configurada'

    client = genai.Client(api_key=api_key)

    prompt = """Eres un experto en producto sellado de cartas coleccionables (trading cards): hobby boxes, blaster boxes, fat packs, collector boxes, mega boxes, hanger boxes, tins, cases, etc. de marcas como Topps, Panini, Upper Deck, Bowman, Select, Prizm, Optic, Chronicles, Immaculate, National Treasures, Leaf, Donruss, Fleer, Score, y también productos de Pokémon TCG.

Analiza esta imagen e identifica el producto sellado.

Devuelve SOLO un JSON válido (sin texto, sin markdown):
{
  "name": "nombre completo del producto (ej: 2024 Topps Chrome Baseball Hobby Box)",
  "product_type": "hobby_box|blaster|fat_pack|collector_box|mega_box|hanger|tin|case|other",
  "sport": "fútbol|baloncesto|béisbol|fútbol americano|hockey|golf|pokemon|otro",
  "year": 2024,
  "brand": "Topps|Panini|Upper Deck|Bowman|etc",
  "notes": "detalles relevantes: número de packs por caja, autos garantizados, edición especial, etc."
}

Responde ÚNICAMENTE con el JSON."""

    try:
        with open(photo_path, 'rb') as f:
            photo_bytes = f.read()
    except Exception as e:
        return None, f'Error leyendo foto: {e}'

    last_error = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[prompt, types.Part.from_bytes(data=photo_bytes, mime_type='image/jpeg')],
            )
            raw = response.text.strip()
            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
                raw = raw.strip()
            data = json.loads(raw)
            return data, None
        except json.JSONDecodeError:
            return {'gemini_raw': response.text, 'name': '', 'product_type': 'other',
                    'sport': None, 'year': None, 'brand': None, 'notes': None}, None
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(5)

    return None, str(last_error)
