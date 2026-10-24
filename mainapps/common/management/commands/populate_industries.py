from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Obsolete: industry is now a CompanyProfile choice field."

    def handle(self, *args, **options):
        raise CommandError(
            "populate_industries is obsolete. CompanyProfile.industry is now backed by Industry choices in "
            "mainapps.profile.models, not a seedable tree model."
        )
