from django.contrib import admin
from django.utils.html import format_html

from .models import UserProfile, Company, CompanyUser, Supplier, SalesInvoice, PurchaseInvoice, InvoiceLine, Client, \
    AccountingEntry


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

# Registrar todo al final
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Company, CompanyAdmin)
admin.site.register(CompanyUser, CompanyUserAdmin)
admin.site.register(Supplier, SupplierAdmin)