from django.contrib.auth import get_user_model
from django.db import models

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








