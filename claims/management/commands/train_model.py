from django.core.management.base import BaseCommand

from claims import ml


class Command(BaseCommand):
    help = "Entrena el modelo de detección de fraude a partir del CSV y lo guarda en ml/"

    def handle(self, *args, **options):
        df = ml.load_dataset()
        self.stdout.write(f"Entrenando con {len(df)} reclamos ({df[ml.TARGET].mean():.1%} de fraude)...")
        pipeline, metrics = ml.train(df)
        ml.save(pipeline, metrics)

        self.stdout.write(self.style.SUCCESS("Modelo guardado. Métricas (validación cruzada, 5 folds):"))
        for key in ["roc_auc", "precision", "recall", "f1"]:
            self.stdout.write(f"  {key:<10} {metrics[key]:.3f}")
        self.stdout.write("Variables más importantes:")
        for feature, value in list(metrics["importance"].items())[:5]:
            self.stdout.write(f"  {feature:<28} {value:.3f}")
