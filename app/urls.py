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

    path("projects/", project_management_page, name="project_management"),    
    path("projects/create/", create_project_management, name="create_project_management"),  
    path("projects/list/", project_management_list_api, name="project_management_list_api"),
    path("projects/edit/<int:project_id>/", project_management_edit, name="project_management_edit"),
    path("projects/delete/<int:project_id>/", project_management_delete, name="project_management_delete"),




    path("invoice-extraction/", invoice_extraction, name="invoice_extraction"), 
]