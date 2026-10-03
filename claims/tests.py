from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from . import ml
from .models import Claim


class FraudScopeTests(TestCase):
    """Pruebas de punta a punta: entrena el modelo, importa el histórico y recorre las vistas."""

    @classmethod
    def setUpTestData(cls):
        if ml.load_metrics() is None:
            call_command("train_model", stdout=StringIO())
        call_command("import_claims", stdout=StringIO())

    def test_import_loads_all_claims_with_scores(self):
        self.assertEqual(Claim.objects.count(), 1000)
        self.assertFalse(Claim.objects.filter(fraud_score__lt=0).exists())
        self.assertFalse(Claim.objects.filter(fraud_score__gt=1).exists())

    def test_high_risk_tier_has_more_fraud_than_low_risk(self):
        def fraud_rate(qs):
            return qs.filter(fraud_reported=True).count() / qs.count()

        high = Claim.objects.filter(fraud_score__gte=ml.HIGH_RISK)
        low = Claim.objects.filter(fraud_score__lt=ml.MEDIUM_RISK)
        self.assertGreater(fraud_rate(high), 3 * fraud_rate(low))

    def test_major_damage_raises_the_score(self):
        claim = Claim.objects.filter(incident_severity="Minor Damage").first()
        features = claim.features()
        minor = ml.predict(features)
        major = ml.predict({**features, "incident_severity": "Major Damage"})
        self.assertGreater(major, minor)

    def test_pages_render(self):
        claim = Claim.objects.first()
        for url in [
            reverse("claims:dashboard"),
            reverse("claims:list"),
            reverse("claims:list") + "?riesgo=alto&estado=pending&orden=monto&q=Columbus",
            reverse("claims:detail", args=[claim.pk]),
            reverse("claims:evaluate"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_review_updates_status(self):
        claim = Claim.objects.first()
        response = self.client.post(
            reverse("claims:detail", args=[claim.pk]),
            {"status": Claim.Status.CONFIRMED, "notes": "Peritaje confirmó daños previos"},
        )
        self.assertRedirects(response, claim.get_absolute_url())
        claim.refresh_from_db()
        self.assertEqual(claim.status, Claim.Status.CONFIRMED)

    def _evaluate_payload(self, **overrides):
        data = {
            "policy_number": "", "age": 40, "insured_hobbies": "chess", "months_as_customer": 120,
            "policy_annual_premium": "1250.50", "policy_deductable": 1000, "incident_type": "Single Vehicle Collision",
            "collision_type": "Rear Collision", "incident_severity": "Major Damage", "authorities_contacted": "Police",
            "incident_hour_of_the_day": 3, "number_of_vehicles_involved": 1, "witnesses": 0, "bodily_injuries": 1,
            "property_damage": "NO", "police_report_available": "NO", "injury_claim": 7000,
            "property_claim": 7000, "vehicle_claim": 50000,
        }
        data.update(overrides)
        return data

    def test_evaluate_shows_result_without_saving(self):
        response = self.client.post(reverse("claims:evaluate"), self._evaluate_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["result"]["risk"], "alto")
        self.assertEqual(Claim.objects.filter(source=Claim.Source.MANUAL).count(), 0)

    def test_evaluate_can_save_claim(self):
        response = self.client.post(reverse("claims:evaluate"), self._evaluate_payload(save_claim="on"))
        claim = Claim.objects.get(source=Claim.Source.MANUAL)
        self.assertRedirects(response, claim.get_absolute_url())
        self.assertEqual(claim.total_claim_amount, 64000)
        self.assertTrue(claim.policy_number.startswith("M-"))

    def test_evaluate_rejects_invalid_hour(self):
        response = self.client.post(reverse("claims:evaluate"), self._evaluate_payload(incident_hour_of_the_day=30))
        self.assertIn("incident_hour_of_the_day", response.context["form"].errors)

    def test_default_form_values_are_valid(self):
        """El formulario precargado con el reclamo típico tiene que poder enviarse tal cual."""
        from .views import example_claim

        response = self.client.post(reverse("claims:evaluate"), self._evaluate_payload(**example_claim()))
        self.assertEqual(response.context["form"].errors, {})
        self.assertIsNotNone(response.context["result"])

    def test_explanation_adds_up_to_the_score(self):
        """Los aportes de Shapley suman la diferencia entre el score y el del reclamo típico."""
        claim = Claim.objects.filter(fraud_score__gte=ml.HIGH_RISK).first()
        features = claim.features()
        factors = ml.explain(features, top=len(ml.FEATURES))
        total = sum(f["delta"] for f in factors)
        self.assertAlmostEqual(total, ml.predict(features) - ml.baseline_score(), delta=0.03)
