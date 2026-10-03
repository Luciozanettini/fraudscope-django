from django.contrib import admin

from .models import Claim


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ["policy_number", "incident_severity", "total_claim_amount", "fraud_score", "status", "source"]
    list_filter = ["status", "source", "incident_severity"]
    search_fields = ["policy_number", "incident_city"]
