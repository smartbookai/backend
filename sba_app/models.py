import uuid as _uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

User = get_user_model()

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    document_type = models.CharField(max_length=255, null=True, blank=True)
    document_number = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    marital_status = models.CharField(max_length=50, null=True, blank=True)
    nationality = models.CharField(max_length=100, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    terms_accepted = models.BooleanField(default=False, verbose_name="Términos aceptados")
    terms_accepted_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de aceptación")
    default_payroll_template = models.ForeignKey('UserTemplate', on_delete=models.SET_NULL, null=True, blank=True, related_name='default_for_payroll_users', verbose_name="Plantilla de nómina predeterminada")
    default_invoice_template = models.ForeignKey('UserTemplate', on_delete=models.SET_NULL, null=True, blank=True, related_name='default_for_invoice_users', verbose_name="Plantilla de factura predeterminada")
    default_delivery_note_template = models.ForeignKey('UserTemplate', on_delete=models.SET_NULL, null=True, blank=True, related_name='default_for_delivery_note_users', verbose_name="Plantilla de albarán predeterminada")
    active_company = models.ForeignKey('Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='active_for_users', verbose_name="Empresa activa")
    tokens = models.PositiveIntegerField(default=0, verbose_name="Tokens disponibles")
    stripe_email = models.EmailField(null=True, blank=True, verbose_name="Email de Stripe")

    def __str__(self):
        return str(self.user.email)

    class Meta:
        verbose_name_plural = "Perfiles de Usuarios"


class PrecontractualAcceptance(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='precontractual_acceptance')
    
    # Checkbox 1: Términos y condiciones y protección de datos
    terms_conditions_accepted = models.BooleanField(default=False, verbose_name="Aceptación de Términos y Condiciones")
    terms_conditions_accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Checkbox 2: Renuncia a derecho de desistimiento
    waiver_right_withdrawal_accepted = models.BooleanField(default=False, verbose_name="Renuncia a derecho de desistimiento")
    waiver_right_withdrawal_accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Checkbox 3: Consentimiento comunicaciones marketing
    marketing_consent_accepted = models.BooleanField(default=False, verbose_name="Consentimiento comunicaciones marketing")
    marketing_consent_accepted_at = models.DateTimeField(null=True, blank=True)
    
    # IP y fecha de la aceptación completa
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Aceptaciones precontractuales - {self.user.email}"
    
    class Meta:
        verbose_name = "Aceptación Precontractual"
        verbose_name_plural = "Aceptaciones Precontractuales"


class Company(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, null=True, blank=True)
    document_type = models.CharField(max_length=255, null=True, blank=True)
    document_number = models.CharField(max_length=255, null=True, blank=True)
    ccc = models.CharField(max_length=11, null=True, blank=True,verbose_name="Código Cuenta Cotización",help_text="Código de 11 dígitos de la Seguridad Social")
    phone = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True, verbose_name="Logo de la empresa")
    
    # Configuración de nóminas
    cnae_code = models.CharField(max_length=10, null=True, blank=True, 
                                verbose_name="CNAE", 
                                help_text="Código Nacional de Actividad Económica")
    
    # Porcentajes de Seguridad Social (valores por defecto actuales)
    ss_contingencies_percent = models.DecimalField(max_digits=5, decimal_places=2, 
                                                     null=True, blank=True,
                                                     verbose_name="% SS Empresa Contingencias Comunes")
    ss_unemployment_percent_indefinite = models.DecimalField(max_digits=5, decimal_places=2,
                                                            null=True, blank=True,
                                                            verbose_name="% SS Empresa Desempleo Indefinido")
    ss_unemployment_percent_temporal = models.DecimalField(max_digits=5, decimal_places=2,
                                                          null=True, blank=True,
                                                          verbose_name="% SS Empresa Desempleo Temporal")
    ss_training_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                             null=True, blank=True,
                                             verbose_name="% SS Empresa Formación Profesional")
    
    # Campos adicionales de Seguridad Social
    ss_mei_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                       null=True, blank=True,
                                       verbose_name="% SS Empresa MEI (Accidentes)")
    ss_fogasa_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                           null=True, blank=True,
                                           verbose_name="% SS Empresa FOGASA")
    ss_extraordinary_payments_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                                         null=True, blank=True,
                                                         verbose_name="% Prorrata Pagas Extraordinarias",
                                                         help_text="Porcentaje de prorrata de pagas extraordinarias")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Empresas"


class CompanyUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_memberships')
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='users')
    role = models.CharField(max_length=50, choices=[('admin', 'Admin'), ('staff', 'Staff')], default='staff')

    def __str__(self):
        return f"{self.user} - {self.company.name}"

    class Meta:
        verbose_name_plural = "Usuarios de Empresa"
        unique_together = ('user', 'company')


class Supplier(models.Model):
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='suppliers')
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
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
    phone = models.CharField(max_length=50, null=True, blank=True)
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
    pdf_file = models.FileField(upload_to='invoices/pdfs/', null=True, blank=True)
    invoice_number = models.CharField(max_length=50)               # Número de factura
    issue_date = models.DateField(default=timezone.now)            # Fecha de emisión
    due_date = models.DateField(null=True, blank=True)             # Fecha de vencimiento
    payment_method = models.CharField(max_length=100, null=True, blank=True)  # Forma de pago

    template_style = models.CharField(max_length=50, default='classic', blank=True, null=True, verbose_name="Estilo de plantilla")

    base_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))  # Base imponible
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # Descuento aplicado (monto)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # Descuento aplicado (porcentaje)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))   # Total de impuestos
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00')) # Total factura

    # Cuentas contables
    account_income = models.CharField(max_length=20, null=True, blank=True)
    account_customer = models.CharField(max_length=20, null=True, blank=True)
    account_vat_output = models.CharField(max_length=20, null=True, blank=True)

    notes = models.TextField(null=True, blank=True)
    is_paid = models.BooleanField(default=False, verbose_name="Pagada")  # Si se ha pagado o no
    payment_date = models.DateField(null=True, blank=True, verbose_name="Fecha de pago")  # Fecha en que se pagó
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.invoice_number} ({self.company.name})"

class SavedTemplate(models.Model):
    name = models.CharField(max_length=200, help_text="Nombre de la copia de la plantilla")
    
    # Campo JSON para el diseño visual
    design_data = models.JSONField(help_text="Datos JSON con las coordenadas y estilos")
    
    # NUEVO CAMPO: Guardar la captura de pantalla (opcional)
    screenshot = models.ImageField(upload_to='template_screenshots/', null=True, blank=True, help_text="Captura de pantalla del folio")
    
    # Metadatos (Corregido auto_now_add y auto_now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_system = models.BooleanField(default=False, help_text="Si es una plantilla de SBA (True) o del usuario (False)")

    class Meta:
        verbose_name = "Diseño de Factura"
        verbose_name_plural = "Diseños de Factura"

    def __str__(self):
        type_prefix = "[SISTEMA]" if self.is_system else "[USUARIO]"
        return f"{type_prefix} {self.name}"

# Facturas emitidas (ventas)
class SalesInvoice(BaseInvoice):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='sales_invoices')
    tokens = models.PositiveIntegerField(null=True, blank=True, default=None)
    irpf_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="% IRPF")
    irpf_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Importe IRPF")

    class Meta:
        verbose_name = "Factura enviada"
        verbose_name_plural = "Facturas enviadas"
        unique_together = ('company', 'invoice_number')


# Facturas recibidas (compras)
class PurchaseInvoice(BaseInvoice):
    supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE, related_name='purchase_invoices')

    # Cuentas específicas para facturas recibidas
    account_expense = models.CharField(max_length=20, null=True, blank=True)
    account_supplier = models.CharField(max_length=20, null=True, blank=True)
    account_vat_input = models.CharField(max_length=20, null=True, blank=True)
    tokens = models.PositiveIntegerField(null=True, blank=True, default=None)

    class Meta:
        verbose_name = "Factura recibida"
        verbose_name_plural = "Facturas recibidas"
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
    entry_number = models.IntegerField(verbose_name="Número de asiento",help_text="Número correlativo del asiento por empresa",default=1)
    date = models.DateField(default=timezone.now)                       # Fecha del asiento
    description = models.CharField(max_length=255)                      # Descripción general
    sales_invoice = models.OneToOneField('SalesInvoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='entry')
    purchase_invoice = models.OneToOneField('PurchaseInvoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='entry')
    payroll = models.OneToOneField('Payroll', on_delete=models.SET_NULL, null=True, blank=True,related_name='entry')

    debit_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    credit_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=[('draft', 'Borrador'), ('posted', 'Confirmado')], default='draft')

    created_at = models.DateTimeField(auto_now_add=True)
    tokens = models.PositiveIntegerField(null=True, blank=True, default=None)

    class Meta:
        unique_together = ('company', 'entry_number')
        ordering = ['company', '-entry_number']
        verbose_name = "Asiento Contable"
        verbose_name_plural = "Asientos Contables"

    def __str__(self):
        return f"Entry {self.id} ({self.company.name})"

    @staticmethod
    def get_next_entry_number(company):
        """
        Obtiene el siguiente número de asiento para una empresa.
        """
        last_entry = (
            AccountingEntry.objects
            .filter(company=company)
            .select_for_update()
            .order_by('-entry_number')
            .first()
        )

        if last_entry:
            return last_entry.entry_number + 1
        return 1


class AccountingEntryLine(models.Model):
    entry = models.ForeignKey('AccountingEntry', on_delete=models.CASCADE, related_name='lines')
    account_code = models.CharField(max_length=20)              # Código contable (ej: 700000, 430000, 477000)
    description = models.CharField(max_length=255)              # Descripción del movimiento
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"{self.account_code} - D:{self.debit} / C:{self.credit}"


class Employee(models.Model):
    CONTRACT_TYPES = [
        ('indefinido', 'Indefinido'),
        ('temporal', 'Temporal'),
        ('practicas', 'En Prácticas'),
        ('formacion', 'Formación'),
        ('obra', 'Obra y Servicio'),
    ]
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='employees')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    document_type = models.CharField(max_length=50)
    document_number = models.CharField(max_length=50)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    job_position = models.CharField(max_length=100, verbose_name="Categoría profesional")
    department = models.CharField(max_length=100, null=True, blank=True)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES, default='indefinido')
    hire_date = models.DateField(verbose_name="Fecha de alta")
    termination_date = models.DateField(null=True, blank=True, verbose_name="Fecha de baja")
    is_active = models.BooleanField(default=True)
    social_security_number = models.CharField(max_length=50, null=True, blank=True, verbose_name="Nº Afiliación SS")
    bank_account = models.CharField(max_length=24, null=True, blank=True,
                                    verbose_name="IBAN")
    collective_agreement = models.CharField(max_length=200, null=True, blank=True, verbose_name="Convenio colectivo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.company.name})"

    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        unique_together = ('company', 'document_number')


class Payroll(models.Model):
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='payrolls')
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='payrolls')
    pdf_file = models.FileField(upload_to='payrolls/pdfs/', null=True, blank=True)
    xml_file = models.FileField(upload_to='payrolls/xml/', null=True, blank=True)
    template_style = models.CharField(max_length=50, default='classic', blank=True, null=True, verbose_name="Estilo de plantilla")

    # Período y fechas
    period_start = models.DateField(verbose_name="Inicio período")
    period_end = models.DateField(verbose_name="Fin período")
    payment_date = models.DateField(verbose_name="Fecha de pago")
    issue_date = models.DateField(default=timezone.now, verbose_name="Fecha de emisión")

    # Devengos (ingresos)
    base_salary = models.DecimalField(max_digits=10, decimal_places=2,default=Decimal('0.00'),verbose_name="Salario base")
    salary_supplements = models.DecimalField(max_digits=10, decimal_places=2,default=Decimal('0.00'),verbose_name="Complementos salariales")
    overtime = models.DecimalField(max_digits=10, decimal_places=2,default=Decimal('0.00'),verbose_name="Horas extras")
    bonuses = models.DecimalField(max_digits=10, decimal_places=2,default=Decimal('0.00'),verbose_name="Incentivos/bonos")
    total_accrued = models.DecimalField(max_digits=10, decimal_places=2,verbose_name="Total devengado")

    # Deducciones
    social_security_employee = models.DecimalField(max_digits=10, decimal_places=2,default=Decimal('0.00'), verbose_name="SS empleado")
    irpf = models.DecimalField(max_digits=10, decimal_places=2,default=Decimal('0.00'),verbose_name="Retención IRPF")
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2,default=Decimal('0.00'),verbose_name="Otras deducciones")
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2,default=Decimal('0.00'),verbose_name="Total deducciones")

    # Líquido a percibir
    net_salary = models.DecimalField(max_digits=10, decimal_places=2,verbose_name="Líquido a percibir")

    # Seguridad Social a cargo de la empresa
    social_security_company = models.DecimalField(max_digits=10, decimal_places=2,default=Decimal('0.00'),verbose_name="SS empresa")

    # Cuentas contables (PGC español)
    account_salary_expense = models.CharField(max_length=20, null=True, blank=True,default='640',verbose_name="Cuenta sueldos y salarios")
    account_social_security_expense = models.CharField(max_length=20, null=True, blank=True,default='642',verbose_name="Cuenta SS empresa")
    account_social_security_payable = models.CharField(max_length=20, null=True, blank=True,default='476',verbose_name="Cuenta SS acreedores")
    account_irpf_payable = models.CharField(max_length=20, null=True, blank=True,default='4751',verbose_name="Cuenta IRPF")
    account_bank = models.CharField(max_length=20, null=True, blank=True, default='572', verbose_name="Cuenta bancos")

    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tokens = models.PositiveIntegerField(null=True, blank=True, default=None)

    def save(self, *args, **kwargs):
        # Validación: Total devengado = deducciones + líquido
        calculated_net = self.total_accrued - self.total_deductions
        if abs(calculated_net - self.net_salary) > Decimal('0.01'):
            from django.core.exceptions import ValidationError
            raise ValidationError(
                f"Error: Total devengado ({self.total_accrued}) - "
                f"Deducciones ({self.total_deductions}) debe ser igual a "
                f"Líquido ({self.net_salary})"
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Nómina {self.employee.first_name} {self.employee.last_name} - {self.period_start.strftime('%m/%Y')}"

    class Meta:
        verbose_name = "Nómina"
        verbose_name_plural = "Nóminas"
        ordering = ['-payment_date']
        unique_together = ('company', 'employee', 'period_start')


class BaseDeliveryNote(models.Model):
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name="%(class)s_delivery_notes")
    pdf_file = models.FileField(upload_to='delivery_notes/pdfs/', null=True, blank=True)
    delivery_note_number = models.CharField(max_length=50)  # Número de albarán
    issue_date = models.DateField(default=timezone.now)  # Fecha de emisión
    delivery_date = models.DateField(null=True, blank=True)  # Fecha de entrega/realización
    delivery_method = models.CharField(max_length=100, null=True, blank=True)  # Forma de entrega

    template_style = models.CharField(max_length=50, default='classic', blank=True, null=True, verbose_name="Estilo de plantilla")

    # Campos opcionales para albaranes con importe
    base_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # Base imponible
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # Total de impuestos
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # Total albarán

    # Estado y conversión
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pendiente facturar'),
        ('invoiced', 'Facturado'),
        ('cancelled', 'Cancelado')
    ], default='pending')

    # Relación con factura (una vez facturado)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tokens = models.PositiveIntegerField(null=True, blank=True, default=None)

    class Meta:
        abstract = True
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.delivery_note_number} ({self.company.name})"


class SalesDeliveryNote(BaseDeliveryNote):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='sales_delivery_notes')

    # Cuentas contables (para referencia futura)
    account_income = models.CharField(max_length=20, null=True, blank=True)
    account_customer = models.CharField(max_length=20, null=True, blank=True)
    account_vat_output = models.CharField(max_length=20, null=True, blank=True)

    # Relación con factura generada
    sales_invoice = models.ForeignKey('SalesInvoice', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='origin_delivery_notes')

    class Meta:
        verbose_name = "Albarán enviado"
        verbose_name_plural = "Albaranes enviados"
        unique_together = ('company', 'delivery_note_number')


class PurchaseDeliveryNote(BaseDeliveryNote):
    supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE, related_name='purchase_delivery_notes')

    # Cuentas contables (para referencia futura)
    account_expense = models.CharField(max_length=20, null=True, blank=True)
    account_supplier = models.CharField(max_length=20, null=True, blank=True)
    account_vat_input = models.CharField(max_length=20, null=True, blank=True)

    # Relación con factura generada
    purchase_invoice = models.ForeignKey('PurchaseInvoice', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='origin_delivery_notes')

    class Meta:
        verbose_name = "Albarán recibido"
        verbose_name_plural = "Albaranes recibidos"
        unique_together = ('company', 'delivery_note_number')


class DeliveryNoteLine(models.Model):
    sales_delivery_note = models.ForeignKey('SalesDeliveryNote', on_delete=models.CASCADE, related_name='lines',
                                            null=True, blank=True)
    purchase_delivery_note = models.ForeignKey('PurchaseDeliveryNote', on_delete=models.CASCADE, related_name='lines',
                                               null=True, blank=True)

    description = models.CharField(max_length=255)  # Descripción del producto/servicio
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, null=True, blank=True)  # Referencia o código

    # Campos opcionales para albaranes con importe
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                   help_text="Porcentaje de IVA, ej: 21")

    def subtotal(self):
        if self.unit_price:
            return self.quantity * self.unit_price
        return Decimal('0.00')

    def total_with_vat(self):
        if self.unit_price and self.vat_rate:
            return self.subtotal() * (1 + self.vat_rate / 100)
        return self.subtotal()

    def __str__(self):
        if self.sales_delivery_note:
            return f"{self.description} ({self.sales_delivery_note.delivery_note_number})"
        elif self.purchase_delivery_note:
            return f"{self.description} ({self.purchase_delivery_note.delivery_note_number})"
        return f"{self.description} (Sin albarán asociado)"

class UserTemplate(models.Model):
    DOCUMENT_TYPES = [
        ('invoice', 'Factura'),
        ('delivery_note', 'Albarán'),
        ('payroll', 'Nómina'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custom_templates', null=True, blank=True)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='invoice', verbose_name="Tipo de Documento")
    style_name = models.CharField(max_length=100, verbose_name="Nombre del Diseño")
    base_style = models.CharField(max_length=50, default='classic')
    custom_html = models.TextField()
    screenshot = models.ImageField(upload_to='template_screenshots/', null=True, blank=True, verbose_name="Miniatura")
    is_system_default = models.BooleanField(default=False, verbose_name="Plantilla maestra del sistema")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Comprobamos de forma segura si tiene usuario o es del sistema
        if self.is_system_default or not self.user:
            propietario = "SISTEMA"
        else:
            # Si tiene usuario, sacamos el email o el username dependiendo de tu modelo de usuario
            propietario = getattr(self.user, 'email', self.user.username)
            
        return f"[{propietario}] {self.style_name}"

    class Meta:
        verbose_name = "Plantilla de Usuario"
        verbose_name_plural = "Plantillas de Usuarios"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


class PendingRegistration(models.Model):
    token = models.UUIDField(default=_uuid.uuid4, unique=True, editable=False)
    nombre = models.CharField(max_length=255)
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField()
    password_hash = models.CharField(max_length=255)
    price_id = models.CharField(max_length=255)
    confirmed = models.BooleanField(default=False)
    link_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_email_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Registro pendiente"
        verbose_name_plural = "Registros pendientes"

    def __str__(self):
        return f"{self.email} ({'confirmado' if self.confirmed else 'pendiente'})"