from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import user_passes_test, login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib import messages
from django.views.decorators.http import require_POST, require_http_methods
import json
import logging
from datetime import datetime

from sba_app.models import CompanyUser, Supplier, User, UserProfile, SalesInvoice, Client
from sba_app.services.openai_service import extract_invoice_data

logger = logging.getLogger(__name__)

def anonymous_required(function=None):
    """Checks if the user is NOT logged in."""
    actual_decorator = user_passes_test(
        lambda u: not u.is_authenticated,
        login_url='index',
    )
    if function:
        return actual_decorator(function)
    return actual_decorator


@anonymous_required
def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                auth_login(request, user)
                next_url = request.GET.get('next', 'index')
                return redirect(next_url)
            else:
                messages.error(request, 'username o password invalidos.')
        else:
            messages.error(request, 'Por favor complete todos los campos.')

    return render(request, 'pages/auth/login.html')


@login_required
def index(request):
    return render(request, 'pages/dashboard.html')


def logout_view(request):
    """Logs out the user and redirects to the login page."""
    logout(request)
    messages.success(request, "Ha cerrado sesion correctamente.")
    return redirect('login')


@login_required
def facturas(request):
    return render(request, 'pages/facturas.html')

@login_required
def invoices_sent(request):
    return render(request, 'pages/facturas_enviadas.html')


@login_required
def proveedores(request):
    return render(request, 'pages/proveedores.html')


@login_required
def trabajadores(request):
    return render(request, 'pages/trabajadores.html')


@login_required
def reportes(request):
    return render(request, 'pages/reportes.html')


@login_required
def clientes(request):
    return render(request, 'pages/clientes.html')


@login_required
def campaigns(request):
    return render(request, 'pages/campaigns.html')


@login_required
def nominas(request):
    return render(request, 'pages/nominas.html')


def get_current_company(user):
    return CompanyUser.objects.select_related('company').get(user=user).company

@login_required
def api_show_table_suppliers(request):
    company = get_current_company(request.user)
    qs = Supplier.objects.filter(company=company).order_by('name')
    data = [
        {
            'id': s.id,
            'name': s.name,
            'contact_person': s.contact_person or '',
            'phone': s.phone or '',
            'email': s.email or '',
            'document': f"{(s.document_type or '')} {('· ' if s.document_type and s.document_number else '')}{(s.document_number or '')}".strip(),
            'address': s.address or '',
        }
        for s in qs
    ]
    return JsonResponse({'suppliers': data})


@login_required
@require_POST
def api_create_supplier(request):
    company = get_current_company(request.user)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = request.POST

    name = (payload.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'El nombre es obligatorio.'}, status=400)

    supplier = Supplier.objects.create(
        company=company,
        name=name,
        contact_person=payload.get('contact_person') or None,
        phone=payload.get('phone') or None,
        email=payload.get('email') or None,
        address=payload.get('address') or None,
        document_type=payload.get('document_type') or None,
        document_number=payload.get('document_number') or None,
    )

    return JsonResponse({
        'supplier': {
            'id': supplier.id,
            'name': supplier.name,
            'contact_person': supplier.contact_person or '',
            'phone': supplier.phone or '',
            'email': supplier.email or '',
            'document': f"{(supplier.document_type or '')} {('· ' if supplier.document_type and supplier.document_number else '')}{(supplier.document_number or '')}".strip(),
            'address': supplier.address or '',
        }
    }, status=201)


def ensure_admin(user):
    return getattr(user.company_user, 'role', None) == 'admin'


def get_company_scoped_supplier_or_404(user, supplier_id):
    company = get_current_company(user)
    try:
        return Supplier.objects.get(id=supplier_id, company=company)
    except Supplier.DoesNotExist:
        raise Http404("Proveedor no encontrado")


@login_required
@require_http_methods(["GET"])
def api_get_supplier(request, supplier_id):
    supplier = get_company_scoped_supplier_or_404(request.user, supplier_id)
    return JsonResponse({
        'supplier': {
            'id': supplier.id,
            'name': supplier.name,
            'contact_person': supplier.contact_person or '',
            'phone': supplier.phone or '',
            'email': supplier.email or '',
            'address': supplier.address or '',
            'document_type': supplier.document_type or '',
            'document_number': supplier.document_number or '',
        }
    })

@login_required
@require_POST
def api_update_supplier(request, supplier_id):
    if not ensure_admin(request.user):
        return HttpResponseForbidden('Solo admin puede editar proveedores')

    supplier = get_company_scoped_supplier_or_404(request.user, supplier_id)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = request.POST

    name = (payload.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'El nombre es obligatorio.'}, status=400)

    supplier.name = name
    supplier.contact_person = payload.get('contact_person') or None
    supplier.phone = payload.get('phone') or None
    supplier.email = payload.get('email') or None
    supplier.address = payload.get('address') or None
    supplier.document_type = payload.get('document_type') or None
    supplier.document_number = payload.get('document_number') or None
    supplier.save()

    return JsonResponse({
        'supplier': {
            'id': supplier.id,
            'name': supplier.name,
            'contact_person': supplier.contact_person or '',
            'phone': supplier.phone or '',
            'email': supplier.email or '',
            'address': supplier.address or '',
            'document_type': supplier.document_type or '',
            'document_number': supplier.document_number or '',
        }
    })


@login_required
@require_POST
def api_delete_supplier(request, supplier_id):
    if not ensure_admin(request.user):
        return HttpResponseForbidden('Solo admin puede eliminar proveedores')

    supplier = get_company_scoped_supplier_or_404(request.user, supplier_id)
    supplier.delete()
    return JsonResponse({'success': True})


# ==========================
# Clients CRUD (company-scoped)
# ==========================
@login_required
def api_show_table_clients(request):
    company = get_current_company(request.user)
    qs = Client.objects.filter(company=company).order_by('name')
    data = [
        {
            'id': c.id,
            'name': c.name,
            'contact_person': c.contact_person or '',
            'phone': c.phone or '',
            'email': c.email or '',
            'document': f"{(c.document_type or '')} {('· ' if c.document_type and c.document_number else '')}{(c.document_number or '')}".strip(),
            'address': c.address or '',
        }
        for c in qs
    ]
    return JsonResponse({'clients': data})


@login_required
@require_POST
def api_create_client(request):
    company = get_current_company(request.user)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = request.POST

    name = (payload.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'El nombre es obligatorio.'}, status=400)

    client = Client.objects.create(
        company=company,
        name=name,
        contact_person=payload.get('contact_person') or None,
        phone=payload.get('phone') or None,
        email=payload.get('email') or None,
        address=payload.get('address') or None,
        document_type=payload.get('document_type') or None,
        document_number=payload.get('document_number') or None,
    )

    return JsonResponse({
        'client': {
            'id': client.id,
            'name': client.name,
            'contact_person': client.contact_person or '',
            'phone': client.phone or '',
            'email': client.email or '',
            'document': f"{(client.document_type or '')} {('· ' if client.document_type and client.document_number else '')}{(client.document_number or '')}".strip(),
            'address': client.address or '',
        }
    }, status=201)


def get_company_scoped_client_or_404(user, client_id):
    company = get_current_company(user)
    try:
        return Client.objects.get(id=client_id, company=company)
    except Client.DoesNotExist:
        raise Http404("Cliente no encontrado")


@login_required
@require_http_methods(["GET"])
def api_get_client(request, client_id):
    client = get_company_scoped_client_or_404(request.user, client_id)
    return JsonResponse({
        'client': {
            'id': client.id,
            'name': client.name,
            'contact_person': client.contact_person or '',
            'phone': client.phone or '',
            'email': client.email or '',
            'address': client.address or '',
            'document_type': client.document_type or '',
            'document_number': client.document_number or '',
        }
    })


@login_required
@require_POST
def api_update_client(request, client_id):
    if not ensure_admin(request.user):
        return HttpResponseForbidden('Solo admin puede editar clientes')

    client = get_company_scoped_client_or_404(request.user, client_id)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = request.POST

    name = (payload.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'El nombre es obligatorio.'}, status=400)

    client.name = name
    client.contact_person = payload.get('contact_person') or None
    client.phone = payload.get('phone') or None
    client.email = payload.get('email') or None
    client.address = payload.get('address') or None
    client.document_type = payload.get('document_type') or None
    client.document_number = payload.get('document_number') or None
    client.save()

    return JsonResponse({
        'client': {
            'id': client.id,
            'name': client.name,
            'contact_person': client.contact_person or '',
            'phone': client.phone or '',
            'email': client.email or '',
            'address': client.address or '',
            'document_type': client.document_type or '',
            'document_number': client.document_number or '',
        }
    })


@login_required
@require_POST
def api_delete_client(request, client_id):
    if not ensure_admin(request.user):
        return HttpResponseForbidden('Solo admin puede eliminar clientes')

    client = get_company_scoped_client_or_404(request.user, client_id)
    client.delete()
    return JsonResponse({'success': True})
@login_required
def api_show_table_workers(request):
    company = get_current_company(request.user)

    company_users = (
        CompanyUser.objects
        .select_related('user', 'user__profile')
        .filter(company=company)
        .order_by('user__first_name', 'user__last_name')
    )

    workers = []
    for company_user in company_users:
        user = company_user.user
        profile = getattr(user, 'profile', None)

        workers.append({
            'id': company_user.id,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'email': user.email or '',
            'phone': getattr(profile, 'phone', '') or '',
            'date_of_birth': (
                profile.date_of_birth.strftime('%d/%m/%Y')
                if profile and profile.date_of_birth else ''
            ),
            'address': getattr(profile, 'address', '') or '',
            'role': company_user.role,
            'profile_picture': (
                profile.profile_picture.url
                if profile and profile.profile_picture else ''
            ),
        })

    return JsonResponse({'workers': workers})


@login_required
@require_POST
def api_create_worker(request):
    if not ensure_admin(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    company = get_current_company(request.user)

    # Leer de multipart/form-data
    data = request.POST
    files = request.FILES

    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    password_confirm = data.get('password_confirm') or ''

    # Validaciones básicas
    if not email:
        return JsonResponse({'error': 'El email es obligatorio.'}, status=400)
    if password != password_confirm:
        return JsonResponse({'error': 'Las contraseñas no coinciden.'}, status=400)
    if User.objects.filter(username=email).exists():
        return JsonResponse({'error': 'Ya existe un usuario con ese email.'}, status=400)

    try:
        with transaction.atomic():
            # User
            user = User(username=email, email=email,
                        first_name=data.get('first_name') or '',
                        last_name=data.get('last_name') or '')
            user.set_password(password)
            user.save()

            # UserProfile
            dob_str = data.get('date_of_birth') or ''
            dob_val = None
            if dob_str:
                try:
                    dob_val = datetime.strptime(dob_str, '%Y-%m-%d').date()
                except ValueError:
                    logger.warning('Fecha de nacimiento inválida en create_worker: %s', dob_str)
                    return JsonResponse({'error': 'Fecha de nacimiento inválida.'}, status=400)

            profile = UserProfile.objects.create(
                user=user,
                document_type=data.get('document_type') or None,
                document_number=data.get('document_number') or None,
                phone=data.get('phone') or None,
                date_of_birth=dob_val,
                address=data.get('address') or None,
                marital_status=data.get('marital_status') or None,
                nationality=data.get('nationality') or None,
                profile_picture=files.get('profile_picture') if files.get('profile_picture') else None,
            )

            # CompanyUser
            CompanyUser.objects.create(
                user=user,
                company=company,
                role=(data.get('role') or 'worker')
            )

        return JsonResponse({
            'worker': {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': profile.phone or '',
                'date_of_birth': str(profile.date_of_birth) if profile.date_of_birth else '',
                'address': profile.address or '',
                'role': (data.get('role') or 'worker'),
                'profile_picture': profile.profile_picture.url if profile.profile_picture else ''
            }
        }, status=201)
    except Exception as e:
        logger.exception('Error al crear el trabajador')
        return JsonResponse({'error': 'Error al crear el trabajador.'}, status=400)


def get_company_scoped_worker_or_404(user, worker_id):
    company = get_current_company(user)
    try:
        cu = CompanyUser.objects.select_related('user', 'user__profile').get(id=worker_id, company=company)
        return cu  # contiene cu.user y cu.user.profile
    except CompanyUser.DoesNotExist:
        raise Http404("Trabajador no encontrado")


@login_required
@require_http_methods(["GET"])
def api_get_worker(request, worker_id):
    cu = get_company_scoped_worker_or_404(request.user, worker_id)
    user = cu.user
    profile = getattr(user, 'profile', None)

    return JsonResponse({
        'worker': {
            'id': cu.id,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'email': user.email or '',
            'phone': getattr(profile, 'phone', '') or '',
            'date_of_birth': (
                profile.date_of_birth.strftime('%Y-%m-%d')
                if profile and profile.date_of_birth else ''
            ),
            'address': getattr(profile, 'address', '') or '',
            'document_type': getattr(profile, 'document_type', '') or '',
            'document_number': getattr(profile, 'document_number', '') or '',
            'marital_status': getattr(profile, 'marital_status', '') or '',
            'nationality': getattr(profile, 'nationality', '') or '',
            'role': cu.role or '',
            'profile_picture': (profile.profile_picture.url if profile and profile.profile_picture else ''),
        }
    })


@login_required
@require_POST
def api_update_worker(request, worker_id):
    if not ensure_admin(request.user):
        return HttpResponseForbidden('Solo admin puede editar trabajadores')

    cu = get_company_scoped_worker_or_404(request.user, worker_id)
    user = cu.user
    profile = getattr(user, 'profile', None)

    data = request.POST
    files = request.FILES

    try:
        with transaction.atomic():
            # User
            user.first_name = data.get('first_name') or ''
            user.last_name = data.get('last_name') or ''
            # Si NO querés permitir cambiar email/username, no lo toques.
            # Si lo permitís:
            # new_email = (data.get('email') or '').strip().lower()
            # if new_email and new_email != user.username:
            #     if User.objects.filter(username=new_email).exclude(pk=user.pk).exists():
            #         return JsonResponse({'error': 'Ya existe un usuario con ese email.'}, status=400)
            #     user.username = new_email
            #     user.email = new_email

            # Password (opcional)
            pwd = data.get('password') or ''
            pwd2 = data.get('password_confirm') or ''
            if pwd or pwd2:
                if pwd != pwd2:
                    logger.warning('Password mismatch en update_worker id=%s', worker_id)
                    return JsonResponse({'error': 'Las contraseñas no coinciden.'}, status=400)
                user.set_password(pwd)
            user.save()

            # Profile
            if profile is None:
                profile = UserProfile.objects.create(user=user)

            profile.document_type = data.get('document_type') or None
            profile.document_number = data.get('document_number') or None
            profile.phone = data.get('phone') or None
            dob = data.get('date_of_birth') or ''
            if dob:
                # viene como YYYY-MM-DD
                try:
                    profile.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
                except ValueError:
                    logger.warning('Fecha de nacimiento inválida en update_worker id=%s: %s', worker_id, dob)
                    return JsonResponse({'error': 'Fecha de nacimiento inválida.'}, status=400)
            else:
                profile.date_of_birth = None
            profile.address = data.get('address') or None
            profile.marital_status = data.get('marital_status') or None
            profile.nationality = data.get('nationality') or None

            if files.get('profile_picture'):
                profile.profile_picture = files['profile_picture']

            profile.save()

            # CompanyUser role
            cu.role = data.get('role') or cu.role
            cu.save()

        return JsonResponse({'success': True})
    except Exception:
        logger.exception('Error al actualizar el trabajador id=%s', worker_id)
        return JsonResponse({'error': 'Error al actualizar el trabajador.'}, status=400)


@login_required
@require_POST
def api_delete_worker(request, worker_id):
    if not ensure_admin(request.user):
        return HttpResponseForbidden('Solo admin puede eliminar trabajadores')

    cu = get_company_scoped_worker_or_404(request.user, worker_id)
    try:
        with transaction.atomic():
            user = cu.user
            # Opción A: borrar todo el usuario (impacta si el user pertenece a otra compañía).
            # Validar que no esté en otra company antes de borrarlo.
            if not CompanyUser.objects.exclude(pk=cu.pk).filter(user=user).exists():
                user.delete()  # borra profile por on_delete=CASCADE (OneToOne)
            else:
                cu.delete()
        return JsonResponse({'success': True})
    except Exception:
        return JsonResponse({'error': 'Error al eliminar el trabajador.'}, status=400)


@login_required
def api_show_table_invoices_sent(request):
    company = get_current_company(request.user)

    invoices_qs = (
        SalesInvoice.objects
        .select_related('client')
        .filter(company=company)
        .order_by('-issue_date', '-id')
    )

    invoices = []
    for invoice in invoices_qs:
        issue_date = invoice.issue_date.strftime('%d/%m/%Y') if invoice.issue_date else ''
        due_date = invoice.due_date.strftime('%d/%m/%Y') if invoice.due_date else ''
        total_amount = f"{invoice.total_amount:.2f}" if invoice.total_amount is not None else ''

        client_name = invoice.client.name if invoice.client else ''
        client_email = invoice.client.email if invoice.client else ''

        pdf_url = request.build_absolute_uri(invoice.pdf_file.url) if invoice.pdf_file else ''

        invoices.append({
            'id': invoice.id,
            'number': invoice.invoice_number or '',
            'customer_name': client_name,
            'customer_email': client_email,
            'issue_date': issue_date,
            'due_date': due_date,
            'total_amount': total_amount,
            'status': '',  # no hay status en el modelo; queda vacío
            'pdf_url': pdf_url,
        })

    return JsonResponse({'invoices': invoices})


@login_required
@require_http_methods(["GET"])
def api_get_invoice_sent(request, invoice_id):
    company = get_current_company(request.user)
    try:
        invoice = (
            SalesInvoice.objects
            .select_related('client')
            .get(id=invoice_id, company=company)
        )
    except SalesInvoice.DoesNotExist:
        raise Http404("Factura no encontrada")

    def fmt_date(d):
        return d.strftime('%Y-%m-%d') if d else ''

    data = {
        'id': invoice.id,
        'invoice_number': invoice.invoice_number or '',
        'issue_date': fmt_date(invoice.issue_date),
        'due_date': fmt_date(invoice.due_date),
        'payment_method': invoice.payment_method or '',
        'base_amount': f"{invoice.base_amount:.2f}" if invoice.base_amount is not None else '',
        'tax_amount': f"{invoice.tax_amount:.2f}" if invoice.tax_amount is not None else '',
        'total_amount': f"{invoice.total_amount:.2f}" if invoice.total_amount is not None else '',
        'notes': invoice.notes or '',
        'client': {
            'id': invoice.client.id if invoice.client else None,
            'name': invoice.client.name if invoice.client else '',
            'email': invoice.client.email if invoice.client else '',
        }
    }

    return JsonResponse({'invoice': data})


@login_required
@require_POST
def api_update_invoice_sent(request, invoice_id):
    if not ensure_admin(request.user):
        return HttpResponseForbidden('Solo admin puede editar facturas')

    company = get_current_company(request.user)
    try:
        invoice = SalesInvoice.objects.get(id=invoice_id, company=company)
    except SalesInvoice.DoesNotExist:
        raise Http404("Factura no encontrada")

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = request.POST

    # Parse fechas
    def parse_date(val):
        if not val:
            return None
        try:
            return datetime.strptime(val, '%Y-%m-%d').date()
        except ValueError:
            return None

    invoice.invoice_number = (payload.get('invoice_number') or '').strip() or invoice.invoice_number
    invoice.issue_date = parse_date(payload.get('issue_date'))
    invoice.due_date = parse_date(payload.get('due_date'))
    invoice.payment_method = payload.get('payment_method') or None
    invoice.base_amount = safe_decimal(payload.get('base_amount'))
    invoice.tax_amount = safe_decimal(payload.get('tax_amount'))
    invoice.total_amount = safe_decimal(payload.get('total_amount'))
    # notes may be omitted from payload; preserve current if not provided
    if 'notes' in payload:
        invoice.notes = payload.get('notes') or ''

    # Update client name if provided
    client_name = (payload.get('client_name') or '').strip()
    if client_name and invoice.client:
        invoice.client.name = client_name
        invoice.client.save()
    invoice.save()

    return JsonResponse({'success': True})


def safe_decimal(value):
    """
    Convierte el valor a Decimal seguro. Si es None, vacío o inválido, devuelve Decimal('0').
    """
    try:
        if value is None or str(value).strip() == "":
            return Decimal("0")
        # Reemplaza coma por punto, por si viene en formato europeo
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


@login_required
@require_POST
@transaction.atomic
def api_create_invoice_sent(request):
    company = get_current_company(request.user)
    file = request.FILES.get("pdf_file")

    if not file:
        return JsonResponse({"success": False, "message": "Falta el archivo"}, status=400)

    if file.size > 10 * 1024 * 1024:
        return JsonResponse({"success": False, "message": "El archivo supera 10MB"}, status=400)

    try:
        # 🧠 Paso 1: Extraer datos con OpenAI (PDF o imagen)
        result = extract_invoice_data(file)

        if not result:
            return JsonResponse({
                "success": False,
                "message": "No se pudo extraer información de la factura."
            }, status=400)

        invoice_data = result.get("invoice", {}) or {}
        client_data = result.get("client", {}) or {}

        # 🧍 Paso 2: Buscar o crear cliente
        client = None
        filters = {"company": company}

        if client_data.get("document_number"):
            filters["document_number"] = client_data["document_number"]
            client = Client.objects.filter(**filters).first()
        elif client_data.get("name"):
            filters["name"] = client_data["name"]
            client = Client.objects.filter(**filters).first()

        if not client:
            client = Client.objects.create(
                company=company,
                name=client_data.get("name") or "Cliente desconocido",
                contact_person=client_data.get("contact_person"),
                phone=client_data.get("phone"),
                email=client_data.get("email"),
                address=client_data.get("address"),
                document_type=client_data.get("document_type"),
                document_number=client_data.get("document_number"),
            )

        # 🧾 Paso 3: Crear factura
        invoice = SalesInvoice.objects.create(
            company=company,
            client=client,
            pdf_file=file,
            invoice_number=invoice_data.get("invoice_number") or "SIN-NUMERO",
            issue_date=invoice_data.get("issue_date") or None,
            due_date=invoice_data.get("due_date") or None,
            payment_method=invoice_data.get("payment_method"),
            base_amount=safe_decimal(invoice_data.get("base_amount")),
            tax_amount=safe_decimal(invoice_data.get("tax_amount")),
            total_amount=safe_decimal(invoice_data.get("total_amount")),
            notes=invoice_data.get("notes") or "",
        )

        return JsonResponse({
            "success": True,
            "message": "Factura procesada correctamente.",
            "invoice_id": invoice.id,
            "invoice_data": invoice_data,
            "client_data": client_data,
        })

    except Exception as e:
        import traceback
        print("🔥 ERROR en api_create_invoice_sent:", traceback.format_exc())
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
@require_POST
def api_delete_invoice_sent(request, invoice_id):
    company = get_current_company(request.user)
    try:
        invoice = SalesInvoice.objects.get(id=invoice_id, company=company)
    except SalesInvoice.DoesNotExist:
        raise Http404("Factura no encontrada")

    # Opcional: eliminar también el archivo del almacenamiento
    if invoice.pdf_file:
        invoice.pdf_file.delete(save=False)

    invoice.delete()
    return JsonResponse({'success': True})