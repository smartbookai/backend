from django.contrib import admin
from django.urls import path
from sba_app import views
from django.conf import settings
from django.conf.urls.static import static
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.login, name="login"),
    path('', views.index, name="index"),
    path('logout/', views.logout_view, name='logout'),
    path('facturas/', views.facturas, name='facturas'),
    path('invoices-sent/', views.invoices_sent, name='invoices_sent'),
    path('proveedores/', views.proveedores, name='proveedores'),
    path('trabajadores/', views.trabajadores, name='trabajadores'),
    path('clientes/', views.clientes, name='clientes'),
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
    path('api/workers/create/', views.api_create_worker, name='api_create_worker'),
    path('api/workers/<int:worker_id>/', views.api_get_worker, name='api_get_worker'),
    path('api/workers/<int:worker_id>/update/', views.api_update_worker, name='api_update_worker'),
    path('api/workers/<int:worker_id>/delete/', views.api_delete_worker, name='api_delete_worker'),

    #sales invoices API endpoints
    path('api/show-table-invoices-sent/', views.api_show_table_invoices_sent, name='api_show_table_invoices_sent'),
    path('api/invoices-sent/create/', views.api_create_invoice_sent, name='api_create_invoice_sent'),
    path('api/invoices-sent/<int:invoice_id>/delete/', views.api_delete_invoice_sent, name='api_delete_invoice_sent'),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
