from django.core.management.base import BaseCommand

from mainapps.profile.models import CompanyProfileAddress
from subapps.kafka.producers.identity import publish_company_profile_upserted


class Command(BaseCommand):
    help = "Republish company profile identity events after shared address migration."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        rows = CompanyProfileAddress.objects.filter(
            shared_address_id__isnull=False,
            profile__isnull=False,
        ).select_related("profile").order_by("pk")
        if options["limit"]:
            rows = rows[: options["limit"]]

        report = {"total": len(rows), "published": 0, "errors": []}
        for address in rows:
            profile = address.profile
            if options["dry_run"]:
                self.stdout.write(f"{profile.pk}: {address.shared_address_id}")
                continue
            try:
                publish_company_profile_upserted(profile)
                report["published"] += 1
            except Exception as exc:  # one broker failure must not stop the replay
                report["errors"].append({"profile_id": profile.pk, "error": f"{type(exc).__name__}: {exc}"})

        self.stdout.write(str(report))
