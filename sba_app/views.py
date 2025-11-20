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
from django.utils import timezone
import os
from django.conf import settings
from django.core.files.storage import default_storage

from sba_app.models import CompanyUser, Supplier, User, UserProfile, SalesInvoice, Client, InvoiceLine, PurchaseInvoice, \
    Employee, Payroll, AccountingEntryLine, AccountingEntry
from sba_app.services.openai_service import extract_invoice_data, extract_purchase_invoice_data, extract_payroll_data, \
    generate_accounting_entry_for_purchase

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
def empleados(request):
    return render(request, 'pages/empleados.html')


@login_required
def nominas(request):
    return render(request, 'pages/nominas.html')


@login_required
def accounting_entries(request):
    company = get_current_company(request.user)
    entries = (
        AccountingEntry.objects
        .filter(company=company)
        .select_related('sales_invoice', 'purchase_invoice', 'payroll__employee')
        .order_by('-date', '-id')
    )
    return render(request, 'pages/accounting_entries.html', {
        'entries': entries,
    })


@login_required
def accounting_entry_detail(request, entry_id):
    company = get_current_company(request.user)
    try:
        entry = AccountingEntry.objects.select_related(
            'sales_invoice', 'purchase_invoice', 'payroll__employee'
        ).get(id=entry_id, company=company)
    except AccountingEntry.DoesNotExist:
        raise Http404("Asiento no encontrado")

    return render(request, 'pages/accounting_entry_detail.html', {
        'entry': entry,
    })


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

    invoice_lines_queryset = InvoiceLine.objects.filter(sales_invoice=invoice).order_by('id')
    invoice_lines_payload = [{
        'id': line.id,
        'description': line.description or '',
        'quantity': float(line.quantity) if line.quantity is not None else 0,
        'unit_price': float(line.unit_price) if line.unit_price is not None else 0,
        'vat_rate': float(line.vat_rate) if line.vat_rate is not None else 0,
    } for line in invoice_lines_queryset]

    return JsonResponse({'invoice': data, 'lines': invoice_lines_payload})


@login_required
@require_POST
@transaction.atomic
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
    if 'notes' in payload:
        invoice.notes = payload.get('notes') or ''

    # Update client name if provided
    client_name = (payload.get('client_name') or '').strip()
    if client_name and invoice.client:
        invoice.client.name = client_name
        invoice.client.save()

    invoice.save()

    incoming_lines_payload = payload.get('lines', []) or []

    existing_lines_by_id = {
        line.id: line
        for line in InvoiceLine.objects.filter(sales_invoice=invoice)
    }

    incoming_line_ids = set(
        ln.get('id') for ln in incoming_lines_payload if ln.get('id')
    )

    for line_item in incoming_lines_payload:
        line_id = line_item.get('id')
        line_data = {
            'description': (line_item.get('description') or '').strip(),
            'quantity': safe_decimal(line_item.get('quantity')) or 0,
            'unit_price': safe_decimal(line_item.get('unit_price')) or 0,
            'vat_rate': safe_decimal(line_item.get('vat_rate')) or 0,
        }
        if line_id and line_id in existing_lines_by_id:
            invoice_line_obj = existing_lines_by_id[line_id]
            invoice_line_obj.description = line_data['description']
            invoice_line_obj.quantity = line_data['quantity']
            invoice_line_obj.unit_price = line_data['unit_price']
            invoice_line_obj.vat_rate = line_data['vat_rate']
            invoice_line_obj.save()
        else:
            InvoiceLine.objects.create(sales_invoice=invoice, **line_data)

    lines_to_delete = [
        obj for obj_id, obj in existing_lines_by_id.items()
        if obj_id not in incoming_line_ids
    ]
    if lines_to_delete:
        InvoiceLine.objects.filter(id__in=[o.id for o in lines_to_delete]).delete()

    return JsonResponse({'success': True})


def safe_decimal(value):
    """
    Convierte el valor a Decimal seguro. Si es None, vacío o inválido, devuelve Decimal('0').
    Maneja formato europeo (1.234,56) y americano (1,234.56)
    """
    try:
        if value is None or str(value).strip() == "":
            return Decimal("0")

        value_str = str(value).strip()

        # Detectar formato: si tiene coma Y punto, determinar cuál es separador decimal
        if "," in value_str and "." in value_str:
            # Si la coma está después del punto: formato americano 1,234.56
            if value_str.rindex(",") < value_str.rindex("."):
                value_str = value_str.replace(",", "")  # Quitar separador de miles
            # Si el punto está después de la coma: formato europeo 1.234,56
            else:
                value_str = value_str.replace(".", "").replace(",", ".")
        # Solo tiene coma: puede ser separador decimal europeo (1,50) o separador de miles americano (1,234)
        elif "," in value_str:
            # Si hay más de 3 dígitos después de la coma, es separador de miles
            parts = value_str.split(",")
            if len(parts[-1]) == 3 and len(parts) > 1:
                value_str = value_str.replace(",", "")  # Separador de miles: 1,234
            else:
                value_str = value_str.replace(",", ".")  # Separador decimal: 1,50
        # Solo tiene punto: puede ser separador decimal (1.50) o separador de miles (1.234)
        elif "." in value_str:
            parts = value_str.split(".")
            if len(parts[-1]) == 3 and len(parts) > 1 and len(parts[0]) <= 3:
                value_str = value_str.replace(".", "")  # Separador de miles: 1.234
            # Si no, es separador decimal, dejarlo como está

        return Decimal(value_str)
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
        lines_data = result.get("lines", []) or []

        #print(f"📊 Datos extraídos - Invoice: {invoice_data}")
        #print(f"👤 Cliente: {client_data}")
        #print(f"📝 Líneas: {lines_data}")

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

        # 📝 Paso 4: Crear líneas de factura
        created_lines = []
        if lines_data:
            for line_data in lines_data:
                line = InvoiceLine.objects.create(
                    sales_invoice=invoice,
                    description=line_data.get("description") or "Sin descripción",
                    quantity=safe_decimal(line_data.get("quantity", "1")),
                    unit_price=safe_decimal(line_data.get("unit_price", "0")),
                    vat_rate=safe_decimal(line_data.get("vat_rate", "0")),
                )
                created_lines.append({
                    "id": line.id,
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unit_price": str(line.unit_price),
                    "vat_rate": str(line.vat_rate),
                    "subtotal": str(line.subtotal()),
                })
                #print(f"✅ Línea creada: {line.description} - Qty: {line.quantity} - Price: {line.unit_price}")
        else:
            print("⚠️ No se encontraron líneas en la factura")

        return JsonResponse({
            "success": True,
            "message": "Factura procesada correctamente.",
            "invoice_id": invoice.id,
            "invoice_data": invoice_data,
            "client_data": client_data,
            "lines": created_lines,
        })

    except Exception as e:
        import traceback
        print("🔥 ERROR en api_create_invoice_sent:", traceback.format_exc())

        # ✅ CRÍTICO: Forzar rollback explícito
        transaction.set_rollback(True)

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


@login_required
def api_show_table_invoices_received(request):
    company = get_current_company(request.user)

    # Query claramente nombrada
    purchase_invoices_queryset = (
        PurchaseInvoice.objects
        .select_related('supplier')  # proveedor en facturas recibidas
        .filter(company=company)
        .order_by('-issue_date', '-id')
    )

    purchases_payload = []
    for invoice in purchase_invoices_queryset:
        issue_date_str = invoice.issue_date.strftime('%d/%m/%Y') if invoice.issue_date else ''
        due_date_str = invoice.due_date.strftime('%d/%m/%Y') if invoice.due_date else ''
        total_amount_str = f"{invoice.total_amount:.2f}" if invoice.total_amount is not None else ''

        supplier_name = invoice.supplier.name if invoice.supplier else ''
        supplier_email = invoice.supplier.email if invoice.supplier else ''

        pdf_absolute_url = request.build_absolute_uri(invoice.pdf_file.url) if invoice.pdf_file else ''

        purchases_payload.append({
            'id': invoice.id,
            'number': invoice.invoice_number or '',
            'supplier_name': supplier_name,
            'supplier_email': supplier_email,
            'issue_date': issue_date_str,
            'due_date': due_date_str,
            'total_amount': total_amount_str,
            'status': '',  # si no hay campo en el modelo, dejamos vacío
            'pdf_url': pdf_absolute_url,
        })

    return JsonResponse({'purchases': purchases_payload})


@login_required
@require_http_methods(["GET"])
def api_get_invoice_received(request, invoice_id):
    company = get_current_company(request.user)
    try:
        purchase_invoice = (
            PurchaseInvoice.objects
            .select_related('supplier')
            .get(id=invoice_id, company=company)
        )
    except PurchaseInvoice.DoesNotExist:
        raise Http404("Factura no encontrada")

    def format_date(date_value):
        return date_value.strftime('%Y-%m-%d') if date_value else ''

    invoice_payload = {
        'id': purchase_invoice.id,
        'invoice_number': purchase_invoice.invoice_number or '',
        'issue_date': format_date(purchase_invoice.issue_date),
        'due_date': format_date(purchase_invoice.due_date),
        'payment_method': getattr(purchase_invoice, 'payment_method', '') or '',
        'base_amount': f"{purchase_invoice.base_amount:.2f}" if getattr(purchase_invoice, 'base_amount', None) is not None else '',
        'tax_amount': f"{purchase_invoice.tax_amount:.2f}" if getattr(purchase_invoice, 'tax_amount', None) is not None else '',
        'total_amount': f"{purchase_invoice.total_amount:.2f}" if purchase_invoice.total_amount is not None else '',
        'notes': getattr(purchase_invoice, 'notes', '') or '',
        'supplier': {
            'id': purchase_invoice.supplier.id if purchase_invoice.supplier else None,
            'name': purchase_invoice.supplier.name if purchase_invoice.supplier else '',
            'email': purchase_invoice.supplier.email if purchase_invoice.supplier else '',
        }
    }

    # Líneas de la factura recibida
    purchase_lines_queryset = InvoiceLine.objects.filter(purchase_invoice=purchase_invoice).order_by('id')
    lines_payload = [{
        'id': line.id,
        'description': line.description or '',
        'quantity': float(line.quantity) if line.quantity is not None else 0,
        'unit_price': float(line.unit_price) if line.unit_price is not None else 0,
        'vat_rate': float(line.vat_rate) if line.vat_rate is not None else 0,
    } for line in purchase_lines_queryset]

    return JsonResponse({'invoice': invoice_payload, 'lines': lines_payload})


@login_required
@require_POST
@transaction.atomic
def api_update_invoice_received(request, invoice_id):
    if not ensure_admin(request.user):
        return HttpResponseForbidden('Solo admin puede editar facturas')

    company = get_current_company(request.user)
    try:
        purchase_invoice = PurchaseInvoice.objects.get(id=invoice_id, company=company)
    except PurchaseInvoice.DoesNotExist:
        raise Http404("Factura no encontrada")

    try:
        request_payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        request_payload = request.POST

    # Parse de fechas (YYYY-MM-DD)
    def parse_date(value):
        if not value:
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            return None

    # Cabecera (solo si vienen en payload)
    invoice_number = (request_payload.get('invoice_number') or '').strip()
    if invoice_number:
        purchase_invoice.invoice_number = invoice_number

    purchase_invoice.issue_date = parse_date(request_payload.get('issue_date'))
    purchase_invoice.due_date = parse_date(request_payload.get('due_date'))
    purchase_invoice.payment_method = request_payload.get('payment_method') or None

    purchase_invoice.base_amount = safe_decimal(request_payload.get('base_amount'))
    purchase_invoice.tax_amount = safe_decimal(request_payload.get('tax_amount'))
    purchase_invoice.total_amount = safe_decimal(request_payload.get('total_amount'))

    if 'notes' in request_payload:
        purchase_invoice.notes = request_payload.get('notes') or ''

    # Actualizar nombre del proveedor si viene
    supplier_name = (request_payload.get('supplier_name') or '').strip()
    if supplier_name and purchase_invoice.supplier:
        purchase_invoice.supplier.name = supplier_name
        purchase_invoice.supplier.save()

    purchase_invoice.save()

    # Sincronizar líneas
    incoming_lines = request_payload.get('lines', []) or []

    existing_lines_by_id = {
        line.id: line
        for line in InvoiceLine.objects.filter(purchase_invoice=purchase_invoice)
    }

    incoming_line_ids = set(ln.get('id') for ln in incoming_lines if ln.get('id'))

    for line_item in incoming_lines:
        line_id = line_item.get('id')
        line_data = {
            'description': (line_item.get('description') or '').strip(),
            'quantity': safe_decimal(line_item.get('quantity')) or 0,
            'unit_price': safe_decimal(line_item.get('unit_price')) or 0,
            'vat_rate': safe_decimal(line_item.get('vat_rate')) or 0,
        }
        if line_id and line_id in existing_lines_by_id:
            invoice_line = existing_lines_by_id[line_id]
            invoice_line.description = line_data['description']
            invoice_line.quantity = line_data['quantity']
            invoice_line.unit_price = line_data['unit_price']
            invoice_line.vat_rate = line_data['vat_rate']
            invoice_line.save()
        else:
            InvoiceLine.objects.create(purchase_invoice=purchase_invoice, **line_data)

    lines_to_delete = [
        obj for obj_id, obj in existing_lines_by_id.items()
        if obj_id not in incoming_line_ids
    ]
    if lines_to_delete:
        InvoiceLine.objects.filter(id__in=[o.id for o in lines_to_delete]).delete()

    return JsonResponse({'success': True})

@login_required
@require_POST
@transaction.atomic
def api_delete_invoice_received(request, invoice_id):
    if not ensure_admin(request.user):
        return HttpResponseForbidden('Solo admin puede eliminar facturas')

    company = get_current_company(request.user)
    try:
        purchase_invoice = PurchaseInvoice.objects.get(id=invoice_id, company=company)
    except PurchaseInvoice.DoesNotExist:
        raise Http404("Factura no encontrada")

    purchase_invoice.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
@transaction.atomic
def api_create_invoice_received(request):
    company = get_current_company(request.user)
    file = request.FILES.get("pdf_file")

    if not file:
        return JsonResponse({"success": False, "message": "Falta el archivo"}, status=400)

    if file.size > 10 * 1024 * 1024:
        return JsonResponse({"success": False, "message": "El archivo supera 10MB"}, status=400)

    try:
        # 🧠 Paso 1: Extraer datos con OpenAI - función específica para purchase
        result = extract_purchase_invoice_data(file)  # ← Usá esta función

        if not result:
            return JsonResponse({
                "success": False,
                "message": "No se pudo extraer información de la factura."
            }, status=400)

        invoice_data = result.get("invoice", {}) or {}
        supplier_data = result.get("supplier", {}) or {}  # ← Ahora viene como "supplier"
        lines_data = result.get("lines", []) or []

        # 🏢 Paso 2: Buscar o crear proveedor (Supplier)
        supplier = None
        filters = {"company": company}

        if supplier_data.get("document_number"):
            filters["document_number"] = supplier_data["document_number"]
            supplier = Supplier.objects.filter(**filters).first()
        elif supplier_data.get("name"):
            filters["name"] = supplier_data["name"]
            supplier = Supplier.objects.filter(**filters).first()

        if not supplier:
            supplier = Supplier.objects.create(
                company=company,
                name=supplier_data.get("name") or "Proveedor desconocido",
                contact_person=supplier_data.get("contact_person"),
                phone=supplier_data.get("phone"),
                email=supplier_data.get("email"),
                address=supplier_data.get("address"),
                document_type=supplier_data.get("document_type"),
                document_number=supplier_data.get("document_number"),
            )

        # 🧾 Paso 3: Crear factura recibida (PurchaseInvoice)
        invoice = PurchaseInvoice.objects.create(
            company=company,
            supplier=supplier,
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

        # 📝 Paso 4: Crear líneas de factura
        created_lines = []
        if lines_data:
            for line_data in lines_data:
                line = InvoiceLine.objects.create(
                    purchase_invoice=invoice,
                    description=line_data.get("description") or "Sin descripción",
                    quantity=safe_decimal(line_data.get("quantity", "1")),
                    unit_price=safe_decimal(line_data.get("unit_price", "0")),
                    vat_rate=safe_decimal(line_data.get("vat_rate", "0")),
                )
                created_lines.append({
                    "id": line.id,
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unit_price": str(line.unit_price),
                    "vat_rate": str(line.vat_rate),
                    "subtotal": str(line.subtotal()),
                })
        else:
            print("⚠️ No se encontraron líneas en la factura")

        return JsonResponse({
            "success": True,
            "message": "Factura recibida procesada correctamente.",
            "invoice_id": invoice.id,
            "invoice_data": invoice_data,
            "supplier_data": supplier_data,
            "lines": created_lines,
        })

    except Exception as e:
        import traceback
        print("🔥 ERROR en api_create_invoice_received:", traceback.format_exc())
        transaction.set_rollback(True)
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
def api_show_table_employees(request):
    company = get_current_company(request.user)

    employees_qs = (
        Employee.objects
        .filter(company=company)
        .order_by('first_name', 'last_name')
    )

    employees = []
    for employee in employees_qs:
        hire_date = employee.hire_date.strftime('%d/%m/%Y') if employee.hire_date else ''
        employees.append({
            'id': employee.id,
            'first_name': employee.first_name or '',
            'last_name': employee.last_name or '',
            'email': employee.email or '',
            'phone': employee.phone or '',
            'document': f"{(employee.document_type or '')} {(employee.document_number or '')}".strip(),
            'job_position': employee.job_position or '',
            'department': employee.department or '',
            'hire_date': hire_date,
            'is_active': employee.is_active,
        })

    return JsonResponse({'employees': employees})


def get_company_scoped_employee_or_404(user, employee_id):
    company = get_current_company(user)
    try:
        return Employee.objects.get(id=employee_id, company=company)
    except Employee.DoesNotExist:
        raise Http404("Empleado no encontrado")


@login_required
@require_http_methods(["GET"])
def api_get_employee(request, employee_id):
    e = get_company_scoped_employee_or_404(request.user, employee_id)
    return JsonResponse({
        'employee': {
            'id': e.id,
            'first_name': e.first_name or '',
            'last_name': e.last_name or '',
            'email': e.email or '',
            'phone': e.phone or '',
            'document_type': e.document_type or '',
            'document_number': e.document_number or '',
            'job_position': e.job_position or '',
            'department': e.department or '',
            'address': e.address or '',
            'date_of_birth': e.date_of_birth.strftime('%Y-%m-%d') if e.date_of_birth else '',
            'contract_type': e.contract_type or '',
            'hire_date': e.hire_date.strftime('%Y-%m-%d') if e.hire_date else '',
            'termination_date': e.termination_date.strftime('%Y-%m-%d') if e.termination_date else '',
            'is_active': e.is_active,
            'social_security_number': e.social_security_number or '',
            'bank_account': e.bank_account or '',
            'collective_agreement': e.collective_agreement or '',
        }
    })


@login_required
@require_POST
def api_create_employee(request):
    company = get_current_company(request.user)
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    first_name = (payload.get('first_name') or '').strip()
    last_name = (payload.get('last_name') or '').strip()
    job_position = (payload.get('job_position') or '').strip()
    hire_date_raw = (payload.get('hire_date') or '').strip()
    termination_date_raw = (payload.get('termination_date') or '').strip()
    date_of_birth_raw = (payload.get('date_of_birth') or '').strip()
    contract_type_in = (payload.get('contract_type') or '').strip() or 'indefinido'

    if not first_name or not last_name:
        return JsonResponse({'error': 'Nombre y apellido son obligatorios.'}, status=400)
    if not job_position:
        return JsonResponse({'error': 'La categoría profesional es obligatoria.'}, status=400)

    hire_date_val = None
    if hire_date_raw:
        try:
            hire_date_val = datetime.strptime(hire_date_raw, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Fecha de alta inválida. Use YYYY-MM-DD.'}, status=400)
    termination_date_val = None
    if termination_date_raw:
        try:
            termination_date_val = datetime.strptime(termination_date_raw, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Fecha de baja inválida. Use YYYY-MM-DD.'}, status=400)
    dob_val = None
    if date_of_birth_raw:
        try:
            dob_val = datetime.strptime(date_of_birth_raw, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Fecha de nacimiento inválida. Use YYYY-MM-DD.'}, status=400)

    valid_contract_types = {c[0] for c in Employee.CONTRACT_TYPES}
    if contract_type_in not in valid_contract_types:
        return JsonResponse({'error': 'Tipo de contrato inválido.'}, status=400)

    e = Employee(
        company=company,
        first_name=first_name,
        last_name=last_name,
        email=(payload.get('email') or None),
        phone=(payload.get('phone') or None),
        document_type=(payload.get('document_type') or None),
        document_number=(payload.get('document_number') or None),
        job_position=job_position,
        department=(payload.get('department') or None),
        address=(payload.get('address') or None),
        date_of_birth=dob_val,
        contract_type=contract_type_in,
        hire_date=hire_date_val,
        termination_date=termination_date_val,
        is_active=bool(payload.get('is_active', True)),
        social_security_number=(payload.get('social_security_number') or None),
        bank_account=(payload.get('bank_account') or None),
        collective_agreement=(payload.get('collective_agreement') or None),
    )
    try:
        e.save()
        return JsonResponse({'success': True, 'id': e.id})
    except Exception:
        logger.exception('Error al crear empleado')
        return JsonResponse({'error': 'Error al crear el empleado.'}, status=400)


@login_required
@require_POST
def api_update_employee(request, employee_id):
    e = get_company_scoped_employee_or_404(request.user, employee_id)
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    if 'first_name' in payload:
        e.first_name = payload.get('first_name') or ''
    if 'last_name' in payload:
        e.last_name = payload.get('last_name') or ''
    if 'email' in payload:
        e.email = payload.get('email') or None
    if 'phone' in payload:
        e.phone = payload.get('phone') or None
    if 'document_type' in payload:
        e.document_type = payload.get('document_type') or None
    if 'document_number' in payload:
        e.document_number = payload.get('document_number') or None
    if 'job_position' in payload:
        e.job_position = payload.get('job_position') or ''
    if 'department' in payload:
        e.department = payload.get('department') or None
    if 'address' in payload:
        e.address = payload.get('address') or None
    if 'contract_type' in payload:
        ct = (payload.get('contract_type') or '').strip()
        if ct:
            valid_contract_types = {c[0] for c in Employee.CONTRACT_TYPES}
            if ct not in valid_contract_types:
                return JsonResponse({'error': 'Tipo de contrato inválido.'}, status=400)
            e.contract_type = ct
    if 'hire_date' in payload:
        hire_date_raw = payload.get('hire_date') or ''
        if hire_date_raw:
            try:
                e.hire_date = datetime.strptime(hire_date_raw, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'error': 'Fecha de alta inválida. Use YYYY-MM-DD.'}, status=400)
        else:
            e.hire_date = None
    if 'termination_date' in payload:
        term_raw = payload.get('termination_date') or ''
        if term_raw:
            try:
                e.termination_date = datetime.strptime(term_raw, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'error': 'Fecha de baja inválida. Use YYYY-MM-DD.'}, status=400)
        else:
            e.termination_date = None
    if 'date_of_birth' in payload:
        dob_raw = payload.get('date_of_birth') or ''
        if dob_raw:
            try:
                e.date_of_birth = datetime.strptime(dob_raw, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'error': 'Fecha de nacimiento inválida. Use YYYY-MM-DD.'}, status=400)
        else:
            e.date_of_birth = None
    if 'is_active' in payload:
        e.is_active = bool(payload.get('is_active'))
    if 'social_security_number' in payload:
        e.social_security_number = payload.get('social_security_number') or None
    if 'bank_account' in payload:
        e.bank_account = payload.get('bank_account') or None
    if 'collective_agreement' in payload:
        e.collective_agreement = payload.get('collective_agreement') or None

    try:
        e.save()
        return JsonResponse({'success': True})
    except Exception:
        logger.exception('Error al actualizar empleado id=%s', employee_id)
        return JsonResponse({'error': 'Error al actualizar el empleado.'}, status=400)


@login_required
@require_POST
def api_delete_employee(request, employee_id):
    e = get_company_scoped_employee_or_404(request.user, employee_id)
    try:
        e.delete()
        return JsonResponse({'success': True})
    except Exception:
        logger.exception('Error al eliminar empleado id=%s', employee_id)
        return JsonResponse({'error': 'Error al eliminar el empleado.'}, status=400)


@login_required
def api_show_table_payrolls(request):
    company = get_current_company(request.user)

    qs = (
        Payroll.objects
        .select_related('employee')
        .filter(company=company)
        .order_by('-issue_date', '-id')
    )

    rows = []
    for p in qs:
        emp = p.employee
        emp_name = ''
        if emp:
            emp_name = f"{emp.first_name or ''} {emp.last_name or ''}".strip()
        period = ''
        if getattr(p, 'period_start', None) and getattr(p, 'period_end', None):
            period = f"{p.period_start.strftime('%d/%m/%Y')} - {p.period_end.strftime('%d/%m/%Y')}"
        elif getattr(p, 'period_start', None):
            period = p.period_start.strftime('%d/%m/%Y')
        elif getattr(p, 'period_end', None):
            period = p.period_end.strftime('%d/%m/%Y')

        def fmt_date(d):
            return d.strftime('%d/%m/%Y') if d else ''

        rows.append({
            'id': p.id,
            'number': getattr(p, 'number', None) or getattr(p, 'code', None) or str(p.id),
            'employee': emp_name or '-',
            'period': period or '-',
            'issue_date': fmt_date(getattr(p, 'issue_date', None)) or '-',
            'payment_date': fmt_date(getattr(p, 'payment_date', None)) or '-',
            'net_salary': str(getattr(p, 'net_salary', '') or ''),
            'pdf_url': p.pdf_file.url if getattr(p, 'pdf_file', None) else '',
        })

    return JsonResponse({'payrolls': rows})

def get_company_scoped_payroll_or_404(user, payroll_id):
    company = get_current_company(user)
    try:
        return Payroll.objects.select_related('employee').get(id=payroll_id, company=company)
    except Payroll.DoesNotExist:
        raise Http404('Nómina no encontrada')

@login_required
@require_http_methods(["GET"])
def api_get_payroll(request, payroll_id):
    p = get_company_scoped_payroll_or_404(request.user, payroll_id)

    def d(val):
        return val.strftime('%Y-%m-%d') if val else ''

    return JsonResponse({
        'payroll': {
            'id': p.id,
            'employee': (f"{p.employee.first_name or ''} {p.employee.last_name or ''}".strip() if p.employee else ''),
            'employee_id': p.employee.id if p.employee else None,
            'number': getattr(p, 'number', None) or getattr(p, 'code', None) or str(p.id),
            'period_start': d(getattr(p, 'period_start', None)),
            'period_end': d(getattr(p, 'period_end', None)),
            'issue_date': d(getattr(p, 'issue_date', None)),
            'payment_date': d(getattr(p, 'payment_date', None)),
            'base_salary': str(getattr(p, 'base_salary', '') or ''),
            'salary_supplements': str(getattr(p, 'salary_supplements', '') or ''),
            'overtime': str(getattr(p, 'overtime', '') or ''),
            'bonuses': str(getattr(p, 'bonuses', '') or ''),
            'total_accrued': str(getattr(p, 'total_accrued', '') or ''),
            'social_security_employee': str(getattr(p, 'social_security_employee', '') or ''),
            'irpf': str(getattr(p, 'irpf', '') or ''),
            'other_deductions': str(getattr(p, 'other_deductions', '') or ''),
            'total_deductions': str(getattr(p, 'total_deductions', '') or ''),
            'net_salary': str(getattr(p, 'net_salary', '') or ''),
            'social_security_company': str(getattr(p, 'social_security_company', '') or ''),
            'account_salary_expense': getattr(p, 'account_salary_expense', '') or '',
            'account_social_security_expense': getattr(p, 'account_social_security_expense', '') or '',
            'account_social_security_payable': getattr(p, 'account_social_security_payable', '') or '',
            'account_irpf_payable': getattr(p, 'account_irpf_payable', '') or '',
            'account_bank': getattr(p, 'account_bank', '') or '',
            'notes': getattr(p, 'notes', '') or '',
            'pdf_url': p.pdf_file.url if getattr(p, 'pdf_file', None) else '',
        }
    })


@login_required
@require_POST
def api_update_payroll(request, payroll_id):
    p = get_company_scoped_payroll_or_404(request.user, payroll_id)
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    def parse_date(key):
        val = payload.get(key)
        if not val:
            return None
        try:
            return datetime.strptime(val, '%Y-%m-%d').date()
        except ValueError:
            return None

    # Dates
    if 'period_start' in payload:
        p.period_start = parse_date('period_start')
    if 'period_end' in payload:
        p.period_end = parse_date('period_end')
    if 'issue_date' in payload:
        p.issue_date = parse_date('issue_date')
    if 'payment_date' in payload:
        p.payment_date = parse_date('payment_date')

    # Amounts
    if 'base_salary' in payload:
        p.base_salary = safe_decimal(payload.get('base_salary'))
    if 'salary_supplements' in payload:
        p.salary_supplements = safe_decimal(payload.get('salary_supplements'))
    if 'overtime' in payload:
        p.overtime = safe_decimal(payload.get('overtime'))
    if 'bonuses' in payload:
        p.bonuses = safe_decimal(payload.get('bonuses'))
    if 'total_accrued' in payload:
        p.total_accrued = safe_decimal(payload.get('total_accrued'))
    if 'social_security_employee' in payload:
        p.social_security_employee = safe_decimal(payload.get('social_security_employee'))
    if 'irpf' in payload:
        p.irpf = safe_decimal(payload.get('irpf'))
    if 'other_deductions' in payload:
        p.other_deductions = safe_decimal(payload.get('other_deductions'))
    if 'total_deductions' in payload:
        p.total_deductions = safe_decimal(payload.get('total_deductions'))
    if 'net_salary' in payload:
        p.net_salary = safe_decimal(payload.get('net_salary'))
    if 'social_security_company' in payload:
        p.social_security_company = safe_decimal(payload.get('social_security_company'))

    # Accounts and notes
    for f in [
        'account_salary_expense', 'account_social_security_expense',
        'account_social_security_payable', 'account_irpf_payable',
        'account_bank', 'notes']:
        if f in payload:
            setattr(p, f, payload.get(f) or None)

    try:
        p.save()
        return JsonResponse({'success': True})
    except Exception:
        logger.exception('Error al actualizar nómina id=%s', payroll_id)
        return JsonResponse({'error': 'Error al actualizar la nómina.'}, status=400)


@login_required
@require_POST
def api_delete_payroll(request, payroll_id):
    p = get_company_scoped_payroll_or_404(request.user, payroll_id)
    try:
        # Try to delete the stored file if present
        if getattr(p, 'pdf_file', None) and p.pdf_file.name:
            try:
                default_storage.delete(p.pdf_file.name)
            except Exception:
                logger.warning('No se pudo borrar el archivo de nómina en storage: %s', p.pdf_file.name)
        p.delete()
        return JsonResponse({'success': True})
    except Exception:
        logger.exception('Error al eliminar nómina id=%s', payroll_id)
        return JsonResponse({'error': 'Error al eliminar la nómina.'}, status=400)


def validate_and_fix_payroll_data(payroll_data, employee_data):
    """
    Valida y corrige datos extraídos de nómina para evitar errores comunes de OpenAI
    """
    from datetime import datetime, date
    import re

    # 1. VALIDAR FECHAS - MEJORADO
    # Solo corregir si es MUY antigua (>5 años)
    current_year = datetime.now().year

    for date_field in ['period_start', 'period_end', 'payment_date', 'issue_date']:
        date_str = payroll_data.get(date_field)
        if date_str:
            try:
                parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()

                # Solo corregir si es de más de 5 años atrás (probablemente error)
                if parsed_date.year < (current_year - 5):
                    print(f"⚠️ Corrigiendo {date_field}: {date_str} → año {current_year}")
                    corrected = parsed_date.replace(year=current_year)
                    payroll_data[date_field] = corrected.strftime('%Y-%m-%d')
                else:
                    print(f"✅ Fecha válida: {date_field} = {date_str}")
            except:
                pass

    # 2. CONSOLIDAR BONUSES EN SALARY_SUPPLEMENTS
    bonuses = safe_decimal(payroll_data.get('bonuses', '0'))
    if bonuses > 0:
        current_supplements = safe_decimal(payroll_data.get('salary_supplements', '0'))
        new_supplements = current_supplements + bonuses
        payroll_data['salary_supplements'] = str(new_supplements)
        payroll_data['bonuses'] = '0.00'
        print(f"✅ Consolidados bonuses ({bonuses}) en salary_supplements → {new_supplements}")

    # 3. VALIDAR TOTAL DEVENGADO
    declared_accrued = safe_decimal(payroll_data.get('total_accrued', '0'))

    if declared_accrued > 0:
        print(f"✅ Usando total devengado extraído: {declared_accrued}")
    else:
        base = safe_decimal(payroll_data.get('base_salary', '0'))
        supplements = safe_decimal(payroll_data.get('salary_supplements', '0'))
        overtime = safe_decimal(payroll_data.get('overtime', '0'))
        bonuses_final = safe_decimal(payroll_data.get('bonuses', '0'))
        calculated_accrued = base + supplements + overtime + bonuses_final
        print(f"⚠️ Total devengado no extraído, calculando: {calculated_accrued}")
        payroll_data['total_accrued'] = str(calculated_accrued)

    # 4. VALIDAR TOTAL DEDUCCIONES
    declared_deductions = safe_decimal(payroll_data.get('total_deductions', '0'))

    if declared_deductions > 0:
        print(f"✅ Usando total deducciones extraído: {declared_deductions}")
    else:
        ss_employee = safe_decimal(payroll_data.get('social_security_employee', '0'))
        irpf = safe_decimal(payroll_data.get('irpf', '0'))
        other_ded = safe_decimal(payroll_data.get('other_deductions', '0'))
        calculated_deductions = ss_employee + irpf + other_ded
        print(f"⚠️ Total deducciones no extraído, calculando: {calculated_deductions}")
        payroll_data['total_deductions'] = str(calculated_deductions)

    # 5. VALIDAR LÍQUIDO - CAMBIO CRÍTICO
    # SIEMPRE usar el líquido extraído por OpenAI si existe
    declared_net = safe_decimal(payroll_data.get('net_salary', '0'))

    if declared_net > 0:
        # Confiar en el valor extraído
        print(f"✅ Usando líquido extraído: {declared_net}")
    else:
        # Solo calcular si no vino
        final_accrued = safe_decimal(payroll_data.get('total_accrued', '0'))
        final_deductions = safe_decimal(payroll_data.get('total_deductions', '0'))
        calculated_net = final_accrued - final_deductions
        print(f"⚠️ Líquido no extraído, calculando: {calculated_net}")
        payroll_data['net_salary'] = str(calculated_net)

    # 6. VALIDAR SS EMPRESA - MEJORADO
    ss_company = safe_decimal(payroll_data.get('social_security_company', '0'))
    total_accrued_final = safe_decimal(payroll_data.get('total_accrued', '0'))

    if total_accrued_final > 0:
        # Rango más amplio: 25-45%
        expected_min = total_accrued_final * Decimal('0.20')
        expected_max = total_accrued_final * Decimal('0.50')

        if ss_company < expected_min or ss_company > expected_max:
            estimated_ss = (total_accrued_final * Decimal('0.32')).quantize(Decimal('0.01'))
            print(f"⚠️ SS empresa sospechosa ({ss_company}). Estimando: {estimated_ss}")
            payroll_data['social_security_company'] = str(estimated_ss)
        else:
            print(f"✅ SS empresa en rango esperado: {ss_company}")

    # 7. LIMPIAR DIRECCIÓN
    address = employee_data.get('address', '')
    if address and 'PALAU REIAL' in address.upper():
        print(f"⚠️ Dirección parece ser de empresa, limpiando: {address}")
        employee_data['address'] = None

    return payroll_data, employee_data


@login_required
@require_POST
@transaction.atomic
def api_create_payroll(request):
    company = get_current_company(request.user)
    file = request.FILES.get("pdf_file")

    if not file:
        return JsonResponse({"success": False, "message": "Falta el archivo"}, status=400)

    if file.size > 10 * 1024 * 1024:
        return JsonResponse({"success": False, "message": "El archivo supera 10MB"}, status=400)

    try:
        # Paso 1: Extraer datos con OpenAI
        result = extract_payroll_data(file)

        if not result:
            return JsonResponse({
                "success": False,
                "message": "No se pudo extraer información de la nómina."
            }, status=400)

        payroll_data = result.get("payroll", {}) or {}
        employee_data = result.get("employee", {}) or {}

        payroll_data, employee_data = validate_and_fix_payroll_data(payroll_data, employee_data)

        period_start = payroll_data.get("period_start")
        period_end = payroll_data.get("period_end")
        payment_date = payroll_data.get("payment_date")

        # Si payment_date es anterior a period_start, corregir
        if period_start and payment_date:
            from datetime import datetime
            try:
                ps = datetime.strptime(period_start, "%Y-%m-%d").date()
                pd = datetime.strptime(payment_date, "%Y-%m-%d").date()

                if pd < ps:
                    print(
                        f"⚠️ payment_date ({payment_date}) es anterior a period_start ({period_start}). Corrigiendo...")
                    # Usar period_end como payment_date
                    payroll_data["payment_date"] = period_end or period_start
            except:
                pass

        # Paso 2: Buscar o crear empleado (Employee)
        employee = None
        filters = {"company": company}

        if employee_data.get("document_number"):
            filters["document_number"] = employee_data["document_number"]
            employee = Employee.objects.filter(**filters).first()
        elif employee_data.get("first_name") and employee_data.get("last_name"):
            filters["first_name__iexact"] = employee_data["first_name"]
            filters["last_name__iexact"] = employee_data["last_name"]
            employee = Employee.objects.filter(**filters).first()

        if not employee:
            employee = Employee.objects.create(
                company=company,
                first_name=employee_data.get("first_name") or "Nombre",
                last_name=employee_data.get("last_name") or "Desconocido",
                document_type=employee_data.get("document_type") or "DNI",
                document_number=employee_data.get("document_number") or "SIN-DOCUMENTO",
                email=employee_data.get("email"),
                phone=employee_data.get("phone"),
                date_of_birth=employee_data.get("date_of_birth"),
                address=employee_data.get("address"),
                job_position=employee_data.get("job_position") or "Sin especificar",
                department=employee_data.get("department"),
                contract_type=employee_data.get("contract_type") or "indefinido",
                hire_date=employee_data.get("hire_date") or timezone.now().date(),
                social_security_number=employee_data.get("social_security_number"),
                bank_account=employee_data.get("bank_account"),
                collective_agreement=employee_data.get("collective_agreement"),
                is_active=True,
            )

        #  Paso 3: Crear nómina (Payroll)
        payroll = Payroll.objects.create(
            company=company,
            employee=employee,
            pdf_file=file,
            period_start=payroll_data.get("period_start") or timezone.now().date(),
            period_end=payroll_data.get("period_end") or timezone.now().date(),
            payment_date=payroll_data.get("payment_date") or timezone.now().date(),
            issue_date=payroll_data.get("issue_date") or timezone.now().date(),

            # Devengos
            base_salary=safe_decimal(payroll_data.get("base_salary", "0")),
            salary_supplements=safe_decimal(payroll_data.get("salary_supplements", "0")),
            overtime=safe_decimal(payroll_data.get("overtime", "0")),
            bonuses=safe_decimal(payroll_data.get("bonuses", "0")),
            total_accrued=safe_decimal(payroll_data.get("total_accrued", "0")),

            # Deducciones
            social_security_employee=safe_decimal(payroll_data.get("social_security_employee", "0")),
            irpf=safe_decimal(payroll_data.get("irpf", "0")),
            other_deductions=safe_decimal(payroll_data.get("other_deductions", "0")),
            total_deductions=safe_decimal(payroll_data.get("total_deductions", "0")),

            # Resultado
            net_salary=safe_decimal(payroll_data.get("net_salary", "0")),
            social_security_company=safe_decimal(payroll_data.get("social_security_company", "0")),

            # Cuentas contables
            account_salary_expense=payroll_data.get("account_salary_expense") or "640",
            account_social_security_expense=payroll_data.get("account_social_security_expense") or "642",
            account_social_security_payable=payroll_data.get("account_social_security_payable") or "476",
            account_irpf_payable=payroll_data.get("account_irpf_payable") or "4751",
            account_bank=payroll_data.get("account_bank") or "572",

            notes=payroll_data.get("notes") or "",
        )

        return JsonResponse({
            "success": True,
            "message": "Nómina procesada correctamente.",
            "payroll_id": payroll.id,
            "payroll_data": payroll_data,
            "employee_data": employee_data,
            "employee_id": employee.id,
        })

    except Exception as e:
        import traceback
        print("ERROR en api_create_payroll:", traceback.format_exc())
        transaction.set_rollback(True)
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
@require_POST
@transaction.atomic
def generate_entry_for_purchase_invoice(request, invoice_id):
    """
    Genera el asiento contable para una factura de compra (PurchaseInvoice)
    utilizando IA para determinar las cuentas contables apropiadas.
    """
    company = get_current_company(request.user)

    print("\n" + "=" * 80)
    print("🔍 GENERANDO ASIENTO CONTABLE PARA FACTURA DE COMPRA")
    print("=" * 80)

    try:
        # Obtener la factura de compra con sus líneas
        invoice = PurchaseInvoice.objects.select_related('supplier').get(
            id=invoice_id,
            company=company
        )

        print(f"\n📄 DATOS DE LA FACTURA:")
        print(f"   ID: {invoice.id}")
        print(f"   Número: {invoice.invoice_number}")
        print(f"   Proveedor: {invoice.supplier.name if invoice.supplier else 'N/A'}")
        print(f"   Fecha emisión: {invoice.issue_date}")
        print(f"   Base imponible: {invoice.base_amount}€")
        print(f"   IVA: {invoice.tax_amount}€")
        print(f"   Total: {invoice.total_amount}€")

    except PurchaseInvoice.DoesNotExist:
        print("❌ ERROR: Factura no encontrada")
        return JsonResponse({
            'success': False,
            'error': 'Factura no encontrada'
        }, status=404)

    # Verificar si ya tiene un asiento generado
    if hasattr(invoice, 'entry') and invoice.entry:
        print("⚠️ ADVERTENCIA: Esta factura ya tiene un asiento contable generado")
        return JsonResponse({
            'success': False,
            'error': 'Esta factura ya tiene un asiento contable generado'
        }, status=400)

    # Validar que la factura tenga los datos necesarios
    if not invoice.total_amount or invoice.total_amount <= 0:
        print("❌ ERROR: La factura no tiene un importe válido")
        return JsonResponse({
            'success': False,
            'error': 'La factura no tiene un importe válido'
        }, status=400)

    try:
        # Preparar datos de la factura para la IA
        invoice_data = {
            'invoice_number': invoice.invoice_number or 'SIN-NUMERO',
            'base_amount': float(invoice.base_amount) if invoice.base_amount else 0,
            'tax_amount': float(invoice.tax_amount) if invoice.tax_amount else 0,
            'total_amount': float(invoice.total_amount) if invoice.total_amount else 0,
        }

        # Obtener líneas de la factura
        lines = InvoiceLine.objects.filter(purchase_invoice=invoice)
        lines_data = [
            {
                'description': line.description or 'Sin descripción',
                'quantity': float(line.quantity) if line.quantity else 0,
                'unit_price': float(line.unit_price) if line.unit_price else 0,
            }
            for line in lines
        ]

        print(f"\n📋 LÍNEAS DE LA FACTURA ({len(lines_data)} líneas):")
        for idx, line in enumerate(lines_data, 1):
            print(f"   Línea {idx}:")
            print(f"      - Descripción: {line['description']}")
            print(f"      - Cantidad: {line['quantity']}")
            print(f"      - Precio unitario: {line['unit_price']}€")
            print(f"      - Subtotal: {line['quantity'] * line['unit_price']}€")

        supplier_name = invoice.supplier.name if invoice.supplier else 'Proveedor desconocido'

        # Llamar a la IA para determinar las cuentas contables
        print(f"\n🤖 CONSULTANDO A LA IA...")
        ai_result = generate_accounting_entry_for_purchase(
            invoice_data=invoice_data,
            lines_data=lines_data,
            supplier_name=supplier_name
        )

        print(f"\n✅ RESPUESTA DE LA IA:")
        print(f"   Cuenta de gasto: {ai_result['account_expense']}")
        print(f"   Descripción gasto: {ai_result['expense_description']}")
        print(f"   Cuenta IVA: {ai_result['account_vat_input']}")
        print(f"   Descripción IVA: {ai_result['vat_description']}")
        print(f"   Cuenta proveedor: {ai_result['account_supplier']}")
        print(f"   Descripción proveedor: {ai_result['supplier_description']}")
        print(f"   Razonamiento: {ai_result.get('reasoning', 'N/A')}")

        # 🆕 OBTENER EL SIGUIENTE NÚMERO DE ASIENTO PARA ESTA EMPRESA
        next_entry_number = AccountingEntry.get_next_entry_number(company)

        print(f"\n🔢 NÚMERO DE ASIENTO: {next_entry_number}")

        # Mostrar cómo quedará el asiento
        print(f"\n📊 ASIENTO CONTABLE A GENERAR:")
        print(f"   Empresa: {company.name}")
        print(f"   Número de asiento: {next_entry_number}")  # ← NUEVO
        print(f"   Fecha: {invoice.issue_date or timezone.now().date()}")
        print(f"   Descripción: Factura compra {invoice.invoice_number} - {supplier_name}")
        print(f"\n   LÍNEAS DEL ASIENTO:")

        # Calcular totales
        debit_total = (invoice.base_amount or Decimal('0.00')) + (invoice.tax_amount or Decimal('0.00'))
        credit_total = invoice.total_amount

        print(f"\n   {'CUENTA':<10} {'DESCRIPCIÓN':<50} {'DEBE':>15} {'HABER':>15}")
        print(f"   {'-' * 10} {'-' * 50} {'-' * 15} {'-' * 15}")

        # Línea 1: Gasto (DEBE)
        if invoice.base_amount and invoice.base_amount > 0:
            print(
                f"   {ai_result['account_expense']:<10} {ai_result['expense_description'][:50]:<50} {str(invoice.base_amount):>15} {'-':>15}")

        # Línea 2: IVA soportado (DEBE)
        if invoice.tax_amount and invoice.tax_amount > 0:
            print(
                f"   {ai_result['account_vat_input']:<10} {ai_result['vat_description'][:50]:<50} {str(invoice.tax_amount):>15} {'-':>15}")

        # Línea 3: Proveedor (HABER)
        print(
            f"   {ai_result['account_supplier']:<10} {ai_result['supplier_description'][:50]:<50} {'-':>15} {str(invoice.total_amount):>15}")

        print(f"   {'-' * 10} {'-' * 50} {'-' * 15} {'-' * 15}")
        print(f"   {'TOTALES':<10} {'':<50} {str(debit_total):>15} {str(credit_total):>15}")

        # Verificar que esté cuadrado
        difference = abs(debit_total - credit_total)
        if difference > Decimal('0.01'):
            print(f"\n   ⚠️ ADVERTENCIA: Asiento descuadrado - Diferencia: {difference}€")
        else:
            print(f"\n   ✅ Asiento cuadrado correctamente")

        print(f"\n{'=' * 80}")
        print("🚀 CREANDO ASIENTO EN LA BASE DE DATOS...")
        print(f"{'=' * 80}\n")

        # Crear el asiento contable con el número correlativo
        description = f"Factura compra {invoice.invoice_number} - {supplier_name}"

        entry = AccountingEntry.objects.create(
            company=company,
            entry_number=next_entry_number,  # ← CRÍTICO: Asignar el número correlativo
            date=invoice.issue_date or timezone.now().date(),
            description=description,
            purchase_invoice=invoice,
            debit_total=Decimal('0.00'),
            credit_total=Decimal('0.00')
        )

        print(f"✅ AccountingEntry creado - ID: {entry.id} | Número: {entry.entry_number}")

        # Línea 1: Gasto (DEBE)
        if invoice.base_amount and invoice.base_amount > 0:
            line1 = AccountingEntryLine.objects.create(
                entry=entry,
                account_code=ai_result['account_expense'],
                description=ai_result['expense_description'],
                debit=invoice.base_amount,
                credit=Decimal('0.00')
            )
            print(f"✅ Línea 1 creada - ID: {line1.id} - {ai_result['account_expense']} - DEBE: {invoice.base_amount}€")

        # Línea 2: IVA soportado (DEBE)
        if invoice.tax_amount and invoice.tax_amount > 0:
            line2 = AccountingEntryLine.objects.create(
                entry=entry,
                account_code=ai_result['account_vat_input'],
                description=ai_result['vat_description'],
                debit=invoice.tax_amount,
                credit=Decimal('0.00')
            )
            print(f"✅ Línea 2 creada - ID: {line2.id} - {ai_result['account_vat_input']} - DEBE: {invoice.tax_amount}€")

        # Línea 3: Proveedor (HABER)
        line3 = AccountingEntryLine.objects.create(
            entry=entry,
            account_code=ai_result['account_supplier'],
            description=ai_result['supplier_description'],
            debit=Decimal('0.00'),
            credit=invoice.total_amount
        )
        print(f"✅ Línea 3 creada - ID: {line3.id} - {ai_result['account_supplier']} - HABER: {invoice.total_amount}€")

        # Calcular totales del asiento
        entry.debit_total = debit_total
        entry.credit_total = credit_total
        entry.save()

        print(f"\n✅ Totales actualizados - DEBE: {entry.debit_total}€ | HABER: {entry.credit_total}€")

        # Verificar que el asiento esté cuadrado
        if abs(entry.debit_total - entry.credit_total) > Decimal('0.01'):
            print(f"\n❌ ERROR: Asiento descuadrado")
            raise ValueError(
                f"El asiento no está cuadrado: Debe={entry.debit_total}, Haber={entry.credit_total}"
            )

        print(f"\n{'=' * 80}")
        print(f"✅ ASIENTO CONTABLE GENERADO EXITOSAMENTE")
        print(f"   Entry ID: {entry.id}")
        print(f"   Número de asiento: {entry.entry_number}")  # ← NUEVO
        print(f"   Empresa: {company.name}")
        print(f"   Factura: {invoice.invoice_number}")
        print(f"   Totales: DEBE={entry.debit_total}€ | HABER={entry.credit_total}€")
        print(f"{'=' * 80}\n")

        logger.info(f'Asiento {entry.entry_number} generado para {company.name} - Factura {invoice.invoice_number}')

        return JsonResponse({
            'success': True,
            'message': f'Asiento contable #{entry.entry_number} generado correctamente',
            'entry_id': entry.id,
            'entry_number': entry.entry_number,  # ← NUEVO
            'debit_total': str(entry.debit_total),
            'credit_total': str(entry.credit_total),
            'ai_reasoning': ai_result.get('reasoning', ''),
            'accounts_used': {
                'expense': ai_result['account_expense'],
                'vat': ai_result['account_vat_input'],
                'supplier': ai_result['account_supplier']
            }
        })

    except ValueError as ve:
        print(f"\n❌ ERROR DE VALIDACIÓN: {ve}\n")
        logger.error(f'Error de validación en asiento para factura {invoice_id}: {ve}')
        return JsonResponse({
            'success': False,
            'error': str(ve)
        }, status=400)
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}\n")
        import traceback
        print(traceback.format_exc())
        logger.exception(f'Error al generar asiento para factura {invoice_id}')
        return JsonResponse({
            'success': False,
            'error': f'Error al generar el asiento contable: {str(e)}'
        }, status=500)