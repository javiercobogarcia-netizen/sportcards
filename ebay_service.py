import requests
import os
import re
from datetime import datetime

FINDING_API_URL = 'https://svcs.ebay.com/services/search/FindingService/v1'


def get_ebay_token():
    app_id = os.getenv('EBAY_APP_ID')
    cert_id = os.getenv('EBAY_CERT_ID', '')
    if not app_id or app_id == 'TU_EBAY_APP_ID_AQUI':
        return None

    credentials = f'{app_id}:{cert_id}'
    encoded = __import__('base64').b64encode(credentials.encode()).decode()

    response = requests.post(
        'https://api.ebay.com/identity/v1/oauth2/token',
        headers={
            'Authorization': f'Basic {encoded}',
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        data='grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope',
        timeout=8
    )
    if response.status_code == 200:
        return response.json().get('access_token')
    return None


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


def _fetch_sold_items(query, app_id, limit=10):
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
    response = requests.get(FINDING_API_URL, params=params, timeout=8)
    if response.status_code != 200:
        return None, f'eBay error {response.status_code}'

    data = response.json()
    search_result = data.get('findCompletedItemsResponse', [{}])[0]
    ack = search_result.get('ack', [''])[0]
    if ack != 'Success':
        return None, 'Sin resultados'

    raw_items = search_result.get('searchResult', [{}])[0].get('item', [])
    return raw_items, None


def search_card_price(player, year, set_name, numbering=None, grading_company=None, grade=None):
    app_id = os.getenv('EBAY_APP_ID')
    if not app_id or app_id == 'TU_EBAY_APP_ID_AQUI':
        return None, 'eBay no configurado'

    query = _build_query(player, year, set_name, numbering, grading_company, grade)

    try:
        raw_items, error = _fetch_sold_items(query, app_id, limit=12)
        if error:
            return None, error
        if not raw_items:
            return None, 'Sin ventas recientes en eBay'

        prices = []
        for item in raw_items:
            selling = item.get('sellingStatus', [{}])[0]
            sold_price = selling.get('convertedCurrentPrice', [{}])[0]
            price_val = sold_price.get('__value__')
            if price_val:
                prices.append(float(price_val))

        if not prices:
            return None, 'Sin precios disponibles'

        prices.sort()
        n = len(prices)
        if n % 2 == 1:
            median = prices[n // 2]
        else:
            median = (prices[n // 2 - 1] + prices[n // 2]) / 2

        return {
            'average': round(median, 2),
            'min': round(min(prices), 2),
            'max': round(max(prices), 2),
            'samples': n,
            'query': query,
            'updated': datetime.now().strftime('%Y-%m-%d %H:%M')
        }, None

    except Exception as e:
        return None, str(e)


def get_recent_sales(player, year=None, set_name=None, numbering=None, grading_company=None, grade=None, limit=8):
    app_id = os.getenv('EBAY_APP_ID')
    if not app_id or app_id == 'TU_EBAY_APP_ID_AQUI':
        return None, 'eBay no configurado'

    query = _build_query(player, year, set_name, numbering, grading_company, grade)

    try:
        raw_items, error = _fetch_sold_items(query, app_id, limit=limit)
        if error:
            return None, error
        if not raw_items:
            return None, 'Sin ventas recientes'

        sales = []
        for item in raw_items:
            selling = item.get('sellingStatus', [{}])[0]
            sold_price = selling.get('convertedCurrentPrice', [{}])[0]
            price_val = sold_price.get('__value__')
            currency = sold_price.get('@currencyId', 'USD')
            end_time = item.get('listingInfo', [{}])[0].get('endTime', [''])[0]
            title = item.get('title', [''])[0]
            url = item.get('viewItemURL', [''])[0]
            if price_val:
                date_str = end_time[:10] if end_time else ''
                sales.append({
                    'title': title,
                    'price': round(float(price_val), 2),
                    'currency': currency,
                    'date': date_str,
                    'url': url,
                })

        if not sales:
            return None, 'Sin ventas recientes'
        return {'sales': sales, 'query': query}, None

    except Exception as e:
        return None, str(e)
