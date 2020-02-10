from django.apps import AppConfig


class SpiderfarmConfig(AppConfig):
    name = 'spiderfarm'

    def ready(self):
        import spiderfarm.signals
