from django.apps import AppConfig


class MoviesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.movies"

    def ready(self):
        from config.public_cache import connect_signals
        connect_signals()
