from app.views import *
from django.urls import path

urlpatterns = [
    path('', LoginView, name='login_view'),
    path('logout/', LogoutView, name='logout_view'),

    path('dashboard/', dashboard_view, name='dashboard'),

    path('role-management/', role_management, name='role_management'),
    path('role-management/delete/<int:id>/', delete_role, name='delete_role'),
    path('role-management/update/', update_role, name='update_role'),

    path('user_management/', user_management, name='user_management'),
    path('user-management/update/', update_user, name='update_user'),
    path('user-management/delete/<int:user_id>/', delete_user, name='delete_user'),

    path('menu-management/', menu_management, name='menu_management'),
    path('menu-permissions/user/get/<int:user_id>/', get_user_menu_permissions, name='get_user_menu_permissions'),
    path('menu-permissions/user/update/', update_user_menu_permissions, name='update_user_menu_permissions'),
    path('menu-permissions/user/delete/', delete_user_all_menus, name='delete_user_all_menus'),

    path("uploads/", upload_management_page, name="upload_management"),    
    path("preview_file_headers/", preview_file_headers, name="preview_file_headers"),
    path("uploads/create/", create_upload_management, name="create_upload_management"),  
    path("uploads/list/", upload_management_list_api, name="upload_management_list_api"),
    path("uploads/delete/<str:batch_id>/",upload_management_delete,name="upload_management_delete"),

    path("custom-field-mapping/", custom_field_mapping, name="custom_field_mapping"),
    path("custom-field/update/", update_custom_field, name="update_custom_field"),
    path("custom-field/delete/<int:field_id>/", delete_custom_field, name="delete_custom_field"),

    path("invoice-extraction/", invoice_extraction, name="invoice_extraction"), 
    path(
        'api/invoice-extraction/start/',
        start_invoice_extraction,
        name='start_invoice_extraction'
    ),
    path(
        "api/invoice-extraction/list/",
        invoice_extraction_list,
        name="invoice_extraction_list",
    ),

    path(
    "api/invoice-extraction/delete/<int:invoice_id>/",
    delete_invoice_extraction,
    name="delete_invoice_extraction"
),
]