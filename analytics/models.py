from django.db import models

class MonthlySales(models.Model):
    month = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.month}: {self.amount}"


from django.db import models

class Contract(models.Model):
    # Original IDs
    order_unique_number = models.CharField(max_length=64, db_index=True)   # "Уникален номер на поръчката"
    contract_number     = models.CharField(max_length=64, blank=True, default="", db_index=True)  # "Номер на договора"

    # Parties
    buyer_name = models.CharField(max_length=255, db_index=True)           # "Наименование на възложителя"
    buyer_eik  = models.CharField(max_length=32, blank=True, default="", db_index=True)  # "ЕИК на възложителя"
    seller_name = models.CharField(max_length=255, db_index=True)          # "Наименование на изпълнителя"
    seller_eik  = models.CharField(max_length=32, blank=True, default="", db_index=True) # "ЕИК на изпълнителя"

    # Meta
    notice_type = models.CharField(max_length=255, blank=True, default="", db_index=True)  # "Вид на поръчката/обявлението"
    lot_identifier = models.CharField(max_length=128, blank=True, default="")  # "Идентификатор на обособената позиция"

    # Dates (normalized)
    notice_published_at   = models.DateField(null=True, blank=True)        # "Дата на публикуване на обявлението"
    contract_signed_at    = models.DateField(null=True, blank=True, db_index=True)  # "Дата на сключване на договора"
    annex_published_at    = models.DateField(null=True, blank=True)        # "Дата на публикуване на анекса"

    # Derived
    year_signed = models.IntegerField(null=True, blank=True, db_index=True)

    # Money (normalized to Decimal; keep original currency and euro-converted where provided)
    contract_subject = models.TextField(blank=True, default="")            # "Предмет на договора"

    contract_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)      # "Стойност на договора"
    contract_currency = models.CharField(max_length=8, blank=True, default="")                         # "Валута по договор"
    contract_value_eur = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)  # "Преизчислена стойност в Евро"

    current_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)        # "Текуща стойност на договора"
    current_currency = models.CharField(max_length=8, blank=True, default="")                          # "Валута на текуща стойност на договор"
    current_value_eur = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)    # "Преизчислена текуща стойност на договор в Евро"

    annex_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)          # "Стойност на анекса"
    annex_currency = models.CharField(max_length=8, blank=True, default="")                            # "Валута на анекса"
    annex_value_eur = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)      # "Преизчислена стойност на анекс в Евро"

    change_of_value_desc = models.TextField(blank=True, default="")        # "Изменение на стойност по договор"
    change_reason = models.TextField(blank=True, default="")               # "Причини за изменението"

    is_group_of_economic_operators = models.BooleanField(default=False)    # "Възложена на група…"
    subcontractor_name = models.CharField(max_length=255, blank=True, default="")
    subcontractor_eik  = models.CharField(max_length=32, blank=True, default="")
    features = models.TextField(blank=True, default="")                    # "Особености"

    class Meta:
        indexes = [
            models.Index(fields=["buyer_eik"]),
            models.Index(fields=["seller_eik"]),
            models.Index(fields=["notice_type"]),
            models.Index(fields=["contract_signed_at"]),
            models.Index(fields=["year_signed"]),
        ]
        verbose_name = "Contract"
        verbose_name_plural = "Contracts"

    def __str__(self):
        return f"{self.order_unique_number} | {self.contract_number} | {self.buyer_name} → {self.seller_name}"
