from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Invalidate permission-evaluation caches shared by downstream services."

    def handle(self, *args, **options):
        try:
            try:
                version = cache.incr("permission:v1:version")
            except ValueError:
                version = 2
                cache.set("permission:v1:version", version, None)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Unable to invalidate permission cache: {exc}"))
            raise

        self.stdout.write(
            self.style.SUCCESS(f"Permission cache invalidated at version {version}.")
        )
