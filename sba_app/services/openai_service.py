import io
import json
import base64
import fitz  # PyMuPDF
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
    """
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

            # Si el texto es corto o sin montos → pasar a imagen
            if len(text.strip()) < 50 or ("€" not in text and "$" not in text):
                print("⚠️ PDF parece escaneado → usando OCR visual.")
                images = convert_from_bytes(pdf_bytes, fmt="png")
                first_page = images[0]
                buf = io.BytesIO()
                first_page.save(buf, format="PNG")
                buf.seek(0)
                image_bytes = buf.read()

                # ✅ CORREGIDO: Codificar imagen en base64
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

        # --- 🖼️ CASO 2: Imagen (JPG / PNG) ---
        elif any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
            image_bytes = file.read()

            # ✅ CORREGIDO: Codificar imagen en base64
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

        else:
            raise ValueError("Formato de archivo no soportado")

        # --- Parsear JSON seguro ---
        content = response.choices[0].message.content
        print(f"🤖 Respuesta de OpenAI: {content}")
        result = json.loads(content)

    except Exception as e:
        print(f"⚠️ Error en extract_invoice_data: {e}")
        import traceback
        print(traceback.format_exc())
        result = {}

    return result

#############################################Here stars the code for purchase invoices#####################################################
# 🧠 Prompt para FACTURAS RECIBIDAS (Purchase Invoices)
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

                # ✅ Codificar imagen en base64
                base64_image = base64.b64encode(image_bytes).decode('utf-8')

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
                                        "url": f"data:image/png;base64,{base64_image}"
                                    }
                                },
                            ],
                        },
                    ],
                    response_format={"type": "json_object"},
                )
            else:
                # Si hay texto legible, usarlo directamente
                print(f"✅ Texto extraído del PDF de nómina ({len(text)} caracteres)")
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": BASE_PROMPT_PAYROLL},
                        {"role": "user", "content": f"Extraé los datos de esta nómina:\n\n{text}"},
                    ],
                    response_format={"type": "json_object"},
                )

        # --- 🖼️ CASO 2: Imagen (JPG / PNG) ---
        elif any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
            image_bytes = file.read()

            # ✅ Codificar imagen en base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')

            # Detectar el mime type correcto
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

        # --- Parsear JSON seguro ---
        content = response.choices[0].message.content
        print(f"🤖 Respuesta de OpenAI (Nómina): {content}")
        result = json.loads(content)

    except Exception as e:
        print(f"⚠️ Error en extract_payroll_data: {e}")
        import traceback
        print(traceback.format_exc())
        result = {}

    return result