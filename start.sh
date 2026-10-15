#!/bin/bash
cd "$(dirname "$0")"

# Instalar dependencias si no están
if [ ! -d "venv" ]; then
  echo "Creando entorno virtual..."
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
else
  source venv/bin/activate
fi

echo ""
echo "======================================"
echo "  SportCards arrancando en puerto 5052"
echo "======================================"
echo ""
# Obtener IP local
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")
echo "  Desde tu Mac:   http://localhost:5052"
echo "  Desde iPhone:   http://$IP:5052"
echo ""
echo "  (iPhone debe estar en la misma WiFi)"
echo "======================================"
echo ""

python3 app.py
