import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from claims import ml
from claims.models import Claim

COLUMNS = [
    "policy_number", "age", "insured_sex", "insured_occupation", "insured_hobbies", "months_as_customer",
    "policy_state", "policy_annual_premium", "policy_deductable", "incident_date", "incident_type",
    "collision_type", "incident_severity", "authorities_contacted", "incident_state", "incident_city",
    "incident_hour_of_the_day", "number_of_vehicles_involved", "property_damage", "bodily_injuries",
    "witnesses", "police_report_available", "injury_claim", "property_claim", "vehicle_claim",
    "auto_make", "auto_model", "auto_year",
]


class Command(BaseCommand):
    help = "Importa los reclamos del CSV histórico con su score de fraude (reemplaza los ya importados)"

    def handle(self, *args, **options):
        metrics = ml.load_metrics()
        if metrics is None:
            raise CommandError("Primero entrená el modelo: python manage.py train_model")
        scores = metrics["oof_scores"]

        df = ml.load_dataset()
        df["incident_date"] = pd.to_datetime(df["incident_date"]).dt.date
        claims = []
        for row in df.to_dict("records"):
            data = {col: row[col] for col in COLUMNS}
            data["policy_number"] = str(data["policy_number"])
            claim = Claim(
                **data,
                source=Claim.Source.DATASET,
                fraud_reported=bool(row[ml.TARGET]),
                fraud_score=scores[data["policy_number"]],
            )
            claim.total_claim_amount = claim.injury_claim + claim.property_claim + claim.vehicle_claim
            claims.append(claim)

        with transaction.atomic():
            Claim.objects.filter(source=Claim.Source.DATASET).delete()
            Claim.objects.bulk_create(claims)

        self.stdout.write(self.style.SUCCESS(f"{len(claims)} reclamos importados."))
