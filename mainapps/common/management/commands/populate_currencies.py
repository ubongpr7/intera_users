from django.core.management.base import BaseCommand
from iso4217 import Currency as ISO4217Currency
from ...models import Currency  # Replace 'your_app' with your actual app name
from tqdm import tqdm  # For progress bar (optional)

class Command(BaseCommand):
    help = 'Populate database with ISO 4217 currencies with non-null codes'

    def handle(self, *args, **options):
        self.stdout.write("Starting currency population...")
        
        added_count = 0
        skipped_count = 0
        
        for iso_currency in tqdm(ISO4217Currency, desc="Processing currencies"):
            try:
                if not iso_currency.code:
                    skipped_count += 1
                    continue
                
                _, created = Currency.objects.get_or_create(
                    code=iso_currency.code,
                    defaults={
                        'name': iso_currency.name,
                    }
                )
                
                if created:
                    added_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing {iso_currency.code}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(
            f"Successfully populated currencies!\n"
            f"Added: {added_count}\n"
            f"Skipped (existing/null): {skipped_count}"
        ))