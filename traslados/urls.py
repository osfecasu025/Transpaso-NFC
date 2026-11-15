from django.urls import path

from . import views

urlpatterns = [
    path("", views.escanear, name="escanear"),
    path("api/responsable/<str:uid>/", views.api_responsable, name="api_responsable"),
    path("api/activo/<str:uid>/", views.api_activo, name="api_activo"),
    path("api/sedes/", views.api_sedes, name="api_sedes"),
    path("api/traslados/", views.api_traslado, name="api_traslado"),
    # Registro de tags (solo administradores)
    path("registrar/", views.registrar, name="registrar"),
    path("autorizar-celular/", views.autorizar, name="autorizar"),
    path("api/uid/<str:uid>/", views.api_uid, name="api_uid"),
    path("api/buscar/<str:tipo>/", views.api_buscar, name="api_buscar"),
    path("api/asociar/", views.api_asociar, name="api_asociar"),
]
