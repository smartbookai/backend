import io
import json
import base64
import fitz  # PyMuPDF
from environ import logger
from pdf2image import convert_from_bytes  # pip install pdf2image
from django.conf import settings
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# 🧠 Prompt base que instruye al modelo
BASE_PROMPT = (
    "Sos un extractor de datos de facturas. "
    "Analizá el contenido y devolvé un JSON EXACTO con esta estructura:\n\n"
    "{\n"
    "  \"invoice\": {\n"
    "    \"invoice_number\": \"string\",\n"
    "    \"issue_date\": \"YYYY-MM-DD\",\n"
    "    \"due_date\": \"YYYY-MM-DD\" o null,\n"
    "    \"payment_method\": \"string\" o null,\n"
    "    \"base_amount\": \"1750.00\",\n"
    "    \"tax_amount\": \"0.00\",\n"
    "    \"total_amount\": \"1750.00\",\n"
    "    \"notes\": \"string\" o null\n"
    "  },\n"
    "  \"client\": {\n"
    "    \"name\": \"string\",\n"
    "    \"contact_person\": \"string\" o null,\n"
    "    \"phone\": \"string\" o null,\n"
    "    \"email\": \"string\" o null,\n"
    "    \"address\": \"string\" o null,\n"
    "    \"document_type\": \"string\" o null,\n"
    "    \"document_number\": \"string\" o null\n"
    "  },\n"
    "  \"lines\": [\n"
    "    {\n"
    "      \"description\": \"Descripción del producto/servicio\",\n"
    "      \"quantity\": \"1.00\",\n"
    "      \"unit_price\": \"1750.00\",\n"
    "      \"vat_rate\": \"21.00\"\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "IMPORTANTE:\n"
    "- Los montos deben ser strings con formato numérico: \"1750.00\", \"0.00\", etc.\n"
    "- NO uses comas como separador de miles\n"
    "- USA punto como separador decimal\n"
    "- Si no encontrás un monto, usa \"0.00\"\n"
    "- Si no encontrás un dato, ponelo como null\n"
    "- Para las líneas (lines), extraé TODOS los ítems/productos/servicios de la factura\n"
    "- Si no hay IVA especificado en la línea, usa \"0.00\" en vat_rate\n"
    "- Cantidad (quantity) por defecto es \"1.00\" si no está especificada\n"
    "- NO inventes valores\n"
)


def extract_invoice_data(file):
    """
    Extrae datos de una factura (PDF o imagen) usando OpenAI.
    Devuelve dict con { 'invoice': {...}, 'client': {...}, 'lines': [...] }.
    Además añade la clave opcional 'tokens' con los tokens totales consumidos.
    """
    content_type = file.content_type.lower()
    result = {}
    tokens = None

    try:
        # --- CASO 1: PDF ---
        if "pdf" in content_type:
            pdf_bytes = file.read()

            # Intentar extraer texto directamente
            text = ""
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for page in doc:
                    text += page.get_text("text")

            # Si el texto es corto o sin montos → pasar a imagen
            if len(text.strip()) < 50 or ("€" not in text and "$" not in text):
                print("⚠️ PDF parece escaneado → usando OCR visual.")
                images = convert_from_bytes(pdf_bytes, fmt="png")
                first_page = images[0]
                buf = io.BytesIO()
                first_page.save(buf, format="PNG")
                buf.seek(0)
                image_bytes = buf.read()

                # CORREGIDO: Codificar imagen en base64
                base64_image = base64.b64encode(image_bytes).decode('utf-8')

                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": BASE_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Extraé los datos de esta factura incluyendo todas las líneas de productos/servicios y devolvé solo el JSON."},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{base64_image}"
                                    }
                                },
                            ],
                        },
                    ],
                    response_format={"type": "json_object"},
                )

                usage = getattr(response, "usage", None)
                if usage is not None:
                    tokens = getattr(usage, "total_tokens", None)

            else:
                # Si hay texto legible, usarlo directamente
                print(f"✅ Texto extraído del PDF ({len(text)} caracteres)")
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": BASE_PROMPT},
                        {"role": "user", "content": f"Extraé los datos de esta factura incluyendo todas las líneas:\n\n{text}"},
                    ],
                    response_format={"type": "json_object"},
                )

        # --- CASO 2: Imagen (JPG / PNG) ---
        elif any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
            image_bytes = file.read()

            # CORREGIDO: Codificar imagen en base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')

            # Detectar el mime type correcto
            mime_type = "image/jpeg" if "jpeg" in content_type or "jpg" in content_type else "image/png"

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": BASE_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extraé los datos de esta factura incluyendo todas las líneas de productos/servicios y devolvé solo el JSON."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                }
                            },
                        ],
                    },
                ],
                response_format={"type": "json_object"},
            )

            usage = getattr(response, "usage", None)
            if usage is not None:
                tokens = getattr(usage, "total_tokens", None)

        else:
            raise ValueError("Formato de archivo no soportado")

        # --- Parsear JSON seguro ---
        content = response.choices[0].message.content
        print(f"🤖 Respuesta de OpenAI: {content}")
        result = json.loads(content)
        result["tokens"] = tokens

    except Exception as e:
        print(f"⚠️ Error en extract_invoice_data: {e}")
        import traceback
        print(traceback.format_exc())
        result = {"tokens": None}

    return result


#############################################Here stars the code for purchase invoices#####################################################
# Prompt para FACTURAS RECIBIDAS (Purchase Invoices)
PURCHASE_INVOICE_PROMPT = (
    "Sos un extractor de datos de facturas RECIBIDAS. "
    "Analizá el contenido y devolvé un JSON EXACTO con esta estructura:\n\n"
    "{\n"
    "  \"invoice\": {\n"
    "    \"invoice_number\": \"string\",\n"
    "    \"issue_date\": \"YYYY-MM-DD\",\n"
    "    \"due_date\": \"YYYY-MM-DD\" o null,\n"
    "    \"payment_method\": \"string\" o null,\n"
    "    \"base_amount\": \"10.00\",\n"
    "    \"tax_amount\": \"2.10\",\n"
    "    \"total_amount\": \"12.10\",\n"
    "    \"notes\": \"string\" o null\n"
    "  },\n"
    "  \"supplier\": {\n"
    "    \"name\": \"string\",\n"
    "    \"contact_person\": \"string\" o null,\n"
    "    \"phone\": \"string\" o null,\n"
    "    \"email\": \"string\" o null,\n"
    "    \"address\": \"string\" o null,\n"
    "    \"document_type\": \"string\" o null,\n"
    "    \"document_number\": \"string\" o null\n"
    "  },\n"
    "  \"lines\": [\n"
    "    {\n"
    "      \"description\": \"Descripción del producto/servicio\",\n"
    "      \"quantity\": \"1.00\",\n"
    "      \"unit_price\": \"10.00\",\n"
    "      \"vat_rate\": \"21.00\"\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "IMPORTANTE:\n"
    "- Esta es una FACTURA RECIBIDA (de compra)\n"
    "- El SUPPLIER es quien EMITE la factura (el que cobra/vende)\n"
    "- Extraé los datos de quien EMITE la factura como 'supplier'\n"
    "- NO extraigas los datos de quien RECIBE la factura\n"
    "- Los montos deben ser strings con formato numérico: \"10.00\", \"2.10\", etc.\n"
    "- NO uses comas como separador de miles\n"
    "- USA punto como separador decimal\n"
    "- Si no encontrás un monto, usa \"0.00\"\n"
    "- Si no encontrás un dato, ponelo como null\n"
    "- Para las líneas (lines), extraé TODOS los ítems/productos/servicios de la factura\n"
    "- Si no hay IVA especificado en la línea, usa \"0.00\" en vat_rate\n"
    "- Cantidad (quantity) por defecto es \"1.00\" si no está especificada\n"
    "- NO inventes valores\n"
)


def extract_purchase_invoice_data(file):
    content_type = file.content_type.lower()
    result = {}

    try:
        # --- 🧾 CASO 1: PDF ---
        if "pdf" in content_type:
            pdf_bytes = file.read()

            # Intentar extraer texto directamente
            text = ""
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for page in doc:
                    text += page.get_text("text")

            print(f"✅ Texto extraído del PDF ({len(text)} caracteres)")

            # Si hay texto, usarlo
            if text.strip():
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": PURCHASE_INVOICE_PROMPT},
                        {"role": "user",
                         "content": f"Extraé los datos de esta factura RECIBIDA. El supplier es quien EMITE la factura:\n\n{text}"},
                    ],
                    response_format={"type": "json_object"},
                )
            else:
                print("⚠️ No se pudo extraer texto del PDF")
                return {}

        # --- 🖼️ CASO 2: Imagen (JPG / PNG) ---
        elif any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
            image_bytes = file.read()
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            mime_type = "image/jpeg" if "jpeg" in content_type or "jpg" in content_type else "image/png"

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": PURCHASE_INVOICE_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text",
                             "text": "Extraé los datos de esta factura RECIBIDA. El supplier es quien EMITE la factura."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                }
                            },
                        ],
                    },
                ],
                response_format={"type": "json_object"},
            )
        else:
            raise ValueError("Formato de archivo no soportado")

        content = response.choices[0].message.content
        print(f"🤖 Respuesta de OpenAI (Purchase): {content}")
        result = json.loads(content)

    except Exception as e:
        print(f"⚠️ Error en extract_purchase_invoice_data: {e}")
        import traceback
        print(traceback.format_exc())
        result = {}

    return result


#############################################Here stars the code for payroll extraction#####################################################
# 🧠 Prompt para extracción de nóminas
BASE_PROMPT_PAYROLL = (
    "Sos un extractor de datos de nóminas españolas. "
    "Analizá CUIDADOSAMENTE el contenido de la nómina y devolvé un JSON EXACTO con esta estructura.\n\n"
    "REGLAS CRÍTICAS:\n"
    "- SOLO extraé datos que VEAS CLARAMENTE en el documento\n"
    "- Si NO estás 100% seguro de un dato, poné null\n"
    "- NO inventes, supongas o deduzcas información\n"
    "- NO completes datos faltantes con información lógica\n"
    "- Si un campo está borroso o no visible, poné null\n\n"

    "UBICACIONES ESPECÍFICAS EN NÓMINAS ESPAÑOLAS:\n"
    "- DIRECCIÓN TRABAJADOR: Buscar en la parte superior del documento, junto al nombre del trabajador\n"
    "- DIRECCIÓN EMPRESA: Buscar en la sección 'EMPRESA' o 'DOMICILIO EMPRESA' (NO usar esta para el trabajador)\n"
    "- SS EMPRESA: Buscar en la tabla inferior 'APORTACIÓN EMPRESARIAL' y SUMAR todas las líneas:\n"
    "  * Contingencias comunes\n"
    "  * MEI (Mecanismo Equidad Intergeneracional)\n"
    "  * AT y EP (Accidentes de trabajo)\n"
    "  * Desempleo\n"
    "  * Formación Profesional\n"
    "  * Fondo Garantía Salarial\n"
    "  NO usar el campo 'COSTE EMPRESA' que incluye salario + aportaciones\n\n"

    "ESTRUCTURA ESPERADA:\n"
    "{\n"
    "  \"employee\": {\n"
    "    \"first_name\": \"string\" (buscar en sección TRABAJADOR, parte superior),\n"
    "    \"last_name\": \"string\" (buscar en sección TRABAJADOR, parte superior),\n"
    "    \"document_type\": \"DNI\" o \"NIE\" o \"Pasaporte\" (buscar DNI/NIF/NIE),\n"
    "    \"document_number\": \"string\" (número de documento del trabajador),\n"
    "    \"email\": null (raramente está en nóminas),\n"
    "    \"phone\": null (raramente está en nóminas),\n"
    "    \"date_of_birth\": null (raramente está en nóminas),\n"
    "    \"address\": \"string\" (buscar domicilio del TRABAJADOR en la parte superior, NO la dirección de la empresa),\n"
    "    \"job_position\": \"string\" (buscar categoría profesional/grupo profesional),\n"
    "    \"department\": null (raramente visible),\n"
    "    \"contract_type\": \"indefinido\" o \"temporal\" o null,\n"
    "    \"hire_date\": \"YYYY-MM-DD\" (buscar fecha de antigüedad/alta) o null,\n"
    "    \"social_security_number\": \"string\" (buscar Nº Afiliación SS o NAF),\n"
    "    \"bank_account\": null (raramente visible),\n"
    "    \"collective_agreement\": \"string\" (buscar convenio) o null\n"
    "  },\n"
    "  \"payroll\": {\n"
    "    \"period_start\": \"YYYY-MM-DD\" (buscar período de liquidación - día 1),\n"
    "    \"period_end\": \"YYYY-MM-DD\" (buscar período de liquidación - último día),\n"
    "    \"payment_date\": \"YYYY-MM-DD\" (buscar fecha de pago) o usar period_end,\n"
    "    \"issue_date\": \"YYYY-MM-DD\" (buscar fecha de emisión/elaboración),\n"
    "    \"base_salary\": \"0.00\" (buscar en DEVENGOS > Salario base),\n"
    "    \"salary_supplements\": \"0.00\" (suma de todos los complementos en DEVENGOS, NO incluir salario base),\n"
    "    \"overtime\": \"0.00\" (buscar horas extras),\n"
    "    \"bonuses\": \"0.00\" (buscar gratificaciones/pagas),\n"
    "    \"total_accrued\": \"0.00\" (buscar TOTAL DEVENGADO o T. DEVENGADO),\n"
    "    \"social_security_employee\": \"0.00\" (buscar en DEDUCCIONES > Cotización Contingencias Comunes),\n"
    "    \"irpf\": \"0.00\" (buscar en DEDUCCIONES > IRPF o Tributación),\n"
    "    \"other_deductions\": \"0.00\" (suma de otras deducciones: MEI, Formación, Desempleo del trabajador),\n"
    "    \"total_deductions\": \"0.00\" (buscar TOTAL A DEDUCIR o T. A DEDUCIR),\n"
    "    \"net_salary\": \"0.00\" (buscar LÍQUIDO A PERCIBIR),\n"
    "    \"social_security_company\": \"0.00\" (buscar en la tabla inferior y SUMAR todas las 'APORTACIÓN EMPRESARIAL': Contingencias comunes + MEI + AT/EP + Desempleo + Formación + Fondo Garantía. NO usar 'COSTE EMPRESA'),\n"
    "    \"notes\": null\n"
    "  }\n"
    "}\n\n"
    "IMPORTANTE - FORMATO DE NÚMEROS:\n"
    "- CRÍTICO: NO uses NUNCA comas en los números\n"
    "- Formato CORRECTO: \"1412.06\"\n"
    "- Formato INCORRECTO: \"1,412.06\"\n"
    "- Los montos deben ser strings sin comas: \"1500.00\", \"0.00\"\n"
    "- USA punto como separador decimal\n"
    "- NO uses comas como separador de miles\n"
    "- Si no encontrás un monto CLARAMENTE, usa \"0.00\"\n"
    "- Si no encontrás un dato, ponelo como null\n"
    "- Las fechas deben estar en formato YYYY-MM-DD\n"
    "- Para social_security_company: SUMAR líneas de aportación empresarial, NO usar COSTE EMPRESA\n"
    "- Para address del employee: Buscar SOLO en la sección del trabajador (parte superior), ignorar dirección de empresa\n"
    "- Si la imagen está borrosa o ilegible, responde con null en los campos poco claros\n"
    "- NUNCA inventes información\n"
)

def extract_payroll_data(file):
    """
    Extrae datos de una nómina (PDF o imagen) usando OpenAI.
    Devuelve dict con { 'payroll': {...}, 'employee': {...} }.
    """
    content_type = file.content_type.lower()
    result = {}

    try:
        # --- 🧾 CASO 1: PDF ---
        if "pdf" in content_type:
            pdf_bytes = file.read()

            # Extraer texto directamente
            text = ""
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for page in doc:
                    text += page.get_text("text")

            print(f"✅ Texto extraído del PDF de nómina ({len(text)} caracteres)")

            # Si hay texto, usarlo
            if text.strip():
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": BASE_PROMPT_PAYROLL},
                        {"role": "user", "content": f"Extraé los datos de esta nómina:\n\n{text}"},
                    ],
                    response_format={"type": "json_object"},
                )
            else:
                print("⚠️ No se pudo extraer texto del PDF")
                return {}

        # --- 🖼️ CASO 2: Imagen (JPG / PNG) ---
        elif any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
            image_bytes = file.read()
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            mime_type = "image/jpeg" if "jpeg" in content_type or "jpg" in content_type else "image/png"

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": BASE_PROMPT_PAYROLL},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extraé los datos de esta nómina y devolvé solo el JSON."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                }
                            },
                        ],
                    },
                ],
                response_format={"type": "json_object"},
            )
        else:
            raise ValueError("Formato de archivo no soportado")

        content = response.choices[0].message.content
        print(f"🤖 Respuesta de OpenAI (Nómina): {content}")
        result = json.loads(content)

    except Exception as e:
        print(f"⚠️ Error en extract_payroll_data: {e}")
        import traceback
        print(traceback.format_exc())
        result = {}

    return result

############################################################################generate accounting entry for purchase#####################################################
def generate_accounting_entry_for_purchase(invoice_data, lines_data, supplier_name):
    """
    Genera la estructura del asiento contable para una factura de compra
    utilizando IA para determinar las cuentas más apropiadas según el PGC español.
    """
    try:
        # Preparar el contexto de las líneas
        lines_context = []
        for idx, line in enumerate(lines_data, 1):
            lines_context.append(
                f"Línea {idx}: {line.get('description', 'Sin descripción')} "
                f"(Cantidad: {line.get('quantity', 0)}, "
                f"Precio unitario: {line.get('unit_price', 0)}€)"
            )

        lines_text = "\n".join(lines_context) if lines_context else "Sin líneas detalladas"

        prompt = f"""Eres un experto contable español. Analiza esta factura de COMPRA y genera el asiento contable según el Plan General Contable (PGC) español.

DATOS DE LA FACTURA:
- Número: {invoice_data.get('invoice_number', 'N/A')}
- Proveedor: {supplier_name}
- Base imponible: {invoice_data.get('base_amount', 0)}€
- IVA: {invoice_data.get('tax_amount', 0)}€
- Total: {invoice_data.get('total_amount', 0)}€

LÍNEAS DE LA FACTURA:
{lines_text}

INSTRUCCIONES CRÍTICAS:
1. Analiza CUIDADOSAMENTE el tipo de gasto según las líneas de la factura
2. Determina la cuenta de gasto MÁS ESPECÍFICA del PGC español (grupos 6XX)
3. **IMPORTANTE**: La cuenta 600 (Compras de mercaderías) SOLO se usa para productos físicos destinados a reventa
4. Para servicios digitales, software, suscripciones, créditos online → Usa 629 (Otros servicios)
5. Para servicios profesionales (asesoría, desarrollo, consultoría) → Usa 623
6. Para suministros físicos (electricidad, agua, material de oficina) → Usa 628
7. Genera el asiento contable completo

GUÍA DE CUENTAS DEL PGC ESPAÑOL:

**COMPRAS (600-607)** - SOLO para productos físicos:
- 600: Compras de mercaderías (productos para revender)
- 601: Compras de materias primas (fabricación)
- 602: Compras de otros aprovisionamientos (materiales auxiliares)

**SERVICIOS (621-629)** - Para servicios y gastos operativos:
- 621: Arrendamientos y cánones (alquileres)
- 622: Reparaciones y conservación (mantenimiento físico)
- 623: Servicios de profesionales independientes (consultores, abogados, desarrolladores)
- 624: Transportes (envíos, logística)
- 625: Primas de seguros
- 626: Servicios bancarios
- 627: Publicidad, propaganda y relaciones públicas
- 628: Suministros (electricidad, agua, teléfono, material oficina)
- 629: Otros servicios (servicios digitales, software, suscripciones, créditos online, licencias, hosting)

**OTROS GASTOS:**
- 631: Otros tributos
- 640: Sueldos y salarios
- 642: Seguridad Social a cargo de la empresa

**EJEMPLOS PRÁCTICOS:**
- "Créditos de Windsurf" → 629 (servicio digital)
- "Suscripción GitHub Pro" → 629 (servicio digital)
- "Hosting AWS" → 629 (servicio digital)
- "Licencia Office 365" → 629 (servicio digital)
- "Asesoría legal" → 623 (servicio profesional)
- "Desarrollo web" → 623 (servicio profesional)
- "Compra de ordenadores" → 600 (si es para revender) o 217 (si es inmovilizado)
- "Electricidad oficina" → 628 (suministro)
- "Material de oficina" → 628 (suministro)

CUENTAS FIJAS:
- 472: H.P. IVA soportado (siempre para el IVA en facturas de compra)
- 400: Proveedores (cuenta principal para proveedores de mercancías)
- 410: Acreedores por prestaciones de servicios (preferible para servicios)

RESPONDE SOLO CON UN JSON VÁLIDO EN ESTE FORMATO EXACTO:
{{
    "account_expense": "código de la cuenta de gasto (ej: 623 o 629)",
    "expense_description": "Descripción clara y específica del gasto",
    "account_vat_input": "472",
    "vat_description": "IVA soportado",
    "account_supplier": "400 o 410 según corresponda (410 preferible para servicios)",
    "supplier_description": "Descripción para la línea del proveedor",
    "reasoning": "Breve explicación de por qué elegiste esas cuentas, explicando por qué NO es 600 si aplica"
}}

IMPORTANTE: 
- Responde SOLO con JSON, sin texto adicional
- No uses markdown ni backticks
- Asegúrate de que el JSON sea válido
- Si tienes duda entre 600 y 629, USA 629 (es más seguro)"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un experto contable español especializado en el Plan General Contable. Respondes SOLO con JSON válido, sin markdown ni texto adicional. Eres especialmente cuidadoso distinguiendo entre compras de mercaderías (600) y servicios (629)."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=800
        )

        response_text = response.choices[0].message.content.strip()

        # Limpiar posibles backticks de markdown
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        # Parsear el JSON
        accounting_entry = json.loads(response_text)

        logger.info(f"Asiento contable generado por IA para factura {invoice_data.get('invoice_number')}")
        logger.info(f"Razonamiento: {accounting_entry.get('reasoning', 'N/A')}")

        return accounting_entry

    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear JSON de OpenAI: {e}")
        logger.error(f"Respuesta recibida: {response_text}")
        # Retornar valores por defecto si falla el parsing
        return {
            "account_expense": "629",  # Otros servicios (genérico y seguro)
            "expense_description": f"Compras - {supplier_name}",
            "account_vat_input": "472",
            "vat_description": "IVA soportado",
            "account_supplier": "410",  # Acreedores por prestaciones de servicios
            "supplier_description": f"{supplier_name}",
            "reasoning": "Valores por defecto debido a error en análisis de IA"
        }
    except Exception as e:
        logger.exception(f"Error al generar asiento contable con IA: {e}")
        return {
            "account_expense": "629",
            "expense_description": f"Compras - {supplier_name}",
            "account_vat_input": "472",
            "vat_description": "IVA soportado",
            "account_supplier": "410",
            "supplier_description": f"{supplier_name}",
            "reasoning": "Valores por defecto debido a error"
        }


def generate_accounting_entry_for_sales(invoice_data, lines_data, client_name):
    """
    Genera la estructura del asiento contable para una factura de VENTA
    utilizando IA para determinar las cuentas más apropiadas según el PGC español.

    Args:
        invoice_data: Dict con datos de la factura (invoice_number, base_amount, tax_amount, total_amount)
        lines_data: List de dicts con las líneas de la factura (description, quantity, unit_price)
        client_name: Nombre del cliente

    Returns:
        Dict con la estructura del asiento contable
    """
    try:
        # Preparar el contexto de las líneas
        lines_context = []
        for idx, line in enumerate(lines_data, 1):
            lines_context.append(
                f"Línea {idx}: {line.get('description', 'Sin descripción')} "
                f"(Cantidad: {line.get('quantity', 0)}, "
                f"Precio unitario: {line.get('unit_price', 0)}€)"
            )

        lines_text = "\n".join(lines_context) if lines_context else "Sin líneas detalladas"

        prompt = f"""Eres un experto contable español. Analiza esta factura de VENTA y genera el asiento contable según el Plan General Contable (PGC) español.

DATOS DE LA FACTURA:
- Número: {invoice_data.get('invoice_number', 'N/A')}
- Cliente: {client_name}
- Base imponible: {invoice_data.get('base_amount', 0)}€
- IVA: {invoice_data.get('tax_amount', 0)}€
- Total: {invoice_data.get('total_amount', 0)}€

LÍNEAS DE LA FACTURA:
{lines_text}

INSTRUCCIONES CRÍTICAS:
1. Esta es una FACTURA DE VENTA (ingresos de la empresa)
2. Analiza CUIDADOSAMENTE el tipo de ingreso según las líneas de la factura
3. Determina la cuenta de ingreso MÁS ESPECÍFICA del PGC español (grupos 7XX)

ASIENTO TÍPICO DE FACTURA DE VENTA:
DEBE:
  (430) Clientes - Total factura
HABER:
  (7XX) Ingresos - Base imponible
  (477) IVA repercutido - IVA

CUENTAS DE INGRESOS DEL PGC ESPAÑOL (grupos 7XX):

**VENTAS (700-709)** - Para venta de productos:
- 700: Ventas de mercaderías (productos comprados para revender)
- 701: Ventas de productos terminados (producción propia)
- 702: Ventas de productos semiterminados
- 703: Ventas de subproductos y residuos
- 704: Ventas de envases y embalajes
- 705: Prestaciones de servicios

**OTROS INGRESOS (740-759):**
- 740: Subvenciones, donaciones y legados
- 752: Ingresos por arrendamientos
- 753: Ingresos de propiedad industrial
- 754: Ingresos por comisiones
- 755: Ingresos por servicios al personal

**EJEMPLOS PRÁCTICOS:**
- "Venta de productos" → 700 (mercaderías) o 701 (producción propia)
- "Servicio de consultoría" → 705 (prestaciones de servicios)
- "Desarrollo de software" → 705 (prestaciones de servicios)
- "Arrendamiento de local" → 752 (ingresos por arrendamientos)
- "Comisión por intermediación" → 754 (ingresos por comisiones)
- "Curso de formación" → 705 (prestaciones de servicios)

CUENTAS FIJAS:
- 430: Clientes (cuenta principal - siempre en el DEBE)
- 477: H.P. IVA repercutido (siempre para el IVA en facturas de venta - en el HABER)

RESPONDE SOLO CON UN JSON VÁLIDO EN ESTE FORMATO EXACTO:
{{
    "account_customer": "430",
    "customer_description": "Descripción para la línea del cliente",
    "account_income": "código de la cuenta de ingreso (ej: 700, 705)",
    "income_description": "Descripción clara del ingreso",
    "account_vat_output": "477",
    "vat_description": "IVA repercutido",
    "reasoning": "Breve explicación de por qué elegiste esas cuentas"
}}

IMPORTANTE: 
- Responde SOLO con JSON, sin texto adicional
- No uses markdown ni backticks
- Asegúrate de que el JSON sea válido
- Diferencia claramente entre venta de productos (700) y servicios (705)"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un experto contable español especializado en el Plan General Contable. Respondes SOLO con JSON válido, sin markdown ni texto adicional."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=800
        )

        response_text = response.choices[0].message.content.strip()

        # Limpiar posibles backticks de markdown
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        # Parsear el JSON
        accounting_entry = json.loads(response_text)

        logger.info(f"Asiento contable de VENTA generado por IA para factura {invoice_data.get('invoice_number')}")
        logger.info(f"Razonamiento: {accounting_entry.get('reasoning', 'N/A')}")

        return accounting_entry

    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear JSON de OpenAI: {e}")
        logger.error(f"Respuesta recibida: {response_text}")
        # Retornar valores por defecto si falla el parsing
        return {
            "account_customer": "430",
            "customer_description": f"{client_name}",
            "account_income": "705",  # Prestaciones de servicios (genérico y seguro)
            "income_description": f"Ventas - {client_name}",
            "account_vat_output": "477",
            "vat_description": "IVA repercutido",
            "reasoning": "Valores por defecto debido a error en análisis de IA"
        }
    except Exception as e:
        logger.exception(f"Error al generar asiento contable de venta con IA: {e}")
        return {
            "account_customer": "430",
            "customer_description": f"{client_name}",
            "account_income": "705",
            "income_description": f"Ventas - {client_name}",
            "account_vat_output": "477",
            "vat_description": "IVA repercutido",
            "reasoning": "Valores por defecto debido a error"
        }


def generate_accounting_entry_for_payroll(payroll_data, employee_name):
    """
    Genera la estructura del asiento contable para una nómina
    utilizando IA para validar y generar descripciones apropiadas según el PGC español.

    Args:
        payroll_data: Dict con datos de la nómina
        employee_name: Nombre del empleado

    Returns:
        Dict con la estructura del asiento contable
    """
    try:
        prompt = f"""Eres un experto contable español. Analiza esta NÓMINA y genera descripciones apropiadas para el asiento contable según el Plan General Contable (PGC) español.

DATOS DE LA NÓMINA:
- Empleado: {employee_name}
- Período: {payroll_data.get('period_start', 'N/A')} - {payroll_data.get('period_end', 'N/A')}
- Total devengado: {payroll_data.get('total_accrued', 0)}€
- SS empleado: {payroll_data.get('social_security_employee', 0)}€
- IRPF: {payroll_data.get('irpf', 0)}€
- Otras deducciones: {payroll_data.get('other_deductions', 0)}€
- Líquido a pagar: {payroll_data.get('net_salary', 0)}€
- SS empresa: {payroll_data.get('social_security_company', 0)}€

ESTRUCTURA DEL ASIENTO DE NÓMINA EN ESPAÑA:

DEBE:
  (640) Sueldos y salarios - Total devengado
  (642) Seguridad Social a cargo de la empresa - SS empresa

HABER:
  (476) Organismos de la Seguridad Social, acreedores - Total SS (empleado + empresa)
  (4751) Hacienda Pública, acreedor por retenciones practicadas - IRPF
  (572) Bancos - Líquido a pagar al empleado

CUENTAS DEL PGC ESPAÑOL:
- 640: Sueldos y salarios (gastos de personal)
- 642: Seguridad Social a cargo de la empresa (gastos de personal)
- 476: Organismos de la Seguridad Social, acreedores
- 4751: Hacienda Pública, acreedor por retenciones practicadas (IRPF)
- 572: Bancos e instituciones de crédito c/c vista, euros

RESPONDE SOLO CON UN JSON VÁLIDO EN ESTE FORMATO EXACTO:
{{
    "account_salary_expense": "640",
    "salary_description": "Descripción para sueldos y salarios",
    "account_social_security_expense": "642",
    "ss_expense_description": "Descripción para SS empresa",
    "account_social_security_payable": "476",
    "ss_payable_description": "Descripción para SS acreedores",
    "account_irpf_payable": "4751",
    "irpf_description": "Descripción para IRPF",
    "account_bank": "572",
    "bank_description": "Descripción para pago bancario",
    "reasoning": "Breve explicación del asiento"
}}

IMPORTANTE: 
- Responde SOLO con JSON, sin texto adicional
- No uses markdown ni backticks
- Las descripciones deben incluir el nombre del empleado y el período
- Asegúrate de que el JSON sea válido"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un experto contable español especializado en el Plan General Contable. Respondes SOLO con JSON válido, sin markdown ni texto adicional."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=800
        )

        response_text = response.choices[0].message.content.strip()

        # Limpiar posibles backticks de markdown
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        # Parsear el JSON
        accounting_entry = json.loads(response_text)

        logger.info(f"Asiento contable de NÓMINA generado por IA para empleado {employee_name}")
        logger.info(f"Razonamiento: {accounting_entry.get('reasoning', 'N/A')}")

        return accounting_entry

    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear JSON de OpenAI: {e}")
        logger.error(f"Respuesta recibida: {response_text}")
        # Retornar valores por defecto si falla el parsing
        return {
            "account_salary_expense": "640",
            "salary_description": f"Sueldos y salarios - {employee_name}",
            "account_social_security_expense": "642",
            "ss_expense_description": f"Seguridad Social empresa - {employee_name}",
            "account_social_security_payable": "476",
            "ss_payable_description": f"Organismos SS acreedores - {employee_name}",
            "account_irpf_payable": "4751",
            "irpf_description": f"HP acreedor IRPF - {employee_name}",
            "account_bank": "572",
            "bank_description": f"Pago nómina {employee_name}",
            "reasoning": "Valores por defecto debido a error en análisis de IA"
        }
    except Exception as e:
        logger.exception(f"Error al generar asiento contable de nómina con IA: {e}")
        return {
            "account_salary_expense": "640",
            "salary_description": f"Sueldos y salarios - {employee_name}",
            "account_social_security_expense": "642",
            "ss_expense_description": f"Seguridad Social empresa - {employee_name}",
            "account_social_security_payable": "476",
            "ss_payable_description": f"Organismos SS acreedores - {employee_name}",
            "account_irpf_payable": "4751",
            "irpf_description": f"HP acreedor IRPF - {employee_name}",
            "account_bank": "572",
            "bank_description": f"Pago nómina {employee_name}",
            "reasoning": "Valores por defecto debido a error"
        }