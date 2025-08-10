from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from django.views.generic.base import RedirectView


urlpatterns = [
    path("admin/", admin.site.urls),
    # DRF auth
    path("api/auth/", include("rest_framework.urls")),
    # allauth
    path("accounts/", include("allauth.urls")),
    # Redirect legacy profile URL to docs
    path("accounts/profile/", RedirectView.as_view(url="/api/docs/", permanent=False)),
    # OpenAPI schema and docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]


