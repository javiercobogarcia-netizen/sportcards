import qrcode
import os
from PIL import Image

DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(__file__))
QR_DIR = os.path.join(DATA_DIR, 'qrcodes')

def generate_qr(card_id, base_url='http://localhost:5052'):
    os.makedirs(QR_DIR, exist_ok=True)
    url = f'{base_url}/card/{card_id}'

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color='black', back_color='white')

    filename = f'card_{card_id}.png'
    path = os.path.join(QR_DIR, filename)
    img.save(path)
    return f'qrcodes/{filename}'
