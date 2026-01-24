import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from decimal import Decimal


def generate_invoice_pdf(invoice):
    """
    Genera un PDF con diseño moderno para una factura de ventas
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)

    # Estilos
    styles = getSampleStyleSheet()

    # Título principal (Factura)
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20,
        alignment=0,  # Alineado a la izquierda
        textColor=colors.black,
        fontName='Helvetica-Bold'
    )

    # Estilo para labels pequeños
    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.black,
        leading=11
    )

    # Estilo para datos pequeños
    data_style = ParagraphStyle(
        'Data',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.black,
        leading=11
    )

    # Estilo para el total grande
    total_big_style = ParagraphStyle(
        'TotalBig',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.black,
        leading=24
    )

    # Estilo para headers de sección
    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.black,
        leading=12,
        spaceAfter=5
    )

    story = []

    # Header: Título y datos de factura en paralelo
    header_data = [
        [
            Paragraph("Factura", title_style),
            ""
        ]
    ]

    header_table = Table(header_data, colWidths=[3.5 * inch, 3 * inch])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 0.1 * inch))

    # Información de factura (número, fechas, forma de pago)
    invoice_info = []
    invoice_info.append([
        Paragraph("<b>Número de factura</b>", label_style),
        Paragraph(invoice.invoice_number or "", data_style)
    ])
    invoice_info.append([
        Paragraph("<b>Fecha de emisión</b>", label_style),
        Paragraph(invoice.issue_date.strftime('%d de %B de %Y') if invoice.issue_date else "", data_style)
    ])
    invoice_info.append([
        Paragraph("<b>Fecha de vencimiento</b>", label_style),
        Paragraph(invoice.due_date.strftime('%d de %B de %Y') if invoice.due_date else "", data_style)
    ])

    invoice_info_table = Table(invoice_info, colWidths=[1.5 * inch, 5 * inch])
    invoice_info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))

    story.append(invoice_info_table)

    # Forma de pago (si existe)
    if invoice.payment_method:
        story.append(Spacer(1, 0.05 * inch))
        payment_info = [[
            Paragraph("<b>Forma de pago:</b>", label_style),
            Paragraph(invoice.payment_method, data_style)
        ]]
        payment_table = Table(payment_info, colWidths=[1.5 * inch, 5 * inch])
        payment_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        story.append(payment_table)

    story.append(Spacer(1, 0.3 * inch))

    # Emisor y Cliente en dos columnas
    emisor_lines = []
    #emisor_lines.append(invoice.company.name or "")
    if invoice.company.address:
        emisor_lines.append(invoice.company.address)
    if invoice.company.document_number:
        emisor_lines.append(f"CIF: {invoice.company.document_number}")
    if invoice.company.email:
        emisor_lines.append(invoice.company.email)
    if invoice.company.phone:
        emisor_lines.append(invoice.company.phone)

    emisor_text = "<br/>".join(emisor_lines)

    cliente_lines = []
    cliente_lines.append(invoice.client.name or "")
    if invoice.client.address:
        cliente_lines.append(invoice.client.address)
    if invoice.client.document_number:
        cliente_lines.append(f"CIF: {invoice.client.document_number}")
    if invoice.client.email:
        cliente_lines.append(invoice.client.email)
    if invoice.client.phone:
        cliente_lines.append(invoice.client.phone)

    cliente_text = "<br/>".join(cliente_lines)

    parties_data = [
        [
            Paragraph(invoice.company.name or "", section_header_style),
            Paragraph("Facturar a", section_header_style)
        ],
        [
            Paragraph(emisor_text, data_style),
            Paragraph(cliente_text, data_style)
        ]
    ]

    parties_table = Table(parties_data, colWidths=[3.25 * inch, 3.25 * inch])
    parties_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    story.append(parties_table)
    story.append(Spacer(1, 0.4 * inch))

    # Tabla de líneas - diseño más limpio
    lines_data = [
        ["Descripción", "Cant.", "Precio unitario", "Impuesto", "Importe"]
    ]

    for line in invoice.lines.all():
        lines_data.append([
            line.description,
            f"{line.quantity:.0f}" if line.quantity == int(line.quantity) else f"{line.quantity:.2f}",
            f"{line.unit_price:.2f} €",
            f"{line.vat_rate:.0f} %",
            f"{line.quantity * line.unit_price:.2f} €"
        ])

    lines_table = Table(lines_data, colWidths=[2.8 * inch, 0.6 * inch, 1.2 * inch, 0.9 * inch, 1 * inch])
    lines_table.setStyle(TableStyle([
        # Header
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#666666')),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),

        # Data rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),

        # Alignment
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Borders - solo línea superior e inferior
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#CCCCCC')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#CCCCCC')),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.HexColor('#CCCCCC')),

        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(lines_table)
    story.append(Spacer(1, 0.25 * inch))

    # Totales - diseño limpio sin bordes
    totals_data = []

    # Subtotal
    totals_data.append([
        "Subtotal",
        f"{invoice.base_amount:.2f} €"
    ])

    # Total sin impuestos (si hay descuento)
    if invoice.discount_amount and invoice.discount_amount > 0:
        subtotal_after_discount = invoice.base_amount - invoice.discount_amount
        totals_data.append([
            "Descuento",
            f"-{invoice.discount_amount:.2f} €"
        ])
        totals_data.append([
            "Total sin impuestos",
            f"{subtotal_after_discount:.2f} €"
        ])
    else:
        totals_data.append([
            "Total sin impuestos",
            f"{invoice.base_amount:.2f} €"
        ])

    # IVA
    if invoice.tax_amount:
        # Calcular el porcentaje de IVA promedio o el principal
        vat_percentage = 21  # Por defecto
        first_line = invoice.lines.first()
        if first_line:
            vat_percentage = int(first_line.vat_rate)

        tax_base = invoice.base_amount - (invoice.discount_amount if invoice.discount_amount else 0)
        totals_data.append([
            f"IVA - España ({vat_percentage} % en {tax_base:.2f} €)",
            f"{invoice.tax_amount:.2f} €"
        ])

    # Total final
    totals_data.append([
        "Total",
        f"{invoice.total_amount:.2f} €"
    ])

    # Importe adeudado (igual al total)
    totals_data.append([
        "Importe adeudado",
        f"{invoice.total_amount:.2f} €"
    ])

    totals_table = Table(totals_data, colWidths=[5 * inch, 1.5 * inch])
    totals_table.setStyle(TableStyle([
        # Todas las filas excepto las dos últimas
        ('FONTNAME', (0, 0), (-1, -3), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -3), 9),

        # Total (penúltima fila)
        ('FONTNAME', (0, -2), (-1, -2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -2), (-1, -2), 9),

        # Importe adeudado (última fila)
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 10),

        # Alignment
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),

        # Línea superior en Total
        ('LINEABOVE', (0, -2), (-1, -2), 1, colors.HexColor('#CCCCCC')),
        # Línea superior en Importe adeudado
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#CCCCCC')),
    ]))

    story.append(totals_table)

    # Notas adicionales
    if invoice.notes:
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph("<b>Notas</b>", section_header_style))
        story.append(Paragraph(invoice.notes, data_style))

    # Generar PDF
    doc.build(story)
    pdf_value = buffer.getvalue()
    buffer.close()

    return pdf_value