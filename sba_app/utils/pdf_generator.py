import io
import os
import json
import base64
import logging
from django.shortcuts import render, get_object_or_404
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.conf import settings
from sba_app.models import SavedTemplate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registro de fuentes TTF
# Cada entrada: (nombre_en_diseño, archivo_regular, archivo_bold, archivo_italic, archivo_bolditalic)
# Los archivos deben estar en sba_app/static/fonts/
# ---------------------------------------------------------------------------
_FONTS_DIR = os.path.join(settings.BASE_DIR, 'sba_app', 'static', 'fonts')

_TTF_REGISTRY = [
    ('Roboto',           'Roboto-Regular.ttf',          'Roboto-Bold.ttf',          'Roboto-Italic.ttf',          'Roboto-BoldItalic.ttf'),
    ('Open Sans',        'OpenSans-Regular.ttf',        'OpenSans-Bold.ttf',        'OpenSans-Italic.ttf',        'OpenSans-BoldItalic.ttf'),
    ('Lato',             'Lato-Regular.ttf',            'Lato-Bold.ttf',            'Lato-Italic.ttf',            'Lato-BoldItalic.ttf'),
    ('Montserrat',       'Montserrat-Regular.ttf',      'Montserrat-Bold.ttf',      'Montserrat-Italic.ttf',      'Montserrat-BoldItalic.ttf'),
    ('Raleway',          'Raleway-Regular.ttf',         'Raleway-Bold.ttf',         'Raleway-Italic.ttf',         'Raleway-BoldItalic.ttf'),
    ('Nunito',           'Nunito-Regular.ttf',          'Nunito-Bold.ttf',          'Nunito-Italic.ttf',          'Nunito-BoldItalic.ttf'),
    ('Inter',            'Inter-Regular.ttf',           'Inter-Bold.ttf',           'Inter-Italic.ttf',           'Inter-BoldItalic.ttf'),
    ('Oswald',           'Oswald-Regular.ttf',          'Oswald-Bold.ttf',          None,                         None),
    ('Poppins',          'Poppins-Regular.ttf',         'Poppins-Bold.ttf',         'Poppins-Italic.ttf',         'Poppins-BoldItalic.ttf'),
    ('Playfair Display', 'PlayfairDisplay-Regular.ttf', 'PlayfairDisplay-Bold.ttf', 'PlayfairDisplay-Italic.ttf', 'PlayfairDisplay-BoldItalic.ttf'),
    ('Merriweather',     'Merriweather-Regular.ttf',    'Merriweather-Bold.ttf',    'Merriweather-Italic.ttf',    'Merriweather-BoldItalic.ttf'),
    ('PT Sans',          'PTSans-Regular.ttf',          'PTSans-Bold.ttf',          'PTSans-Italic.ttf',          'PTSans-BoldItalic.ttf'),
]

_REGISTERED_FONTS = set()

def _find_font_file(filename):
    """Busca un .ttf mirando primero en la carpeta fonts/ directamente,
    luego dentro de una subcarpeta con el mismo nombre (estructura de zip de Google Fonts),
    tanto en /static/ como en la raíz de esa subcarpeta."""
    direct = os.path.join(_FONTS_DIR, filename)
    if os.path.isfile(direct):
        return direct
    # El zip de Google Fonts crea una carpeta con el mismo nombre que el archivo regular
    # Ej: fonts/Roboto-Regular.ttf/static/Roboto-Regular.ttf
    # Buscar en todas las subcarpetas de _FONTS_DIR
    try:
        for entry in os.scandir(_FONTS_DIR):
            if not entry.is_dir():
                continue
            # Intentar static/filename
            candidate = os.path.join(entry.path, 'static', filename)
            if os.path.isfile(candidate):
                return candidate
            # Intentar directamente dentro de la carpeta
            candidate = os.path.join(entry.path, filename)
            if os.path.isfile(candidate):
                return candidate
    except FileNotFoundError:
        pass
    return None

def _register_ttf_fonts():
    for (name, f_reg, f_bold, f_italic, f_bi) in _TTF_REGISTRY:
        try:
            reg_path = _find_font_file(f_reg)
            if not reg_path:
                continue  # archivo no encontrado, silenciosamente ignorar

            pdfmetrics.registerFont(TTFont(name, reg_path))
            _REGISTERED_FONTS.add(name)

            bold_path = _find_font_file(f_bold) if f_bold else None
            it_path   = _find_font_file(f_italic) if f_italic else None
            bi_path   = _find_font_file(f_bi) if f_bi else None

            if bold_path:
                pdfmetrics.registerFont(TTFont(name + '-Bold', bold_path))
            if it_path:
                pdfmetrics.registerFont(TTFont(name + '-Italic', it_path))
            if bi_path:
                pdfmetrics.registerFont(TTFont(name + '-BoldItalic', bi_path))

            pdfmetrics.registerFontFamily(
                name,
                normal     = name,
                bold       = name + '-Bold'        if bold_path else name,
                italic     = name + '-Italic'      if it_path   else name,
                boldItalic = name + '-BoldItalic'  if bi_path   else name,
            )
        except Exception as e:
            logger.debug("No se pudo registrar la fuente '%s': %s", name, e)

_register_ttf_fonts()


# --- 1. LÓGICA DE GUARDADO (EDITOR) ---

def save_screenshot_from_dataurl(saved_template, dataurl):
    logger.debug("Iniciando proceso de guardado de foto")
    try:
        if not dataurl or ';base64,' not in dataurl:
            logger.error("La imagen llegó vacía o corrupta desde el navegador.")
            return False

        logger.debug("Imagen recibida correctamente. Tamaño base64: %d caracteres.", len(dataurl))

        format, imgstr = dataurl.split(';base64,')
        ext = format.split('/')[-1]
        data = ContentFile(base64.b64decode(imgstr), name=f'template_{saved_template.id}.{ext}')

        logger.debug("Intentando escribir el archivo en el disco duro...")
        saved_template.screenshot.save(f'template_{saved_template.id}.{ext}', data, save=True)

        logger.debug("Foto guardada en: %s", saved_template.screenshot.path)
        return True
    except Exception as e:
        logger.error("Excepción al guardar screenshot: %s", e)
        return False

def template_builder_view(request, template_id=None):
    # --- AQUÍ ESTÁ LA MAGIA: ATRAPAMOS EL POST DIRECTAMENTE EN LA VISTA PRINCIPAL ---
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            template_name = body.get('name', 'Nueva Plantilla')
            design_data = body.get('design', [])
            screenshot_dataurl = body.get('screenshot')
            overwrite = body.get('overwrite', False)

            # Usamos SavedTemplate
            template, created = SavedTemplate.objects.update_or_create(
                id=template_id if template_id and overwrite else None,
                defaults={
                    'name': template_name,
                    'design_data': design_data,
                    'is_system': False,
                }
            )
            
            # Guardamos la foto usando la función que ya tenemos arriba
            if screenshot_dataurl:
                logger.debug("Recibida captura de: %d caracteres", len(screenshot_dataurl))
                save_screenshot_from_dataurl(template, screenshot_dataurl)
            else:
                logger.debug("No se ha recibido ninguna captura")
            
            return JsonResponse({'success': True, 'id': template.id})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    # --- SI NO ES POST, ES GET (CARGAMOS LA PÁGINA NORMALMENTE) ---
    plantilla_a_editar = None
    if template_id:
        plantilla_a_editar = get_object_or_404(SavedTemplate, id=template_id)

    # Preparamos los diseños de usuario con sus URLs de imagen
    mis_disenos = SavedTemplate.objects.filter(is_system=False).order_by('-updated_at')
    templates_usuario = []
    for d in mis_disenos:
        templates_usuario.append({
            'id': d.id,
            'style_name': d.name,
            'screenshot_url': d.screenshot.url if d.screenshot else None
        })

    context = {
        'saved_json': json.dumps(plantilla_a_editar.design_data) if plantilla_a_editar else "[]",
        'templates_sistema': SavedTemplate.objects.filter(is_system=True),
        'templates_usuario': templates_usuario,
    }
    return render(request, 'template_builder.html', context)


# --- 2. LÓGICA DE GENERACIÓN DE PDF ---

def get_document_data(document):
    """Mapea los datos del modelo a los tokens del diseño"""
    client  = getattr(document, 'client', None)
    company = getattr(document, 'company', None)

    fmt_date  = lambda d: d.strftime('%d/%m/%Y') if d else ''
    fmt_money = lambda v: f"{v:.2f} €" if v is not None else ''

    base      = float(getattr(document, 'base_amount',   0) or 0)
    tax       = float(getattr(document, 'tax_amount',    0) or 0)
    total     = float(getattr(document, 'total_amount',  0) or 0)
    disc_a    = float(getattr(document, 'discount_amount',    0) or 0)
    disc_p    = float(getattr(document, 'discount_percentage', 0) or 0)
    irpf_rate = float(getattr(document, 'irpf_rate',   0) or 0)
    irpf_amt  = float(getattr(document, 'irpf_amount', 0) or 0)

    # IVA rate from first invoice line (best-effort)
    iva_rate = 0.0
    try:
        first_line = document.lines.first()
        if first_line:
            iva_rate = float(getattr(first_line, 'vat_rate', 0) or 0)
    except Exception:
        pass

    data = {
        # ── Número y fechas ────────────────────────────────────────────
        'NUMERO':            getattr(document, 'invoice_number', ''),
        'NUMERO_FACTURA':    getattr(document, 'invoice_number', ''),
        'FECHA_EMISION':     fmt_date(getattr(document, 'issue_date', None)),
        'FECHA':             fmt_date(getattr(document, 'issue_date', None)),
        'FECHA_VENCIMIENTO': fmt_date(getattr(document, 'due_date', None)),
        'VENCIMIENTO':       fmt_date(getattr(document, 'due_date', None)),
        'FORMA_PAGO':        getattr(document, 'payment_method', '') or '',

        # ── Importes ───────────────────────────────────────────────────
        'BASE_IMPONIBLE':   fmt_money(base),
        'SUBTOTAL':         fmt_money(base),
        'BASE':             fmt_money(base),
        'IVA':              fmt_money(tax),
        'IVA_TOTAL':        fmt_money(tax),
        'TOTAL_IVA':        fmt_money(tax),
        'IMPORTE_IVA':      fmt_money(tax),
        'TASA_IVA':         f"{iva_rate:.0f} %" if iva_rate else '',
        'PCT_IVA':          f"{iva_rate:.0f} %" if iva_rate else '',
        'DESCUENTO':        fmt_money(disc_a) if disc_a else '',
        'DESCUENTO_PCT':    f"{disc_p:.2f} %" if disc_p else '',
        'DESCUENTO_PORCENTAJE': f"{disc_p:.2f} %" if disc_p else '',
        'TOTAL':            fmt_money(total),
        'TOTAL_DOC':        fmt_money(total),
        'TOTAL_FACTURA':    fmt_money(total),

        # ── IRPF (vacío cuando no hay retención) ──────────────────────
        'IRPF_TASA':        f"{irpf_rate:.0f} %" if irpf_rate else '',
        'PCT_IRPF':         f"{irpf_rate:.0f} %" if irpf_rate else '',
        'IRPF_IMPORTE':     f"-{irpf_amt:.2f} €" if irpf_amt else '',
        'IRPF':             f"-{irpf_amt:.2f} €" if irpf_amt else '',

        # ── Notas ──────────────────────────────────────────────────────
        'NOTAS':            getattr(document, 'notes', '') or '',
        'OBSERVACIONES':    getattr(document, 'notes', '') or '',

        # ── Empresa ────────────────────────────────────────────────────
        'EMPRESA_NOMBRE':   getattr(company, 'name', '')            if company else '',
        'EMPRESA_NAME':     getattr(company, 'name', '')            if company else '',
        'EMPRESA_CIF':      getattr(company, 'document_number', '') if company else '',
        'EMPRESA_NIF':      getattr(company, 'document_number', '') if company else '',
        'EMPRESA_DIR':      getattr(company, 'address', '')         if company else '',
        'EMPRESA_DIRECCION':getattr(company, 'address', '')         if company else '',
        'EMPRESA_EMAIL':    getattr(company, 'email', '')           if company else '',
        'EMPRESA_TEL':      getattr(company, 'phone', '')           if company else '',
        'EMPRESA_TELEFONO': getattr(company, 'phone', '')           if company else '',
        'EMPRESA_WEB':      getattr(company, 'website', '')         if company else '',

        # ── Cliente ────────────────────────────────────────────────────
        'CLIENTE_NOMBRE':   getattr(client, 'name', '')            if client else '',
        'CLIENTE_NAME':     getattr(client, 'name', '')            if client else '',
        'CLIENTE_CIF':      getattr(client, 'document_number', '') if client else '',
        'CLIENTE_NIF':      getattr(client, 'document_number', '') if client else '',
        'CLIENTE_DIR':      getattr(client, 'address', '')         if client else '',
        'CLIENTE_DIRECCION':getattr(client, 'address', '')         if client else '',
        'CLIENTE_EMAIL':    getattr(client, 'email', '')           if client else '',
        'CLIENTE_TEL':      getattr(client, 'phone', '')           if client else '',
        'CLIENTE_TELEFONO': getattr(client, 'phone', '')           if client else '',
        'CLIENTE_CONTACTO': getattr(client, 'contact_person', '')  if client else '',

        # ── Cuentas contables ──────────────────────────────────────────
        'CUENTA_INGRESOS':  getattr(document, 'account_income', '')     or '',
        'CUENTA_CLIENTE':   getattr(document, 'account_customer', '')   or '',
        'CUENTA_IVA':       getattr(document, 'account_vat_output', '') or '',
    }
    return data

def get_reportlab_font(font_name, bold, italic):
    """Mapeo de fuentes web a las 3 familias built-in de ReportLab"""
    fn = str(font_name).lower()

    SERIF = {'times', 'times-roman', 'times new roman', 'playfair display', 'playfair', 'merriweather', 'pt serif'}
    MONO  = {'courier', 'courier new', 'source code pro', 'source code'}

    if fn in SERIF or 'times' in fn or 'serif' in fn and 'sans' not in fn:
        base = "Times-Roman"
    elif fn in MONO or 'courier' in fn or 'mono' in fn or 'code' in fn:
        base = "Courier"
    else:
        base = "Helvetica"

    if base == "Times-Roman":
        if bold and italic: return "Times-BoldItalic"
        return "Times-Bold" if bold else ("Times-Italic" if italic else base)
    elif base == "Courier":
        if bold and italic: return "Courier-BoldOblique"
        return "Courier-Bold" if bold else ("Courier-Oblique" if italic else base)
    else:
        if bold and italic: return "Helvetica-BoldOblique"
        return "Helvetica-Bold" if bold else ("Helvetica-Oblique" if italic else base)

def _load_template_design(template_id, doc_type):
    """Load and parse a UserTemplate's custom_html as JSON design data.

    Tries the specific template_id first; falls back to the system default for
    doc_type.  Returns the parsed list or None if nothing is found / parseable.
    """
    from sba_app.models import UserTemplate

    if template_id:
        tpl = UserTemplate.objects.filter(id=template_id, document_type=doc_type).first()
        if tpl and tpl.custom_html:
            try:
                return json.loads(tpl.custom_html)
            except (ValueError, TypeError):
                pass

    tpl = UserTemplate.objects.filter(is_system_default=True, document_type=doc_type).first()
    if tpl and tpl.custom_html:
        try:
            return json.loads(tpl.custom_html)
        except (ValueError, TypeError):
            pass

    return None


def generate_invoice_pdf(invoice, template_id=None):
    """Genera el PDF basándose en el JSON de la base de datos"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    design_data = _load_template_design(template_id, 'invoice')

    if not design_data:
        c.drawString(100, height - 100, "Error: No hay diseño.")
        c.save()
        return buffer.getvalue()
    invoice_data = get_document_data(invoice)
    y_table = height - 500 

    # DIBUJAR SHAPES (FONDOS)
    # Si el shape tiene un 'token', se omite cuando ese token está vacío en los datos
    for item in design_data:
        if item.get('type') == 'shape':
            shape_token = item.get('token', '')
            if shape_token and not invoice_data.get(shape_token, ''):
                continue
            x, y_web = item.get('x', 0), item.get('y', 0)
            w, h = item.get('width', 100), item.get('height', 50)
            c.setFillColor(colors.HexColor(item.get('bg_color', '#CCCCCC')))
            c.rect(x, height - y_web - h, w, h, stroke=0, fill=1)

    # DIBUJAR TEXTOS Y LOGO
    for item in design_data:
        x, y_web = item.get('x', 0), item.get('y', 0)
        token = item.get('token', '')
        
        if token == 'LOGO_EMPRESA' and invoice.company.logo:
            try:
                img = ImageReader(invoice.company.logo.path)
                box_w = item.get('logo_width', 120)
                box_h = box_w * 0.8  # same bounding box the builder placeholder uses
                iw, ih = img.getSize()
                aspect = ih / float(iw)
                if aspect <= 0.8:
                    desired_w, desired_h = box_w, box_w * aspect
                else:
                    desired_h, desired_w = box_h, box_h / aspect
                c.drawImage(img, x, height - y_web - desired_h, width=desired_w, height=desired_h, mask='auto')
            except: pass
            
        elif item.get('type') in ['label', 'value'] and token != 'TABLA_ITEMS':
            size = item.get('size', 10)
            c.setFillColor(colors.HexColor(item.get('color', '#000000')))
            c.setFont(get_reportlab_font(item.get('font', 'Helvetica'), item.get('bold', False), item.get('italic', False)), size)
            
            texto = item.get('text', '') if item.get('type') == 'label' else str(invoice_data.get(token, ''))
            if texto and texto != 'None':
                c.drawString(x, height - y_web - size, texto)

    c.showPage()
    c.save()
    return buffer.getvalue()