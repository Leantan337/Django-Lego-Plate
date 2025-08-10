from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from django.views.generic.base import RedirectView
from . import views


urlpatterns = [
    path("admin/", admin.site.urls),
    # DRF auth
    path("api/auth/", include("rest_framework.urls")),
    # allauth
    path("accounts/", include("allauth.urls")),
    # Redirect legacy profile URL to docs
    path("accounts/profile/", RedirectView.as_view(url="/api/docs/", permanent=False)),
    # Landing & UI pages
    path("", views.home, name="home"),
    path("bricks/", views.bricks_catalog, name="bricks-catalog"),
    path("system/", views.system_status, name="system-status"),
    path("demo/", views.demo, name="demo"),
    path("blog/", include("blog.urls")),
# OpenAPI schema and docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]


