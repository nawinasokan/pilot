from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import RegexValidator
from crum import get_current_user

# -----------------TimeStamp------------------
class AuditModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created"
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.pk and not self.created_by:
            user = get_current_user()
            if user and user.is_authenticated:
                self.created_by = user
        super().save(*args, **kwargs)

# -----------------Super User------------------
class User(AbstractUser, AuditModel):
    location = models.CharField(max_length=150)

    def __str__(self):
        return self.username

# -----------------Role------------------
class Role(AuditModel):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

# -----------------User Management------------------
class UserProfile(AuditModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    def __str__(self):
        return self.user.username


class UserRole(AuditModel):
    user_profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )

    class Meta:
        unique_together = ('user_profile', 'role')

    def __str__(self):
        return f"{self.user_profile.user.username} - {self.role.name}"

# -----------------Menu Management------------------
class Menu(AuditModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class UserMenuPermission(AuditModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='menu_permissions'
    )
    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name='user_permissions'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'menu')

    def __str__(self):
        return f"{self.user.username} -> {self.menu.name}"



# ----------------Custom Extraction Fields---------------

class CustomExtractionField(AuditModel):
    FIELD_TYPES = [
        ('string', 'Text'),
        ('number', 'Numeric/Amount'),
        ('date', 'Date'),
        ('boolean', 'Yes/No'),
    ]
    name = models.CharField(max_length=100, help_text="Internal key name (e.g., gstin_number)")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='string')
    is_required = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.field_type})"
    
# ----------------Upload Management-------------------
class UploadManagement(AuditModel):
    BATCH_STATUS_CHOICES = [
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    LINK_STATUS_CHOICES = [
        ('PENDING', 'Pending Validation'),
        ('VALID', 'Valid Link'),
        ('DUPLICATE', 'Duplicate Link'),
        ('INVALID', 'Invalid Link'),
    ]

    batch_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="e.g. BATCH001"
    )

    file_name = models.CharField(max_length=255)
    file_url = models.URLField(max_length=500, null=True, blank=True, db_index=True)

    storage_path = models.CharField(
        max_length=500,
        editable=False,
        help_text="s3://bucket/key.xlsx",
        null=True, blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=BATCH_STATUS_CHOICES,
        default='PROCESSING',
        null=True, blank=True
    )

    link_status = models.CharField(
        max_length=20,
        choices=LINK_STATUS_CHOICES,
        default='PENDING',
        db_index=True,
        null=True, blank=True
    )

    class Meta:
        db_table = 'upload_management'
        verbose_name_plural = "Upload Management"
        indexes = [
            models.Index(fields=['batch_id', 'link_status']),
        ]

# ------------------- Invoice Extraction -------------------
class InvoiceExtraction(AuditModel):
    EXTRACTION_STATUS_CHOICES = [
        ("PROCESSING", "Processing"),
        ("SUCCESS", "Success"),
        ("DUPLICATE", "Duplicate"),
        ("FAILED", "Failed"),
    ]

    batch = models.ForeignKey(
        UploadManagement,
        on_delete=models.CASCADE,
        related_name="extractions",
        db_index=True
    )

    source_file_name = models.CharField(
        max_length=255,
        help_text="Source Excel name"
    )

    source_file_url = models.URLField(
        max_length=500,
        help_text="URL"
    )

    invoice_no = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True
    )

    invoice_supplier_gstin_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True
    )

    invoice_date = models.DateField(
        null=True,
        blank=True,
        db_index=True
    )

    invoice_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )

    duplicate_fingerprint = models.CharField(
        max_length=255,
        help_text="Hash(invoice_no + gstin + date + amount)"
    )


    extracted_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw Gemini / LLM extraction output"
    )

    attempt_count = models.PositiveSmallIntegerField(
        default=1,
        help_text="Number of LLM attempts"
    )

    tota_count = models.PositiveSmallIntegerField(
        default=1,
        help_text="Number of Input"
    )

    last_error = models.TextField(
        null=True,
        blank=True,
        help_text="Last extraction error if failed"
    )

    status = models.CharField(
        max_length=20,
        choices=EXTRACTION_STATUS_CHOICES,
        default="PROCESSING",
        db_index=True
    )

    class Meta:
        db_table = "invoice_extractions"

        constraints = [
            models.UniqueConstraint(
                fields=["duplicate_fingerprint"],
                name="uniq_invoice_fingerprint"
            )
        ]

        indexes = [
            models.Index(fields=["batch", "status"]),
            models.Index(fields=["invoice_no"]),
            models.Index(fields=["invoice_supplier_gstin_number"]),
            models.Index(fields=["invoice_date"]),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_no or 'UNKNOWN'} ({self.status})"