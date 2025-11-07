import json
import fitz  # PyMuPDF
import openai
import base64
from django.conf import settings

openai.api_key = settings.OPENAI_API_KEY


def extract_invoice_data(file):
    """
    Detecta si el archivo es PDF o imagen (JPG/PNG),
    extrae los datos con OpenAI y devuelve un dict con:
    { "invoice": {...}, "client": {...} }
    """
    content_type = file.content_type.lower()

    # --- 1️⃣ PDF: extraer texto localmente ---
    if "pdf" in content_type:
        text = ""
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()

        messages = [
            {"role": "system", "content": BASE_PROMPT},
            {"role": "user", "content": [{"type": "text", "text": text}]},
        ]

    # --- 2️⃣ Imagen: codificar a base64 y pasar como data URL ---
    elif any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
        image_bytes = file.read()
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        messages = [
            {"role": "system", "content": BASE_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analizá esta imagen de factura y devolvé los datos en JSON."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{encoded_image}"
                        },
                    },
                ],
            },
        ]

    else:
        raise ValueError("Formato de archivo no soportado")

    # --- 3️⃣ Llamada a OpenAI ---
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        response_format={"type": "json_object"},
    )

    # ✅ El contenido viene en message.content (no indexable)
    content = response.choices[0].message.content

    # --- 4️⃣ Parsear JSON ---
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError("Respuesta de OpenAI no es JSON válido")

    return data


# --- Prompt base compartido ---
BASE_PROMPT = (
    "Sos un extractor de datos de facturas. "
    "Devolvé un JSON con esta estructura exacta:\n\n"
    "{\n"
    "  'invoice': {\n"
    "    'invoice_number': str,\n"
    "    'issue_date': 'YYYY-MM-DD',\n"
    "    'due_date': 'YYYY-MM-DD' o null,\n"
    "    'payment_method': str o null,\n"
    "    'base_amount': str,\n"
    "    'tax_amount': str,\n"
    "    'total_amount': str,\n"
    "    'notes': str o null\n"
    "  },\n"
    "  'client': {\n"
    "    'name': str,\n"
    "    'contact_person': str o null,\n"
    "    'phone': str o null,\n"
    "    'email': str o null,\n"
    "    'address': str o null,\n"
    "    'document_type': str o null,\n"
    "    'document_number': str o null\n"
    "  }\n"
    "}\n\n"
    "Si no encontrás un dato, ponelo como null."
)
