from django import template

from claims import labels

register = template.Library()


@register.filter
def money(value):
    """Formatea un monto con separador de miles al estilo argentino: $ 52.080"""
    try:
        return "$ " + f"{int(round(float(value))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


@register.filter
def money_short(value):
    """Monto abreviado para tarjetas: $ 18,1 M"""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(value) >= 1_000_000:
        return "$ " + f"{value / 1_000_000:.1f}".replace(".", ",") + " M"
    return money(value)


@register.filter
def pct(value, decimals=0):
    try:
        return f"{float(value) * 100:.{int(decimals)}f}%"
    except (TypeError, ValueError):
        return "—"


@register.filter
def feature_label(name):
    return labels.FEATURES.get(name, name)


@register.simple_tag
def value_label(feature, value):
    """Traduce el valor de una variable categórica; formatea los montos."""
    mapping = labels.CATEGORY_LABELS.get(feature)
    if mapping:
        return mapping.get(value, value)
    if feature.endswith("_claim") or feature == "policy_annual_premium":
        return money(value)
    return value


@register.filter
def label_for(value, feature):
    mapping = labels.CATEGORY_LABELS.get(feature, {})
    return mapping.get(value, value)


@register.filter
def abs_pct(value):
    return f"{abs(float(value)) * 100:.1f}"
