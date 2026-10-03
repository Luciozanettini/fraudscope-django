import uuid

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from . import labels, ml
from .forms import EvaluateForm, ReviewForm
from .models import Claim

RISK_FILTERS = {
    "alto": Q(fraud_score__gte=ml.HIGH_RISK),
    "medio": Q(fraud_score__gte=ml.MEDIUM_RISK, fraud_score__lt=ml.HIGH_RISK),
    "bajo": Q(fraud_score__lt=ml.MEDIUM_RISK),
}

SORTS = {
    "riesgo": "-fraud_score",
    "monto": "-total_claim_amount",
    "fecha": "-incident_date",
}

OPEN_STATUSES = [Claim.Status.PENDING, Claim.Status.REVIEWING]


def dashboard(request):
    claims = Claim.objects.all()
    metrics = ml.load_metrics()
    if not claims.exists() or metrics is None:
        return render(request, "claims/empty.html")

    high = claims.filter(RISK_FILTERS["alto"])
    open_high = high.filter(status__in=OPEN_STATUSES)

    kpis = {
        "total": claims.count(),
        "fraud_rate": claims.filter(fraud_reported=True).count() / max(claims.exclude(fraud_reported=None).count(), 1),
        "high_open": open_high.count(),
        "amount_at_risk": open_high.aggregate(s=Sum("total_claim_amount"))["s"] or 0,
        "confirmed": claims.filter(status=Claim.Status.CONFIRMED).count(),
    }

    # Tasa de fraude histórica por severidad
    severity = (
        claims.exclude(fraud_reported=None)
        .values("incident_severity")
        .annotate(n=Count("id"), fraud=Count("id", filter=Q(fraud_reported=True)))
    )
    severity = sorted(severity, key=lambda r: r["fraud"] / r["n"], reverse=True)
    severity_chart = {
        "labels": [labels.SEVERITY.get(r["incident_severity"], r["incident_severity"]) for r in severity],
        "values": [round(r["fraud"] / r["n"] * 100, 1) for r in severity],
    }

    # Hobbies con mayor tasa de fraude
    hobbies = (
        claims.exclude(fraud_reported=None)
        .values("insured_hobbies")
        .annotate(n=Count("id"), fraud=Count("id", filter=Q(fraud_reported=True)))
    )
    hobbies = sorted(hobbies, key=lambda r: r["fraud"] / r["n"], reverse=True)[:8]
    hobby_chart = {
        "labels": [labels.HOBBIES.get(r["insured_hobbies"], r["insured_hobbies"]) for r in hobbies],
        "values": [round(r["fraud"] / r["n"] * 100, 1) for r in hobbies],
    }

    # Distribución de scores, separando fraudes reales de legítimos
    bins = [0] * 10, [0] * 10
    for score, fraud in claims.exclude(fraud_reported=None).values_list("fraud_score", "fraud_reported"):
        bins[1 if fraud else 0][min(int(score * 10), 9)] += 1
    score_chart = {
        "labels": [f"{i * 10}-{i * 10 + 10}%" for i in range(10)],
        "legit": bins[0],
        "fraud": bins[1],
    }

    importance = list(metrics["importance"].items())[:8]
    importance_chart = {
        "labels": [labels.FEATURES[f] for f, _ in importance],
        "values": [round(v * 100, 1) for _, v in importance],
    }

    # Qué tan bien separa el modelo: tasa real de fraude dentro de cada nivel de riesgo
    tiers = []
    for level, query in RISK_FILTERS.items():
        tier = claims.filter(query).exclude(fraud_reported=None)
        n = tier.count()
        tiers.append({
            "level": level,
            "n": n,
            "share": n / kpis["total"],
            "fraud_rate": tier.filter(fraud_reported=True).count() / n if n else 0,
        })

    context = {
        "kpis": kpis,
        "metrics": metrics,
        "tiers": tiers,
        "top_open": open_high[:6],
        "charts": {
            "severity": severity_chart,
            "hobbies": hobby_chart,
            "scores": score_chart,
            "importance": importance_chart,
        },
    }
    return render(request, "claims/dashboard.html", context)


def claim_list(request):
    claims = Claim.objects.all()
    params = request.GET

    if (risk := params.get("riesgo")) in RISK_FILTERS:
        claims = claims.filter(RISK_FILTERS[risk])
    if (status := params.get("estado")) in Claim.Status.values:
        claims = claims.filter(status=status)
    if (severity := params.get("severidad")) in labels.SEVERITY:
        claims = claims.filter(incident_severity=severity)
    if query := params.get("q", "").strip():
        claims = claims.filter(Q(policy_number__icontains=query) | Q(incident_city__icontains=query) | Q(auto_make__icontains=query))
    sort = params.get("orden", "riesgo")
    claims = claims.order_by(SORTS.get(sort, "-fraud_score"), "pk")

    summary = claims.aggregate(n=Count("id"), amount=Sum("total_claim_amount"), avg_score=Avg("fraud_score"))
    page = Paginator(claims, 20).get_page(params.get("page"))

    querystring = params.copy()
    querystring.pop("page", None)

    context = {
        "page": page,
        "summary": summary,
        "filters": {"riesgo": risk, "estado": status, "severidad": severity, "q": query, "orden": sort},
        "querystring": querystring.urlencode(),
        "status_choices": Claim.Status.choices,
        "severity_choices": labels.choices(labels.SEVERITY),
    }
    return render(request, "claims/claim_list.html", context)


def claim_detail(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    form = ReviewForm(request.POST or None, instance=claim)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Reclamo actualizado: {claim.get_status_display()}.")
        return redirect(claim)

    context = {
        "claim": claim,
        "form": form,
        "factors": ml.explain(claim.features()),
        "base_pct": round(ml.baseline_score() * 100),
    }
    return render(request, "claims/claim_detail.html", context)


def evaluate(request):
    form = EvaluateForm(request.POST or None)
    result = None

    if request.method == "POST" and form.is_valid():
        claim = form.save(commit=False)
        features = {f: form.cleaned_data[f] for f in ml.FEATURES}
        features["policy_annual_premium"] = float(features["policy_annual_premium"])
        claim.fraud_score = ml.predict(features)

        if form.cleaned_data["save_claim"]:
            claim.policy_number = claim.policy_number or f"M-{uuid.uuid4().hex[:8].upper()}"
            claim.source = Claim.Source.MANUAL
            claim.save()
            messages.success(request, "Reclamo guardado en la bandeja.")
            return redirect(claim)

        result = {
            "score": claim.fraud_score,
            "pct": round(claim.fraud_score * 100),
            "risk": ml.risk_level(claim.fraud_score),
            "factors": ml.explain(features),
            "total": claim.injury_claim + claim.property_claim + claim.vehicle_claim,
        }
    elif request.method == "GET":
        form = EvaluateForm(initial=example_claim())

    context = {"form": form, "result": result, "base_pct": round(ml.baseline_score() * 100)}
    return render(request, "claims/evaluate.html", context)


def example_claim():
    """Valores iniciales del formulario: un reclamo típico del dataset."""
    baseline = (ml.load_metrics() or {}).get("baseline", {})
    initial = dict(baseline)
    for key in ml.NUMERIC:
        if key in initial:
            initial[key] = int(round(initial[key]))
    if "policy_annual_premium" in baseline:
        initial["policy_annual_premium"] = round(baseline["policy_annual_premium"], 2)
    return initial
