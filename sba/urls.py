from django.contrib import admin
from django.urls import path, re_path
from sba_app import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.login_page, name='login_page'),
    path('register/', views.register_page, name='register_page'),
    path('bienvenido/', views.bienvenido, name='bienvenido'),
    path('', views.index, name="index"),
    path('logout/', views.logout_view, name='logout'),
    path('facturas/', views.facturas, name='facturas'),
    path('invoices-sent/', views.invoices_sent, name='invoices_sent'),
    path('generar-factura/', views.generar_factura, name='generar_factura'),
    path('proveedores/', views.proveedores, name='proveedores'),
    path('trabajadores/', views.trabajadores, name='trabajadores'),
    path('clientes/', views.clientes, name='clientes'),
    path('reportes/', views.reportes, name='reportes'),
    path('condiciones/', views.aceptaciones, name='condiciones'),
    path('empleados/', views.empleados, name='empleados'),
    path('nominas/', views.nominas, name='nominas'),
    path('generar-nomina/', views.generar_nomina, name='generar_nomina'),
    path('albaranes-recibidos/', views.albaranes_recibidos, name='albaranes_recibidos'),
    path('albaranes-enviados/', views.albaranes_enviados, name='albaranes_enviados'),
    path('generar-albaran/', views.generar_albaran, name='generar_albaran'),
    
    #delivery notes API endpoints
    path('api/upload-delivery-note/', views.api_upload_delivery_note, name='api_upload_delivery_note'),
    path('api/upload-purchase-delivery-note/', views.api_upload_purchase_delivery_note, name='api_upload_purchase_delivery_note'),
    path('api/show-table-delivery-notes-sent/', views.api_show_table_delivery_notes_sent, name='api_show_table_delivery_notes_sent'),
    path('api/show-table-delivery-notes-received/', views.api_show_table_delivery_notes_received, name='api_show_table_delivery_notes_received'),
    path('api/delivery-notes-sent/manual-create/', views.api_create_manual_delivery_note, name='api_create_manual_delivery_note'),
    path('api/delivery-notes/<int:delivery_note_id>/update/', views.api_update_delivery_note, name='api_update_delivery_note'),
    path('api/delivery-notes/<int:delivery_note_id>/delete/', views.api_delete_delivery_note, name='api_delete_delivery_note'),
    path('api/purchase-delivery-notes/<int:delivery_note_id>/update/', views.api_update_purchase_delivery_note, name='api_update_purchase_delivery_note'),
    path('api/purchase-delivery-notes/<int:delivery_note_id>/delete/', views.api_delete_purchase_delivery_note, name='api_delete_purchase_delivery_note'),
    path('asientos-contables/', views.accounting_entries, name='accounting_entries'),
    path('asientos-contables/<int:entry_id>/', views.accounting_entry_detail, name='accounting_entry_detail'),

    #supplier API endpoints
    path('api/show-table-suppliers/', views.api_show_table_suppliers, name='api_show_table_suppliers'),
    path('api/suppliers/create/', views.api_create_supplier, name='api_create_supplier'),
    path('api/suppliers/<int:supplier_id>/', views.api_get_supplier, name='api_get_supplier'),
    path('api/suppliers/<int:supplier_id>/update/', views.api_update_supplier, name='api_update_supplier'),
    path('api/suppliers/<int:supplier_id>/delete/', views.api_delete_supplier, name='api_delete_supplier'),

    #clients API endpoints
    path('api/show-table-clients/', views.api_show_table_clients, name='api_show_table_clients'),
    path('api/clients/create/', views.api_create_client, name='api_create_client'),
    path('api/clients/<int:client_id>/', views.api_get_client, name='api_get_client'),
    path('api/clients/<int:client_id>/update/', views.api_update_client, name='api_update_client'),
    path('api/clients/<int:client_id>/delete/', views.api_delete_client, name='api_delete_client'),

    #workers API endpoints
    path('api/show-table-workers/', views.api_show_table_workers, name='api_show_table_workers'),
    path('api/workers/create/', views.api_create_worker, name='api_create_worker'),
    path('api/workers/<int:worker_id>/', views.api_get_worker, name='api_get_worker'),
    path('api/workers/<int:worker_id>/update/', views.api_update_worker, name='api_update_worker'),
    path('api/workers/<int:worker_id>/delete/', views.api_delete_worker, name='api_delete_worker'),


    #company API endpoints
    path('api/company/', views.api_get_company, name='api_get_company'),
    path('api/company/update/', views.api_update_company, name='api_update_company'),
    path('api/company/switch/', views.switch_company, name='switch_company'),
    path('crear-empresa/', views.crear_empresa, name='crear_empresa'),

    #sales invoices API endpoints
    path('api/show-table-invoices-sent/', views.api_show_table_invoices_sent, name='api_show_table_invoices_sent'),
    path('api/invoices-sent/create/', views.api_create_invoice_sent, name='api_create_invoice_sent'),
    path('api/invoices-sent/manual-create/', views.api_create_manual_invoice, name='api_create_manual_invoice'),
    path('api/invoices-sent/<int:invoice_id>/delete/', views.api_delete_invoice_sent, name='api_delete_invoice_sent'),
    path('api/invoices-sent/<int:invoice_id>/', views.api_get_invoice_sent, name='api_get_invoice_sent'),
    path('api/invoices-sent/<int:invoice_id>/update/', views.api_update_invoice_sent, name='api_update_invoice_sent'),
    path('templates/builder/', views.template_builder, name='template_builder_new'),
    path('templates/builder/<int:template_id>/', views.template_builder, name='template_builder_edit'),
    path('templates/builder/<int:template_id>/delete/', views.delete_user_template, name='delete_user_template'),
    path('api/user/set-default-payroll-template/', views.set_default_payroll_template, name='set_default_payroll_template'),
    path('api/user/set-default-delivery-note-template/', views.set_default_delivery_note_template, name='set_default_delivery_note_template'),
    

    #purchase invoices API endpoints
    path('api/show-table-invoices-received/', views.api_show_table_invoices_received, name='api_show_table_invoices_received'),
    path('api/invoices-received/create/', views.api_create_invoice_received, name='api_create_invoice_received'),
    path('api/invoices-received/<int:invoice_id>/delete/', views.api_delete_invoice_received, name='api_delete_invoice_received'),
    path('api/invoices-received/<int:invoice_id>/', views.api_get_invoice_received, name='api_get_invoice_received'),
    path('api/invoices-received/<int:invoice_id>/update/', views.api_update_invoice_received, name='api_update_invoice_received'),

    #employees API endpoints
    path('api/show-table-employees/', views.api_show_table_employees, name='api_show_table_employees'),
    path('api/employees/create/', views.api_create_employee, name='api_create_employee'),
    path('api/employees/<int:employee_id>/', views.api_get_employee, name='api_get_employee'),
    path('api/employees/<int:employee_id>/update/', views.api_update_employee, name='api_update_employee'),
    path('api/employees/<int:employee_id>/delete/', views.api_delete_employee, name='api_delete_employee'),

    #payrolls API endpoints
    path('api/show-table-payrolls/', views.api_show_table_payrolls, name='api_show_table_payrolls'),
    path('api/payrolls/create/', views.api_create_payroll, name='api_create_payroll'),
    path('api/payrolls/manual-create/', views.api_create_manual_payroll, name='api_create_manual_payroll'),
    path('api/payrolls/<int:payroll_id>/', views.api_get_payroll, name='api_get_payroll'),
    path('api/payrolls/<int:payroll_id>/update/', views.api_update_payroll, name='api_update_payroll'),
    path('api/payrolls/<int:payroll_id>/delete/', views.api_delete_payroll, name='api_delete_payroll'),

    #accounting entries API endpoints
    path("api/invoices-received/<int:invoice_id>/generate-entry/", views.generate_entry_for_purchase_invoice, name="generate_entry_for_purchase_invoice"),
    path("api/invoices-sent/<int:invoice_id>/generate-entry/", views.generate_entry_for_sales_invoice, name="generate_entry_for_sales_invoice"),
    path('api/payrolls/<int:payroll_id>/generate-entry/', views.generate_entry_for_payroll, name='generate_entry_for_payroll'),

    path('api/accounting-entries/<int:entry_id>/confirm/', views.api_confirm_accounting_entry, name='api_confirm_accounting_entry'),
    path('api/accounting-entries/<int:entry_id>/delete/', views.api_delete_accounting_entry, name='api_delete_accounting_entry'),
    path('api/accounting-entries/<int:entry_id>/update/', views.api_update_accounting_entry, name='api_update_accounting_entry'),
    path('api/accounting-entries/<int:entry_id>/export-excel/', views.api_export_accounting_entry_excel, name='api_export_accounting_entry_excel'),
    path('api/accounting-entries/<int:entry_id>/export-csv/', views.api_export_accounting_entry_csv, name='api_export_accounting_entry_csv'),
    path('api/accounting-entries/<int:entry_id>/export-pdf/', views.api_export_accounting_entry_pdf, name='api_export_accounting_entry_pdf'),
    path('api/accounting-entries/<int:entry_id>/export-xtml/', views.api_export_accounting_entry_xtml, name='api_export_accounting_entry_xtml'),
    path('api/accounting-entries/filtered/', views.accounting_entries_filtered, name='accounting_entries_filtered'),
    path('api/accounting-entries/download/', views.accounting_entries_download, name='accounting_entries_download'),

    #dashboard API endpoints
    path('api/dashboard/last-invoices/', views.api_dashboard_last_invoices, name='api_dashboard_last_invoices'),

    #terms and conditions API endpoint
    path('api/accept-terms/', views.api_accept_terms, name='api_accept_terms'),
    
    #precontractual acceptance API endpoint
    path('api/precontractual-acceptance/', views.api_precontractual_acceptance, name='api_precontractual_acceptance'),

    #api stripe crear pago
    path('api/crear-pago/', views.crear_pago_stripe, name='crear_pago'),
    path('api/stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),

    path('api/login/', views.api_login, name='api_login'),
    path('api/register/', views.api_register, name='api_register'),
    path('api/resend-confirmation/', views.api_resend_confirmation, name='api_resend_confirmation'),
    path('api/auth/google/', views.api_google_auth, name='api_google_auth'),
    path('confirmar/', views.confirm_page, name='confirm_page'),
    path('confirmar-email/<uuid:token>/', views.confirmar_email, name='confirmar_email'),
    path('mi-plan/', views.mi_plan, name='mi_plan'),
    path('planes/', views.planes, name='planes'),
    path('planes/cambiar/', views.cambiar_plan, name='cambiar_plan'),
    path('mi-plan/cancelar/', views.cancelar_plan, name='cancelar_plan'),
    path('mi-plan/cancelar/feedback/', views.api_cancellation_feedback, name='api_cancellation_feedback'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Sirve los archivos del frontend (SBA-PAGE) como fallback en local
    if settings.FRONTEND_DIR:
        from django.views.static import serve
        urlpatterns += [re_path(r'^(?P<path>.*)$', serve, {'document_root': settings.FRONTEND_DIR, 'show_indexes': False})]
