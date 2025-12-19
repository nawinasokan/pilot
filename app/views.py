import json
import os
from time import time
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
from django.db.models import Count, Q, Max
from google import genai
from app.gemini.builder import build_invoice_prompt
import logging
from app.gemini.builder import build_invoice_prompt
from app.gemini.invoice_storage import store_invoice_extraction
from app.gemini.url_filter import filter_valid_invoice_urls
from app.gemini.url_filter import normalize_url
from app.gemini.client import client, GEMINI_MODEL


logger = logging.getLogger(__name__)


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
@login_required(login_url='/')
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


@login_required(login_url='/')
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

################ Upload Management ######################
def generate_batch_id():
    last_batch = UploadManagement.objects.aggregate(
        max_batch=Max("batch_id")
    )["max_batch"]
    if not last_batch:
        return "BATCH001"
    num = int(last_batch.replace("BATCH", ""))
    return f"BATCH{num + 1:03d}"


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

    qs = UploadManagement.objects.filter(created_by=request.user)

    if not qs.exists():
        return JsonResponse({"data": []})

    batches = (
        qs.values("batch_id", "file_name")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="COMPLETED")),
            failed=Count("id", filter=Q(status="FAILED")),
            created_at=Max("created_at"),
        )
        .order_by("-created_at")
    )

    data = []

    for index, b in enumerate(batches, start=1):

        if b["failed"] > 0:
            status = "FAILED"
        elif b["completed"] == b["total"]:
            status = "COMPLETED"
        else:
            status = "PROCESSING"

        data.append({
            "sl_no": index,
            "batch_id": b["batch_id"],
            "file_name": b["file_name"],
            "status": status,
            "created_at": b["created_at"].strftime("%Y-%m-%d %H:%M"),
            "created_by": request.user.username,
        })

    return JsonResponse({"data": data})

@login_required(login_url='/')
@require_POST
def upload_management_delete(request, batch_id):

    uploads = UploadManagement.objects.filter(
        batch_id=batch_id,
        created_by=request.user
    )

    if not uploads.exists():
        return JsonResponse(
            {"success": False, "message": "Batch not found"},
            status=404
        )

    upload = uploads.first()
    file_path = upload.storage_path

    uploads_root = os.path.join(settings.MEDIA_ROOT, "uploads")
    batch_folder = os.path.dirname(file_path)

    try:
        if batch_folder and batch_folder.startswith(uploads_root) and os.path.isdir(batch_folder):
            shutil.rmtree(batch_folder, ignore_errors=True)
    except Exception:
        pass 

    with transaction.atomic():
        uploads.delete()

    return JsonResponse({
        "success": True,
        "message": f"Batch {batch_id} deleted successfully"
    })

################ Invoice  Extraction ######################
@login_required(login_url="/")
def invoice_extraction(request):

    # 1️⃣ Fetch only cheap DB-level filters
    qs = (
        UploadManagement.objects
        .filter(
            status="COMPLETED",
            link_status="VALID",
            file_url__isnull=False,
        )
        .exclude(file_url="")
        .order_by("-updated_at")
    )

    valid_files = []
    invalid_files = []

    # 2️⃣ Hard validation in Python
    for f in qs:
        cleaned = normalize_url(f.file_url)
        if cleaned:
            f.file_url = cleaned  # normalize for frontend usage
            valid_files.append(f)
        else:
            invalid_files.append(f)

    # 3️⃣ Debug / audit logs
    logger.info(f"📦 Total DB candidates: {qs.count()}")
    logger.info(f"✅ Total VALID invoice URLs: {len(valid_files)}")
    logger.warning(f"❌ Skipped invalid URLs: {len(invalid_files)}")

    for f in valid_files:
        print(
            f"➡ ID={f.id} | "
            f"BATCH={f.batch_id} | "
            f"FILE={f.file_name} | "
            f"URL={f.file_url}"
        )

    return render(
        request,
        "pages/invoice_extraction.html",
        {
            "files": valid_files,
            "invalid_count": len(invalid_files),
        }
    )


@login_required(login_url="/")
@require_POST
def start_invoice_extraction(request):
    """
    Batch-level invoice extraction using Gemini (google.genai).
    """

    # ------------------ Parse Request ------------------
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "message": "Invalid JSON payload"},
            status=400,
        )

    batch_id = payload.get("batch_id")
    if not batch_id:
        return JsonResponse(
            {"success": False, "message": "batch_id is required"},
            status=400,
        )

    logger.info(f"📥 Extraction requested for batch: {batch_id}")

    # ------------------ Fetch Batch Records ------------------
    batch_files = UploadManagement.objects.filter(
        Q(batch_id=batch_id) | Q(id=batch_id)
    )

    if not batch_files.exists():
        return JsonResponse(
            {"success": False, "message": "Batch exists but has no files"},
            status=404,
        )

    # ------------------ Collect & Filter URLs ------------------
    urls = [obj.file_url for obj in batch_files if obj.file_url]
    valid_urls, invalid_urls = filter_valid_invoice_urls(urls)

    logger.info(f"📦 Total URLs in batch: {len(urls)}")
    logger.info(f"✅ Valid invoice URLs: {len(valid_urls)}")
    logger.warning(f"❌ Invalid URLs skipped: {len(invalid_urls)}")

    if not valid_urls:
        return JsonResponse(
            {
                "success": False,
                "message": "No valid invoice URLs found",
                "invalid_urls": invalid_urls,
            },
            status=400,
        )

    # ------------------ Build Prompt ------------------
    try:
        prompt = build_invoice_prompt()

    except ValueError as exc:
        logger.warning(str(exc))
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=400,
        )

    except Exception:
        logger.exception("Prompt build failed")
        return JsonResponse(
            {
                "success": False,
                "message": "Internal error while building extraction prompt",
            },
            status=500,
        )


    # ------------------ Process Each Invoice ------------------
    results = []
    batch_obj = batch_files.first()

    for url in valid_urls:
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    prompt,
                    url,   # ✅ image/PDF URL
                ]
            )

            raw_text = (response.text or "").strip()

            start = raw_text.find("{")
            end = raw_text.rfind("}")

            if start == -1 or end == -1:
                raise ValueError("Gemini returned invalid JSON")

            extracted_data = json.loads(raw_text[start:end + 1])

            record = store_invoice_extraction(
                batch=batch_obj,
                source_file_name=batch_obj.file_name,
                source_file_url=url,
                extracted_data=extracted_data,
            )

            results.append(
                {
                    "url": url,
                    "status": record.status,
                    "invoice_id": record.id,
                }
            )

        except Exception as exc:
            logger.exception(f"❌ Extraction failed for {url}")
            results.append(
                {
                    "url": url,
                    "status": "FAILED",
                    "error": str(exc),
                }
            )

    # ------------------ Final Response ------------------
    return JsonResponse(
        {
            "success": True,
            "batch_id": batch_id,
            "total_urls": len(urls),
            "valid_urls": len(valid_urls),
            "invalid_urls": invalid_urls,
            "results": results,
        },
        status=200,
    )
