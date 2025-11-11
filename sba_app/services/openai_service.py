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