from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Obsolete: company currency is now stored directly on CompanyProfile."

    def handle(self, *args, **options):
        raise CommandError(
            "populate_currencies is obsolete. Currency is no longer backed by a common.Currency model; "
            "CompanyProfile.currency is stored directly as a plain field."
        )
