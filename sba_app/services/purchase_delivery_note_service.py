import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from sba_app.models import (
    Company, Supplier, PurchaseDeliveryNote, DeliveryNoteLine
)
from sba_app.services import openai_service


class PurchaseDeliveryNoteService:
    """Servicio para procesar albaranes recibidos con OpenAI"""

    def __init__(self, company: Company):
        self.company = company

    def process_delivery_note_from_file(self, file: UploadedFile) -> Dict:
        """
        Procesa un archivo PDF de albarán recibido usando OpenAI y extrae toda la información

        Args:
            file: Archivo PDF del albarán

        Returns:
            Dict con la información extraída y resultado del procesamiento
        """
        try:
            # 1. Convertir PDF a imágenes
            images = self._extract_images_from_pdf(file)

            # 2. Analizar con OpenAI
            analysis_result = self._analyze_delivery_note_with_openai(images)

            # 3. Procesar la información y guardar el PDF original
            result = self._process_delivery_note_data(analysis_result, file)

            return result

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Error procesando el albarán: {str(e)}'
            }

    def _extract_images_from_pdf(self, file: UploadedFile) -> List[Tuple[int, bytes]]:
        """Convierte PDF a imágenes (múltiples páginas)"""
        try:
            import fitz  # PyMuPDF
            
            # Resetear puntero del archivo
            file.seek(0)
            pdf_bytes = file.read()
            
            images = []
            
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for page_num in range(len(doc)):
                    # Convertir cada página a imagen
                    mat = fitz.Matrix(2, 2)  # 2x zoom para mejor calidad
                    pix = doc[page_num].get_pixmap(matrix=mat)
                    image_bytes = pix.tobytes("png")
                    images.append((page_num, image_bytes))
            
            return images
            
        except ImportError:
            raise Exception("PyMuPDF no está instalado. Ejecute: pip install PyMuPDF")
        except Exception as e:
            raise Exception(f"Error convirtiendo PDF a imágenes: {str(e)}")

    def _analyze_delivery_note_with_openai(self, images: List[Tuple[int, bytes]]) -> Dict:
        """Usa OpenAI Vision para analizar las imágenes del albarán recibido"""

        print(f"\n🤖 DEBUG: Analizando albarán recibido con OpenAI Vision...")
        print(f"   - Número de imágenes: {len(images)}")

        # Preparar el contenido de las imágenes para OpenAI
        image_contents = []
        for page_idx, image_bytes in images:
            import base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            image_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}"
                }
            })

        # Construir el mensaje para OpenAI
        user_content = [
            {
                "type": "text",
                "text": """
Analiza este albarán de entrega RECIBIDO (de un proveedor) y extrae toda la información importante.

Este es un albarán RECIBIDO, por lo que el proveedor es quien ENVÍA/EMITE el albarán.

Debes responder con un JSON con esta estructura EXACTA:

{
  "delivery_note_number": "número del albarán",
  "issue_date": "fecha de emisión en formato DD/MM/YYYY",
  "delivery_date": "fecha de entrega en formato DD/MM/YYYY",
  "delivery_method": "método de entrega",
  "notes": null,
  "supplier_name": "nombre del proveedor/empresa que envía",
  "supplier_document_number": "NIF/CIF del proveedor",
  "supplier_address": "dirección completa del proveedor",
  "supplier_phone": "teléfono del proveedor",
  "supplier_email": "email del proveedor",
  "lines": [
    {
      "reference": "referencia del producto",
      "description": "descripción del producto",
      "quantity": número cantidad sin texto,
      "unit_price": número precio unitario sin símbolo € (solo el número),
      "vat_rate": número porcentaje IVA sin símbolo % (solo el número, ej: 21)
    }
  ],
  "base_amount": número base imponible sin símbolo €,
  "tax_amount": número IVA sin símbolo €,
  "total_amount": número total sin símbolo €,
  "has_amounts": true o false
}

INSTRUCCIONES IMPORTANTES:
1. Extrae TODAS las líneas de productos/servicios que encuentres
2. Para los números (quantity, unit_price, vat_rate, amounts): usa SOLO números decimales, SIN símbolos € ni %
3. Ejemplo: si ves "120.00 €", extrae solo "120.00"
4. Ejemplo: si ves "21.00 %", extrae solo "21.00"
5. Si el albarán tiene una tabla de productos con precios, IVA y totales, pon has_amounts: true
6. Si no hay precios en el albarán, pon has_amounts: false y deja unit_price, vat_rate y amounts en null
7. Responde ÚNICAMENTE con el JSON, sin explicaciones adicionales ni markdown
"""
            }
        ]
        
        # Agregar las imágenes al contenido
        user_content.extend(image_contents)

        try:
            print(f"📤 DEBUG: Enviando solicitud a OpenAI Vision...")
            response = openai_service.client.chat.completions.create(
                model="gpt-4o",  # Usar gpt-4o que tiene vision capabilities
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un experto en extracción de datos de documentos. Respondes SIEMPRE con JSON válido, sin markdown ni explicaciones."
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4000
            )

            content = response.choices[0].message.content.strip()
            print(f"📥 DEBUG: Respuesta recibida de OpenAI")
            print(f"   - Longitud: {len(content)} caracteres")
            print(f"   - Contenido completo:\n{content}")

            print(f"🔧 DEBUG: Parseando JSON...")
            analysis_data = json.loads(content)
            print(f"   - JSON parseado exitosamente")
            print(f"   - Proveedor encontrado: {analysis_data.get('supplier_name')}")
            print(f"   - Número albarán: {analysis_data.get('delivery_note_number')}")
            print(f"   - Líneas encontradas: {len(analysis_data.get('lines', []))}")
            print(f"   - Has amounts: {analysis_data.get('has_amounts')}")

            # Mostrar detalles de las líneas
            for i, line in enumerate(analysis_data.get('lines', []), 1):
                print(
                    f"   - Línea {i}: {line.get('description')} | Cant: {line.get('quantity')} | Precio: {line.get('unit_price')} | IVA: {line.get('vat_rate')}%")

            # Validar y limpiar datos
            print(f"🧹 DEBUG: Validando y limpiando datos...")
            cleaned_data = self._validate_and_clean_data(analysis_data)
            print(f"   - Datos limpiados exitosamente")

            return cleaned_data

        except Exception as e:
            print(f"❌ ERROR en análisis OpenAI: {str(e)}")
            import traceback
            print(f"   - Traceback: {traceback.format_exc()}")
            raise Exception(f"Error analizando con OpenAI: {str(e)}")

    def _validate_and_clean_data(self, data: Dict) -> Dict:
        """Valida y limpia los datos extraídos"""

        print(f"🔍 DEBUG: Validando datos...")

        cleaned_data = {
            'delivery_note_number': self._clean_string(data.get('delivery_note_number')),
            'issue_date': self._clean_date(data.get('issue_date')),
            'delivery_date': self._clean_date(data.get('delivery_date')),
            'delivery_method': self._clean_string(data.get('delivery_method')),
            'notes': self._clean_string(data.get('notes')),
            'supplier': {
                'name': self._clean_string(data.get('supplier_name')),
                'document_number': self._clean_string(data.get('supplier_document_number')),
                'address': self._clean_string(data.get('supplier_address')),
                'phone': self._clean_string(data.get('supplier_phone')),
                'email': self._clean_string(data.get('supplier_email')),
            },
            'lines': [],
            'base_amount': self._clean_decimal(data.get('base_amount')),
            'tax_amount': self._clean_decimal(data.get('tax_amount')),
            'total_amount': self._clean_decimal(data.get('total_amount')),
            'has_amounts': bool(data.get('has_amounts', False))
        }

        # Limpiar líneas
        lines = data.get('lines', [])
        for i, line in enumerate(lines, 1):
            print(f"   - Procesando línea {i}: {line.get('description')}")
            cleaned_line = {
                'reference': self._clean_string(line.get('reference')),
                'description': self._clean_string(line.get('description')),
                'quantity': self._clean_decimal(line.get('quantity')) or Decimal('1.00'),
                'unit_price': self._clean_decimal(line.get('unit_price')),
                'vat_rate': self._clean_decimal(line.get('vat_rate'))
            }

            print(f"     • Ref: {cleaned_line['reference']}")
            print(f"     • Desc: {cleaned_line['description']}")
            print(f"     • Cantidad: {cleaned_line['quantity']}")
            print(f"     • Precio: {cleaned_line['unit_price']}")
            print(f"     • IVA: {cleaned_line['vat_rate']}")

            # Solo incluir líneas con descripción
            if cleaned_line['description']:
                cleaned_data['lines'].append(cleaned_line)

        print(f"✅ DEBUG: Datos limpios finales:")
        print(f"   - Número: {cleaned_data['delivery_note_number']}")
        print(f"   - Proveedor: {cleaned_data['supplier']['name']}")
        print(f"   - Líneas válidas: {len(cleaned_data['lines'])}")
        print(f"   - Base: {cleaned_data['base_amount']}")
        print(f"   - IVA: {cleaned_data['tax_amount']}")
        print(f"   - Total: {cleaned_data['total_amount']}")

        return cleaned_data

    def _clean_string(self, value) -> Optional[str]:
        """Limpia un valor de texto"""
        if value is None:
            return None
        return str(value).strip() if str(value).strip() else None

    def _clean_date(self, value) -> Optional[datetime]:
        """Limpia y convierte una fecha"""
        if not value:
            return None

        try:
            if isinstance(value, str):
                # Intentar diferentes formatos de fecha
                formats = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y']
                for fmt in formats:
                    try:
                        return datetime.strptime(value.strip(), fmt).date()
                    except ValueError:
                        continue

            return None

        except Exception:
            return None

    def _clean_decimal(self, value) -> Optional[Decimal]:
        """Limpia y convierte un valor decimal"""
        if value is None or value == '':
            return None

        try:
            # Limpiar el valor de caracteres no numéricos excepto punto y coma
            cleaned = re.sub(r'[^\d.,-]', '', str(value))
            # Reemplazar coma por punto para decimales
            cleaned = cleaned.replace(',', '.')

            return Decimal(str(cleaned))

        except (ValueError, TypeError):
            return None

    def _process_delivery_note_data(self, data: Dict, original_file: UploadedFile = None) -> Dict:
        """Procesa los datos del albarán recibido y lo crea en la base de datos"""

        try:
            print(f"\n🔍 DEBUG: Procesando datos del albarán recibido")
            print(f"   - Número: {data.get('delivery_note_number')}")
            print(f"   - Proveedor: {data.get('supplier', {}).get('name')}")
            print(f"   - Líneas: {len(data.get('lines', []))}")
            print(f"   - Tiene importes: {data.get('has_amounts')}")

            with transaction.atomic():

                # 1. Obtener o crear proveedor
                print(f"🏭 DEBUG: Procesando proveedor...")
                supplier = self._get_or_create_supplier(data['supplier'])
                print(f"   - Proveedor creado/encontrado: {supplier.name} (ID: {supplier.id})")

                # 2. Generar número de albarán si no existe
                delivery_note_number = data['delivery_note_number']
                if not delivery_note_number:
                    delivery_note_number = self._generate_delivery_note_number()
                    print(f"📝 DEBUG: Número generado: {delivery_note_number}")

                # 3. Verificar que no exista el número
                if PurchaseDeliveryNote.objects.filter(
                        company=self.company,
                        delivery_note_number=delivery_note_number
                ).exists():
                    print(f"❌ ERROR: Ya existe albarán con número {delivery_note_number}")
                    return {
                        'success': False,
                        'error': 'duplicate_number',
                        'message': f'Ya existe un albarán con el número {delivery_note_number}'
                    }

                # 4. Obtener cuentas contables
                accounts = self._get_default_accounts()
                print(f"💰 DEBUG: Cuentas contables: {accounts}")

                # 5. Crear el albarán
                print(f"📋 DEBUG: Creando albarán recibido...")
                delivery_note = PurchaseDeliveryNote.objects.create(
                    company=self.company,
                    supplier=supplier,
                    delivery_note_number=delivery_note_number,
                    issue_date=data['issue_date'] or timezone.now().date(),
                    delivery_date=data['delivery_date'],
                    delivery_method=data['delivery_method'],
                    base_amount=data['base_amount'] if data['has_amounts'] else None,
                    tax_amount=data['tax_amount'] if data['has_amounts'] else None,
                    total_amount=data['total_amount'] if data['has_amounts'] else None,
                    notes=data['notes'],
                    account_expense=accounts.get('expense'),
                    account_supplier=accounts.get('supplier'),
                    account_vat_input=accounts.get('vat_input'),
                )
                print(f"   - Albarán creado: ID {delivery_note.id}")

                # 6. Crear líneas
                print(f"📦 DEBUG: Creando líneas...")
                for i, line_data in enumerate(data['lines']):
                    print(f"   - Línea {i + 1}: {line_data.get('description', 'Sin descripción')}")
                    DeliveryNoteLine.objects.create(
                        purchase_delivery_note=delivery_note,
                        description=line_data['description'],
                        quantity=line_data['quantity'] or Decimal('1.00'),
                        reference=line_data['reference'] or '',
                        unit_price=line_data['unit_price'] if data['has_amounts'] else None,
                        vat_rate=line_data['vat_rate'] if data['has_amounts'] else None,
                    )
                print(f"   - Total líneas creadas: {len(data['lines'])}")

                # 7. Guardar el PDF original si se proporcionó
                if original_file:
                    print(f"📄 DEBUG: Guardando PDF original...")
                    try:
                        # Resetear el puntero del archivo al inicio
                        original_file.seek(0)

                        # Guardar el archivo original
                        filename = f"albaran_recibido_{delivery_note.delivery_note_number}.pdf"
                        delivery_note.pdf_file.save(filename, original_file, save=True)
                        print(f"   - PDF original guardado: {filename}")
                    except Exception as pdf_error:
                        print(f"⚠️  ERROR guardando PDF: {pdf_error}")
                else:
                    print(f"⚠️  No se proporcionó archivo PDF original")

                print(f"✅ DEBUG: Albarán recibido procesado exitosamente")
                return {
                    'success': True,
                    'delivery_note_id': delivery_note.id,
                    'delivery_note_number': delivery_note.delivery_note_number,
                    'supplier_name': supplier.name,
                    'total_amount': str(delivery_note.total_amount) if delivery_note.total_amount else None,
                    'has_amounts': data['has_amounts'],
                    'message': 'Albarán recibido procesado correctamente'
                }

        except Exception as e:
            print(f"❌ ERROR en _process_delivery_note_data: {str(e)}")
            import traceback
            print(f"   - Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': 'processing_error',
                'message': f'Error procesando los datos: {str(e)}'
            }

    def _get_or_create_supplier(self, supplier_data: Dict) -> Supplier:
        """Obtiene o crea un proveedor"""

        name = supplier_data.get('name')
        if not name:
            raise Exception("El nombre del proveedor es requerido")

        # Buscar proveedor existente por nombre
        supplier = Supplier.objects.filter(
            company=self.company,
            name__iexact=name.strip()
        ).first()

        if supplier:
            # Actualizar datos si faltan
            if not supplier.document_number and supplier_data.get('document_number'):
                supplier.document_number = supplier_data['document_number']
            if not supplier.address and supplier_data.get('address'):
                supplier.address = supplier_data['address']
            if not supplier.phone and supplier_data.get('phone'):
                supplier.phone = supplier_data['phone']
            if not supplier.email and supplier_data.get('email'):
                supplier.email = supplier_data['email']
            supplier.save()
            return supplier

        # Crear nuevo proveedor
        supplier = Supplier.objects.create(
            company=self.company,
            name=name.strip(),
            document_number=supplier_data.get('document_number', ''),
            address=supplier_data.get('address', ''),
            phone=supplier_data.get('phone', ''),
            email=supplier_data.get('email', ''),
        )

        return supplier

    def _generate_delivery_note_number(self) -> str:
        """Genera un número de albarán recibido único"""

        year = timezone.now().year
        prefix = f"ALB-REC-{year}"

        # Buscar el último número
        last_delivery_note = PurchaseDeliveryNote.objects.filter(
            company=self.company,
            delivery_note_number__startswith=prefix
        ).order_by('delivery_note_number').last()

        if last_delivery_note:
            try:
                # Extraer número del prefijo
                last_number = int(last_delivery_note.delivery_note_number.split('-')[-1])
                new_number = last_number + 1
            except (ValueError, IndexError):
                new_number = 1
        else:
            new_number = 1

        return f"{prefix}-{new_number:04d}"

    def _get_default_accounts(self) -> Dict[str, Optional[str]]:
        """Obtiene las cuentas contables por defecto para compras (códigos fijos)"""

        return {
            'expense': '60000000',  # Cuenta de gastos/compras por defecto
            'supplier': '40000000',  # Cuenta de proveedores por defecto
            'vat_input': '47200000'  # Cuenta de IVA soportado por defecto
        }