import io
import json
import base64
import fitz  # PyMuPDF
from environ import logger
from pdf2image import convert_from_bytes  # pip install pdf2image
from django.conf import settings
from openai import OpenAI


client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Prompt base que instruye al modelo
BASE_PROMPT = (
    "Sos un extractor de datos de facturas EMITIDAS (de venta). "
    "Esta es una factura donde el EMISOR vende al CLIENTE. "
    "El CLIENTE es quien RECIBE y PAGA la factura.\n\n"
    "Analizá la imagen de la factura y devolvé un JSON EXACTO con esta estructura:\n\n"
    "{\n"
    "  \"invoice\": {\n"
    "    \"invoice_number\": \"string\",\n"
    "    \"issue_date\": \"YYYY-MM-DD\",\n"
    "    \"due_date\": \"YYYY-MM-DD\" o null,\n"
    "    \"payment_method\": \"string\" o null,\n"
    "    \"base_amount\": \"1750.00\",\n"
    "    \"discount_amount\": \"0.00\" o null,\n"
    "    \"discount_percentage\": \"5.00\" o null,\n"
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
    "INSTRUCCIONES PARA FACTURAS ESPAÑOLAS:\n"
    "- Buscar 'Nº Factura', 'Factura Nº', 'Número' para invoice_number\n"
    "- Buscar 'Fecha Factura', 'Fecha', 'Fecha de emisión' para issue_date\n"
    "- Buscar 'Fecha Vto', 'Vencimiento', 'Fecha de vencimiento' para due_date\n"
    "- Buscar 'Base Imponible', 'B. Imponible', 'Importe' para base_amount\n"
    "- Buscar 'IVA', 'Iva', '%Iva' para tax_amount (el monto, no el porcentaje)\n"
    "- Buscar 'Total Factura', 'TOTAL', 'Importes' para total_amount\n"
    "- Buscar 'Descuento', 'Dto', 'Discount', 'Rappel' para discount_amount (el monto del descuento, no el porcentaje). SIEMPRE como valor POSITIVO, nunca negativo.\n"
    "- El CLIENT es quien aparece en 'DIRECCIÓN POSTAL', 'Cliente', 'Destinatario'\n"
    "- Buscar 'CIF', 'NIF', 'DNI' del cliente para document_number\n\n"
    "IMPORTANTE:\n"
    "- Los montos deben ser strings con formato numérico: \"1750.00\", \"0.00\", etc.\n"
    "- NO uses comas como separador de miles\n"
    "- USA punto como separador decimal\n"
    "- Convertí fechas DD/MM/YYYY a formato YYYY-MM-DD\n"
    "- Si no encontrás un monto, usa \"0.00\"\n"
    "- Si no encontrás un dato, ponelo como null\n"
    "- Para las líneas (lines), extraé TODOS los ítems/productos/servicios de la factura\n"
    "- Si no hay IVA especificado en la línea, usa \"0.00\" en vat_rate\n"
    "- Cantidad (quantity) por defecto es \"1.00\" si no está especificada\n"
    "- NO inventes valores, solo extraé lo que VES en la imagen\n"
)


def extract_invoice_data(file):
    """
    Extrae datos de facturas de ventas desde un archivo PDF o imagen.
    Si el PDF tiene múltiples páginas, procesa cada página como una factura independiente.
    
    Retorna:
    - Si es 1 página/imagen: dict con los datos (comportamiento original)
    - Si son múltiples páginas: tupla (lista de dicts, pdf_bytes) para poder extraer páginas después
    """
    content_type = file.content_type.lower()

    try:
        # --- CASO 1: PDF ---
        if "pdf" in content_type:
            pdf_bytes = file.read()
            
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                num_pages = len(doc)
                print(f"📄 PDF con {num_pages} página(s) detectada(s)")
                
                # Si es una sola página, comportamiento original (retorna dict)
                if num_pages == 1:
                    print("📄 Procesando PDF de 1 página...")
                    mat = fitz.Matrix(2, 2)
                    pix = doc[0].get_pixmap(matrix=mat)
                    image_bytes = pix.tobytes("png")
                    print(f"📐 Tamaño: {pix.width}x{pix.height}")
                    return _extract_single_page_sales_invoice(image_bytes, "image/png")
                
                # Múltiples páginas: procesar cada una EN PARALELO
                # Retorna tupla (resultados, pdf_bytes) para que views.py use los mismos bytes
                print(f"📄 Procesando {num_pages} páginas como facturas separadas (en paralelo)...")
                
                # Preparar imágenes de todas las páginas primero
                page_images = []
                for page_idx in range(num_pages):
                    mat = fitz.Matrix(2, 2)
                    pix = doc[page_idx].get_pixmap(matrix=mat)
                    image_bytes = pix.tobytes("png")
                    page_images.append((page_idx, image_bytes))
                
                # Función para procesar una página
                def process_single_page(args):
                    page_idx, image_bytes = args
                    page_number = page_idx + 1
                    print(f"\n📄 Extrayendo página {page_number}/{num_pages} (índice {page_idx})...")
                    try:
                        result = _extract_single_page_sales_invoice(image_bytes, "image/png")
                        result["page_number"] = page_number
                        return (page_idx, result)
                    except Exception as e:
                        print(f"⚠️ Error en página {page_number}: {e}")
                        return (page_idx, {"error": str(e), "page_number": page_number, "tokens": None})
                
                # Procesar en paralelo con ThreadPoolExecutor
                from concurrent.futures import ThreadPoolExecutor, as_completed
                results_dict = {}
                
                with ThreadPoolExecutor(max_workers=min(4, num_pages)) as executor:
                    futures = [executor.submit(process_single_page, args) for args in page_images]
                    for future in as_completed(futures):
                        page_idx, result = future.result()
                        results_dict[page_idx] = result
                
                # Ordenar resultados por índice de página
                results = [results_dict[i] for i in range(num_pages)]
                
                print(f"\n✅ Procesadas {len(results)} páginas")
                # Retornar tupla con resultados Y los bytes del PDF para usar después
                return (results, pdf_bytes)

        # --- CASO 2: Imagen (JPG / PNG) - siempre una sola factura ---
        elif any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
            image_bytes = file.read()
            mime_type = "image/jpeg" if "jpeg" in content_type or "jpg" in content_type else "image/png"
            print("🖼️ Procesando imagen...")
            return _extract_single_page_sales_invoice(image_bytes, mime_type)
        
        else:
            raise ValueError("Formato de archivo no soportado")

    except Exception as e:
        print(f"⚠️ Error en extract_invoice_data: {e}")
        import traceback
        print(traceback.format_exc())
        return {"tokens": None, "error": str(e)}


def _extract_single_page_sales_invoice(image_bytes, mime_type="image/png", max_retries=2):
    """
    Extrae datos de una sola página/imagen de factura de ventas.
    Función auxiliar interna con retry automático.
    """
    import time
    
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    for attempt in range(max_retries):
        start_time = time.time()
        timeout_seconds = 45 if attempt == 0 else 60  # Primer intento más corto
        
        print(f"🤖 Llamando a OpenAI (intento {attempt + 1}/{max_retries}, timeout={timeout_seconds}s, {len(image_bytes)} bytes)...")
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": BASE_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extraé los datos de esta factura EMITIDA y devolvé el resultado en formato JSON. El client es quien RECIBE la factura."},
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
                timeout=timeout_seconds,
            )
            
            elapsed_time = time.time() - start_time
            print(f"✅ OpenAI respondió en {elapsed_time:.1f}s")
            
            usage = getattr(response, "usage", None)
            tokens = getattr(usage, "total_tokens", None) if usage else None
            
            content = response.choices[0].message.content
            
            if content is None:
                raise ValueError("OpenAI no pudo procesar la imagen o no encontró datos válidos")
            
            result = json.loads(content)
            result["tokens"] = tokens
            
            return result
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"❌ Error en OpenAI después de {elapsed_time:.1f}s: {e}")
            
            if attempt < max_retries - 1:
                print(f"🔄 Reintentando...")
                continue
            else:
                raise


#############################################Here stars the code for purchase invoices#####################################################
# Prompt para FACTURAS RECIBIDAS (Purchase Invoices)
PURCHASE_INVOICE_PROMPT = (
    "Sos un extractor experto de datos de FACTURAS RECIBIDAS españolas (incluye FACTURAS y ABONOS). "
    "Analizá el documento completo y devolvé un JSON EXACTO con la siguiente estructura:\n\n"

    "{\n"
    "  \"invoice\": {\n"
    "    \"invoice_number\": \"string\",\n"
    "    \"issue_date\": \"YYYY-MM-DD\",\n"
    "    \"due_date\": \"YYYY-MM-DD\" o null,\n"
    "    \"payment_method\": \"string\" o null,\n"
    "    \"base_amount\": \"10.00\",\n"
    "    \"discount_amount\": \"0.00\" o null,\n"
    "    \"discount_percentage\": \"5.00\" o null,\n"
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

    "🔴 IDENTIFICACIÓN DEL PROVEEDOR (REGLA CRÍTICA):\n"
    "Esta es una FACTURA RECIBIDA. El PROVEEDOR es la empresa que EMITE y COBRA la factura.\n\n"

    "PASO 1 - DETECTAR EMPRESAS:\n"
    "Identificá TODAS las empresas que aparecen en el documento.\n\n"

    "PASO 2 - CLASIFICAR ROL:\n"
    "Para cada empresa, determiná si actúa como:\n"
    "- PROVEEDOR (vende / cobra)\n"
    "- CLIENTE (recibe la factura)\n"
    "- ENVÍO / DESTINATARIO\n\n"

    "PASO 3 - CRITERIOS POSITIVOS DE PROVEEDOR (OBLIGATORIOS):\n"
    "Una empresa ES PROVEEDOR si cumple AL MENOS 2 de los siguientes criterios:\n"
    "1. Aparece en el encabezado del documento\n"
    "2. Está acompañada de un logo o identidad visual\n"
    "3. Aparece ANTES de cualquier sección de cliente\n"
    "4. Tiene datos comerciales generales (web, email, teléfono fijo)\n"
    "5. No está precedida por etiquetas como 'Cliente', 'Datos fiscales', 'Datos de envío'\n\n"

    "PASO 4 - REGLA ABSOLUTA DE EXCLUSIÓN:\n"
    "CUALQUIER empresa que aparezca bajo los encabezados:\n"
    "- 'DATOS FISCALES'\n"
    "- 'DATOS DE ENVÍO'\n"
    "- 'CLIENTE'\n"
    "- 'DESTINATARIO'\n"
    "NUNCA puede ser el proveedor.\n\n"

    "PASO 5 - CASOS DE DUDA:\n"
    "Si hay más de una empresa posible:\n"
    "Elegí como proveedor la empresa que esté más arriba en el documento y fuera de secciones de cliente.\n\n"

    "NOTA SOBRE ABONOS:\n"
    "Un 'ABONO' mantiene el MISMO proveedor que una factura normal.\n"
    "La palabra 'ABONO' no cambia quién es el emisor.\n\n"

    "IMPORTANTE:\n"
    "- Los montos deben ser strings con formato \"10.00\"\n"
    "- Usá punto como separador decimal\n"
    "- Si no encontrás un monto, usá \"0.00\"\n"
    "- Si no encontrás un dato, usá null\n"
    "- Extraé TODAS las líneas de la factura\n"
    "- Si no hay IVA en una línea, usá \"0.00\" en vat_rate\n"
    "- Descuentos: buscar 'Descuento', 'Dto', 'Rappel' (monto positivo)\n"
)


def _extract_single_page_purchase_invoice(image_bytes, mime_type="image/png", max_retries=2):
    """
    Extrae datos de una sola página/imagen de factura de compra.
    Función auxiliar interna con retry automático.
    """
    import time
    
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    for attempt in range(max_retries):
        start_time = time.time()
        timeout_seconds = 45 if attempt == 0 else 60  # Primer intento más corto
        
        print(f"🤖 Llamando a OpenAI (intento {attempt + 1}/{max_retries}, timeout={timeout_seconds}s, {len(image_bytes)} bytes)...")
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": PURCHASE_INVOICE_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extraé los datos de esta factura RECIBIDA y devolvé el resultado en formato JSON. El supplier es quien EMITE la factura."},
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
                timeout=timeout_seconds,
            )
            
            elapsed_time = time.time() - start_time
            print(f"✅ OpenAI respondió en {elapsed_time:.1f}s")
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"❌ Error en OpenAI después de {elapsed_time:.1f}s: {e}")
            
            if attempt < max_retries - 1:
                print(f"🔄 Reintentando...")
                continue
            else:
                raise
    
    usage = getattr(response, "usage", None)
    tokens = getattr(usage, "total_tokens", None) if usage else None
    
    content = response.choices[0].message.content
    
    # Manejar caso donde OpenAI devuelve None (no puede procesar la imagen)
    if content is None:
        raise ValueError("OpenAI no pudo procesar la imagen o no encontró datos válidos")
    
    result = json.loads(content)
    
    return result


def extract_single_invoice_from_pdf(file):
    """
    MODO OPTIMIZADO: Extrae datos de 1 factura de ventas desde un PDF multipágina.
    Envía TODAS las páginas en UNA SOLA llamada a OpenAI.
    """
    import time
    start_time = time.time()
    content_type = file.content_type.lower()
    
    try:
        if "pdf" in content_type:
            pdf_bytes = file.read()
            
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                num_pages = len(doc)
                print(f"📄 MODO RÁPIDO: PDF con {num_pages} página(s) - procesando como 1 factura")
                
                image_contents = []
                for page_idx in range(num_pages):
                    mat = fitz.Matrix(2, 2)
                    pix = doc[page_idx].get_pixmap(matrix=mat)
                    image_bytes = pix.tobytes("png")
                    base64_image = base64.b64encode(image_bytes).decode('utf-8')
                    image_contents.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                    })
                    print(f"   📄 Página {page_idx + 1}: {pix.width}x{pix.height}")
                
                user_content = [{"type": "text", "text": f"Esta factura EMITIDA tiene {num_pages} página(s). Analizá TODAS las páginas como UN SOLO documento y extraé los datos completos. El client es quien RECIBE la factura."}]
                user_content.extend(image_contents)
                
                print(f"🤖 Enviando {num_pages} páginas a OpenAI en UNA sola llamada...")
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": BASE_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    response_format={"type": "json_object"},
                    timeout=90,
                )
                
                elapsed_time = time.time() - start_time
                print(f"✅ OpenAI respondió en {elapsed_time:.1f}s")
                
                usage = getattr(response, "usage", None)
                tokens = getattr(usage, "total_tokens", None) if usage else None
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("OpenAI no pudo procesar las imágenes")
                
                result = json.loads(content)
                result["tokens"] = tokens
                result["pages_processed"] = num_pages
                return result
        
        elif any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
            image_bytes = file.read()
            mime_type = "image/jpeg" if "jpeg" in content_type or "jpg" in content_type else "image/png"
            return _extract_single_page_sales_invoice(image_bytes, mime_type)
        else:
            raise ValueError("Formato de archivo no soportado")
    except Exception as e:
        print(f"⚠️ Error en extract_single_invoice_from_pdf: {e}")
        import traceback
        print(traceback.format_exc())
        return {"tokens": None, "error": str(e)}


def extract_single_purchase_invoice_from_pdf(file):
    """
    MODO OPTIMIZADO: Extrae datos de 1 factura de compra desde un PDF multipágina.
    Envía TODAS las páginas en UNA SOLA llamada a OpenAI.
    """
    import time
    start_time = time.time()
    content_type = file.content_type.lower()
    
    try:
        if "pdf" in content_type:
            pdf_bytes = file.read()
            
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                num_pages = len(doc)
                print(f"📄 MODO RÁPIDO: PDF con {num_pages} página(s) - procesando como 1 factura")
                
                image_contents = []
                for page_idx in range(num_pages):
                    mat = fitz.Matrix(2, 2)
                    pix = doc[page_idx].get_pixmap(matrix=mat)
                    image_bytes = pix.tobytes("png")
                    base64_image = base64.b64encode(image_bytes).decode('utf-8')
                    image_contents.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                    })
                    print(f"   📄 Página {page_idx + 1}: {pix.width}x{pix.height}")
                
                user_content = [{"type": "text", "text": f"Esta factura RECIBIDA tiene {num_pages} página(s). Analizá TODAS las páginas como UN SOLO documento y extraé los datos completos. El supplier es quien EMITE la factura."}]
                user_content.extend(image_contents)
                
                print(f"🤖 Enviando {num_pages} páginas a OpenAI en UNA sola llamada...")
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": PURCHASE_INVOICE_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    response_format={"type": "json_object"},
                    timeout=90,
                )
                
                elapsed_time = time.time() - start_time
                print(f"✅ OpenAI respondió en {elapsed_time:.1f}s")
                
                usage = getattr(response, "usage", None)
                tokens = getattr(usage, "total_tokens", None) if usage else None
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("OpenAI no pudo procesar las imágenes")
                
                result = json.loads(content)
                result["tokens"] = tokens
                result["pages_processed"] = num_pages
                return result
        
        elif any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
            image_bytes = file.read()
            mime_type = "image/jpeg" if "jpeg" in content_type or "jpg" in content_type else "image/png"
            return _extract_single_page_purchase_invoice(image_bytes, mime_type)
        else:
            raise ValueError("Formato de archivo no soportado")
    except Exception as e:
        print(f"⚠️ Error en extract_single_purchase_invoice_from_pdf: {e}")
        import traceback
        print(traceback.format_exc())
        return {"tokens": None, "error": str(e)}


def _are_consecutive_numbers(num1, num2):
    """
    Detecta si dos números de factura son correlativos.
    Ejemplo: "001", "002" o "A-001", "A-002"
    """
    if not num1 or not num2:
        return False
    
    # Extraer parte numérica
    import re
    nums1 = re.findall(r'\d+', str(num1))
    nums2 = re.findall(r'\d+', str(num2))
    
    if len(nums1) == 1 and len(nums2) == 1:
        try:
            n1 = int(nums1[0])
            n2 = int(nums2[0])
            return abs(n1 - n2) == 1
        except ValueError:
            return False
    
    return False


def _are_same_invoice(inv1, sup1, inv2, sup2):
    """
    Determina si dos páginas pertenecen a la misma factura
    usando múltiples criterios.
    """
    # Criterio 1: Mismo número de factura (el más fuerte)
    num1 = normalize_document_number(inv1.get("invoice_number"))
    num2 = normalize_document_number(inv2.get("invoice_number"))
    if num1 and num2 and num1 == num2:
        return True
    
    # Criterio 2: Mismo proveedor + misma fecha
    sup1_name = normalize_company_name(sup1.get("name"))
    sup2_name = normalize_company_name(sup2.get("name"))
    date1 = inv1.get("issue_date")
    date2 = inv2.get("issue_date")
    
    if sup1_name and sup2_name and sup1_name == sup2_name:
        if date1 and date2 and date1 == date2:
            return True
    
    # Criterio 3: Mismo proveedor + números de factura correlativos
    if sup1_name and sup2_name and sup1_name == sup2_name:
        if _are_consecutive_numbers(inv1.get("invoice_number"), inv2.get("invoice_number")):
            return True
    
    return False


def should_group_invoices(page_results):
    """
    Analiza si las páginas del PDF deben agruparse en una sola factura
    o crearse facturas separadas.
    
    Retorna: lista de grupos, cada grupo contiene índices de páginas que van juntas
    """
    if len(page_results) <= 1:
        return [[0]]  # Una sola página = un grupo
    
    groups = []
    used_indices = set()
    
    for i, current_page in enumerate(page_results):
        if i in used_indices:
            continue
            
        current_group = [i]
        current_data = current_page.get("invoice", {})
        current_supplier = current_page.get("supplier", {})
        
        # Comparar con las páginas restantes
        for j in range(i + 1, len(page_results)):
            if j in used_indices:
                continue
                
            other_page = page_results[j]
            other_data = other_page.get("invoice", {})
            other_supplier = other_page.get("supplier", {})
            
            # Criterios de coincidencia
            if _are_same_invoice(current_data, current_supplier, other_data, other_supplier):
                current_group.append(j)
                used_indices.add(j)
        
        groups.append(current_group)
        used_indices.add(i)
    
    return groups


def consolidate_invoice_group(page_results, group_indices):
    """
    Consolida los datos de múltiples páginas que pertenecen a la misma factura.
    
    IMPORTANTE: Cuando las páginas son de la misma factura (mismo número),
    NO se suman los totales. Se usa el total de la primera página que tenga
    un valor válido, ya que las otras páginas son detalles de la misma factura.
    """
    if len(group_indices) == 1:
        return page_results[group_indices[0]]
    
    # Usar la primera página como base
    base_result = page_results[group_indices[0]].copy()
    consolidated_invoice = base_result.get("invoice", {}).copy()
    consolidated_supplier = base_result.get("supplier", {}).copy()
    consolidated_lines = []
    
    # Acumular líneas de todas las páginas
    for idx in group_indices:
        page_result = page_results[idx]
        page_lines = page_result.get("lines", [])
        consolidated_lines.extend(page_lines)
    
    # NO sumar totales - usar el de la primera página con valor válido
    # Las otras páginas son detalles de la misma factura, no facturas separadas
    final_base = 0
    final_tax = 0
    final_total = 0
    final_discount = 0
    
    for idx in group_indices:
        page_invoice = page_results[idx].get("invoice", {})
        try:
            page_base = float(page_invoice.get("base_amount", 0) or 0)
            page_tax = float(page_invoice.get("tax_amount", 0) or 0)
            page_total = float(page_invoice.get("total_amount", 0) or 0)
            page_discount = float(page_invoice.get("discount_amount", 0) or 0)
            
            # Usar el primer valor válido encontrado (no sumar)
            if page_base > 0 and final_base == 0:
                final_base = page_base
            if page_tax > 0 and final_tax == 0:
                final_tax = page_tax
            if page_total > 0 and final_total == 0:
                final_total = page_total
            if page_discount > 0 and final_discount == 0:
                final_discount = page_discount
        except (ValueError, TypeError):
            pass
    
    # Actualizar datos consolidados con valores únicos (no sumados)
    consolidated_invoice["base_amount"] = f"{final_base:.2f}"
    consolidated_invoice["tax_amount"] = f"{final_tax:.2f}"
    consolidated_invoice["total_amount"] = f"{final_total:.2f}"
    if final_discount > 0:
        consolidated_invoice["discount_amount"] = f"{final_discount:.2f}"
    
    # Construir resultado consolidado
    consolidated_result = {
        "invoice": consolidated_invoice,
        "supplier": consolidated_supplier,
        "lines": consolidated_lines,
        "tokens": sum(page_results[idx].get("tokens", 0) or 0 for idx in group_indices),
        "page_group": group_indices,  # Para referencia
        "consolidated": True
    }
    
    return consolidated_result


def extract_purchase_invoice_data(file):
    """
    Extrae datos de facturas de compra desde un archivo PDF o imagen.
    Si el PDF tiene múltiples páginas, procesa cada página como una factura independiente.
    
    Retorna:
    - Si es 1 página/imagen: dict con los datos (comportamiento original)
    - Si son múltiples páginas: tupla (lista de dicts, pdf_bytes) para poder extraer páginas después
    """
    content_type = file.content_type.lower()

    try:
        # --- CASO 1: PDF ---
        if "pdf" in content_type:
            pdf_bytes = file.read()
            
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                num_pages = len(doc)
                print(f"📄 PDF con {num_pages} página(s) detectada(s)")
                
                # Si es una sola página, comportamiento original (retorna dict)
                if num_pages == 1:
                    print("📄 Procesando PDF de 1 página...")
                    mat = fitz.Matrix(2, 2)
                    pix = doc[0].get_pixmap(matrix=mat)
                    image_bytes = pix.tobytes("png")
                    print(f"📐 Tamaño: {pix.width}x{pix.height}")
                    return _extract_single_page_purchase_invoice(image_bytes, "image/png")
                
                # Múltiples páginas: procesar cada una EN PARALELO
                # Retorna tupla (resultados, pdf_bytes) para que views.py use los mismos bytes
                print(f"📄 Procesando {num_pages} páginas como facturas separadas (en paralelo)...")
                
                # Preparar imágenes de todas las páginas primero
                page_images = []
                for page_idx in range(num_pages):
                    mat = fitz.Matrix(2, 2)
                    pix = doc[page_idx].get_pixmap(matrix=mat)
                    image_bytes = pix.tobytes("png")
                    page_images.append((page_idx, image_bytes))
                
                # Función para procesar una página
                def process_single_page(args):
                    page_idx, image_bytes = args
                    page_number = page_idx + 1
                    print(f"\n📄 Extrayendo página {page_number}/{num_pages} (índice {page_idx})...")
                    try:
                        result = _extract_single_page_purchase_invoice(image_bytes, "image/png")
                        result["page_number"] = page_number
                        return (page_idx, result)
                    except Exception as e:
                        print(f"⚠️ Error en página {page_number}: {e}")
                        return (page_idx, {"error": str(e), "page_number": page_number, "tokens": None})
                
                # Procesar en paralelo con ThreadPoolExecutor
                from concurrent.futures import ThreadPoolExecutor, as_completed
                results_dict = {}
                
                with ThreadPoolExecutor(max_workers=min(4, num_pages)) as executor:
                    futures = [executor.submit(process_single_page, args) for args in page_images]
                    for future in as_completed(futures):
                        page_idx, result = future.result()
                        results_dict[page_idx] = result
                
                # Ordenar resultados por índice de página
                results = [results_dict[i] for i in range(num_pages)]
                
                print(f"\n✅ Procesadas {len(results)} páginas")
                # Retornar tupla con resultados Y los bytes del PDF para usar después
                return (results, pdf_bytes)

        # --- CASO 2: Imagen (JPG / PNG) - siempre una sola factura ---
        elif any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
            image_bytes = file.read()
            mime_type = "image/jpeg" if "jpeg" in content_type or "jpg" in content_type else "image/png"
            print("🖼️ Procesando imagen...")
            return _extract_single_page_purchase_invoice(image_bytes, mime_type)
        
        else:
            raise ValueError("Formato de archivo no soportado")

    except Exception as e:
        print(f"⚠️ Error en extract_purchase_invoice_data: {e}")
        import traceback
        print(traceback.format_exc())
        return {"tokens": None, "error": str(e)}


def process_invoice_header_only(pdf_file):
    """
    Extrae SOLO el proveedor (emisor) desde el encabezado del PDF.
    Usa el mismo cliente OpenAI que el resto del sistema.
    """

    import fitz
    import base64
    import json

    # 🔄 IMPORTANTE: Resetear el puntero del archivo al inicio
    # Esto es necesario porque el archivo ya fue leído anteriormente
    pdf_file.seek(0)

    # 1️⃣ Abrir PDF y renderizar SOLO la parte superior
    pdf_bytes = pdf_file.read()

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc[0]

        # Recortar solo el 30% superior de la página
        rect = page.rect
        header_rect = fitz.Rect(
            rect.x0,
            rect.y0,
            rect.x1,
            rect.y0 + rect.height * 0.30
        )

        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat, clip=header_rect)
        image_bytes = pix.tobytes("png")

    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
Extrae EXCLUSIVAMENTE los datos del PROVEEDOR (EMISOR) de esta factura.

REGLAS ESTRICTAS:
- El proveedor es quien EMITE y COBRA la factura
- NO es el cliente
- NO es el receptor
- NO es la empresa que paga
- Normalmente aparece en la parte SUPERIOR del documento
- Si hay duda, devuelve null

Devuelve SOLO este JSON:

{
  "supplier": {
    "name": null,
    "contact_person": null,
    "phone": null,
    "email": null,
    "address": null,
    "document_type": null,
    "document_number": null
  }
}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Identificá únicamente el proveedor (emisor) de esta factura."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        },
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=300,
    )

    content = response.choices[0].message.content
    return json.loads(content)

#############################################Here stars the code for payroll extraction#####################################################
# Prompt para extracción de nóminas
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
    "- SS TRABAJADOR: Buscar en sección 'II. DEDUCCIONES' > '1. Aportación del trabajador'. SUMAR:\n"
    "  * Contingencias comunes (ej: 48.22)\n"
    "  * Desempleo (ej: 15.48)\n"
    "  * Formación Profesional (ej: 1.00)\n"
    "  El TOTAL APORTACIONES suele aparecer al final de esta sección\n"
    "- SS EMPRESA (MUY IMPORTANTE - LEER TODA ESTA SECCIÓN):\n"
    "  UBICACIÓN: Tabla al final del documento titulada 'DETERMINACIÓN DE LAS BASES DE COTIZACIÓN A LA SEGURIDAD SOCIAL Y CONCEPTOS DE RECAUDACIÓN CONJUNTA Y DE LA BASE SUJETA A RETENCIÓN DEL I.R.P.F. Y APORTACIÓN DE LA EMPRESA'\n"
    "  COLUMNA: Buscar la columna 'APORTACIÓN EMPRESARIAL' (última columna a la derecha de la tabla)\n"
    "  ACCIÓN: SUMAR ABSOLUTAMENTE TODOS los importes en euros que aparezcan en esa columna. Normalmente hay entre 5 y 6 líneas con valores.\n"
    "  LÍNEAS TÍPICAS A SUMAR:\n"
    "    1. Base incapacidad temporal (Contingencias comunes) - suele ser el mayor valor (ej: 128.50, 358.07)\n"
    "    2. MEI o Mecanismo Equidad Intergeneracional (ej: 10.17, 0.67)\n"
    "    3. AT y EP (Accidentes trabajo) (ej: 19.13, 54.62)\n"
    "    4. Desempleo (ej: 29.23, 83.45) - NO OLVIDAR ESTA LÍNEA\n"
    "    5. Formación Profesional (ej: 3.19, 9.10)\n"
    "    6. Fondo Garantía Salarial/FOGASA (ej: 1.06, 3.03)\n"
    "  EJEMPLO REAL: 128.50 + 19.13 + 29.23 + 3.19 + 1.06 = 181.11\n"
    "  OTRO EJEMPLO: 358.07 + 10.17 + 54.62 + 83.45 + 9.10 + 3.03 = 518.44\n"
    "  ERRORES COMUNES A EVITAR:\n"
    "    - NO usar la columna 'TIPO' (son porcentajes, no euros)\n"
    "    - NO usar la columna 'BASE' (es la base de cotización)\n"
    "    - NO olvidar ninguna línea, especialmente DESEMPLEO que a veces se salta\n"
    "    - NO usar 'COSTE EMPRESA' que incluye el salario\n"
    "  Si no encuentras esta tabla o columna, usa \"0.00\"\n\n"

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
    "    \"social_security_employee\": \"0.00\" (buscar en DEDUCCIONES > TOTAL APORTACIONES del trabajador, que incluye: Contingencias Comunes + Desempleo + Formación Profesional. Si no hay total, SUMAR estas 3 líneas),\n"
    "    \"irpf\": \"0.00\" (CRÍTICO: buscar en DEDUCCIONES sección '2. Impuesto sobre la renta' el IMPORTE RETENIDO, NO la base. El formato es 'Base X,XX %  IMPORTE'. Solo extraer el IMPORTE final en euros. Si el porcentaje es 0% o no hay importe, usar \"0.00\". Ejemplo: '1.517,24  2,63%  39,90' → extraer solo 39.90),\n"
    "    \"other_deductions\": \"0.00\" (SOLO otras deducciones que NO sean SS ni IRPF, como anticipos, embargos, préstamos, etc. NO incluir aquí Desempleo ni Formación del trabajador),\n"
    "    \"total_deductions\": \"0.00\" (buscar TOTAL A DEDUCIR o T. A DEDUCIR),\n"
    "    \"net_salary\": \"0.00\" (buscar LÍQUIDO A PERCIBIR),\n"
    "    \"social_security_company\": \"0.00\" (MUY IMPORTANTE: buscar tabla inferior columna 'APORTACIÓN EMPRESARIAL' y SUMAR TODAS las líneas. Típicamente 5-6 valores. Ejemplo: 128.50+19.13+29.23+3.19+1.06=181.11. NO olvidar DESEMPLEO),\n"
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
    "- Para social_security_company: SUMAR ABSOLUTAMENTE TODOS los valores de la columna 'APORTACIÓN EMPRESARIAL' (5-6 líneas típicamente). Incluir siempre: Contingencias, MEI, AT/EP, DESEMPLEO, Formación, FOGASA. NO olvidar ninguna línea.\n"
    "- Para address del employee: Buscar SOLO en la sección del trabajador (parte superior), ignorar dirección de empresa\n"
    "- Si la imagen está borrosa o ilegible, responde con null en los campos poco claros\n"
    "- NUNCA inventes información\n"
)

def _extract_single_page_payroll(image_bytes, mime_type="image/png"):
    """
    Función auxiliar que extrae datos de una sola página de nómina usando OpenAI.
    """
    import time
    start_time = time.time()
    print(f"🤖 Llamando a OpenAI para procesar nómina ({len(image_bytes)} bytes)...")
    
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    try:
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
            timeout=60,
        )
        
        elapsed_time = time.time() - start_time
        print(f"✅ OpenAI respondió en {elapsed_time:.1f}s")
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Error en OpenAI después de {elapsed_time:.1f}s: {e}")
        raise
    
    usage = getattr(response, "usage", None)
    tokens = getattr(usage, "total_tokens", None) if usage else None
    
    content = response.choices[0].message.content
    
    if content is None:
        raise ValueError("OpenAI no pudo procesar la imagen o no encontró datos válidos")
    
    result = json.loads(content)
    result["tokens"] = tokens
    
    return result


def extract_payroll_data(file):
    """
    Extrae datos de una nómina (PDF o imagen) usando OpenAI.
    Devuelve dict con { 'payroll': {...}, 'employee': {...} } para una sola nómina,
    o una tupla (lista_resultados, pdf_bytes) para PDFs múltiples.
    """
    content_type = file.content_type.lower()
    result = {}
    tokens = None

    try:
        # --- CASO 1: PDF ---
        if "pdf" in content_type:
            pdf_bytes = file.read()
            
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                num_pages = len(doc)
                
                if num_pages == 1:
                    # PDF de una sola página - comportamiento original
                    # Intentar extraer texto directamente
                    text = ""
                    for page in doc:
                        text += page.get_text("text")

                    # Si el texto es corto o sin montos → pasar a imagen
                    if len(text.strip()) < 50 or ("€" not in text and "$" not in text):
                        print("⚠️ PDF parece escaneado → usando OCR visual.")
                        first_page = doc[0]
                        mat = fitz.Matrix(2, 2)
                        pix = first_page.get_pixmap(matrix=mat)
                        image_bytes = pix.tobytes("png")
                        print(f"📐 Tamaño de imagen: {pix.width}x{pix.height}")
                        return _extract_single_page_payroll(image_bytes, "image/png")
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

                        usage = getattr(response, "usage", None)
                        if usage is not None:
                            tokens = getattr(usage, "total_tokens", None)

                        content = response.choices[0].message.content
                        print(f"🤖 Respuesta de OpenAI (Nómina): {content}")
                        result = json.loads(content)
                        result["tokens"] = tokens
                        return result
                else:
                    # PDF con múltiples páginas - procesar cada una
                    print(f"📄 PDF con {num_pages} páginas detectado, procesando cada página...")
                    results = []
                    
                    for page_idx in range(num_pages):
                        print(f"🔄 Procesando página {page_idx + 1} de {num_pages}...")
                        
                        try:
                            # Extraer página como imagen
                            page = doc[page_idx]
                            mat = fitz.Matrix(2, 2)
                            pix = page.get_pixmap(matrix=mat)
                            image_bytes = pix.tobytes("png")
                            
                            # Extraer datos de esta página
                            page_result = _extract_single_page_payroll(image_bytes, "image/png")
                            page_result["page_number"] = page_idx + 1
                            results.append(page_result)
                            
                            print(f"✅ Página {page_idx + 1} procesada")
                            
                        except Exception as e:
                            print(f"❌ Error procesando página {page_idx + 1}: {e}")
                            results.append({
                                "page_number": page_idx + 1,
                                "error": str(e),
                                "tokens": None
                            })
                    
                    return (results, pdf_bytes)

        # --- CASO 2: Imagen (JPG / PNG) ---
        elif any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
            image_bytes = file.read()
            mime_type = "image/jpeg" if "jpeg" in content_type or "jpg" in content_type else "image/png"
            return _extract_single_page_payroll(image_bytes, mime_type)
        else:
            raise ValueError("Formato de archivo no soportado")

    except Exception as e:
        print(f"⚠️ Error en extract_payroll_data: {e}")
        import traceback
        print(traceback.format_exc())
        result = {"tokens": None}
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

        discount_amount = invoice_data.get('discount_amount', 0) or 0
        
        prompt = f"""Eres un experto contable español. Analiza esta factura de COMPRA y genera el asiento contable según el Plan General Contable (PGC) español.

DATOS DE LA FACTURA:
- Número: {invoice_data.get('invoice_number', 'N/A')}
- Proveedor: {supplier_name}
- Base imponible: {invoice_data.get('base_amount', 0)}€
- Descuento: {discount_amount}€
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