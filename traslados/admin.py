from django.contrib import admin

from .models import Activo, Area, Dispositivo, Movimiento, Responsable, Sede


class AreaInline(admin.TabularInline):
    model = Area
    extra = 1


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ciudad", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre", "ciudad")
    inlines = [AreaInline]


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "sede", "activa")
    list_filter = ("sede", "activa")
    search_fields = ("nombre",)


@admin.register(Activo)
class ActivoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "serial", "sede_actual", "area_actual", "estado", "actualizado")
    list_filter = ("sede_actual", "estado")
    search_fields = ("codigo", "nombre", "serial", "pin_uid")
    autocomplete_fields = ("area_actual",)
    readonly_fields = ("actualizado",)


@admin.register(Responsable)
class ResponsableAdmin(admin.ModelAdmin):
    list_display = ("nombre", "documento", "cargo", "tarjeta_uid", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "documento", "tarjeta_uid")


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    """Solo lectura: el historial no se edita ni se borra."""

    list_display = ("fecha", "activo", "responsable", "area_origen", "area_destino", "registrado_por")
    list_filter = ("sede_destino", "sede_origen", "fecha")
    search_fields = ("activo__codigo", "activo__nombre", "responsable__nombre")
    date_hierarchy = "fecha"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Dispositivo)
class DispositivoAdmin(admin.ModelAdmin):
    """Los celulares se autorizan desde "Registrar tags" en el propio celular.

    Aquí solo se consultan y se desactivan (celular perdido o retirado).
    """

    list_display = ("nombre", "activo", "autorizado_por", "creado", "ultimo_uso")
    list_filter = ("activo",)
    readonly_fields = ("autorizado_por", "creado", "ultimo_uso")
    fields = ("nombre", "activo", "autorizado_por", "creado", "ultimo_uso")

    def has_add_permission(self, request):
        return False
