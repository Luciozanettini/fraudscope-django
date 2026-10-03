"""Traducciones al español de los valores categóricos del dataset (que viene en inglés)."""

SEVERITY = {
    "Trivial Damage": "Daño trivial",
    "Minor Damage": "Daño menor",
    "Major Damage": "Daño mayor",
    "Total Loss": "Pérdida total",
}

INCIDENT_TYPE = {
    "Single Vehicle Collision": "Choque de un vehículo",
    "Multi-vehicle Collision": "Choque múltiple",
    "Vehicle Theft": "Robo del vehículo",
    "Parked Car": "Auto estacionado",
}

COLLISION_TYPE = {
    "Front Collision": "Frontal",
    "Rear Collision": "Trasera",
    "Side Collision": "Lateral",
    "UNKNOWN": "Sin dato",
}

AUTHORITIES = {
    "Police": "Policía",
    "Fire": "Bomberos",
    "Ambulance": "Ambulancia",
    "Other": "Otra",
    "None": "Ninguna",
}

YES_NO = {
    "YES": "Sí",
    "NO": "No",
    "UNKNOWN": "Sin dato",
}

HOBBIES = {
    "base-jumping": "Base jumping",
    "basketball": "Básquet",
    "board-games": "Juegos de mesa",
    "bungie-jumping": "Bungee jumping",
    "camping": "Camping",
    "chess": "Ajedrez",
    "cross-fit": "CrossFit",
    "dancing": "Baile",
    "exercise": "Ejercicio",
    "golf": "Golf",
    "hiking": "Senderismo",
    "kayaking": "Kayak",
    "movies": "Cine",
    "paintball": "Paintball",
    "polo": "Polo",
    "reading": "Lectura",
    "skydiving": "Paracaidismo",
    "sleeping": "Dormir",
    "video-games": "Videojuegos",
    "yachting": "Navegación",
}

# Nombre legible de cada variable del modelo
FEATURES = {
    "incident_severity": "Severidad del incidente",
    "insured_hobbies": "Hobby del asegurado",
    "incident_type": "Tipo de incidente",
    "collision_type": "Tipo de colisión",
    "authorities_contacted": "Autoridad contactada",
    "property_damage": "Daño a la propiedad",
    "police_report_available": "Denuncia policial",
    "age": "Edad",
    "months_as_customer": "Antigüedad como cliente",
    "policy_annual_premium": "Prima anual",
    "policy_deductable": "Franquicia",
    "incident_hour_of_the_day": "Hora del incidente",
    "number_of_vehicles_involved": "Vehículos involucrados",
    "witnesses": "Testigos",
    "bodily_injuries": "Lesionados",
    "injury_claim": "Monto por lesiones",
    "property_claim": "Monto por propiedad",
    "vehicle_claim": "Monto por vehículo",
}

# Para cada variable categórica, su diccionario de traducción
CATEGORY_LABELS = {
    "incident_severity": SEVERITY,
    "insured_hobbies": HOBBIES,
    "incident_type": INCIDENT_TYPE,
    "collision_type": COLLISION_TYPE,
    "authorities_contacted": AUTHORITIES,
    "property_damage": YES_NO,
    "police_report_available": YES_NO,
}


def choices(mapping):
    """Convierte un diccionario de traducción en `choices` de Django, ordenado por la etiqueta."""
    return sorted(mapping.items(), key=lambda item: item[1])
