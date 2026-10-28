import requests
import os
import re
from datetime import datetime

FINDING_API_URL = 'https://svcs.ebay.com/services/search/FindingService/v1'
BROWSE_API_URL = 'https://api.ebay.com/buy/browse/v1/item_summary/search'


def _get_oauth_token(app_id, cert_id):
    credentials = f'{app_id}:{cert_id}'
    encoded = __import__('base64').b64encode(credentials.encode()).decode()
    try:
        r = requests.post(
            'https://api.ebay.com/identity/v1/oauth2/token',
            headers={
                'Authorization': f'Basic {encoded}',
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            data='grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope',
            timeout=8
        )
        if r.status_code == 200:
            return r.json().get('access_token')
    except Exception:
        pass
    return None


def get_ebay_token():
    app_id = os.getenv('EBAY_APP_ID')
    cert_id = os.getenv('EBAY_CERT_ID', '')
    if not app_id or app_id == 'TU_EBAY_APP_ID_AQUI':
        return None
    return _get_oauth_token(app_id, cert_id)


def _build_query(player, year, set_name, numbering=None, grading_company=None, grade=None):
    parts = [player]
    year_str = str(year) if year else ''
    short_set = re.sub(r'^\d{4}(-\d{2})?\s+', '', set_name or '').strip()
    if year_str:
        parts.insert(0, year_str)
    if short_set:
        parts.append(short_set)
    if numbering:
        parts.append(numbering)
    if grading_company and grade:
        parts.append(f'{grading_company} {grade}')
    return ' '.join(p for p in parts if p).strip()


def _fetch_sold_finding(query, app_id, token, limit=12):
    params = {
        'OPERATION-NAME': 'findCompletedItems',
        'SERVICE-VERSION': '1.0.0',
        'SECURITY-APPNAME': app_id,
        'RESPONSE-DATA-FORMAT': 'JSON',
        'keywords': query,
        'categoryId': '212',
        'itemFilter(0).name': 'SoldItemsOnly',
        'itemFilter(0).value': 'true',
        'sortOrder': 'EndTimeSoonest',
        'paginationInput.entriesPerPage': str(limit),
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (compatible; SportCardsApp/1.0)',
    }
    r = requests.get(FINDING_API_URL, headers=headers, params=params, timeout=10)
    if r.status_code == 418:
        return None, '418'
    if r.status_code != 200:
        return None, f'eBay error {r.status_code}'
    data = r.json()
    result = data.get('findCompletedItemsResponse', [{}])[0]
    if result.get('ack', [''])[0] != 'Success':
        return None, 'Sin resultados'
    items = result.get('searchResult', [{}])[0].get('item', [])
    return items, None


def _fetch_active_browse(query, token, player, limit=20):
    headers = {
        'Authorization': f'Bearer {token}',
        'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US',
        'Content-Type': 'application/json',
    }
    params = {
        'q': query,
        'category_ids': '212',
        'filter': 'buyingOptions:{FIXED_PRICE|AUCTION}',
        'sort': 'bestMatch',
        'limit': limit,
    }
    r = requests.get(BROWSE_API_URL, headers=headers, params=params, timeout=10)
    if r.status_code != 200:
        return None, f'eBay error {r.status_code}'
    items = r.json().get('itemSummaries', [])
    player_lower = player.lower()
    relevant = [i for i in items if player_lower in i.get('title', '').lower()]
    return relevant if relevant else items, None


def search_card_price(player, year, set_name, numbering=None, grading_company=None, grade=None):
    app_id = os.getenv('EBAY_APP_ID')
    cert_id = os.getenv('EBAY_CERT_ID', '')
    if not app_id or app_id == 'TU_EBAY_APP_ID_AQUI':
        return None, 'eBay no configurado'

    token = _get_oauth_token(app_id, cert_id)
    if not token:
        return None, 'No se pudo obtener token eBay'

    query = _build_query(player, year, set_name, numbering, grading_company, grade)
    source = 'sold'

    try:
        raw_items, err = _fetch_sold_finding(query, app_id, token, limit=12)

        if err == '418' or not raw_items:
            source = 'active'
            browse_items, err2 = _fetch_active_browse(query, token, player)
            if err2 or not browse_items:
                return None, err2 or 'Sin resultados en eBay'
            prices = [float(i.get('price', {}).get('value', 0)) for i in browse_items if i.get('price', {}).get('value')]
        else:
            prices = []
            for item in raw_items:
                selling = item.get('sellingStatus', [{}])[0]
                sold_price = selling.get('convertedCurrentPrice', [{}])[0]
                val = sold_price.get('__value__')
                if val:
                    prices.append(float(val))

        if not prices:
            return None, 'Sin precios disponibles'

        prices.sort()
        n = len(prices)
        median = prices[n // 2] if n % 2 == 1 else (prices[n // 2 - 1] + prices[n // 2]) / 2

        return {
            'average': round(median, 2),
            'min': round(min(prices), 2),
            'max': round(max(prices), 2),
            'samples': n,
            'query': query,
            'source': source,
            'updated': datetime.now().strftime('%Y-%m-%d %H:%M')
        }, None

    except Exception as e:
        return None, str(e)


def get_recent_sales(player, year=None, set_name=None, numbering=None, grading_company=None, grade=None, limit=8):
    app_id = os.getenv('EBAY_APP_ID')
    cert_id = os.getenv('EBAY_CERT_ID', '')
    if not app_id or app_id == 'TU_EBAY_APP_ID_AQUI':
        return None, 'eBay no configurado'

    token = _get_oauth_token(app_id, cert_id)
    if not token:
        return None, 'No se pudo obtener token eBay'

    query = _build_query(player, year, set_name, numbering, grading_company, grade)

    try:
        raw_items, err = _fetch_sold_finding(query, app_id, token, limit=limit)

        if err == '418' or not raw_items:
            browse_items, err2 = _fetch_active_browse(query, token, player, limit=limit)
            if err2 or not browse_items:
                return None, err2 or 'Sin ventas recientes'
            sales = []
            for item in browse_items:
                val = item.get('price', {}).get('value')
                if val:
                    sales.append({
                        'title': item.get('title', ''),
                        'price': round(float(val), 2),
                        'currency': item.get('price', {}).get('currency', 'USD'),
                        'date': '',
                        'url': item.get('itemWebUrl', ''),
                        'note': 'listado activo',
                    })
            if not sales:
                return None, 'Sin resultados'
            return {'sales': sales, 'query': query, 'source': 'active'}, None

        sales = []
        for item in raw_items:
            selling = item.get('sellingStatus', [{}])[0]
            sold_price = selling.get('convertedCurrentPrice', [{}])[0]
            val = sold_price.get('__value__')
            currency = sold_price.get('@currencyId', 'USD')
            end_time = item.get('listingInfo', [{}])[0].get('endTime', [''])[0]
            title = item.get('title', [''])[0]
            url = item.get('viewItemURL', [''])[0]
            if val:
                sales.append({
                    'title': title,
                    'price': round(float(val), 2),
                    'currency': currency,
                    'date': end_time[:10] if end_time else '',
                    'url': url,
                })

        if not sales:
            return None, 'Sin ventas recientes'
        return {'sales': sales, 'query': query, 'source': 'sold'}, None

    except Exception as e:
        return None, str(e)
