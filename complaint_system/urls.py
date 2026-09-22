from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('complaints.urls')),
]

handler403 = 'complaints.views.handler403'
handler404 = 'complaints.views.handler404'
handler500 = 'complaints.views.handler500'
