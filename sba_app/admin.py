from django.contrib import admin
from django.utils.html import format_html

from .models import UserProfile, Company, CompanyUser, Supplier, SalesInvoice, PurchaseInvoice, InvoiceLine, Client, \
    AccountingEntry, Payroll, Employee


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
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def period_display(self, obj):
        return f"{obj.period_start.strftime('%m/%Y')}"

    period_display.short_description = 'Período'

# Registrar todo al final
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Company, CompanyAdmin)
admin.site.register(CompanyUser, CompanyUserAdmin)
admin.site.register(Supplier, SupplierAdmin)