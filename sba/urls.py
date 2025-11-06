"""
URL configuration for sba project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from sba_app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.login, name="login"),
    path('', views.index, name="index"),
    path('logout/', views.logout_view, name='logout'),
    path('facturas/', views.facturas, name='facturas'),
    path('proveedores/', views.proveedores, name='proveedores'),
    path('trabajadores/', views.trabajadores, name='trabajadores'),
    path('reportes/', views.reportes, name='reportes'),
    #path('campaigns/', views.campaigns, name='campaigns'),
    path('nominas/', views.nominas, name='nominas'),

    #supplier API endpoints
    path('api/show-table-suppliers/', views.api_show_table_suppliers, name='api_show_table_suppliers'),
    path('api/suppliers/create/', views.api_create_supplier, name='api_create_supplier'),
    path('api/suppliers/<int:supplier_id>/', views.api_get_supplier, name='api_get_supplier'),
    path('api/suppliers/<int:supplier_id>/update/', views.api_update_supplier, name='api_update_supplier'),
    path('api/suppliers/<int:supplier_id>/delete/', views.api_delete_supplier, name='api_delete_supplier'),

    #workers API endpoints
    path('api/show-table-workers/', views.api_show_table_workers, name='api_show_table_workers'),


]
