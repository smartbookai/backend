import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
from decimal import Decimal


def generate_delivery_note_pdf(delivery_note):
    """
    Genera un PDF con diseño moderno para un albarán de ventas
    """
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

    # Título principal
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=primary_color,
        spaceAfter=10,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
        leading=32
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

    # Logo de la empresa (si existe)
    logo_element = ""
    if delivery_note.company.logo:
        try:
            logo_path = delivery_note.company.logo.path
            if os.path.exists(logo_path):
                logo_element = Image(logo_path, width=1.5*cm, height=1.5*cm)
                logo_element.hAlign = 'LEFT'
        except Exception:
            pass  # Si hay error con el logo, continuar sin él

    # ===== ENCABEZADO =====
    # Crear contenido del título con o sin logo
    if logo_element:
        title_content = Table([[logo_element, Paragraph("ALBARÁN DE ENTREGA", title_style)]], 
                              colWidths=[2*cm, 8*cm])
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
    info_data = [
        [
            [
                Paragraph("<b>DATOS DE LA EMPRESA</b>", section_header_style),
                Paragraph(f"<b>{delivery_note.company.name}</b>", data_style),
            ],
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