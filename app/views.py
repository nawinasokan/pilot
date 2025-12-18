import json
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from app.models import *
from django.http import JsonResponse 
from django.contrib import messages
from django.contrib.auth.hashers import make_password 
from django.db import transaction 
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_http_methods
from django.db.models import Min, Max
import re
import shutil
import pandas as pd
from .thread_utils import run_in_thread
from .services import process_uploaded_file

User = get_user_model()


#################### Login/Logout ######################
def LoginView(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(
            request,
            username=username,
            password=password
        )
        if not user:
            return render(
                request,
                'registration/login.html',
                {'error_message': 'Invalid username or password'}
            )
        login(request, user)
        return redirect('dashboard')
    return render(request, 'registration/login.html')

@require_POST
def LogoutView(request):
    logout(request)
    return redirect('login_view')

#################### Dashboard ######################
@login_required
def dashboard_view(request):
    return render(request, 'dashboard.html')


#################### Role Management ######################
@login_required(login_url='/')
def role_management(request):
    if request.method == 'POST':
        role_name = request.POST.get('role_name')
        if role_name:
            if Role.objects.filter(name__iexact=role_name).exists():
                messages.error(request, f'Role "{role_name}" already exists.')
            else:
                Role.objects.create(name=role_name, created_by=request.user)
                messages.success(request, f'Role "{role_name}" created successfully.')
        else:
            messages.error(request, 'Role name cannot be empty.')
        return redirect('role_management')

    roles = Role.objects.all().order_by('created_at')
    return render(request, 'pages/role_management.html', {'roles': roles})

@login_required(login_url='/')
def update_role(request):
    if request.method == 'POST':
        role_id = request.POST.get('role_id')
        new_name = request.POST.get('role_name')

        try:
            role = get_object_or_404(Role, id=role_id)
            role.name = new_name
            role.save()
            messages.success(request, 'Role updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating role: {e}')
    
    return redirect('role_management')

@login_required(login_url='/')
def delete_role(request, id):
    try:
        role = get_object_or_404(Role, id=id)
        role.delete()
        messages.success(request, 'Role deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting role: {e}')
    
    return redirect('role_management')


#################### User Management ######################
@login_required(login_url='/')
def user_management(request):

    if request.method == 'POST':
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        location = request.POST.get('location')
        role_name = request.POST.get('role')

        if not all([username, first_name, last_name, email, location, role_name]):
            error_msg = 'All fields are required.'
            if is_ajax:
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('user_management')

        try:
            role = Role.objects.get(name__iexact=role_name)

            if User.objects.filter(email=email).exclude(username=username).exists():
                error_msg = 'Email already exists.'
                if is_ajax:
                    return JsonResponse({'error': error_msg}, status=400)
                messages.error(request, error_msg)
                return redirect('user_management')

            user = User.objects.filter(username=username).first()

            if user:
                if not user.is_active:
                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = email
                    user.location = location
                    user.is_active = True
                    user.save()
                    success_msg = f'User {username} reactivated successfully.'
                else:
                    error_msg = 'Username already exists.'
                    if is_ajax:
                        return JsonResponse({'error': error_msg}, status=400)
                    messages.error(request, error_msg)
                    return redirect('user_management')

            else:
                user = User.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    location=location,
                    password='Admin@123#'
                )
                user.created_by = request.user
                user.save()
                success_msg = f'User {username} created successfully.'

            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={'created_by': request.user}
            )

            UserRole.objects.update_or_create(
                user_profile=profile,
                defaults={'role': role, 'created_by': request.user}
            )

            if is_ajax:
                return JsonResponse({'message': success_msg}, status=200)
            else:
                messages.success(request, success_msg)
                return redirect('user_management')

        except Role.DoesNotExist:
            error_msg = 'Invalid role selected.'
            if is_ajax:
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('user_management')

        except Exception as e:
            if is_ajax:
                return JsonResponse({'error': str(e)}, status=500)
            raise

    user_profiles = (
        UserProfile.objects
        .select_related('user')
        .prefetch_related('user_roles__role')
        .filter(user__is_active=True)
        .order_by('id')
    )

    roles = Role.objects.all().order_by('created_at')

    return render(request, 'pages/user_management.html', {
        'user_profiles': user_profiles,
        'roles': roles
    })

@login_required(login_url='/')
@require_http_methods(["POST"])
def update_user(request):
    try:
        user_id = request.POST.get('user_id')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        location = request.POST.get('location')
        role_name = request.POST.get('role')

        with transaction.atomic():
            user = get_object_or_404(User, id=user_id)
            user.first_name = first_name
            user.last_name = last_name
            user.location = location
            
            if User.objects.filter(email=email).exclude(id=user_id).exists():
                 return JsonResponse({'error': 'Email already exists for another user.'}, status=400)
            user.email = email
            user.save()

            new_role = get_object_or_404(Role, name=role_name)
            
            profile = get_object_or_404(UserProfile, user=user)

            UserRole.objects.update_or_create(
                user_profile=profile,
                defaults={'role': new_role, 'created_by': request.user}
            )

        return JsonResponse({'message': 'User updated successfully.'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



@login_required(login_url="/")
def delete_user(request, user_id):
    if request.method == "POST":
        try:
            user = get_object_or_404(User, id=user_id)
            user.is_active = False
            user.save(update_fields=["is_active"])
            UserMenuPermission.objects.filter(user=user).delete()
            UserRole.objects.filter(user_profile__user=user).delete()
            return JsonResponse({"message": "User deactivated and access removed successfully."})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid method"}, status=400)

####################### MENU MANAGEMENT #########################
@login_required(login_url='/')
def user_menu_permissions(request):
    allowed_menus = []
    is_admin = False

    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.profile.user_roles.filter(role__name__iexact='Admin').exists():
            is_admin = True
        
        else:
            try:
                allowed_menus = UserMenuPermission.objects.filter(
                    user=request.user
                ).values_list('menu__name', flat=True)
                allowed_menus = list(allowed_menus)
            except Exception as e:
                print(f"Menu Context Error: {e}")
                allowed_menus = []

    return {'allowed_menus': allowed_menus, 'is_admin': is_admin}

@login_required(login_url='/')
def menu_management(request):

    SYSTEM_MENUS = [
        'Dashboard',
        'Role Management',
        'User Management',
        'Menu Permission',
        'Upload Management',
        'Custom Field Mapping',
        'Invoice Extraction',
    ]

    for menu_name in SYSTEM_MENUS:
        Menu.objects.get_or_create(
            name=menu_name,
            defaults={'created_by': request.user}
        )

    menus = Menu.objects.all().order_by('name')

    users = (
        User.objects
        .filter(is_active=True, is_superuser=False)
        .exclude(profile__user_roles__role__name__iexact='Admin')
        .distinct()
        .order_by('username')
    )

    return render(request, 'pages/menu_permission.html', {
        'menus': menus,
        'users': users
    })

@login_required(login_url='/')
def get_user_menu_permissions(request, user_id):
    
    user = get_object_or_404(User, id=user_id)

    if user.is_superuser:
        all_menus = Menu.objects.all()
        
        return JsonResponse({
            "user_id": user.id,
            "username": user.username,
            "assigned_at": user.date_joined.strftime("%d %b %Y"), 
            "created_by": "System (Admin Access)",
            "menu_ids": list(all_menus.values_list("id", flat=True)),
            "menus": [{"name": m.name} for m in all_menus]
        })

    qs = (
        UserMenuPermission.objects
        .filter(user_id=user_id)
        .select_related("menu", "user", "created_by")
        .order_by("created_at")
    )

    if not qs.exists():
        return JsonResponse({
            "user_id": user_id,
            "username": user.username,
            "assigned_at": "",
            "created_by": "",
            "menu_ids": [],
            "menus": []
        })

    first_perm = qs.first()

    return JsonResponse({
        "user_id": user_id,
        "username": user.username,
        "is_admin": user.is_superuser,
        "assigned_at": first_perm.created_at.strftime("%d %b %Y"),
        "created_by": first_perm.created_by.username if first_perm.created_by else "",
        "menu_ids": list(qs.values_list("menu_id", flat=True)),
        "menus": [
            {"name": p.menu.name}
            for p in qs
        ]
    })


@login_required(login_url='/')
@require_POST
def update_user_menu_permissions(request):
    try:
        user_id = request.POST.get('user_id')
        selected_menu_ids = request.POST.getlist('menu_ids[]')
        selected_menu_ids = [int(mid) for mid in selected_menu_ids] 

        target_user = get_object_or_404(User, id=user_id)

        if target_user.is_superuser:
            return JsonResponse({
                'error': 'Admin permissions cannot be modified'
            }, status=403)

        current_perms = UserMenuPermission.objects.filter(user=target_user)
        current_ids = set(current_perms.values_list('menu_id', flat=True))
        new_ids = set(selected_menu_ids)

        to_add = new_ids - current_ids
        for menu_id in to_add:
            UserMenuPermission.objects.create(user=target_user, menu_id=menu_id, created_by=request.user)

        to_remove = current_ids - new_ids
        if to_remove:
            UserMenuPermission.objects.filter(user=target_user, menu_id__in=to_remove).delete()

        return JsonResponse({'message': f'Permissions updated for {target_user.username}'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required(login_url='/')
@require_POST
def delete_user_all_menus(request):
    user_id = request.POST.get('user_id')
    target_user = get_object_or_404(User, id=user_id)

    if target_user.is_superuser:
        return JsonResponse({
            'error': 'Admin menus cannot be deleted'
        }, status=403)

    UserMenuPermission.objects.filter(user=target_user).delete()
    return JsonResponse({'success': True})



# #################### Custom Field Mapping ######################


@login_required
def custom_field_mapping(request):
    if request.method == "POST":
        name = request.POST.get("field_name")
        field_type = request.POST.get("field_type")
        is_required = request.POST.get("is_required") == "required"

        if CustomExtractionField.objects.filter(name=name).exists():
            return JsonResponse({"error": "Field already exists"}, status=400)

        CustomExtractionField.objects.create(
            name=name,
            field_type=field_type,
            is_required=is_required
        )

        return JsonResponse({"success": True})

    fields = CustomExtractionField.objects.all().order_by("-created_at")
    for field in fields:
        print(field.name, field.field_type, field.is_required, field.created_at)
    return render(request, "pages/custom_field_mapping.html", {
        "fields": fields,
        "field_types": CustomExtractionField.FIELD_TYPES
    })


@login_required
def update_custom_field(request):
    if request.method == "POST":
        field_id = request.POST.get("id")
        field = get_object_or_404(CustomExtractionField, id=field_id)

        field.name = request.POST.get("field_name")
        field.field_type = request.POST.get("field_type")
        field.is_required = request.POST.get("is_required") == "required"
        field.save()

        return JsonResponse({"success": True})

@login_required
def delete_custom_field(request, field_id):
    field = get_object_or_404(CustomExtractionField, id=field_id)
    field.delete()
    return JsonResponse({"success": True})


def generate_batch_id():
    
    last_batch = UploadManagement.objects.aggregate(
        max_batch=Max("batch_id")
    )["max_batch"]

    if not last_batch:
        return "BATCH001"

    num = int(last_batch.replace("BATCH", ""))
    return f"BATCH{num + 1:03d}"


def safe_folder_name(name):
    return "".join(c for c in name if c.isalnum() or c in ("_", "-"))


@login_required(login_url="/")
def preview_file_headers(request):
    upload_file = request.FILES.get("file")
    if not upload_file:
        return JsonResponse({"success": False, "message": "File required"}, status=400)

    ext = upload_file.name.split(".")[-1].lower()
    try:
        if ext == "csv":
            df = pd.read_csv(upload_file, nrows=0)
        elif ext in ["xlsx", "xls"]:
            print("SSSSSS")
            df = pd.read_excel(upload_file, nrows=0)
            print(df.columns)
        else:
            return JsonResponse({"success": False, "message": "Unsupported file"})

        headers = list(df.columns)

        return JsonResponse({
            "success": True,
            "headers": headers
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)














################ Project Creation ######################

@login_required(login_url="/")
def upload_management_page(request):
    uploads = UploadManagement.objects.order_by("-created_at")
    return render(request, "pages/upload_management.html", {
        "uploads": uploads
    })



@login_required(login_url="/")
@require_POST
def create_upload_management(request):
    upload_file = request.FILES.get("file")
    selected_header = request.POST.get("selected_header")

    if not upload_file or not selected_header:
        return JsonResponse({
            "success": False,
            "message": "File and header selection required"
        }, status=400)

    batch_id = generate_batch_id()

    batch_folder = os.path.join(
        settings.MEDIA_ROOT,
        "uploads",
        batch_id
    )
    os.makedirs(batch_folder, exist_ok=True)

    file_path = os.path.join(batch_folder, upload_file.name)

    with open(file_path, "wb+") as dest:
        for chunk in upload_file.chunks():
            dest.write(chunk)

    upload_obj = UploadManagement.objects.create(
        batch_id=batch_id,
        file_name=upload_file.name,
        file_url=selected_header,  
        storage_path=file_path,
        status="PROCESSING",
        link_status="VALID",
        created_by=request.user
    )

    run_in_thread(process_uploaded_file, upload_obj.id)

    return JsonResponse({
        "success": True,
        "message": "Upload started",
        "batch_id": batch_id
    }, status=201)



@login_required(login_url='/')
def upload_management_list_api(request):
    uploads = (
        UploadManagement.objects
        .order_by("batch_id", "-created_at")
        .distinct("batch_id")
    )

    data = []
    for i, p in enumerate(uploads, start=1):
        data.append({
            "id": p.id,                    
            "batch_id": p.batch_id,
            "sl_no": i,
            "file_name": p.file_name,
            "status": p.status,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M"),
            "created_by": p.created_by.username if p.created_by else "-",
        })

    return JsonResponse({"data": data})


@login_required(login_url='/')
@require_POST
def upload_management_delete(request, upload_id):

    upload = get_object_or_404(UploadManagement, id=upload_id)
    batch_id = upload.batch_id

    file_path = upload.storage_path
    batch_folder = os.path.dirname(file_path)
    uploads_root = os.path.join(settings.MEDIA_ROOT, "uploads")

    try:
        if batch_folder.startswith(uploads_root) and os.path.isdir(batch_folder):
            shutil.rmtree(batch_folder, ignore_errors=True)
    except Exception:
        pass 

    with transaction.atomic():
        UploadManagement.objects.filter(batch_id=batch_id).delete()

    return JsonResponse({
        "success": True,
        "message": f"Batch {batch_id} deleted successfully"
    })




################ Invoice ######################
@login_required(login_url='/')
def invoice_extraction(request):
    return render(request, "pages/invoice_extraction.html")