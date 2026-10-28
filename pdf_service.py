import os
import tempfile
from datetime import datetime

def export_pdf(cards, stats):
    from fpdf import FPDF

    owned = [c for c in cards if c.get('status') == 'owned']
    sold  = [c for c in cards if c.get('status') == 'sold']

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_text_color(180, 0, 0)
    pdf.cell(0, 10, 'SportCards - Informe de Coleccion', ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f'Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}', ln=True)
    pdf.ln(4)

    pdf.set_fill_color(245, 245, 245)
    pdf.set_draw_color(220, 220, 220)
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, 'Resumen de cartera', ln=True, fill=True)
    pdf.ln(2)

    cost    = stats.get('total_cost', 0) or 0
    value   = stats.get('current_value', 0) or 0
    gain_u  = stats.get('unrealized_gain', 0) or 0
    gain_r  = stats.get('realized_profit', 0) or 0
    n_owned = stats.get('owned', 0) or 0
    n_sold  = stats.get('sold', 0) or 0
    n_grad  = stats.get('graded_owned', 0) or 0

    def kv(label, val):
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(70, 7, label + ':', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(20, 20, 20)
        pdf.cell(0, 7, val, ln=True)

    kv('Cartas en coleccion', str(n_owned))
    kv('Cartas gradadas', str(n_grad))
    kv('Coste total invertido', f'{cost:.2f} EUR')
    kv('Valor actual (mercado)', f'{value:.2f} EUR')
    roi_pct = ((value - cost) / cost * 100) if cost else 0
    kv('Ganancia latente', f'{gain_u:+.2f} EUR  ({roi_pct:+.1f}%)')
    kv('Beneficio realizado (ventas)', f'{gain_r:+.2f} EUR')
    kv('Cartas vendidas', str(n_sold))
    pdf.ln(6)

    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, f'Coleccion actual ({n_owned} cartas)', ln=True, fill=True)
    pdf.ln(1)

    col_w = [8, 48, 12, 50, 22, 22, 28]
    headers = ['#', 'Jugador', 'Ano', 'Coleccion', 'Compra', 'Mercado', 'P&L']
    pdf.set_fill_color(200, 30, 30)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 8)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=0, fill=True, align='C' if i > 1 else 'L')
    pdf.ln()

    pdf.set_font('Helvetica', '', 8)
    for idx, c in enumerate(sorted(owned, key=lambda x: -(x.get('market_price') or x.get('purchase_price') or 0))):
        bg = (250, 250, 250) if idx % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*bg)
        pdf.set_text_color(30, 30, 30)
        purchase = c.get('purchase_price') or 0
        market   = c.get('market_price') or 0
        pnl      = (market - purchase) if market else None
        grade_str = f" {c['grading_company']} {c['grade']}" if c.get('graded') else ''
        player_str = (c.get('player') or '')[:24] + grade_str
        set_str = (c.get('set_name') or '')[:28]
        purchase_str = f'{purchase:.2f}' if purchase else '-'
        market_str   = f'{market:.2f}' if market else '-'
        pnl_str      = f'{pnl:+.2f}' if pnl is not None else '-'
        if pnl is not None and pnl >= 0:
            pnl_color = (0, 120, 0)
        elif pnl is not None:
            pnl_color = (180, 0, 0)
        else:
            pnl_color = (120, 120, 120)
        row_h = 6
        pdf.cell(col_w[0], row_h, str(idx + 1), fill=True, align='C')
        pdf.cell(col_w[1], row_h, player_str, fill=True)
        pdf.cell(col_w[2], row_h, str(c.get('year') or ''), fill=True, align='C')
        pdf.cell(col_w[3], row_h, set_str, fill=True)
        pdf.cell(col_w[4], row_h, purchase_str, fill=True, align='R')
        pdf.cell(col_w[5], row_h, market_str, fill=True, align='R')
        pdf.set_text_color(*pnl_color)
        pdf.cell(col_w[6], row_h, pnl_str, fill=True, align='R')
        pdf.set_text_color(30, 30, 30)
        pdf.ln()

    if sold:
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 13)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 8, f'Historial de ventas ({len(sold)} cartas)', ln=True, fill=True)
        pdf.ln(1)
        col_w2 = [8, 55, 12, 25, 25, 25, 40]
        headers2 = ['#', 'Jugador', 'Ano', 'Compra', 'Venta', 'Beneficio', 'Fecha venta']
        pdf.set_fill_color(60, 60, 60)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 8)
        for i, h in enumerate(headers2):
            pdf.cell(col_w2[i], 7, h, border=0, fill=True, align='C' if i > 1 else 'L')
        pdf.ln()
        pdf.set_font('Helvetica', '', 8)
        for idx, c in enumerate(sorted(sold, key=lambda x: x.get('sale_date') or '', reverse=True)):
            bg = (250, 250, 250) if idx % 2 == 0 else (255, 255, 255)
            pdf.set_fill_color(*bg)
            pdf.set_text_color(30, 30, 30)
            purchase = c.get('purchase_price') or 0
            sale     = c.get('sale_price') or 0
            profit   = sale - purchase
            grade_str = f" {c['grading_company']} {c['grade']}" if c.get('graded') else ''
            pdf.cell(col_w2[0], 6, str(idx + 1), fill=True, align='C')
            pdf.cell(col_w2[1], 6, ((c.get('player') or '')[:28] + grade_str)[:32], fill=True)
            pdf.cell(col_w2[2], 6, str(c.get('year') or ''), fill=True, align='C')
            pdf.cell(col_w2[3], 6, f'{purchase:.2f}', fill=True, align='R')
            pdf.cell(col_w2[4], 6, f'{sale:.2f}', fill=True, align='R')
            color = (0, 120, 0) if profit >= 0 else (180, 0, 0)
            pdf.set_text_color(*color)
            pdf.cell(col_w2[5], 6, f'{profit:+.2f}', fill=True, align='R')
            pdf.set_text_color(30, 30, 30)
            pdf.cell(col_w2[6], 6, c.get('sale_date') or '-', fill=True, align='C')
            pdf.ln()

    pdf.ln(8)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 5, 'SportCards - Informe generado automaticamente para uso personal', ln=True, align='C')

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', dir='/tmp')
    pdf.output(tmp.name)
    filename = f'sportcards_{datetime.now().strftime("%Y%m%d")}.pdf'
    return tmp.name, filename
