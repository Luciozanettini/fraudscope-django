from django.db import models
from django.urls import reverse

from . import labels, ml


class Claim(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        REVIEWING = "reviewing", "En revisión"
        CLEARED = "cleared", "Legítimo"
        CONFIRMED = "confirmed", "Fraude confirmado"

    class Source(models.TextChoices):
        DATASET = "dataset", "Dataset histórico"
        MANUAL = "manual", "Carga manual"

    policy_number = models.CharField("N° de póliza", max_length=20, unique=True)
    source = models.CharField("Origen", max_length=10, choices=Source.choices, default=Source.MANUAL)

    # Asegurado
    age = models.PositiveSmallIntegerField("Edad")
    insured_sex = models.CharField("Sexo", max_length=10, blank=True)
    insured_occupation = models.CharField("Ocupación", max_length=40, blank=True)
    insured_hobbies = models.CharField("Hobby", max_length=30, choices=labels.choices(labels.HOBBIES))
    months_as_customer = models.PositiveIntegerField("Antigüedad como cliente (meses)")

    # Póliza
    policy_state = models.CharField("Estado de la póliza", max_length=5, blank=True)
    policy_annual_premium = models.DecimalField("Prima anual", max_digits=10, decimal_places=2)
    policy_deductable = models.PositiveIntegerField("Franquicia")

    # Incidente
    incident_date = models.DateField("Fecha del incidente", null=True, blank=True)
    incident_type = models.CharField("Tipo de incidente", max_length=40, choices=labels.choices(labels.INCIDENT_TYPE))
    collision_type = models.CharField("Tipo de colisión", max_length=30, choices=labels.choices(labels.COLLISION_TYPE))
    incident_severity = models.CharField("Severidad", max_length=30, choices=labels.choices(labels.SEVERITY))
    authorities_contacted = models.CharField("Autoridad contactada", max_length=20, choices=labels.choices(labels.AUTHORITIES))
    incident_state = models.CharField("Estado del incidente", max_length=5, blank=True)
    incident_city = models.CharField("Ciudad", max_length=40, blank=True)
    incident_hour_of_the_day = models.PositiveSmallIntegerField("Hora del incidente")
    number_of_vehicles_involved = models.PositiveSmallIntegerField("Vehículos involucrados")
    property_damage = models.CharField("Daño a la propiedad", max_length=10, choices=labels.choices(labels.YES_NO))
    bodily_injuries = models.PositiveSmallIntegerField("Lesionados")
    witnesses = models.PositiveSmallIntegerField("Testigos")
    police_report_available = models.CharField("Denuncia policial", max_length=10, choices=labels.choices(labels.YES_NO))

    # Montos
    injury_claim = models.PositiveIntegerField("Monto por lesiones")
    property_claim = models.PositiveIntegerField("Monto por propiedad")
    vehicle_claim = models.PositiveIntegerField("Monto por vehículo")
    total_claim_amount = models.PositiveIntegerField("Monto total reclamado")

    # Vehículo
    auto_make = models.CharField("Marca", max_length=30, blank=True)
    auto_model = models.CharField("Modelo", max_length=30, blank=True)
    auto_year = models.PositiveSmallIntegerField("Año", null=True, blank=True)

    # Resultado
    fraud_reported = models.BooleanField("Fraude reportado (histórico)", null=True, blank=True)
    fraud_score = models.FloatField("Probabilidad de fraude", db_index=True)
    status = models.CharField("Estado", max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    notes = models.TextField("Notas del auditor", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fraud_score"]
        verbose_name = "reclamo"
        verbose_name_plural = "reclamos"

    def __str__(self):
        return f"Póliza {self.policy_number}"

    def get_absolute_url(self):
        return reverse("claims:detail", args=[self.pk])

    def save(self, *args, **kwargs):
        self.total_claim_amount = self.injury_claim + self.property_claim + self.vehicle_claim
        super().save(*args, **kwargs)

    @property
    def risk(self):
        return ml.risk_level(self.fraud_score)

    @property
    def score_pct(self):
        return round(self.fraud_score * 100)

    def features(self):
        """Variables que usa el modelo, en el formato que espera `ml.predict`."""
        data = {f: getattr(self, f) for f in ml.FEATURES}
        data["policy_annual_premium"] = float(self.policy_annual_premium)
        return data
