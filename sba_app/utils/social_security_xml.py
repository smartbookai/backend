from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from decimal import Decimal
from datetime import datetime


def generate_social_security_xml(payroll_data):
    """
    Genera XML para presentación a la Seguridad Social (formato RED)
    """
    payroll = payroll_data['payroll']
    employee = payroll_data['employee']
    company = payroll_data['company']
    desglose_ss_empleado = payroll_data['desglose_ss_empleado']
    desglose_ss_empresa = payroll_data['desglose_ss_empresa']
    bases_cotizacion = payroll_data['bases_cotizacion']

    # Crear elemento raíz
    root = Element('FicheroLiquidacion')
    root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    root.set('version', '1.0')

    # Cabecera del fichero
    cabecera = SubElement(root, 'CabeceraFichero')
    SubElement(cabecera, 'CodigoEntidad').text = '0000'  # Código entidad colaboradora
    SubElement(cabecera, 'FechaGeneracion').text = datetime.now().strftime('%Y-%m-%d')
    SubElement(cabecera, 'HoraGeneracion').text = datetime.now().strftime('%H:%M:%S')

    # Datos empresa
    empresa = SubElement(root, 'DatosEmpresa')
    SubElement(empresa, 'CIF').text = company.document_number or ''
    SubElement(empresa, 'CodigoCuentaCotizacion').text = company.ccc or ''
    SubElement(empresa, 'RazonSocial').text = company.name

    # Período de liquidación
    periodo = SubElement(root, 'PeriodoLiquidacion')
    SubElement(periodo, 'Anio').text = str(payroll.period_start.year)
    SubElement(periodo, 'Mes').text = str(payroll.period_start.month).zfill(2)

    # Trabajadores
    trabajadores = SubElement(root, 'Trabajadores')
    trabajador = SubElement(trabajadores, 'Trabajador')

    # Datos del trabajador
    datos_trabajador = SubElement(trabajador, 'DatosTrabajador')
    SubElement(datos_trabajador, 'NumeroAfiliacion').text = employee.social_security_number or ''
    SubElement(datos_trabajador, 'NIF').text = employee.document_number or ''
    SubElement(datos_trabajador, 'Apellidos').text = employee.last_name
    SubElement(datos_trabajador, 'Nombre').text = employee.first_name

    # Datos de cotización
    cotizacion = SubElement(trabajador, 'DatosCotizacion')

    # Contingencias Comunes
    cc = SubElement(cotizacion, 'ContingenciasComunes')
    SubElement(cc, 'BaseCotizacion').text = format_decimal(bases_cotizacion['common'])
    SubElement(cc, 'TipoAportacionEmpresarial').text = '23.60'
    SubElement(cc, 'AportacionEmpresarial').text = format_decimal(desglose_ss_empresa['common'])
    SubElement(cc, 'TipoAportacionTrabajador').text = '4.70'
    SubElement(cc, 'AportacionTrabajador').text = format_decimal(desglose_ss_empleado['common'])

    # MEI (Mecanismo Equidad Intergeneracional)
    mei = SubElement(cotizacion, 'MEI')
    SubElement(mei, 'TipoAportacionEmpresarial').text = '0.58'
    SubElement(mei, 'AportacionEmpresarial').text = format_decimal(desglose_ss_empresa['mei'])
    SubElement(mei, 'TipoAportacionTrabajador').text = '0.00'
    SubElement(mei, 'AportacionTrabajador').text = '0.00'

    # Contingencias Profesionales (AT y EP)
    cp = SubElement(cotizacion, 'ContingenciasProfesionales')
    SubElement(cp, 'BaseCotizacion').text = format_decimal(bases_cotizacion['professional'])
    # El tipo de AT y EP varía según CNAE - aquí un ejemplo genérico
    SubElement(cp, 'TipoAportacionEmpresarial').text = '1.50'
    SubElement(cp, 'AportacionEmpresarial').text = format_decimal(
        bases_cotizacion['professional'] * Decimal('0.015')
    )

    # Desempleo
    desempleo = SubElement(cotizacion, 'Desempleo')
    SubElement(desempleo, 'BaseCotizacion').text = format_decimal(bases_cotizacion['professional'])
    SubElement(desempleo, 'TipoAportacionEmpresarial').text = '5.50'
    SubElement(desempleo, 'AportacionEmpresarial').text = format_decimal(desglose_ss_empresa['unemployment'])
    SubElement(desempleo, 'TipoAportacionTrabajador').text = '1.55'
    SubElement(desempleo, 'AportacionTrabajador').text = format_decimal(desglose_ss_empleado['unemployment'])

    # Formación Profesional
    fp = SubElement(cotizacion, 'FormacionProfesional')
    SubElement(fp, 'BaseCotizacion').text = format_decimal(bases_cotizacion['professional'])
    SubElement(fp, 'TipoAportacionEmpresarial').text = '0.60'
    SubElement(fp, 'AportacionEmpresarial').text = format_decimal(desglose_ss_empresa['training'])
    SubElement(fp, 'TipoAportacionTrabajador').text = '0.10'
    SubElement(fp, 'AportacionTrabajador').text = format_decimal(desglose_ss_empleado['training'])

    # FOGASA
    fogasa = SubElement(cotizacion, 'FOGASA')
    SubElement(fogasa, 'TipoAportacion').text = '0.20'
    SubElement(fogasa, 'Aportacion').text = format_decimal(desglose_ss_empresa['fogasa'])

    # Totales
    totales = SubElement(trabajador, 'TotalesTrabajador')
    total_empresa = sum([
        desglose_ss_empresa['common'],
        desglose_ss_empresa['mei'],
        desglose_ss_empresa['unemployment'],
        desglose_ss_empresa['training'],
        desglose_ss_empresa['fogasa']
    ])
    total_trabajador = sum([
        desglose_ss_empleado['common'],
        desglose_ss_empleado['unemployment'],
        desglose_ss_empleado['training']
    ])

    SubElement(totales, 'TotalAportacionEmpresarial').text = format_decimal(total_empresa)
    SubElement(totales, 'TotalAportacionTrabajador').text = format_decimal(total_trabajador)
    SubElement(totales, 'TotalCuota').text = format_decimal(total_empresa + total_trabajador)

    # Convertir a string con formato pretty
    rough_string = tostring(root, encoding='unicode')
    reparsed = minidom.parseString(rough_string)

    return reparsed.toprettyxml(indent="  ", encoding='utf-8')


def format_decimal(value):
    """
    Formatea un Decimal para el XML (2 decimales, sin separadores de miles)
    """
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return f"{float(value):.2f}"