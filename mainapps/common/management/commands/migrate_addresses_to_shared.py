import json
from urllib.parse import urljoin

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from mainapps.common.models import SharedAddressMigrationMap
from mainapps.accounts.models import ResidentialAddress
from mainapps.profile.models import CompanyProfileAddress


class Command(BaseCommand):
    help = "Copy legacy users-service addresses to the shared locations service safely."

    def add_arguments(self, parser):
        parser.add_argument("--base-url", default="http://subscriptions:8550/api/v1/locations/")
        parser.add_argument("--service-key", default="")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--timeout", type=float, default=10)

    def handle(self, *args, **options):
        if not options["dry_run"] and not options["service_key"]:
            self.stderr.write(self.style.ERROR("--service-key is required unless --dry-run is used."))
            return

        sources = list(self._company_addresses()) + list(self._residential_addresses())
        if options["limit"]:
            sources = sources[: options["limit"]]
        report = {"total": len(sources), "migrated": 0, "skipped": 0, "invalid": 0, "errors": []}

        for source_model, source in sources:
            source_pk = str(source.pk)
            mapping, _ = SharedAddressMigrationMap.objects.get_or_create(
                source_model=source_model,
                source_pk=source_pk,
                defaults={"profile_id": self._profile_id(source_model, source)},
            )
            if mapping.status == "migrated" and mapping.shared_address_id:
                report["skipped"] += 1
                continue

            payload, error = self._payload(source_model, source)
            if error:
                self._mark(mapping, "invalid", error)
                report["invalid"] += 1
                report["errors"].append({"source": f"{source_model}:{source_pk}", "error": error})
                continue
            if options["dry_run"]:
                self.stdout.write(json.dumps({"source": f"{source_model}:{source_pk}", "payload": payload}, default=str))
                continue

            try:
                response = requests.post(
                    urljoin(options["base_url"].rstrip("/") + "/", "internal/import/addresses/"),
                    json=payload,
                    headers={"X-Intera-Service-Key": options["service_key"], "Accept": "application/json"},
                    timeout=options["timeout"],
                )
                response.raise_for_status()
                shared_id = response.json().get("id")
                if not shared_id:
                    raise ValueError("Shared service response did not include id")
                with transaction.atomic():
                    source.shared_address_id = shared_id
                    source.save(update_fields=["shared_address_id"])
                    mapping.profile_id = payload["profile_id"]
                    mapping.shared_address_id = shared_id
                    mapping.status = "migrated"
                    mapping.error = ""
                    mapping.save()
                report["migrated"] += 1
            except Exception as exc:  # command continues and is resumable
                error = f"{type(exc).__name__}: {exc}"
                self._mark(mapping, "error", error)
                report["errors"].append({"source": f"{source_model}:{source_pk}", "error": error})

        self.stdout.write(json.dumps(report, indent=2, default=str))

    @staticmethod
    def _company_addresses():
        return [("profile.CompanyProfileAddress", address) for address in CompanyProfileAddress.objects.select_related("profile").order_by("pk")]

    @staticmethod
    def _residential_addresses():
        return [("accounts.ResidentialAddress", address) for address in ResidentialAddress.objects.select_related("resident").order_by("pk")]

    @staticmethod
    def _profile_id(source_model, source):
        if source_model.startswith("profile.") and source.profile_id:
            return str(source.profile_id)
        return f"user:{source.resident_id}"

    def _payload(self, source_model, source):
        line_1 = " ".join(str(part).strip() for part in [source.street_number, source.street] if part not in (None, ""))
        profile_id = self._profile_id(source_model, source)
        if not profile_id or not line_1 or not source.country or not source.city:
            return None, "Address needs profile, street, country, and city before canonical migration."
        return {
            "profile_id": profile_id,
            "label": "legacy-" + slugify(source_model),
            "address_line_1": line_1,
            "address_line_2": str(source.apt_number or ""),
            "postal_code": str(source.postal_code or ""),
            "country": self._int_or_none(source.country),
            "region": self._int_or_none(source.region),
            "subregion": self._int_or_none(source.subregion),
            "city": self._int_or_none(source.city),
            "external_reference": f"users:{source_model}:{source.pk}",
            "is_primary": bool(getattr(source.profile, "headquarters_address_id", None) == source.pk) if source_model.startswith("profile.") else False,
        }, None

    @staticmethod
    def _int_or_none(value):
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _mark(mapping, status, error):
        mapping.status = status
        mapping.error = error
        mapping.save(update_fields=["status", "error", "updated_at"])
