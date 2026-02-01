from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth import get_user_model
from django.contrib import auth
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import UserProfile, Company, CompanyUser, Supplier, SalesInvoice, PurchaseInvoice, InvoiceLine, Client, \
    AccountingEntry, Payroll, Employee, PrecontractualAcceptance


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone')
    search_fields = ('user__email', 'user__username', 'phone')

class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone')
    search_fields = ('name', 'email')

class CompanyUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'role')
    list_filter = ('role',)

class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'phone')

    search_fields = ('name', 'email')


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'document_type', 'document_number', 'company')
    list_filter = ('company', 'document_type')
    search_fields = ('name', 'email', 'document_number', 'company__name')


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    fields = ('description', 'quantity', 'unit_price', 'vat_rate')
    readonly_fields = ()
    can_delete = True

def pdf_link(obj):
    if obj.pdf_file:
        return format_html('<a href="{}" target="_blank">Ver PDF</a>', obj.pdf_file.url)
    return '-'
pdf_link.short_description = 'PDF'


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'company', 'client', 'issue_date', 'due_date', 'total_amount', pdf_link)
    list_filter = ('company', 'issue_date', 'due_date')
    search_fields = ('invoice_number', 'client__name', 'client__email', 'company__name')
    inlines = [InvoiceLineInline]


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'company', 'supplier', 'issue_date', 'due_date', 'total_amount', pdf_link)
    list_filter = ('company', 'issue_date', 'due_date')
    search_fields = ('invoice_number', 'supplier__name', 'supplier__email', 'company__name')
    inlines = [InvoiceLineInline]


@admin.register(AccountingEntry)
class AccountingEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'date', 'description', 'sales_invoice', 'purchase_invoice', 'debit_total', 'credit_total')
    list_filter = ('company', 'date')
    search_fields = ('description', 'company__name')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'document_number', 'company', 'job_position', 'contract_type', 'is_active')
    list_filter = ('company', 'is_active', 'contract_type', 'department')
    search_fields = ('first_name', 'last_name', 'document_number', 'email', 'social_security_number')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'document_type', 'document_number',
                       'email', 'phone', 'date_of_birth', 'address')
        }),
        ('Información Laboral', {
            'fields': ('company', 'job_position', 'department', 'contract_type',
                       'hire_date', 'termination_date', 'is_active')
        }),
        ('Datos para Nómina', {
            'fields': ('social_security_number', 'bank_account', 'collective_agreement')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    full_name.short_description = 'Nombre Completo'


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('employee', 'period_display', 'payment_date', 'net_salary', 'company', pdf_link)
    list_filter = ('company', 'payment_date', 'period_start')
    search_fields = ('employee__first_name', 'employee__last_name', 'employee__document_number')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Información General', {
            'fields': ('company', 'employee', 'pdf_file')
        }),
        ('Período y Fechas', {
            'fields': ('period_start', 'period_end', 'payment_date', 'issue_date')
        }),
        ('Devengos', {
            'fields': ('base_salary', 'salary_supplements', 'overtime', 'bonuses', 'total_accrued')
        }),
        ('Deducciones', {
            'fields': ('social_security_employee', 'irpf', 'other_deductions', 'total_deductions')
        }),
        ('Resultado', {
            'fields': ('net_salary', 'social_security_company')
        }),
        ('Cuentas Contables', {
            'fields': ('account_salary_expense', 'account_social_security_expense',
                       'account_social_security_payable', 'account_irpf_payable', 'account_bank'),
            'classes': ('collapse',)
        }),
        ('Notas', {
            'fields': ('notes', 'tokens')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def period_display(self, obj):
        return f"{obj.period_start.strftime('%m/%Y')}"

    period_display.short_description = 'Período'


@admin.register(PrecontractualAcceptance)
class PrecontractualAcceptanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'terms_conditions_accepted', 'waiver_right_withdrawal_accepted', 
                   'marketing_consent_accepted', 'ip_address', 'completed_at')
    list_filter = ('terms_conditions_accepted', 'waiver_right_withdrawal_accepted', 
                   'marketing_consent_accepted', 'completed_at')
    search_fields = ('user__email', 'user__username', 'ip_address')
    readonly_fields = ('completed_at', 'terms_conditions_accepted_at', 
                       'waiver_right_withdrawal_accepted_at', 'marketing_consent_accepted_at')
    
    fieldsets = (
        ('Información de Usuario', {
            'fields': ('user', 'ip_address')
        }),
        ('Aceptaciones Obligatorias', {
            'fields': ('terms_conditions_accepted', 'terms_conditions_accepted_at',
                      'waiver_right_withdrawal_accepted', 'waiver_right_withdrawal_accepted_at')
        }),
        ('Aceptaciones Opcionales', {
            'fields': ('marketing_consent_accepted', 'marketing_consent_accepted_at')
        }),
        ('Metadata', {
            'fields': ('completed_at',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # No permitir agregar manualmente desde el admin
        return False
    
    def has_delete_permission(self, request, obj=None):
        # No permitir eliminar para mantener registro legal
        return False

# Registrar todo al final
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Company, CompanyAdmin)
admin.site.register(CompanyUser, CompanyUserAdmin)
admin.site.register(Supplier, SupplierAdmin)


# ==================== IMPERSONACIÓN DESDE ADMIN ====================

User = get_user_model()

# Desregistrar el UserAdmin por defecto de Django
from django.contrib.admin import site
admin.site.unregister(User)

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'impersonate_actions')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    
    def impersonate_actions(self, obj):
        """Muestra botón de impersonación solo para superadmins"""
        if hasattr(self, 'request') and self.request.user.is_superuser and self.request.user != obj:
            return format_html(
                '<a class="button" href="{}?impersonate_user_id={}">🎭 Impersonar</a>',
                reverse('admin:auth_user_changelist'),
                obj.id
            )
        return '-'
    impersonate_actions.short_description = 'Acciones'
    
    def changelist_view(self, request, extra_context=None):
        """Procesar impersonación en la vista de lista"""
        self.request = request  # Guardar request para usar en impersonate_actions
        
        # Verificar si es superadmin y hay parámetro de impersonación
        if request.user.is_superuser and 'impersonate_user_id' in request.GET:
            try:
                target_user = User.objects.get(id=request.GET['impersonate_user_id'])
                
                # Guardar el usuario original en sesión
                request.session['original_user_id'] = request.user.id
                request.session['impersonating'] = True
                
                # Login como el usuario objetivo
                auth.login(request, target_user)
                
                messages.success(request, f'🎭 Ahora estás impersonando a {target_user.username}')
                
                # Redirigir al index de la aplicación
                return HttpResponseRedirect(reverse('index'))
                
            except User.DoesNotExist:
                messages.error(request, '❌ Usuario no encontrado')
        
        return super().changelist_view(request, extra_context)
    
    def get_actions(self, request):
        """Agregar acción personalizada de impersonación"""
        actions = super().get_actions(request)
        
        if request.user.is_superuser:
            def impersonate_selected_users(modeladmin, request, queryset):
                """Permitir impersonar usuarios seleccionados"""
                if queryset.count() == 1:
                    user = queryset.first()
                    if user != request.user:
                        # Guardar el usuario original en sesión
                        request.session['original_user_id'] = request.user.id
                        request.session['impersonating'] = True
                        
                        # Login como el usuario objetivo
                        auth.login(request, user)
                        
                        messages.success(request, f'🎭 Ahora estás impersonando a {user.username}')
                        return HttpResponseRedirect(reverse('index'))
                    else:
                        messages.warning(request, '⚠️ No puedes impersonarte a ti mismo')
                else:
                    messages.warning(request, '⚠️ Selecciona exactamente un usuario para impersonar')
            
            impersonate_selected_users.short_description = '🎭 Impersonar usuario seleccionado'
            actions['impersonate_selected_users'] = (impersonate_selected_users, 'impersonate_selected_users', impersonate_selected_users.short_description)
        
        return actions