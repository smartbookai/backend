import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from decimal import Decimal


def generate_delivery_note_pdf(delivery_note):
    """
    Genera un PDF con diseño moderno para un albarán de ventas
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)

    # Estilos
    styles = getSampleStyleSheet()

    # Título principal (Albarán)
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

    # Estilo para encabezados de sección
    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=10,
        spaceBefore=20,
        textColor=colors.black,
        fontName='Helvetica-Bold'
    )

    # Contenido del PDF
    story = []

    # Título
    story.append(Paragraph("ALBARÁN", title_style))

    # Información de la empresa y albarán
    company_info = [
        [Paragraph("<b>Empresa:</b>", label_style), Paragraph(delivery_note.company.name, data_style)],
        [Paragraph("<b>Número de Albarán:</b>", label_style), Paragraph(delivery_note.delivery_note_number, data_style)],
        [Paragraph("<b>Fecha de Emisión:</b>", label_style), Paragraph(delivery_note.issue_date.strftime('%d/%m/%Y'), data_style)],
        [Paragraph("<b>Fecha de Entrega:</b>", label_style), Paragraph(delivery_note.delivery_date.strftime('%d/%m/%Y') if delivery_note.delivery_date else 'No especificada', data_style)],
        [Paragraph("<b>Método de Entrega:</b>", label_style), Paragraph(delivery_note.delivery_method or 'No especificado', data_style)],
        [Paragraph("<b>Estado:</b>", label_style), Paragraph(delivery_note.status, data_style)],
    ]

    company_table = Table(company_info, colWidths=[2*inch, 4*inch])
    company_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    story.append(company_table)
    story.append(Spacer(1, 0.3 * inch))

    # Información del cliente
    story.append(Paragraph("Datos del Cliente", section_header_style))
    
    client_info = [
        [Paragraph("<b>Nombre:</b>", label_style), Paragraph(delivery_note.client.name, data_style)],
        [Paragraph("<b>NIF/CIF:</b>", label_style), Paragraph(delivery_note.client.document_number or 'No especificado', data_style)],
        [Paragraph("<b>Dirección:</b>", label_style), Paragraph(delivery_note.client.address or 'No especificada', data_style)],
        [Paragraph("<b>Teléfono:</b>", label_style), Paragraph(delivery_note.client.phone or 'No especificado', data_style)],
        [Paragraph("<b>Email:</b>", label_style), Paragraph(delivery_note.client.email or 'No especificado', data_style)],
    ]

    client_table = Table(client_info, colWidths=[2*inch, 4*inch])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    story.append(client_table)
    story.append(Spacer(1, 0.3 * inch))

    # Líneas del albarán
    story.append(Paragraph("Líneas del Albarán", section_header_style))
    
    # Datos de las líneas
    lines_data = [['Descripción', 'Referencia', 'Cantidad', 'Precio Unit.', 'IVA %', 'Total']]
    
    for line in delivery_note.lines.all():
        total_line = line.quantity * line.unit_price if line.unit_price else Decimal('0.00')
        lines_data.append([
            Paragraph(line.description, data_style),
            Paragraph(line.reference or '-', data_style),
            Paragraph(str(line.quantity), data_style),
            Paragraph(f"€{line.unit_price:.2f}" if line.unit_price else '-', data_style),
            Paragraph(f"{line.vat_rate}%" if line.vat_rate else '-', data_style),
            Paragraph(f"€{total_line:.2f}" if line.unit_price else '-', data_style),
        ])
    
    # Si no hay líneas, mostrar mensaje
    if len(lines_data) == 1:
        lines_data.append(['No hay líneas', '-', '-', '-', '-', '-'])

    lines_table = Table(lines_data, colWidths=[2.5*inch, 1*inch, 0.8*inch, 1*inch, 0.8*inch, 1*inch])
    lines_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    story.append(lines_table)

    # Totales (si hay importes)
    if delivery_note.total_amount:
        story.append(Spacer(1, 0.3 * inch))
        
        totals_data = [
            ['Base Imponible:', f"€{delivery_note.base_amount:.2f}" if delivery_note.base_amount else '€0.00'],
            ['Importe IVA:', f"€{delivery_note.tax_amount:.2f}" if delivery_note.tax_amount else '€0.00'],
            ['Total Albarán:', f"€{delivery_note.total_amount:.2f}" if delivery_note.total_amount else '€0.00'],
        ]
        
        totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 2), (1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 2), (-1, 2), 12),
            ('TEXTCOLOR', (0, 2), (-1, 2), colors.red),
            ('GRID', (0, 0), (-1, -1), 0, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))

        story.append(totals_table)

    # Notas adicionales
    if delivery_note.notes:
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph("<b>Notas</b>", section_header_style))
        story.append(Paragraph(delivery_note.notes, data_style))

    # Generar PDF
    doc.build(story)
    pdf_value = buffer.getvalue()
    buffer.close()

    return pdf_value