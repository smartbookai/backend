from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    document_type = models.CharField(max_length=255, null=True, blank=True)
    document_number = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    marital_status = models.CharField(max_length=50, null=True, blank=True)
    nationality = models.CharField(max_length=100, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)

    def __str__(self):
        return str(self.user.email)

    class Meta:
        verbose_name_plural = "Perfiles de Usuarios"


class Company(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, null=True, blank=True)
    document_type = models.CharField(max_length=255, null=True, blank=True)
    document_number = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Empresas"


class CompanyUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_user')
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='users')
    role = models.CharField(max_length=50, choices=[('admin', 'Admin'), ('staff', 'Staff')], default='staff')

    def __str__(self):
        return f"{self.user} - {self.company.name}"

    class Meta:
        verbose_name_plural = "Usuarios de Empresa"


class Supplier(models.Model):
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='suppliers')
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    document_type = models.CharField(max_length=255, null=True, blank=True)
    document_number = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Proveedores"


class Client(models.Model):
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='clients')
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    document_type = models.CharField(max_length=255, null=True, blank=True)
    document_number = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.company.name})"

    class Meta:
        verbose_name_plural = "Clientes"
        unique_together = ('company', 'document_number')


class BaseInvoice(models.Model):
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name="%(class)s_invoices")
    invoice_number = models.CharField(max_length=50)               # Número de factura
    issue_date = models.DateField(default=timezone.now)            # Fecha de emisión
    due_date = models.DateField(null=True, blank=True)             # Fecha de vencimiento
    payment_method = models.CharField(max_length=100, null=True, blank=True)  # Forma de pago

    base_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))  # Base imponible
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))   # Total de impuestos
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00')) # Total factura

    # Cuentas contables
    account_income = models.CharField(max_length=20, null=True, blank=True)
    account_customer = models.CharField(max_length=20, null=True, blank=True)
    account_vat_output = models.CharField(max_length=20, null=True, blank=True)

    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.invoice_number} ({self.company.name})"


# Facturas emitidas (ventas)
class SalesInvoice(BaseInvoice):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='sales_invoices')

    class Meta:
        verbose_name = "Sales Invoice"
        verbose_name_plural = "Sales Invoices"
        unique_together = ('company', 'invoice_number')


# Facturas recibidas (compras)
class PurchaseInvoice(BaseInvoice):
    supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE, related_name='purchase_invoices')

    # Cuentas específicas para facturas recibidas
    account_expense = models.CharField(max_length=20, null=True, blank=True)
    account_supplier = models.CharField(max_length=20, null=True, blank=True)
    account_vat_input = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        verbose_name = "Purchase Invoice"
        verbose_name_plural = "Purchase Invoices"
        unique_together = ('company', 'invoice_number')


class InvoiceLine(models.Model):
    sales_invoice = models.ForeignKey('SalesInvoice', on_delete=models.CASCADE, related_name='lines', null=True, blank=True)
    purchase_invoice = models.ForeignKey('PurchaseInvoice', on_delete=models.CASCADE, related_name='lines', null=True, blank=True)
    description = models.CharField(max_length=255)                          # Descripción del producto o servicio
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Porcentaje de IVA, ej: 21")

    def subtotal(self):
        return self.quantity * self.unit_price

    def total_with_vat(self):
        return self.subtotal() * (1 + self.vat_rate / 100)

    def __str__(self):
        invoice = self.sales_invoice or self.purchase_invoice
        return f"{self.description} ({invoice.invoice_number})"


class AccountingEntry(models.Model):
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='entries')
    date = models.DateField(default=timezone.now)                       # Fecha del asiento
    description = models.CharField(max_length=255)                      # Descripción general
    sales_invoice = models.OneToOneField('SalesInvoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='entry')
    purchase_invoice = models.OneToOneField('PurchaseInvoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='entry')

    debit_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    credit_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Entry {self.id} ({self.company.name})"


class AccountingEntryLine(models.Model):
    entry = models.ForeignKey('AccountingEntry', on_delete=models.CASCADE, related_name='lines')
    account_code = models.CharField(max_length=20)              # Código contable (ej: 700000, 430000, 477000)
    description = models.CharField(max_length=255)              # Descripción del movimiento
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"{self.account_code} - D:{self.debit} / C:{self.credit}"





