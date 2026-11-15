from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Inventario – Traslados NFC"
admin.site.site_title = "Traslados NFC"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("traslados.urls")),
]
