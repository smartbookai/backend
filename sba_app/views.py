from django.contrib.auth.decorators import user_passes_test, login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib import messages

from sba_app.models import CompanyUser, Supplier


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
def proveedores(request):
    return render(request, 'pages/proveedores.html')


@login_required
def trabajadores(request):
    return render(request, 'pages/trabajadores.html')


@login_required
def reportes(request):
    return render(request, 'pages/reportes.html')


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
    print("API Suppliers called")
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
