from django import forms

from .models import Claim

INPUT = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT)
            if isinstance(field, forms.ChoiceField) and field.choices and field.choices[0][0] == "":
                field.choices = [("", "Elegí una opción")] + list(field.choices)[1:]


class EvaluateForm(StyledFormMixin, forms.ModelForm):
    """Formulario para evaluar un reclamo nuevo con el modelo."""

    save_claim = forms.BooleanField(
        label="Guardar el reclamo en la bandeja",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded border-slate-300 text-indigo-600"}),
    )

    # Grupos para dibujar el formulario por secciones
    SECTIONS = [
        ("Incidente", ["incident_type", "collision_type", "incident_severity", "authorities_contacted",
                       "incident_hour_of_the_day", "number_of_vehicles_involved", "witnesses", "bodily_injuries",
                       "property_damage", "police_report_available"]),
        ("Montos reclamados", ["injury_claim", "property_claim", "vehicle_claim"]),
        ("Asegurado y póliza", ["age", "insured_hobbies", "months_as_customer", "policy_annual_premium",
                                "policy_deductable", "policy_number"]),
    ]

    class Meta:
        model = Claim
        fields = [
            "policy_number", "age", "insured_hobbies", "months_as_customer", "policy_annual_premium",
            "policy_deductable", "incident_type", "collision_type", "incident_severity", "authorities_contacted",
            "incident_hour_of_the_day", "number_of_vehicles_involved", "witnesses", "bodily_injuries",
            "property_damage", "police_report_available", "injury_claim", "property_claim", "vehicle_claim",
        ]
        help_texts = {"policy_number": "Opcional. Si lo dejás vacío se genera uno automáticamente."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["policy_number"].required = False
        self.fields["incident_hour_of_the_day"].widget.attrs.update(min=0, max=23)

    def clean_policy_number(self):
        value = self.cleaned_data.get("policy_number", "").strip()
        if value and Claim.objects.filter(policy_number=value).exists():
            raise forms.ValidationError("Ya existe un reclamo con ese número de póliza.")
        return value

    def clean_incident_hour_of_the_day(self):
        hour = self.cleaned_data["incident_hour_of_the_day"]
        if hour > 23:
            raise forms.ValidationError("La hora debe estar entre 0 y 23.")
        return hour

    def sections(self):
        return [(title, [self[name] for name in names]) for title, names in self.SECTIONS]


class ReviewForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Claim
        fields = ["status", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Ej: se pidió peritaje del vehículo"})}
