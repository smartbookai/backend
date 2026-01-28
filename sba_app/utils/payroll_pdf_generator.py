# sba_app/utils/payroll_pdf_generator.py

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import black, white
from io import BytesIO
from decimal import Decimal


def generate_payroll_pdf(data):
    """
    Genera PDF de nómina con formato oficial español en UNA SOLA PÁGINA.
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

    # Márgenes más pequeños
    margin = 12 * mm
    page_width = width - (2 * margin)

    y = height - margin

    # ============ CABECERA CON TABLA ============
    p.setLineWidth(1)
    header_height = 55
    p.rect(margin, y - header_height, page_width, header_height)

    # Línea vertical central
    p.line(margin + page_width / 2, y - header_height, margin + page_width / 2, y)

    # Caja EMPRESA
    p.setFillColor(black)
    p.rect(margin, y - 12, page_width / 2, 12, fill=1)
    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 8)
    p.drawString(margin + 2, y - 9, "EMPRESA")

    # Datos empresa
    p.setFillColor(black)
    p.setFont("Helvetica", 7)
    y_temp = y - 22
    p.drawString(margin + 2, y_temp, f"Domicilio: {company.address or company.name}")
    y_temp -= 9
    p.drawString(margin + 2, y_temp, f"C.I.F.: {company.document_number or ''}")
    y_temp -= 9
    if company.ccc:
        p.drawString(margin + 2, y_temp, f"Código cuenta cotización: {company.ccc}")

    # Caja TRABAJADOR/A
    p.setFillColor(black)
    p.rect(margin + page_width / 2, y - 12, page_width / 2, 12, fill=1)
    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 8)
    p.drawString(margin + page_width / 2 + 2, y - 9, "TRABAJADOR/A")

    # Datos trabajador
    p.setFillColor(black)
    p.setFont("Helvetica", 7)
    y_temp = y - 22
    nombre_completo = f"{employee.first_name} {employee.last_name}".upper()
    p.drawString(margin + page_width / 2 + 2, y_temp, nombre_completo)
    y_temp -= 9
    p.drawString(margin + page_width / 2 + 2, y_temp, f"N.I.F.: {employee.document_number or ''}")
    y_temp -= 9
    p.drawString(margin + page_width / 2 + 2, y_temp, f"Núm. afiliación SS: {employee.social_security_number or ''}")
    y_temp -= 9
    p.drawString(margin + page_width / 2 + 2, y_temp, f"Categoría: {employee.job_position or ''}")

    y -= header_height + 3

    # ============ PERÍODO DE LIQUIDACIÓN ============
    p.rect(margin, y - 12, page_width, 12)
    p.setFont("Helvetica", 7)
    periodo_text = f"Período de liquidación:  MENS  del  {payroll.period_start.strftime('%d')}  de  {payroll.period_start.strftime('%B').upper()}  al  {payroll.period_end.strftime('%d')}  de  {payroll.period_end.strftime('%B').upper()}  de  {payroll.period_end.strftime('%Y')}"
    p.drawString(margin + 2, y - 8, periodo_text)

    y -= 15

    # ============ I. DEVENGOS Y TOTALES ============
    devengos_box_height = 100
    p.rect(margin, y - devengos_box_height, page_width, devengos_box_height)

    # Línea vertical que separa devengos de totales
    col_split = margin + (page_width * 0.55)
    p.line(col_split, y - devengos_box_height, col_split, y)

    # Encabezado I. DEVENGOS
    p.setFillColor(black)
    p.rect(margin, y - 12, col_split - margin, 12, fill=1)
    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 8)
    p.drawString(margin + 2, y - 8, "I. DEVENGOS")

    # Encabezado TOTALES
    p.setFillColor(black)
    p.rect(col_split, y - 12, margin + page_width - col_split, 12, fill=1)
    p.setFillColor(white)
    p.drawString(col_split + 2, y - 8, "TOTALES")

    p.setFillColor(black)

    # Contenido devengos
    y_dev = y - 20
    p.setFont("Helvetica-Bold", 7)
    p.drawString(margin + 2, y_dev, "1. Percepciones salariales")
    y_dev -= 8

    p.setFont("Helvetica", 6)
    items = [
        ("Salario base", payroll.base_salary),
        ("Horas extraordinarias", payroll.overtime),
        ("Complementos salariales", payroll.salary_supplements),
    ]

    for concepto in conceptos_adicionales:
        items.append((concepto['name'], concepto['value']))

    for label, value in items:
        if value and value > 0:
            texto = f"  {label}"
            p.drawString(margin + 4, y_dev, texto + "." * 60)
            p.drawRightString(col_split - 3, y_dev, f"{value:.2f}")
            y_dev -= 7

    # Contenido totales (columna derecha)
    y_tot = y - 20
    p.setFont("Helvetica-Bold", 7)
    p.drawString(col_split + 2, y_tot, "2. Percepciones no salariales")
    y_tot -= 8

    p.setFont("Helvetica", 6)
    p.drawString(col_split + 4, y_tot, "Indemnizaciones o suplidos:")
    y_tot -= 7

    ss_benefits = percepciones_no_salariales.get('ss_benefits', Decimal('0'))
    if ss_benefits > 0:
        p.drawString(col_split + 4, y_tot, "Prestaciones SS:" + "." * 30)
        p.drawRightString(margin + page_width - 3, y_tot, f"{ss_benefits:.2f}")
        y_tot -= 7

    # Línea antes del total devengado
    y_total_dev = y - devengos_box_height + 15
    p.line(col_split, y_total_dev, margin + page_width, y_total_dev)

    p.setFont("Helvetica-Bold", 8)
    p.drawString(col_split + 2, y_total_dev - 8, "A. TOTAL DEVENGADO")
    p.drawRightString(margin + page_width - 3, y_total_dev - 8, f"{payroll.total_accrued:.2f}")

    y = y - devengos_box_height - 3

    # ============ II. DEDUCCIONES ============
    deduc_height = 95
    p.rect(margin, y - deduc_height, page_width, deduc_height)
    p.line(col_split, y - deduc_height, col_split, y)

    # Encabezado
    p.setFillColor(black)
    p.rect(margin, y - 12, page_width, 12, fill=1)
    p.setFillColor(white)
    p.setFont("Helvetica-Bold", 8)
    p.drawString(margin + 2, y - 8, "II. DEDUCCIONES")
    p.setFillColor(black)

    # Columna izquierda: Aportación trabajador
    y_ded = y - 20
    p.setFont("Helvetica-Bold", 6)
    p.drawString(margin + 2, y_ded, "1. Aportación trabajador cotizaciones SS")
    y_ded -= 7

    p.setFont("Helvetica", 6)

    # Tabla de cotizaciones
    base_common = bases_cotizacion.get('common', Decimal('0'))
    ss_common = desglose_ss_empleado.get('common', Decimal('0'))
    ss_unemployment = desglose_ss_empleado.get('unemployment', Decimal('0'))
    ss_training = desglose_ss_empleado.get('training', Decimal('0'))

    # Contingencias comunes
    p.drawString(margin + 4, y_ded, "Contingencias comunes")
    p.drawRightString(margin + 85, y_ded, f"{base_common:.2f}")
    p.drawRightString(margin + 110, y_ded, "4,70 %")
    p.drawRightString(col_split - 3, y_ded, f"{ss_common:.2f}")
    y_ded -= 7

    # Desempleo
    p.drawString(margin + 4, y_ded, "Desempleo")
    p.drawRightString(margin + 85, y_ded, f"{base_common:.2f}")
    p.drawRightString(margin + 110, y_ded, "1,55 %")
    p.drawRightString(col_split - 3, y_ded, f"{ss_unemployment:.2f}")
    y_ded -= 7

    # Formación Profesional
    p.drawString(margin + 4, y_ded, "Formación Profesional")
    p.drawRightString(margin + 85, y_ded, f"{base_common:.2f}")
    p.drawRightString(margin + 110, y_ded, "0,10 %")
    p.drawRightString(col_split - 3, y_ded, f"{ss_training:.2f}")
    y_ded -= 8

    p.drawString(margin + 4, y_ded, "Horas extraordinarias:")
    y_ded -= 6
    p.drawString(margin + 6, y_ded, "Fuerza mayor")
    p.drawRightString(margin + 110, y_ded, "%")
    y_ded -= 6
    p.drawString(margin + 6, y_ded, "Resto horas extraordinarias")
    p.drawRightString(margin + 110, y_ded, "%")
    y_ded -= 8

    p.setFont("Helvetica-Bold", 6)
    p.drawString(margin + 4, y_ded, "TOTAL APORTACIONES" + "." * 50)
    p.drawRightString(col_split - 3, y_ded, f"{payroll.social_security_employee:.2f}")

    # Columna derecha: IRPF y otras deducciones (CORREGIDO)
    y_ded_der = y - 20
    p.setFont("Helvetica-Bold", 6)

    # Línea 1: Título
    p.drawString(col_split + 2, y_ded_der, "2. Impuesto sobre la renta de")
    y_ded_der -= 6
    p.drawString(col_split + 4, y_ded_der, "las personas físicas")
    y_ded_der -= 7

    # Línea 2: Base e IRPF (en NUEVA línea, sin superposición)
    base_irpf = bases_cotizacion.get('irpf', Decimal('0'))
    irpf_percent = (payroll.irpf / base_irpf * 100) if base_irpf > 0 else Decimal('0')

    p.setFont("Helvetica", 6)
    p.drawRightString(col_split + 65, y_ded_der, f"{base_irpf:.2f}")
    p.drawRightString(col_split + 95, y_ded_der, f"{irpf_percent:.2f} %")
    y_ded_der -= 7

    # Línea 3: Monto IRPF
    p.drawRightString(margin + page_width - 3, y_ded_der, f"{payroll.irpf:.2f}")
    y_ded_der -= 10

    p.setFont("Helvetica-Bold", 6)
    p.drawString(col_split + 2, y_ded_der, "3. Anticipos" + "." * 50)
    y_ded_der -= 8
    p.drawString(col_split + 2, y_ded_der, "4. Valor productos recibidos en especie" + "." * 30)
    y_ded_der -= 8
    p.drawString(col_split + 2, y_ded_der, "5. Otras deducciones:")
    y_ded_der -= 12

    # Totales finales
    y_total_ded = y - deduc_height + 20
    p.setLineWidth(1.5)
    p.line(col_split, y_total_ded, margin + page_width, y_total_ded)

    p.setFont("Helvetica-Bold", 7)
    p.drawString(col_split + 2, y_total_ded - 8, "B. TOTAL A DEDUCIR" + "." * 25)
    p.drawRightString(margin + page_width - 3, y_total_ded - 8, f"{payroll.total_deductions:.2f}")

    y_total_ded -= 17
    p.drawString(col_split + 2, y_total_ded, "LIQUIDO TOTAL A PERCIBIR (A-B)    Euros")
    p.setFont("Helvetica-Bold", 9)
    p.drawRightString(margin + page_width - 3, y_total_ded, f"{payroll.net_salary:.2f}")

    y = y - deduc_height - 8

    # ============ FECHA Y FIRMA ============
    p.setFont("Helvetica", 7)
    ciudad = datos_emision.get('city', 'madrid')
    dia = datos_emision.get('day', payroll.issue_date.day)
    mes = datos_emision.get('month', payroll.issue_date.strftime('%B').upper())
    año = datos_emision.get('year', payroll.issue_date.year)

    p.drawCentredString(width / 2, y, f"{ciudad}          {dia} de {mes}          de          {año}")
    y -= 10
    p.drawCentredString(width / 2, y, "RECIBÍ")
    y -= 12

    # ============ DATOS BANCARIOS ============
    if datos_bancarios.get('iban'):
        p.rect(margin, y - 12, page_width, 12)
        p.setFont("Helvetica-Bold", 7)
        p.drawString(margin + 2, y - 8, f"IBAN: {datos_bancarios['iban']}")
        p.drawString(margin + page_width / 2, y - 8, f"SWIFT/BIC: {datos_bancarios.get('swift', '')}")
        y -= 22

    # ============ BASES DE COTIZACIÓN (CORREGIDO - sin superposición) ============
    p.setFont("Helvetica-Bold", 5.5)

    # Dividir el texto largo en dos líneas para evitar superposición
    p.drawString(margin, y, "DETERMINACIÓN DE LAS BASES DE COTIZACIÓN A LA SEGURIDAD SOCIAL Y CONCEPTOS DE")
    y -= 7
    p.drawString(margin, y,
                 "RECAUDACIÓN CONJUNTA Y DE LA BASE SUJETA A RETENCIÓN DEL I.R.P.F. Y APORTACIÓN DE LA EMPRESA")
    y -= 10

    # Tabla de bases
    table_height = 75
    p.rect(margin, y - table_height, page_width, table_height)

    # Encabezados
    p.setFont("Helvetica-Bold", 6)
    p.drawString(margin + 2, y - 7, "CONCEPTO")
    p.drawRightString(margin + 230, y - 7, "BASE")
    p.drawRightString(margin + 280, y - 7, "TIPO")
    p.drawRightString(margin + page_width - 3, y - 7, "APORTACIÓN EMPRESARIAL")

    y -= 12
    p.setFont("Helvetica", 5)

    # Fila 1
    base_cc = bases_cotizacion.get('common', Decimal('0'))
    p.drawString(margin + 2, y, "1. Base de cotización por contingencias comunes")
    y -= 6
    p.drawString(margin + 4, y, "Remuneración mensual")
    y -= 6
    p.drawString(margin + 4, y, "Prorrata pagas extraordinarias")
    p.drawRightString(margin + 230, y - 6, f"{base_cc:.2f}")

    ss_common_emp = desglose_ss_empresa.get('common', Decimal('0'))
    ss_mei = desglose_ss_empresa.get('mei', Decimal('0'))

    p.drawRightString(margin + 280, y, "23,60")
    p.drawRightString(margin + page_width - 3, y, f"{ss_common_emp:.2f}")
    y -= 6
    p.drawString(margin + 10, y, "Mecanismo Equidad Intergeneracional (MEI)")
    p.drawRightString(margin + 280, y, "0,58")
    p.drawRightString(margin + page_width - 3, y, f"{ss_mei:.2f}")

    # Fila 2
    y -= 8
    base_cp = bases_cotizacion.get('professional', Decimal('0'))
    p.drawString(margin + 2, y, "2. Base de cotización por contingencias profesionales")
    p.drawRightString(margin + 280, y, "AT y EP")
    y -= 6
    p.drawString(margin + 4, y, "conceptos de recaudación")
    p.drawRightString(margin + 230, y - 6, f"{base_cp:.2f}")

    ss_unemp_emp = desglose_ss_empresa.get('unemployment', Decimal('0'))
    ss_train_emp = desglose_ss_empresa.get('training', Decimal('0'))
    ss_fogasa = desglose_ss_empresa.get('fogasa', Decimal('0'))

    y -= 6
    p.drawString(margin + 6, y, "Desempleo")
    p.drawRightString(margin + 280, y, "5,50")
    p.drawRightString(margin + page_width - 3, y, f"{ss_unemp_emp:.2f}")
    y -= 6
    p.drawString(margin + 6, y, "Formación Profesional")
    p.drawRightString(margin + 280, y, "0,60")
    p.drawRightString(margin + page_width - 3, y, f"{ss_train_emp:.2f}")
    y -= 6
    p.drawString(margin + 6, y, "Fondo Garantía Salarial")
    p.drawRightString(margin + 280, y, "0,20")
    p.drawRightString(margin + page_width - 3, y, f"{ss_fogasa:.2f}")

    # Fila 3
    y -= 6
    p.drawString(margin + 2, y, "3. Base de cotización adicional por horas extraordinarias")

    # Fila 4
    y -= 6
    base_irpf_final = bases_cotizacion.get('irpf', Decimal('0'))
    p.drawString(margin + 2, y, "4. Base sujeta a retención del I.R.P.F.")
    p.drawRightString(margin + 230, y, f"{base_irpf_final:.2f}")

    p.showPage()
    p.save()

    buffer.seek(0)
    return buffer.getvalue()