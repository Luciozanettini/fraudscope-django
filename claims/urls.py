from django.urls import path

from . import views

app_name = "claims"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("reclamos/", views.claim_list, name="list"),
    path("reclamos/<int:pk>/", views.claim_detail, name="detail"),
    path("evaluar/", views.evaluate, name="evaluate"),
]
