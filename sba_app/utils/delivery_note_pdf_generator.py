import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from decimal import Decimal


# ── Token mapper ────────────────────────────────────────────────────────────

def get_delivery_note_data(dn):
    client  = getattr(dn, 'client', None)
    company = getattr(dn, 'company', None)
    fmt_date  = lambda d: d.strftime('%d/%m/%Y') if d else ''
    fmt_money = lambda v: f"{v:.2f} €" if v is not None else ''

    STATUS_LABELS = {'pending': 'Pendiente', 'invoiced': 'Facturado', 'cancelled': 'Cancelado'}

    return {
        'NUMERO_ALBARAN':  getattr(dn, 'delivery_note_number', ''),
        'NUMERO':          getattr(dn, 'delivery_note_number', ''),
        'FECHA_EMISION':   fmt_date(getattr(dn, 'issue_date', None)),
        'FECHA_ENTREGA':   fmt_date(getattr(dn, 'delivery_date', None)),
        'METODO_ENTREGA':  getattr(dn, 'delivery_method', '') or '',
        'ESTADO':          STATUS_LABELS.get(getattr(dn, 'status', ''), ''),
        'NOTAS':           getattr(dn, 'notes', '') or '',
        'OBSERVACIONES':   getattr(dn, 'notes', '') or '',
        'BASE_IMPONIBLE':  fmt_money(getattr(dn, 'base_amount', None)),
        'SUBTOTAL':        fmt_money(getattr(dn, 'base_amount', None)),
        'IVA':             fmt_money(getattr(dn, 'tax_amount', None)),
        'TOTAL':           fmt_money(getattr(dn, 'total_amount', None)),
        'TOTAL_DOC':       fmt_money(getattr(dn, 'total_amount', None)),
        # Empresa
        'EMPRESA_NOMBRE':    getattr(company, 'name', '')            if company else '',
        'EMPRESA_CIF':       getattr(company, 'document_number', '') if company else '',
        'EMPRESA_DIR':       getattr(company, 'address', '')         if company else '',
        'EMPRESA_EMAIL':     getattr(company, 'email', '')           if company else '',
        'EMPRESA_TEL':       getattr(company, 'phone', '')           if company else '',
        'EMPRESA_WEB':       getattr(company, 'website', '')         if company else '',
        # Cliente
        'CLIENTE_NOMBRE':    getattr(client, 'name', '')             if client else '',
        'CLIENTE_CIF':       getattr(client, 'document_number', '')  if client else '',
        'CLIENTE_DIR':       getattr(client, 'address', '')          if client else '',
        'CLIENTE_EMAIL':     getattr(client, 'email', '')            if client else '',
        'CLIENTE_TEL':       getattr(client, 'phone', '')            if client else '',
        'CLIENTE_CONTACTO':  getattr(client, 'contact_person', '')   if client else '',
        # Cuentas contables
        'CUENTA_INGRESOS':   getattr(dn, 'account_income', '')       or '',
        'CUENTA_CLIENTE':    getattr(dn, 'account_customer', '')     or '',
        'CUENTA_IVA':        getattr(dn, 'account_vat_output', '')   or '',
    }


# ── Helpers compartidos con pdf_generator ───────────────────────────────────

from sba_app.utils.pdf_generator import get_reportlab_font as _rl_font, _load_template_design


# ── Generador basado en plantilla JSON ──────────────────────────────────────

def _render_from_template(delivery_note, design_data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    dn_data = get_delivery_note_data(delivery_note)

    # Pre-compute label IDs to hide: labels whose linked value is empty
    _SKIP_TOKENS = ('TABLA_LINEAS', 'LOGO_EMPRESA')
    labels_to_skip = set()
    for it in design_data:
        if it.get('type') == 'value' and it.get('label_id') and it.get('token') not in _SKIP_TOKENS:
            if not dn_data.get(it.get('token', ''), ''):
                labels_to_skip.add(it['label_id'])

    # 1. Shapes
    for item in design_data:
        if item.get('type') == 'shape':
            x, y_web = item.get('x', 0), item.get('y', 0)
            w, h = item.get('width', 100), item.get('height', 50)
            c.setFillColor(colors.HexColor(item.get('bg_color', '#CCCCCC')))
            c.rect(x, height - y_web - h, w, h, stroke=0, fill=1)

    # 2. Textos, logo y tabla
    for item in design_data:
        x, y_web = item.get('x', 0), item.get('y', 0)
        token = item.get('token', '')

        if token == 'LOGO_EMPRESA' and delivery_note.company.logo:
            try:
                img = ImageReader(delivery_note.company.logo.path)
                box_w = item.get('logo_width', 120)
                box_h = box_w * 0.8
                iw, ih = img.getSize()
                aspect = ih / float(iw)
                if aspect <= 0.8:
                    dw, dh = box_w, box_w * aspect
                else:
                    dh, dw = box_h, box_h / aspect
                c.drawImage(img, x, height - y_web - dh, width=dw, height=dh, mask='auto')
            except Exception:
                pass

        elif token == 'TABLA_LINEAS':
            _draw_lines_table(c, delivery_note, x, height - y_web, width - x - 50)

        elif item.get('type') in ['label', 'value']:
            if item.get('type') == 'label':
                item_id = item.get('id', '')
                if item_id and item_id in labels_to_skip:
                    continue
                # Fallback Y-proximity for templates without explicit links
                if not item.get('value_id'):
                    label_y = item.get('y', 0)
                    nearby = [
                        it for it in design_data
                        if it.get('type') == 'value'
                        and it.get('token')
                        and it.get('token') not in _SKIP_TOKENS
                        and abs(it.get('y', 0) - label_y) <= 6
                    ]
                    if nearby and all(not dn_data.get(it['token'], '') for it in nearby):
                        continue

            size = item.get('size', 10)
            c.setFillColor(colors.HexColor(item.get('color', '#000000')))
            c.setFont(_rl_font(item.get('font', 'Helvetica'), item.get('bold', False), item.get('italic', False)), size)
            texto = item.get('text', '') if item.get('type') == 'label' else str(dn_data.get(token, ''))
            if texto and texto != 'None':
                c.drawString(x, height - y_web - size, texto)

    c.showPage()
    c.save()
    return buffer.getvalue()


def _draw_lines_table(c, delivery_note, x, y_top, max_width):
    """Dibuja la tabla de líneas del albarán con canvas directo."""
    ROW_H = 16
    headers = ['Descripción', 'Ref.', 'Cant.', 'Precio', 'IVA', 'Total']
    col_w   = [max_width * 0.40, max_width * 0.10, max_width * 0.08,
               max_width * 0.14, max_width * 0.10, max_width * 0.18]

    y = y_top

    # Cabecera
    c.setFillColor(colors.HexColor('#1e293b'))
    c.rect(x, y - ROW_H, max_width, ROW_H, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 8)
    cx = x
    for i, h in enumerate(headers):
        c.drawString(cx + 3, y - ROW_H + 4, h)
        cx += col_w[i]
    y -= ROW_H

    # Filas
    c.setFont('Helvetica', 8)
    for idx, line in enumerate(delivery_note.lines.all()):
        bg = '#f8fafc' if idx % 2 == 0 else '#ffffff'
        c.setFillColor(colors.HexColor(bg))
        c.rect(x, y - ROW_H, max_width, ROW_H, stroke=0, fill=1)
        c.setFillColor(colors.HexColor('#1e293b'))
        total_line = line.quantity * line.unit_price if line.unit_price else Decimal('0.00')
        row = [
            line.description[:45],
            line.reference or '-',
            str(line.quantity),
            f"{line.unit_price:.2f} €" if line.unit_price else '-',
            f"{line.vat_rate}%" if line.vat_rate else '-',
            f"{total_line:.2f} €" if line.unit_price else '-',
        ]
        cx = x
        for i, cell in enumerate(row):
            c.drawString(cx + 3, y - ROW_H + 4, str(cell))
            cx += col_w[i]
        y -= ROW_H


# ── Punto de entrada principal ───────────────────────────────────────────────

def generate_delivery_note_pdf(delivery_note, template_id=None):
    """Genera PDF del albarán usando plantilla JSON si existe, o diseño por defecto."""
    design_data = _load_template_design(template_id, 'delivery_note')

    if design_data:
        return _render_from_template(delivery_note, design_data)

    # ── Fallback: diseño hardcoded original ─────────────────────────────────
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm
    )

    # Colores personalizados modernos
    primary_color = colors.HexColor('#2C3E50')  # Azul oscuro elegante
    accent_color = colors.HexColor('#3498DB')  # Azul claro
    gray_light = colors.HexColor('#ECF0F1')  # Gris claro
    gray_dark = colors.HexColor('#7F8C8D')  # Gris medio

    # Estilos
    styles = getSampleStyleSheet()

    # Título principal (más pequeño)
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=primary_color,
        spaceAfter=5,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
        leading=22
    )

    # Subtítulo
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=gray_dark,
        spaceAfter=20,
        alignment=TA_LEFT,
        fontName='Helvetica'
    )

    # Estilo para encabezados de sección
    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=primary_color,
        spaceAfter=8,
        spaceBefore=15,
        fontName='Helvetica-Bold',
        borderColor=accent_color,
        borderWidth=0,
        borderPadding=5
    )

    # Estilo para datos
    data_style = ParagraphStyle(
        'DataStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.black,
        fontName='Helvetica',
        leading=12
    )

    # Estilo para labels
    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=gray_dark,
        fontName='Helvetica-Bold',
        leading=12
    )

    # Contenido del PDF
    story = []

    # Logo de la empresa (si existe) - más grande
    logo_element = ""
    if delivery_note.company.logo:
        try:
            logo_path = delivery_note.company.logo.path
            if os.path.exists(logo_path):
                logo_element = Image(logo_path, width=3*cm, height=3*cm)
                logo_element.hAlign = 'LEFT'
        except Exception:
            pass  # Si hay error con el logo, continuar sin él

    # ===== ENCABEZADO =====
    # Crear contenido del título con o sin logo
    if logo_element:
        title_content = Table([[logo_element, Paragraph("ALBARÁN DE ENTREGA", title_style)]], 
                              colWidths=[3.5*cm, 6.5*cm])
        title_content.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        title_content = Paragraph("ALBARÁN DE ENTREGA", title_style)

    header_data = [
        [
            title_content,
            Paragraph(f"<b>Nº {delivery_note.delivery_note_number}</b>",
                      ParagraphStyle('HeaderRight',
                                     parent=styles['Normal'],
                                     fontSize=16,
                                     textColor=accent_color,
                                     fontName='Helvetica-Bold',
                                     alignment=TA_RIGHT))
        ]
    ]

    header_table = Table(header_data, colWidths=[10 * cm, 7 * cm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 0.3 * cm))

    # Línea divisoria
    line_data = [['']]
    line_table = Table(line_data, colWidths=[17 * cm])
    line_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 2, accent_color),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.5 * cm))

    # ===== INFORMACIÓN PRINCIPAL =====
    # Construir datos de la empresa con todos los campos disponibles
    company_data = [Paragraph("<b>DATOS DE LA EMPRESA</b>", section_header_style)]
    company_data.append(Paragraph(f"<b>{delivery_note.company.name}</b>", data_style))
    if delivery_note.company.address:
        company_data.append(Paragraph(delivery_note.company.address, data_style))
    if delivery_note.company.document_number:
        company_data.append(Paragraph(f"CIF: {delivery_note.company.document_number}", data_style))
    if delivery_note.company.email:
        company_data.append(Paragraph(delivery_note.company.email, data_style))
    if delivery_note.company.phone:
        company_data.append(Paragraph(delivery_note.company.phone, data_style))

    info_data = [
        [
            company_data,
            [
                Paragraph("<b>INFORMACIÓN DEL ALBARÁN</b>", section_header_style),
                Paragraph(f"<b>Fecha de emisión:</b> {delivery_note.issue_date.strftime('%d/%m/%Y')}", data_style),
                Paragraph(
                    f"<b>Fecha de entrega:</b> {delivery_note.delivery_date.strftime('%d/%m/%Y') if delivery_note.delivery_date else 'No especificada'}",
                    data_style),
                Paragraph(f"<b>Método de entrega:</b> {delivery_note.delivery_method or 'No especificado'}",
                          data_style),
            ]
        ]
    ]

    # Crear tabla con dos columnas
    main_info_table = Table(info_data, colWidths=[8.5 * cm, 8.5 * cm])
    main_info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, 0), gray_light),
        ('BACKGROUND', (1, 0), (1, 0), gray_light),
        ('BOX', (0, 0), (0, 0), 1, gray_dark),
        ('BOX', (1, 0), (1, 0), 1, gray_dark),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(main_info_table)
    story.append(Spacer(1, 0.5 * cm))

    # ===== DATOS DEL CLIENTE =====
    story.append(Paragraph("CLIENTE", section_header_style))

    client_info = [
        [Paragraph("<b>Nombre:</b>", label_style), Paragraph(delivery_note.client.name, data_style)],
        [Paragraph("<b>NIF/CIF:</b>", label_style),
         Paragraph(delivery_note.client.document_number or 'No especificado', data_style)],
        [Paragraph("<b>Dirección:</b>", label_style),
         Paragraph(delivery_note.client.address or 'No especificada', data_style)],
        [Paragraph("<b>Teléfono:</b>", label_style),
         Paragraph(delivery_note.client.phone or 'No especificado', data_style)],
        [Paragraph("<b>Email:</b>", label_style),
         Paragraph(delivery_note.client.email or 'No especificado', data_style)],
    ]

    client_table = Table(client_info, colWidths=[3.5 * cm, 13.5 * cm])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), gray_light),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOX', (0, 0), (-1, -1), 1, gray_dark),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.white),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(client_table)
    story.append(Spacer(1, 0.6 * cm))

    # ===== LÍNEAS DEL ALBARÁN =====
    story.append(Paragraph("DETALLE DE PRODUCTOS/SERVICIOS", section_header_style))
    story.append(Spacer(1, 0.2 * cm))

    # Encabezados de tabla
    lines_data = [[
        Paragraph('<b>Descripción</b>', label_style),
        Paragraph('<b>Ref.</b>', label_style),
        Paragraph('<b>Cant.</b>', label_style),
        Paragraph('<b>Precio Unit.</b>', label_style),
        Paragraph('<b>IVA %</b>', label_style),
        Paragraph('<b>Total</b>', label_style)
    ]]

    # Agregar líneas
    for line in delivery_note.lines.all():
        total_line = line.quantity * line.unit_price if line.unit_price else Decimal('0.00')
        lines_data.append([
            Paragraph(line.description, data_style),
            Paragraph(line.reference or '-', data_style),
            Paragraph(str(line.quantity), data_style),
            Paragraph(f"{line.unit_price:.2f} €" if line.unit_price else '-', data_style),
            Paragraph(f"{line.vat_rate}%" if line.vat_rate else '-', data_style),
            Paragraph(f"<b>{total_line:.2f} €</b>" if line.unit_price else '-', data_style),
        ])

    # Si no hay líneas
    if len(lines_data) == 1:
        lines_data.append([
            Paragraph('No hay líneas', data_style),
            '-', '-', '-', '-', '-'
        ])

    lines_table = Table(lines_data, colWidths=[6 * cm, 2 * cm, 1.5 * cm, 2.5 * cm, 1.5 * cm, 3.5 * cm])
    lines_table.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (-1, 0), 'CENTER'),

        # Contenido
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('ALIGN', (-1, 1), (-1, -1), 'RIGHT'),

        # Bordes y espaciado
        ('BOX', (0, 0), (-1, -1), 1, gray_dark),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, gray_light),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, gray_light]),

        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(lines_table)

    # ===== TOTALES =====
    if delivery_note.total_amount:
        story.append(Spacer(1, 0.5 * cm))

        totals_data = [
            ['Base Imponible:', f"{delivery_note.base_amount:.2f} €" if delivery_note.base_amount else '0.00 €'],
            ['IVA:', f"{delivery_note.tax_amount:.2f} €" if delivery_note.tax_amount else '0.00 €'],
            ['', ''],  # Línea de separación
            ['TOTAL:', f"{delivery_note.total_amount:.2f} €"]
        ]

        totals_table = Table(totals_data, colWidths=[13.5 * cm, 3.5 * cm])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 1), 10),
            ('TEXTCOLOR', (0, 0), (-1, 1), colors.black),

            # Línea divisoria
            ('LINEABOVE', (0, 2), (-1, 2), 1, gray_dark),
            ('LINEBELOW', (0, 2), (-1, 2), 1, gray_dark),

            # Total final
            ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 3), (-1, 3), 14),
            ('TEXTCOLOR', (0, 3), (-1, 3), primary_color),
            ('BACKGROUND', (1, 3), (1, 3), gray_light),

            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))

        story.append(totals_table)

    # ===== NOTAS =====
    if delivery_note.notes:
        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph("OBSERVACIONES", section_header_style))

        notes_data = [[Paragraph(delivery_note.notes, data_style)]]
        notes_table = Table(notes_data, colWidths=[17 * cm])
        notes_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), gray_light),
            ('BOX', (0, 0), (-1, -1), 1, gray_dark),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(notes_table)

    # ===== PIE DE PÁGINA =====
    story.append(Spacer(1, 1 * cm))

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=gray_dark,
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique'
    )

    story.append(Paragraph(
        f"Documento generado el {delivery_note.issue_date.strftime('%d/%m/%Y')} | {delivery_note.company.name}",
        footer_style
    ))

    # Generar PDF
    doc.build(story)
    pdf_value = buffer.getvalue()
    buffer.close()

    return pdf_value