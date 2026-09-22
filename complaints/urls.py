from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboards
    path('', views.dashboard_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/admin/', views.admin_dashboard_view, name='admin_dashboard'),
    path('dashboard/user/', views.user_dashboard_view, name='user_dashboard'),

    # Complaints
    path('complaints/', views.complaint_list_view, name='complaint_list'),
    path('complaints/create/', views.complaint_create_view, name='complaint_create'),
    path('complaints/<str:complaint_id>/', views.complaint_detail_view, name='complaint_detail'),
    path('complaints/<str:complaint_id>/status/', views.complaint_status_update_view, name='complaint_status_update'),
    path('complaints/<str:complaint_id>/escalate/', views.complaint_escalate_view, name='complaint_escalate'),
    path('complaints/<str:complaint_id>/assign/', views.complaint_assign_view, name='complaint_assign'),
    path('complaints/<str:complaint_id>/priority/', views.complaint_priority_update_view, name='complaint_priority_update'),
    path('complaints/<str:complaint_id>/respond/', views.complaint_response_view, name='complaint_response'),
    path('complaints/<str:complaint_id>/reopen/', views.complaint_reopen_view, name='complaint_reopen'),
    path('complaints/<str:complaint_id>/delete/', views.complaint_delete_view, name='complaint_delete'),

    # Categories (Admin)
    path('categories/', views.category_list_view, name='category_list'),
    path('categories/create/', views.category_create_view, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit_view, name='category_edit'),
    path('categories/<int:pk>/toggle/', views.category_toggle_active_view, name='category_toggle_active'),

    # Users (Admin)
    path('users/', views.user_list_view, name='user_list'),
    path('users/create/', views.user_create_view, name='user_create'),
    path('users/<int:user_id>/', views.user_detail_view, name='user_detail'),
    path('users/<int:user_id>/toggle/', views.user_toggle_active_view, name='user_toggle_active'),
    path('users/<int:user_id>/delete/', views.user_delete_view, name='user_delete'),

    # Reports (Admin)
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/', views.reports_export_csv_view, name='reports_export_csv'),

    # Profile & Security
    path('profile/', views.profile_view, name='profile'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
]
