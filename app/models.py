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


# ----------------Project Creation---------------
class Project(AuditModel):
    PROJECT_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
    ]

    name = models.CharField(max_length=255)

    code = models.CharField(
        max_length=50,
        unique=True,
        editable=False
    )

    status = models.CharField(
        max_length=20,
        choices=PROJECT_STATUS_CHOICES
    )

    storage_path = models.CharField(
        max_length=500,
        editable=False
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.code})"

# ----------------Batch Creation---------------
class Batch(AuditModel):
    BATCH_STATUS_CHOICES = [
        ('PROCESSING', 'Processing'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='batches'
    )

    batch_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="e.g. upload_20240115_143022"
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_batches'
    )

    original_zip_path = models.CharField(max_length=500)
    duplicate_images = models.PositiveIntegerField(default=0)
    total_images = models.PositiveIntegerField(default=0)
    completed_count = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=BATCH_STATUS_CHOICES,
        default='PROCESSING'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.batch_id

