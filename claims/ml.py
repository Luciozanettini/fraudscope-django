"""Entrenamiento, persistencia y uso del modelo de detección de fraude.

El modelo es un pipeline de scikit-learn (One-Hot Encoding + Gradient Boosting) entrenado
sobre un subconjunto de variables que un analista puede cargar a mano en el formulario.
"""

import json
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

CATEGORICAL = [
    "incident_severity",
    "insured_hobbies",
    "incident_type",
    "collision_type",
    "authorities_contacted",
    "property_damage",
    "police_report_available",
]
NUMERIC = [
    "age",
    "months_as_customer",
    "policy_annual_premium",
    "policy_deductable",
    "incident_hour_of_the_day",
    "number_of_vehicles_involved",
    "witnesses",
    "bodily_injuries",
    "injury_claim",
    "property_claim",
    "vehicle_claim",
]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "fraud_reported"

# Umbrales de riesgo sobre la probabilidad de fraude. Se eligieron mirando la tasa real de
# fraude por tramo de score (validación cruzada): <20% ≈ 4%, 20-50% ≈ 13%, ≥50% ≈ 63%.
HIGH_RISK = 0.5
MEDIUM_RISK = 0.2


def risk_level(score):
    if score >= HIGH_RISK:
        return "alto"
    if score >= MEDIUM_RISK:
        return "medio"
    return "bajo"


def load_dataset(path=None):
    """Lee el CSV original y normaliza los valores faltantes.

    En el dataset los faltantes vienen como '?' y la autoridad "None" como celda vacía.
    En lugar de imputar con la moda, se los trata como una categoría propia ("UNKNOWN"),
    porque el hecho de no tener el dato también puede ser una señal.
    """
    df = pd.read_csv(path or settings.DATA_CSV, keep_default_na=False, na_values=[])
    df.columns = [c.strip().lstrip("-") for c in df.columns]
    df = df.drop(columns=[c for c in df.columns if c.startswith("_c")])
    for col in ["collision_type", "property_damage", "police_report_available"]:
        df[col] = df[col].replace("?", "UNKNOWN")
    df["authorities_contacted"] = df["authorities_contacted"].replace("", "None")
    df[TARGET] = df[TARGET].map({"Y": 1, "N": 0})
    return df


def build_pipeline():
    preprocess = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)],
        remainder="passthrough",
    )
    # Se compararon Random Forest, Regresión Logística y Gradient Boosting con validación cruzada:
    # Gradient Boosting dio el mejor ROC-AUC y los scores más escalonados por nivel de riesgo.
    # class_weight="balanced" prioriza el recall: es mejor auditar de más que dejar pasar un fraude.
    model = HistGradientBoostingClassifier(
        max_depth=3,
        learning_rate=0.05,
        max_iter=200,
        class_weight="balanced",
        random_state=42,
    )
    return Pipeline([("preprocess", preprocess), ("model", model)])


def train(df):
    """Entrena el modelo y devuelve (pipeline, métricas).

    Las métricas y los scores de los reclamos importados se calculan con validación cruzada
    (out-of-fold): cada reclamo recibe el score de un modelo que NO lo vio al entrenar.
    Así los números del dashboard no están inflados por sobreajuste.
    """
    X, y = df[FEATURES], df[TARGET]

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof = cross_val_predict(build_pipeline(), X, y, cv=cv, method="predict_proba")[:, 1]
    pred = (oof >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()

    pipeline = build_pipeline().fit(X, y)

    # Importancia por permutación: cuánto cae el ROC-AUC si se mezclan al azar los valores de
    # cada variable. Se calcula sobre las variables originales, no sobre las columnas one-hot.
    perm = permutation_importance(pipeline, X, y, scoring="roc_auc", n_repeats=5, random_state=42)
    raw = {f: max(float(v), 0.0) for f, v in zip(FEATURES, perm.importances_mean)}
    total = sum(raw.values()) or 1.0
    importance = {f: v / total for f, v in raw.items()}

    metrics = {
        "n_claims": int(len(df)),
        "fraud_rate": float(y.mean()),
        "roc_auc": float(roc_auc_score(y, oof)),
        "precision": float(precision_score(y, pred)),
        "recall": float(recall_score(y, pred)),
        "f1": float(f1_score(y, pred)),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "importance": dict(sorted(importance.items(), key=lambda kv: kv[1], reverse=True)),
        # Valores "típicos" usados como referencia para explicar cada predicción
        "baseline": {
            **{c: str(X[c].mode()[0]) for c in CATEGORICAL},
            **{c: float(X[c].median()) for c in NUMERIC},
        },
        "oof_scores": {str(p): round(float(s), 4) for p, s in zip(df["policy_number"], oof)},
    }
    return pipeline, metrics


def save(pipeline, metrics):
    settings.ML_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, settings.ML_MODEL_PATH)
    settings.ML_METRICS_PATH.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    load_model.cache_clear()
    load_metrics.cache_clear()


@lru_cache(maxsize=1)
def load_model():
    if not settings.ML_MODEL_PATH.exists():
        raise FileNotFoundError("No hay modelo entrenado. Ejecutá: python manage.py train_model")
    return joblib.load(settings.ML_MODEL_PATH)


@lru_cache(maxsize=1)
def load_metrics():
    if not settings.ML_METRICS_PATH.exists():
        return None
    return json.loads(settings.ML_METRICS_PATH.read_text(encoding="utf-8"))


def _frame(rows):
    return pd.DataFrame(rows, columns=FEATURES)


def predict(features):
    """Probabilidad de fraude (0 a 1) para un reclamo dado como diccionario de variables."""
    return float(load_model().predict_proba(_frame([features]))[0, 1])


def baseline_score():
    """Probabilidad de fraude de un reclamo "típico" (moda/mediana de cada variable)."""
    return predict(load_metrics()["baseline"])


def explain(features, top=5, n_permutations=40):
    """Explica una predicción con valores de Shapley aproximados por muestreo de permutaciones.

    Se parte del reclamo típico y se van "encendiendo" las variables del reclamo real en orden
    aleatorio, midiendo cuánto sube o baja la probabilidad con cada una. Promediando sobre muchas
    permutaciones, cada variable recibe su aporte justo aunque interactúe con otras (por ejemplo,
    severidad y hobby juntos). Los aportes suman exactamente: score - score del reclamo típico.
    Un delta positivo significa que ese valor SUBE el riesgo.
    """
    baseline = load_metrics()["baseline"]
    differing = [f for f in FEATURES if features[f] != baseline[f]]
    if not differing:
        return []

    rng = np.random.default_rng(42)  # semilla fija: la misma explicación cada vez que se abre
    rows, orders = [], []
    for _ in range(n_permutations):
        order = rng.permutation(differing)
        current = dict(baseline)
        rows.append(dict(current))
        for feature in order:
            current[feature] = features[feature]
            rows.append(dict(current))
        orders.append(order)

    probs = score_many(rows)
    contributions = dict.fromkeys(differing, 0.0)
    step = len(differing) + 1
    for i, order in enumerate(orders):
        chunk = probs[i * step:(i + 1) * step]
        for feature, before, after in zip(order, chunk[:-1], chunk[1:]):
            contributions[feature] += (after - before) / n_permutations

    deltas = [
        {"feature": f, "value": features[f], "delta": float(contributions[f])}
        for f in differing
    ]
    deltas.sort(key=lambda d: abs(d["delta"]), reverse=True)
    return [d for d in deltas[:top] if abs(d["delta"]) >= 0.005]


def score_many(rows):
    return np.asarray(load_model().predict_proba(_frame(rows))[:, 1], dtype=float)
