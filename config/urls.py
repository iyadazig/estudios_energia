from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from estudios import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("acceso/", auth_views.LoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.inicio, name="inicio"),
    path("expedientes/nuevo/", views.expediente_nuevo, name="expediente_nuevo"),
    path("expedientes/importar/", views.expediente_importar, name="expediente_importar"),
    path("plantilla-estudio/", views.plantilla_estudio_descargar, name="plantilla_estudio"),
    path("expedientes/<int:pk>/", views.expediente_detalle, name="expediente_detalle"),
    path("expedientes/<int:pk>/importar-cups/", views.expediente_importar_puntos, name="expediente_importar_puntos"),
    path("expedientes/<int:pk>/editar/", views.expediente_editar, name="expediente_editar"),
    path("expedientes/<int:pk>/excel/", views.expediente_excel, name="expediente_excel"),
    path("expedientes/<int:pk>/pdf/", views.expediente_pdf, name="expediente_pdf"),
    path("expedientes/<int:expediente_pk>/ofertas/nueva/", views.oferta_editar, name="oferta_nueva"),
    path("expedientes/<int:expediente_pk>/ofertas/<int:pk>/", views.oferta_editar, name="oferta_editar"),
    path("expedientes/<int:expediente_pk>/ofertas/<int:pk>/borrar/", views.oferta_borrar, name="oferta_borrar"),
    path("expedientes/<int:expediente_pk>/ofertas/<int:pk>/a-catalogo/", views.oferta_a_catalogo, name="oferta_a_catalogo"),
    path("catalogo/", views.catalogo, name="catalogo"),
    path("catalogo/<int:pk>/", views.catalogo_detalle, name="catalogo_detalle"),
    path("catalogo/<int:pk>/editar/", views.catalogo_editar, name="catalogo_editar"),
    path("catalogo/<int:pk>/borrar/", views.catalogo_borrar, name="catalogo_borrar"),
    path("parametros/", views.parametros, name="parametros"),
    path("parametros/plantilla/", views.parametros_plantilla, name="parametros_plantilla"),
    path("usuarios/", views.usuarios, name="usuarios"),
    path("usuarios/nuevo/", views.usuario_nuevo, name="usuario_nuevo"),
    path("usuarios/<int:pk>/editar/", views.usuario_editar, name="usuario_editar"),
]
