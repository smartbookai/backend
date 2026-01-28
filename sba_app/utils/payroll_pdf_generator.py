# sba_app/utils/payroll_pdf_generator.py

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import black, white
from io import BytesIO
from decimal import Decimal


def generate_payroll_pdf(data):
    """
    Genera PDF de nómina con formato oficial español EXACTO.
    """
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    payroll = data['payroll']
    employee = data['employee']
    company = data['company']

    conceptos_adicionales = data.get('conceptos_adicionales', [])
    desglose_ss_empleado = data.get('desglose_ss_empleado', {})
    desglose_ss_empresa = data.get('desglose_ss_empresa', {})
    bases_cotizacion = data.get('bases_cotizacion', {})
    datos_emision = data.get('datos_emision', {})
    datos_bancarios = data.get('datos_bancarios', {})
    percepciones_no_salariales = data.get('percepciones_no_salariales', {})

    # Márgenes
    margin = 15 * mm
    page_width = width - (2 * margin)

    y = height - margin

    # ============ CABECERA CON TABLA ============
    # Dibujar rectángulo exterior
    p.setLineWidth(1)
    header_height = 65
    p.rect(margin, y - header_height, page_width, header_height)

    # Línea vertical central
    p.line(margin + page_width / 2, y - header_height, margin + page_width / 2, y)

    # Caja EMPRESA
    p.setFillColor(black)
    p.rect(margin, y - 15, page_width / 2, 15, fill=1)
    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margin + 2, y - 10, "EMPRESA")

    # Datos empresa
    p.setFillColor(black)
    p.setFont("Helvetica", 8)
    y_temp = y - 25
    p.drawString(margin + 2, y_temp, f"Domicilio:")
    p.drawString(margin + 30, y_temp, company.address or company.name)
    y_temp -= 10
    p.drawString(margin + 2, y_temp, f"C.I.F.:")
    p.drawString(margin + 30, y_temp, company.document_number or "")
    y_temp -= 10
    if company.ccc:
        p.drawString(margin + 2, y_temp, f"Código cuenta cotización:")
        p.drawString(margin + 30, y_temp + 10, company.ccc)

    # Caja TRABAJADOR/A
    p.setFillColor(black)
    p.rect(margin + page_width / 2, y - 15, page_width / 2, 15, fill=1)
    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margin + page_width / 2 + 2, y - 10, "TRABAJADOR/A")

    # Datos trabajador
    p.setFillColor(black)
    p.setFont("Helvetica", 8)
    y_temp = y - 25
    nombre_completo = f"{employee.first_name} {employee.last_name}".upper()
    p.drawString(margin + page_width / 2 + 2, y_temp, nombre_completo)
    y_temp -= 10
    p.drawString(margin + page_width / 2 + 2, y_temp, f"N.I.F.: {employee.document_number or ''}")
    p.drawString(margin + page_width / 2 + 80, y_temp, f"Número libro de Matrícula:")
    y_temp -= 10
    p.drawString(margin + page_width / 2 + 2, y_temp, f"Núm. afiliación a la Seguridad Social:")
    p.drawString(margin + page_width / 2 + 100, y_temp, employee.social_security_number or "")
    y_temp -= 10
    p.drawString(margin + page_width / 2 + 2, y_temp, f"Categoría o grupo profesional:")
    p.drawString(margin + page_width / 2 + 80, y_temp, employee.job_position or "")

    y -= header_height + 5

    # ============ PERÍODO DE LIQUIDACIÓN ============
    p.rect(margin, y - 15, page_width, 15)
    p.setFont("Helvetica", 8)
    periodo_text = f"Período de liquidación:  MENS  del  {payroll.period_start.strftime('%d')}  de  {payroll.period_start.strftime('%B').upper()}  al  {payroll.period_end.strftime('%d')}  de  {payroll.period_end.strftime('%B').upper()}  de  {payroll.period_end.strftime('%Y')}     Total Días [    ]"
    p.drawString(margin + 2, y - 10, periodo_text)

    y -= 20

    # ============ I. DEVENGOS Y TOTALES ============
    devengos_box_height = 150
    p.rect(margin, y - devengos_box_height, page_width, devengos_box_height)

    # Línea vertical que separa devengos de totales
    col_split = margin + (page_width * 0.55)
    p.line(col_split, y - devengos_box_height, col_split, y)

    # Encabezado I. DEVENGOS
    p.setFillColor(black)
    p.rect(margin, y - 15, col_split - margin, 15, fill=1)
    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margin + 2, y - 10, "I. DEVENGOS")

    # Encabezado TOTALES
    p.setFillColor(black)
    p.rect(col_split, y - 15, margin + page_width - col_split, 15, fill=1)
    p.setFillColor(white)
    p.drawString(col_split + 2, y - 10, "TOTALES")

    p.setFillColor(black)

    # Contenido devengos
    y_dev = y - 25
    p.setFont("Helvetica-Bold", 8)
    p.drawString(margin + 2, y_dev, "1. Percepciones salariales")
    y_dev -= 10

    p.setFont("Helvetica", 7)
    items = [
        ("Salario base", payroll.base_salary),
        ("Horas extraordinarias", payroll.overtime),
        ("Gratificaciones extraordinarias", Decimal('0')),
        ("Salario en especie", Decimal('0')),
        ("Complementos salariales", payroll.salary_supplements),
    ]

    for concepto in conceptos_adicionales:
        items.append((concepto['name'], concepto['value']))

    for label, value in items:
        texto = f"  {label}"
        # Agregar puntos suspensivos
        p.drawString(margin + 4, y_dev, texto + "." * 50)
        if value and value > 0:
            p.drawRightString(col_split - 5, y_dev, f"{value:.2f}")
        y_dev -= 8

    # Contenido totales (columna derecha)
    y_tot = y - 25
    p.setFont("Helvetica-Bold", 8)
    p.drawString(col_split + 2, y_tot, "2. Percepciones no salariales")
    y_tot -= 10

    p.setFont("Helvetica", 7)
    p.drawString(col_split + 4, y_tot, "Indemnizaciones o suplidos:")
    y_tot -= 8

    ss_benefits = percepciones_no_salariales.get('ss_benefits', Decimal('0'))
    if ss_benefits > 0:
        p.drawString(col_split + 4, y_tot, "Prestaciones e indemnizaciones SS:" + "." * 20)
        p.drawRightString(margin + page_width - 5, y_tot, f"{ss_benefits:.2f}")
        y_tot -= 8

    # Línea antes del total devengado
    y_total_dev = y - devengos_box_height + 20
    p.line(col_split, y_total_dev, margin + page_width, y_total_dev)

    p.setFont("Helvetica-Bold", 8)
    p.drawString(col_split + 2, y_total_dev - 10, "A. TOTAL DEVENGADO")
    p.drawRightString(margin + page_width - 5, y_total_dev - 10, f"{payroll.total_accrued:.2f}")

    y = y - devengos_box_height - 5

    # ============ II. DEDUCCIONES ============
    deduc_height = 120
    p.rect(margin, y - deduc_height, page_width, deduc_height)
    p.line(col_split, y - deduc_height, col_split, y)

    # Encabezado
    p.setFillColor(black)
    p.rect(margin, y - 15, page_width, 15, fill=1)
    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margin + 2, y - 10, "II. DEDUCCIONES")
    p.setFillColor(black)

    # Columna izquierda: Aportación trabajador
    y_ded = y - 25
    p.setFont("Helvetica-Bold", 7)
    p.drawString(margin + 2, y_ded, "1. Aportación del trabajador a las cotizaciones a la Seguridad Social y")
    y_ded -= 8
    p.drawString(margin + 4, y_ded, "conceptos de recaudación conjunta")
    y_ded -= 10

    p.setFont("Helvetica", 7)

    # Tabla de cotizaciones
    base_common = bases_cotizacion.get('common', Decimal('0'))
    ss_common = desglose_ss_empleado.get('common', Decimal('0'))
    ss_unemployment = desglose_ss_empleado.get('unemployment', Decimal('0'))
    ss_training = desglose_ss_empleado.get('training', Decimal('0'))

    # Contingencias comunes
    p.drawString(margin + 4, y_ded, "Contingencias comunes")
    p.drawRightString(margin + 100, y_ded, f"{base_common:.2f}")
    p.drawRightString(margin + 130, y_ded, "4,70 %")
    p.drawRightString(col_split - 5, y_ded, f"{ss_common:.2f}")
    y_ded -= 8

    # Desempleo
    p.drawString(margin + 4, y_ded, "Desempleo")
    p.drawRightString(margin + 100, y_ded, f"{base_common:.2f}")
    p.drawRightString(margin + 130, y_ded, "1,55 %")
    p.drawRightString(col_split - 5, y_ded, f"{ss_unemployment:.2f}")
    y_ded -= 8

    # Formación Profesional
    p.drawString(margin + 4, y_ded, "Formación Profesional")
    p.drawRightString(margin + 100, y_ded, f"{base_common:.2f}")
    p.drawRightString(margin + 130, y_ded, "0,10 %")
    p.drawRightString(col_split - 5, y_ded, f"{ss_training:.2f}")
    y_ded -= 10

    p.drawString(margin + 4, y_ded, "Horas extraordinarias:")
    y_ded -= 8
    p.drawString(margin + 6, y_ded, "Fuerza mayor")
    p.drawRightString(margin + 130, y_ded, "%")
    y_ded -= 8
    p.drawString(margin + 6, y_ded, "Resto horas extraordinarias")
    p.drawRightString(margin + 130, y_ded, "%")
    y_ded -= 10

    p.setFont("Helvetica-Bold", 7)
    p.drawString(margin + 4, y_ded, "TOTAL APORTACIONES" + "." * 40)
    p.drawRightString(col_split - 5, y_ded, f"{payroll.social_security_employee:.2f}")

    # Columna derecha: IRPF y otras deducciones
    y_ded_der = y - 25
    p.setFont("Helvetica-Bold", 7)
    p.drawString(col_split + 2, y_ded_der, "2. Impuesto sobre la renta de")
    y_ded_der -= 8
    p.drawString(col_split + 4, y_ded_der, "las personas físicas")

    base_irpf = bases_cotizacion.get('irpf', Decimal('0'))
    irpf_percent = (payroll.irpf / base_irpf * 100) if base_irpf > 0 else Decimal('0')

    p.drawRightString(col_split + 80, y_ded_der, f"{base_irpf:.2f}")
    p.drawRightString(col_split + 110, y_ded_der, f"{irpf_percent:.2f} %")
    y_ded_der -= 10
    p.drawRightString(margin + page_width - 5, y_ded_der, f"{payroll.irpf:.2f}")
    y_ded_der -= 12

    p.drawString(col_split + 2, y_ded_der, "3. Anticipos" + "." * 30)
    y_ded_der -= 10
    p.drawString(col_split + 2, y_ded_der, "4. Valor de los productos recibidos en especie" + "." * 10)
    y_ded_der -= 10
    p.drawString(col_split + 2, y_ded_der, "5. Otras deducciones:")

    # Totales finales
    y_total_ded = y - deduc_height + 25
    p.line(col_split, y_total_ded, margin + page_width, y_total_ded)

    p.setFont("Helvetica-Bold", 8)
    p.drawString(col_split + 2, y_total_ded - 10, "B. TOTAL A DEDUCIR" + "." * 20)
    p.drawRightString(margin + page_width - 5, y_total_ded - 10, f"{payroll.total_deductions:.2f}")

    y_total_ded -= 12
    p.drawString(col_split + 2, y_total_ded, "LIQUIDO TOTAL A PERCIBIR (A-B)" + "." * 10 + "Euros")
    p.setFont("Helvetica-Bold", 10)
    p.drawRightString(margin + page_width - 5, y_total_ded, f"{payroll.net_salary:.2f}")

    y = y - deduc_height - 10

    # ============ FECHA Y FIRMA ============
    p.setFont("Helvetica", 8)
    ciudad = datos_emision.get('city', '')
    dia = datos_emision.get('day', payroll.issue_date.day)
    mes = datos_emision.get('month', payroll.issue_date.strftime('%B').upper())
    año = datos_emision.get('year', payroll.issue_date.year)

    p.drawCentredString(width / 2, y, f"{ciudad}          {dia} de {mes}          de          {año}")
    y -= 15
    p.drawCentredString(width / 2, y, "RECIBÍ")
    y -= 15

    # ============ DATOS BANCARIOS ============
    if datos_bancarios.get('iban'):
        p.rect(margin, y - 15, page_width, 15)
        p.setFont("Helvetica-Bold", 8)
        p.drawString(margin + 2, y - 10, f"IBAN: {datos_bancarios['iban']}")
        p.drawString(margin + page_width / 2, y - 10, f"SWIFT/BIC: {datos_bancarios.get('swift', '')}")
        y -= 20

    # ============ NUEVA PÁGINA: BASES DE COTIZACIÓN ============
    p.showPage()
    y = height - margin

    p.setFont("Helvetica-Bold", 7)
    p.drawString(margin, y,
                 "DETERMINACIÓN DE LAS BASES DE COTIZACIÓN A LA SEGURIDAD SOCIAL Y CONCEPTOS DE RECAUDACIÓN CONJUNTA Y DE LA")
    y -= 8
    p.drawString(margin, y, "BASE SUJETA A RETENCIÓN DEL I.R.P.F. Y APORTACIÓN DE LA EMPRESA")
    y -= 15

    # Tabla de bases
    table_height = 120
    p.rect(margin, y - table_height, page_width, table_height)

    # Encabezados
    p.setFont("Helvetica-Bold", 7)
    p.drawString(margin + 2, y - 10, "CONCEPTO")
    p.drawRightString(margin + 250, y - 10, "BASE")
    p.drawRightString(margin + 310, y - 10, "TIPO")
    p.drawRightString(margin + page_width - 5, y - 10, "APORTACIÓN EMPRESARIAL")

    y -= 15
    p.setFont("Helvetica", 6)

    # Fila 1
    base_cc = bases_cotizacion.get('common', Decimal('0'))
    p.drawString(margin + 2, y, "1. Base de cotización por contingencias comunes")
    y -= 8
    p.drawString(margin + 4, y, "Remuneración mensual")
    y -= 8
    p.drawString(margin + 4, y, "Prorrata pagas extraordinarias")
    p.drawRightString(margin + 250, y - 8, f"{base_cc:.2f}")

    ss_common_emp = desglose_ss_empresa.get('common', Decimal('0'))
    ss_mei = desglose_ss_empresa.get('mei', Decimal('0'))

    p.drawRightString(margin + 310, y, "23,60")
    p.drawRightString(margin + page_width - 5, y, f"{ss_common_emp:.2f}")
    y -= 8
    p.drawString(margin + 10, y, "Mecanismo Equidad Intergeneracional (MEI)")
    p.drawRightString(margin + 310, y, "0,58")
    p.drawRightString(margin + page_width - 5, y, f"{ss_mei:.2f}")

    # Fila 2
    y -= 12
    base_cp = bases_cotizacion.get('professional', Decimal('0'))
    p.drawString(margin + 2, y, "2. Base de cotización por contingencias profesionales y")
    p.drawRightString(margin + 310, y, "AT y EP")
    y -= 8
    p.drawString(margin + 4, y, "conceptos de recaudación")
    p.drawRightString(margin + 250, y - 8, f"{base_cp:.2f}")

    ss_unemp_emp = desglose_ss_empresa.get('unemployment', Decimal('0'))
    ss_train_emp = desglose_ss_empresa.get('training', Decimal('0'))
    ss_fogasa = desglose_ss_empresa.get('fogasa', Decimal('0'))

    y -= 8
    p.drawString(margin + 6, y, "Desempleo")
    p.drawRightString(margin + 310, y, "5,50")
    p.drawRightString(margin + page_width - 5, y, f"{ss_unemp_emp:.2f}")
    y -= 8
    p.drawString(margin + 6, y, "Formación Profesional")
    p.drawRightString(margin + 310, y, "0,60")
    p.drawRightString(margin + page_width - 5, y, f"{ss_train_emp:.2f}")
    y -= 8
    p.drawString(margin + 6, y, "Fondo Garantía Salarial")
    p.drawRightString(margin + 310, y, "0,20")
    p.drawRightString(margin + page_width - 5, y, f"{ss_fogasa:.2f}")

    # Fila 3
    y -= 10
    p.drawString(margin + 2, y, "3. Base de cotización adicional por horas extraordinarias")

    # Fila 4
    y -= 10
    base_irpf_final = bases_cotizacion.get('irpf', Decimal('0'))
    p.drawString(margin + 2, y, "4. Base sujeta a retención del I.R.P.F.")
    p.drawRightString(margin + 250, y, f"{base_irpf_final:.2f}")

    p.showPage()
    p.save()

    buffer.seek(0)
    return buffer.getvalue()