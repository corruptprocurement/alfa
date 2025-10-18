import csv
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from analytics.models import Contract

# Bulgarian header → internal key
H = {
    "Уникален номер на поръчката": "order_unique_number",
    "Дата на публикуване на обявлението": "notice_published_at",
    "Наименование на възложителя": "buyer_name",
    "ЕИК на възложителя": "buyer_eik",
    "Наименование на изпълнителя": "seller_name",
    "ЕИК на изпълнителя": "seller_eik",
    "Вид на поръчката/обявлението": "notice_type",
    "Идентификатор на обособената позиция": "lot_identifier",
    "Номер на договора": "contract_number",
    "Дата на сключване на договора": "contract_signed_at",
    "Предмет на договора": "contract_subject",
    "Стойност на договора": "contract_value",
    "Валута по договор": "contract_currency",
    "Преизчислена стойност в Евро": "contract_value_eur",
    "Текуща стойност на договора": "current_value",
    "Валута на текуща стойност на договор": "current_currency",
    "Преизчислена текуща стойност на договор в Евро": "current_value_eur",
    "Стойност на анекса": "annex_value",
    "Валута на анекса": "annex_currency",
    "Преизчислена стойност на анекс в Евро": "annex_value_eur",
    "Дата на публикуване на анекса": "annex_published_at",
    "Изменение на стойност по договор": "change_of_value_desc",
    "Причини за изменението": "change_reason",
    "Възложена на група икономически оператори и/или стопански субекти": "is_group_of_economic_operators",
    "Наименование на подизпълнителя": "subcontractor_name",
    "ЕИК на подизпълнителя": "subcontractor_eik",
    "Особености": "features",
}

def parse_date_bg(s: str):
    s = (s or "").strip()
    if not s:
        return None
    # typical format: "14.10.2025"
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def parse_decimal_bg(s: str):
    s = (s or "").strip()
    if not s:
        return None
    # "39 999,00" → "39999.00"
    s = s.replace(" ", "").replace("\u00A0", "").replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None

class Command(BaseCommand):
    help = "Import contracts CSV with Bulgarian headers; adds year_signed; normalizes numbers/dates."

    def add_arguments(self, parser):
        parser.add_argument("--file", "-f", default=str(Path(settings.BASE_DIR) / "data" / "contracts.csv"))
        parser.add_argument("--replace", action="store_true")
        parser.add_argument("--batch", type=int, default=5000)

    def handle(self, *args, **opts):
        path = Path(opts["file"])
        if not path.exists():
            self.stderr.write(f"CSV not found: {path}")
            return

        if opts["replace"]:
            self.stdout.write("Clearing existing contracts…")
            Contract.objects.all().delete()

        total = 0
        batch = []
        batch_size = int(opts["batch"])

        with path.open("r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096); f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except Exception:
                dialect = csv.get_dialect("excel")

            reader = csv.DictReader(f, dialect=dialect)
            # normalize header keys: keep original Bulgarian headers
            for row in reader:
                data = {}
                for bg_key, dst in H.items():
                    raw = row.get(bg_key, "")

                    if dst in ("notice_published_at", "contract_signed_at", "annex_published_at"):
                        data[dst] = parse_date_bg(raw)
                    elif dst in (
                        "contract_value","contract_value_eur",
                        "current_value","current_value_eur",
                        "annex_value","annex_value_eur"
                    ):
                        data[dst] = parse_decimal_bg(raw)
                    elif dst == "is_group_of_economic_operators":
                        val = (raw or "").strip().lower()
                        data[dst] = val in ("да", "yes", "true", "1")
                    else:
                        data[dst] = (raw or "").strip()

                # derive year_signed
                year = data["contract_signed_at"].year if data["contract_signed_at"] else None
                data["year_signed"] = year

                batch.append(Contract(**data))
                if len(batch) >= batch_size:
                    with transaction.atomic():
                        Contract.objects.bulk_create(batch, batch_size=batch_size)
                    total += len(batch); batch.clear()
                    self.stdout.write(f"Imported {total}…")

            if batch:
                with transaction.atomic():
                    Contract.objects.bulk_create(batch, batch_size=batch_size)
                total += len(batch)

        self.stdout.write(self.style.SUCCESS(f"Done. Imported {total} rows."))
