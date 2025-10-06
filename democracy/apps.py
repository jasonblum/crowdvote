from django.apps import AppConfig


class DemocracyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'democracy'
    
    def ready(self):
        """
        Import signals when Django starts to ensure they are registered.
        
        This enables automatic vote recalculation when important events occur:
        - Vote cast/updated/deleted
        - Following relationships changed
        - Community memberships changed
        - Ballot tags modified
        - Decisions published/closed
        """
        # TODO (Change 0002): Re-enable after fixing Following model
        # import democracy.signals  # noqa
        pass