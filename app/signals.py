from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Role, UserProfile, UserRole

User = get_user_model()

@receiver(post_save, sender=User)
def create_superuser_profile(sender, instance, created, **kwargs):
    if created and instance.is_superuser:
        role, _ = Role.objects.get_or_create(
            name="Admin",
            defaults={'created_by': instance}
        )
        print(f'Role "{role.name}" ready')
        profile, _ = UserProfile.objects.get_or_create(
            user=instance,
            defaults={'created_by': instance}
        )
        print('UserProfile created')

        UserRole.objects.get_or_create(
            user_profile=profile,
            role=role,
            defaults={'created_by': instance}
        )
        print('UserRole assigned successfully')