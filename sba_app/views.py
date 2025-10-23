from django.contrib.auth.decorators import user_passes_test, login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib import messages


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
    return render(request, 'index.html')


def logout_view(request):
    """Logs out the user and redirects to the login page."""
    logout(request)
    messages.success(request, "Ha cerrado sesion correctamente.")
    return redirect('login')
