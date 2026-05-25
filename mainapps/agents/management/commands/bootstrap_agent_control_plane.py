from django.core.management.base import BaseCommand

from mainapps.agents.bootstrap import bootstrap_platform_catalog


class Command(BaseCommand):
    help = "Populate platform agent templates, tool servers, tools, skills, and instruction presets."

    def handle(self, *args, **options):
        stats = bootstrap_platform_catalog(stdout=self.stdout)
        for key, value in stats.items():
            self.stdout.write(self.style.SUCCESS(f"{key}: {value}"))

