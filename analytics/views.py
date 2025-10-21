import json
from django.shortcuts import render
from analytics.models import MonthlySales
from django.http import HttpResponse
from pathlib import Path
from django.shortcuts import render
from analytics.models import MonthlySales
import csv
from django.conf import settings
from django.shortcuts import render
from django.db.models import Sum, Count
from django.shortcuts import render
from analytics.models import Contract
from datetime import datetime
from django.db.models.functions import ExtractMonth
import pandas as pd
from pathlib import Path
import csv
from django.conf import settings
from django.shortcuts import render
import re
from django.http import JsonResponse

# try pandas, but don't require it
try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None

def _pick_delimiter(header_line: str) -> str:
    # try common delimiters and pick the one that yields the most columns
    candidates = [ ";", ",", "\t", "|" ]
    best = max(candidates, key=lambda d: len(header_line.split(d)))
    return best


DATA_DIR = Path(settings.BASE_DIR) / "data"
MONTH_NAMES_BG = {
    1:"Ян",2:"Фев",3:"Мар",4:"Апр",5:"Май",6:"Юни",
    7:"Юли",8:"Авг",9:"Сеп",10:"Окт",11:"Ное",12:"Дек",
}


def _normalize_eik(value):
    if value is None:
        return ""
    # keep digits only; strip spaces
    return re.sub(r"\D", "", str(value)).lstrip("0") or ""

def _find_column(columns, candidates):
    """Return first existing column from candidates (case-insensitive)."""
    low_map = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in low_map:
            return low_map[cand.lower()]
    # try contains
    for c in columns:
        for cand in candidates:
            if cand.lower() in c.lower():
                return c
    return None
#
def bar_chart(request):
    qs = MonthlySales.objects.all()
    labels = [str(m.month) for m in qs]
    values = [float(m.amount) for m in qs]   # force plain floats
    return render(request, "analytics/bar_chart.html", {
        "labels": labels,
        "values": values,
    })



def bar_chart_from_csv(request):
    csv_path = Path(settings.BASE_DIR) / "data" / "sales.csv"
    labels, values = [], []

    if csv_path.exists():
        # Handle UTF-8 with/without BOM
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            f.seek(0)
            # Detect delimiter (comma/semicolon/tab)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except Exception:
                class Simple(csv.Dialect):
                    delimiter = ","
                    quotechar = '"'
                    doublequote = True
                    skipinitialspace = True
                    lineterminator = "\n"
                    quoting = csv.QUOTE_MINIMAL
                dialect = Simple()

            reader = csv.DictReader(f, dialect=dialect)
            for row in reader:
                # normalize keys: city/value or month/amount etc.
                lower = { (k or "").strip().lower(): (v or "").strip() for k, v in row.items() }

                label = lower.get("city") or lower.get("month") or lower.get("label") or ""
                raw = lower.get("value") or lower.get("amount") or lower.get("count") or "0"

                # make "1 234,56" → 1234.56; "1,234.56" → 1234.56
                cleaned = raw.replace(" ", "").replace(",", ".")
                try:
                    num = float(cleaned)
                except Exception:
                    num = 0.0

                if label:
                    labels.append(label)
                    values.append(num)

    # Render same template you already have
    return render(request, "analytics/bar_chart.html", {
        "labels": labels,
        "values": values,
    })




def bar_contracts_by_year(request):
    metric = request.GET.get("metric", "sum_value_eur")  # sum_value_eur | sum_value | count
    order = request.GET.get("order", "desc")

    current_year = datetime.now().year

    # Filter only years > 2019 and <= current year
    qs = Contract.objects.filter(
        year_signed__gt=2019,
        year_signed__lte=current_year,
    )

    if metric == "count":
        agg_qs = qs.values("year_signed").annotate(metric=Count("id"))
    elif metric == "sum_value":
        agg_qs = qs.values("year_signed").annotate(metric=Sum("contract_value"))
    else:
        agg_qs = qs.values("year_signed").annotate(metric=Sum("contract_value_eur"))

    # Always order by year ascending
    agg_qs = agg_qs.order_by("year_signed")

    labels = [str(r["year_signed"]) for r in agg_qs]
    values = [float(r["metric"] or 0) for r in agg_qs]

    return render(request, "analytics/bar_chart.html", {
        "page_title": "Contracts by Year",
        "labels": labels,
        "values": values,
    })

def contracts_bar(request):
    """
    mode=year | month
    metric=sum_value_eur | sum_value | count
    year=<YYYY> (only used when mode=month)
    """
    mode   = request.GET.get("mode", "year")       # 'year' or 'month'
    metric = request.GET.get("metric", "sum_value_eur").lower()
    order  = request.GET.get("order", "asc").lower()  # yearly chart is chronological; monthly also chronological

    current_year = datetime.now().year
    qs = Contract.objects.filter(year_signed__gt=2019, year_signed__lte=current_year)

    # metric aggregators
    if metric == "count":
        agg = Count("id")
    elif metric == "sum_value":
        agg = Sum("contract_value")
    else:
        agg = Sum("contract_value_eur")

    # build the chart data
    if mode == "month":
        # which year? default to latest available
        year_param = request.GET.get("year")
        if year_param and year_param.isdigit():
            year = int(year_param)
        else:
            # latest year with data
            year = (qs.values_list("year_signed", flat=True)
                      .order_by("-year_signed").first()) or current_year

        qs_year = qs.filter(year_signed=year)
        # annotate month number
        agg_qs = (qs_year
                  .annotate(month_num=ExtractMonth("contract_signed_at"))
                  .values("month_num")
                  .annotate(metric=agg)
                  .order_by("month_num"))

        # ensure all 12 months appear (fill zeros)
        month_to_val = {r["month_num"] or 0: float(r["metric"] or 0) for r in agg_qs}
        labels = [MONTH_NAMES_BG[m] for m in range(1,13)]
        values = [month_to_val.get(m, 0.0) for m in range(1,13)]

        page_title = f"Contracts by Month — {year}"
        selected_year = year
    else:
        # YEAR mode
        agg_qs = (qs.values("year_signed")
                    .annotate(metric=agg)
                    .order_by("year_signed"))  # chronological

        labels = [str(r["year_signed"]) for r in agg_qs]
        values = [float(r["metric"] or 0) for r in agg_qs]
        page_title = "Contracts by Year"
        selected_year = None

    # years for the dropdown (distinct, sorted desc for UX)
    years = (qs.values_list("year_signed", flat=True)
               .distinct().order_by("-year_signed"))

    context = {
        "page_title": page_title,
        "labels": labels,
        "values": values,
        "mode": mode,
        "metric": metric,
        "years": list(years),
        "selected_year": selected_year,
    }
    return render(request, "analytics/contracts_bar.html", context)



#
def _read_csv_fallback(path: Path, limit: int = 500):
    rows = []
    columns = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        first_line = f.readline()
        if not first_line:
            return [], []
        delim = _pick_delimiter(first_line.strip("\n\r"))
        f.seek(0)

        reader = csv.DictReader(f, delimiter=delim)
        columns = reader.fieldnames or []
        for i, row in enumerate(reader):
            if i >= limit:
                break
            rows.append(row)
    return columns, rows
def data_table(request):
    file = request.GET.get("file", "final.csv")
    path = DATA_DIR / file

    if not path.exists():
        return render(request, "analytics/data_table.html", {
            "error": f"File not found: {path}",
            "columns": [], "rows": [], "filename": file,
        })

    try:
        # 1) Load the main CSV
        if pd is not None:
            df = pd.read_csv(path, encoding="utf-8-sig", sep=None, engine="python", dtype=str, nrows=500)
            df = df.fillna("")
        else:
            columns, dict_rows = _read_csv_fallback(path, limit=500)
    except Exception as e:
        import traceback
        return render(request, "analytics/data_table.html", {
            "error": f"Failed to read CSV: {e}\n\n{traceback.format_exc()}",
            "columns": [], "rows": [], "filename": file,
        })

    # 2) If this is final.csv, dynamically map 'Наименование на възложителя' from clients.csv via EIK
    try:
        if file.lower() == "final.csv":
            clients_path = DATA_DIR / "clients.csv"
            executors_path = DATA_DIR / "executors.csv"
            if clients_path.exists():
                if pd is not None:
                    # --- pandas path ---
                    clients = pd.read_csv(clients_path, encoding="utf-8-sig", sep=None, engine="python", dtype=str)
                    clients = clients.fillna("")

                    # detect columns
                    final_cols = list(df.columns)
                    clients_cols = list(clients.columns)

                    eik_candidates = ["ЕИК на възложителя", "ЕИК", "EIK", "ЕИК на възложител"]
                    name_candidates = ["Наименование на възложителя", "Наименование", "Име на възложителя"]

                    final_eik = _find_column(final_cols, eik_candidates)
                    clients_eik = _find_column(clients_cols, eik_candidates)
                    clients_name = _find_column(clients_cols, name_candidates)

                    if final_eik and clients_eik and clients_name:
                        # normalize EIKs
                        df["_eik_norm"] = df[final_eik].map(_normalize_eik)
                        clients["_eik_norm"] = clients[clients_eik].map(_normalize_eik)

                        # build small mapping frame (unique)
                        clients_small = clients[["_eik_norm", clients_name]].drop_duplicates("_eik_norm")

                        # left join to add name
                        df = df.merge(clients_small, on="_eik_norm", how="left")

                        # rename the added name column to standard label
                        if clients_name != "Наименование на възложителя":
                            df.rename(columns={clients_name: "Наименование на възложителя"}, inplace=True)

                        # clean
                        df.drop(columns=["_eik_norm"], inplace=True)
                    else:
                        # couldn't detect columns – just continue without mapping
                        pass
                if executors_path.exists():
                    if pd is not None:
                        # --- pandas path ---
                        executors = pd.read_csv(executors_path, encoding="utf-8-sig", sep=None, engine="python", dtype=str)
                        executors = executors.fillna("")

                        # detect columns
                        final_cols = list(df.columns)
                        executors_cols = list(executors.columns)

                        eik_executors = ["ЕИК на изпълнителя", "ЕИК", "EIK", "ЕИК на изпълнителя"]
                        name_executors = ["Наименование на изпълнителя", "Наименование", "Име на изпълнителя"]

                        final_eik = _find_column(final_cols, eik_executors)
                        executors_eik = _find_column(executors_cols, eik_executors)
                        executors_name = _find_column(executors_cols, name_executors)

                        if final_eik and executors_eik and executors_name:
                            # normalize EIKs
                            df["_eik_norm"] = df[final_eik].map(_normalize_eik)
                            executors["_eik_norm"] = executors[executors_eik].map(_normalize_eik)

                            # build small mapping frame (unique)
                            executors_small = executors[["_eik_norm", executors_name]].drop_duplicates("_eik_norm")

                            # left join to add name
                            df = df.merge(executors_small, on="_eik_norm", how="left")

                            # rename the added name column to standard label
                            if executors_name != "Наименование на изпълнителя":
                                df.rename(columns={executors_name: "Наименование на изпълнителя"}, inplace=True)

                            # clean
                            df.drop(columns=["_eik_norm"], inplace=True)
                        else:
                            # couldn't detect columns – just continue without mapping
                            pass
                else:
                    # --- csv fallback path ---
                    # read clients to dict mapping
                    c_cols, c_rows = _read_csv_fallback(clients_path, limit=200000)  # read many; it’s small anyway
                    eik_candidates = ["ЕИК на възложителя", "ЕИК", "EIK", "ЕИК на възложител"]
                    name_candidates = ["Наименование на възложителя", "Наименование", "Име на възложителя"]
                    clients_eik = _find_column(c_cols, eik_candidates)
                    clients_name = _find_column(c_cols, name_candidates)

                    mapping = {}
                    if clients_eik and clients_name:
                        for r in c_rows:
                            mapping[_normalize_eik(r.get(clients_eik, ""))] = r.get(clients_name, "")

                    # detect EIK col in final
                    final_eik = _find_column(columns, eik_candidates)

                    # inject new column in each row dict
                    if final_eik:
                        for r in dict_rows:
                            e = _normalize_eik(r.get(final_eik, ""))
                            r["Наименование на възложителя"] = mapping.get(e, "")
                        # ensure column list includes new column at the end
                        if "Наименование на възложителя" not in columns:
                            columns.append("Наименование на възложителя")
            else:
                # clients.csv missing -> no mapping, but not an error
                pass
    except Exception as e:
        # don’t crash the page if mapping fails; show a small error banner
        map_error = f"Mapping skipped: {e}"
    else:
        map_error = None

    # 3) Convert to template-friendly structure
    if pd is not None:
        columns = list(df.columns)
        records = df.astype(object).where(pd.notnull(df), "").to_dict(orient="records")
    else:
        records = dict_rows  # already dicts

    # list-of-lists (no custom filters needed)
    matrix_rows = []
    for r in records:
        matrix_rows.append([ (r.get(c, "") if r.get(c, "") is not None else "") for c in columns ])

    return render(request, "analytics/data_table.html", {
        "columns": columns,
        "rows": matrix_rows,
        "filename": file,
        "error": map_error,  # shown as a small warning if present
    })

def get_unique_orders_count(request):
    OUTPUT_DIR = Path(r"C:\Users\m.rusinov\Downloads\wowdash-tailwind-bootstrap-react-next-django-2025-09-21-18-38-19-utc\Main-file_WowDash_Bundle\Django\Django\data")
    file_path = OUTPUT_DIR / 'number_of_unique_orders.csv'

    # Прочитане на CSV или генериране, ако трябва
    df = pd.read_csv(file_path)

    # Изчисляваме броя на уникалните поръчки
    unique_orders = df['Уникален номер на поръчката (nnnnn-yyyy-xxxx)'].nunique()

    # Връщаме JSON отговора
    return JsonResponse({'unique_orders_count': unique_orders})

def dashboard(request):
    OUTPUT_DIR = Path(r"C:\Users\m.rusinov\Downloads\wowdash-tailwind-bootstrap-react-next-django-2025-09-21-18-38-19-utc\Main-file_WowDash_Bundle\Django\Django\data")
    file_path = OUTPUT_DIR / 'number_of_unique_orders.csv'

    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        if 'Уникален номер на поръчката (nnnnn-yyyy-xxxx)' in df.columns:
            unique_orders = df['Уникален номер на поръчката (nnnnn-yyyy-xxxx)'].nunique()
        else:
            unique_orders = df.iloc[:, 0].nunique()
    except Exception as e:
        print("⚠️ CSV error:", e)
        unique_orders = 0

    context = {'unique_orders_count': unique_orders}
    return render(request, 'dashboard.html', context)


def dashboard_total_value(request):
    OUTPUT_DIR = Path(r"C:\Users\m.rusinov\Downloads\wowdash-tailwind-bootstrap-react-next-django-2025-09-21-18-38-19-utc\Main-file_WowDash_Bundle\Django\Django\data")
    file_path = OUTPUT_DIR / "total_spent.csv"

    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        if 'Преизчислена стойност в Евро' in df.columns:
            total_sum = df['Преизчислена стойност в Евро'].sum()

    except Exception as e:
        print("⚠️ CSV error:", e)
        unique_orders = 0

    context = {'total_sum': total_sum}
    return render(request, 'dashboard.html', context)




def get_unique_orders_count(request):
    OUTPUT_DIR = Path(r"C:\Users\m.rusinov\Downloads\wowdash-tailwind-bootstrap-react-next-django-2025-09-21-18-38-19-utc\Main-file_WowDash_Bundle\Django\Django\data")
    file_path = OUTPUT_DIR / 'number_of_unique_orders.csv'

    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        print("✅ CSV loaded successfully")
        print("Columns:", list(df.columns))

        # Try to detect the correct column
        if 'Уникален номер на поръчката (nnnnn-yyyy-xxxx)' in df.columns:
            unique_orders = df['Уникален номер на поръчката (nnnnn-yyyy-xxxx)'].nunique()
        else:
            # fallback: first column
            unique_orders = df.iloc[:, 0].nunique()

        return JsonResponse({'unique_orders_count': int(unique_orders)})

    except Exception as e:
        print("❌ Error in /api/unique-orders/:", e)
        return JsonResponse({'error': str(e)}, status=500)


def sales_data(request):
    OUTPUT_DIR = Path(
        r"C:\Users\m.rusinov\Downloads\wowdash-tailwind-bootstrap-react-next-django-2025-09-21-18-38-19-utc\Main-file_WowDash_Bundle\Django\Django\data")
    file_path = OUTPUT_DIR / "total_spent.csv"

    # Get the 'period' query param: yearly or monthly
    period = request.GET.get('period', 'monthly')

    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        df['Дата на публикуване на обявлението'] = pd.to_datetime(df['Дата на публикуване на обявлението'])

        if period == 'yearly':
            grouped = df.groupby(df['Дата на публикуване на обявлението'].dt.year)['Преизчислена стойност в Евро'].sum()
            labels = grouped.index.astype(str).tolist()
        else:  # monthly
            grouped = df.groupby(df['Дата на публикуване на обявлението'].dt.strftime('%Y-%m'))[
                'Преизчислена стойност в Евро'].sum()
            labels = grouped.index.tolist()

        data = grouped.tolist()
        return JsonResponse({'labels': labels, 'data': data})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
def get_total_sum(request):
    OUTPUT_DIR = Path(r"C:\Users\m.rusinov\Downloads\wowdash-tailwind-bootstrap-react-next-django-2025-09-21-18-38-19-utc\Main-file_WowDash_Bundle\Django\Django\data")
    file_path = OUTPUT_DIR / "total_spent.csv"

    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')

        print("✅ CSV loaded successfully")
        print("Columns:", list(df.columns))

        if 'Преизчислена стойност в Евро' in df.columns:
            total_sum = df['Преизчислена стойност в Евро'].sum()

        return JsonResponse({'total_sum': int(total_sum)})

    except Exception as e:
        print("❌ Error in /api/unique-orders/:", e)
        return JsonResponse({'error': str(e)}, status=500)
# analytics/views.py
# from pathlib import Path
# import csv
# import re
# from django.conf import settings
# from django.shortcuts import render
#
# try:
#     import pandas as pd
# except ImportError:
#     pd = None
#
# DATA_DIR = Path(settings.BASE_DIR) / "data"
#
# # ----------------- mappings (your dictionaries) -----------------
#
# CRITERIA_MAP = {
#     "Най-ниска цена": {"coding": 1, "value": 100},
#     "Оптимално съотношение качество/цена; Най-ниска цена": {"coding": 2, "value": 50},
#     "Оптимално съотношение качество/цена": {"coding": 3, "value": 0},
# }
#
# PROCEDURES_MAP = {
#     "Събиране на оферти с обява": {"coding": 1, "value": 100},
#     "Покана до определени лица": {"coding": 2, "value": 50},
#     "Публично състезание": {"coding": 3, "value": 100},
#     "Пряко договаряне": {"coding": 4, "value": 0},
#     "Вътрешен конкурентен избор по РС": {"coding": 5, "value": 50},
#     "Открита процедура": {"coding": 6, "value": 100},
#     "Договаряне без предварително обявление": {"coding": 7, "value": 0},
#     "Обявление за изменение на договор – Общата директива": {"coding": 8, "value": 100},
#     "Ограничена процедура по ДСП": {"coding": 9, "value": 0},
#     "Обявление за възложена поръчка – Общата директива, стандартен режим": {"coding": 10, "value": 100},
#     "Договаряне без предварителна покана за участие": {"coding": 11, "value": 0},
#     "Обявление за изменение на договор – Секторната директива": {"coding": 12, "value": 100},
#     "Обявление за доброволна прозрачност ex-ante – Общата директива": {"coding": 13, "value": 100},
#     "Договаряне с предварителна покана за участие по КС": {"coding": 14, "value": 0},
#     "Обявление за възложена поръчка – Секторната директива, стандартен режим": {"coding": 15, "value": 100},
#     "Договаряне с предварителна покана за участие": {"coding": 16, "value": 50},
#     "Договаряне с публикуване на обявление за поръчка": {"coding": 17, "value": 100},
#     "Договаряне без публикуване на обявление за поръчка": {"coding": 18, "value": 0},
#     "Ограничена процедура": {"coding": 19, "value": 0},
#     "Състезателна процедура с договаряне": {"coding": 20, "value": 100},
#     "Ограничена процедура по КС": {"coding": 21, "value": 0},
#     "Конкурс за проект - открит": {"coding": 22, "value": 100},
#     "Обявление за възложена поръчка – комунални услуги": {"coding": 23, "value": 100},
#     "Обявление за възложена поръчка": {"coding": 24, "value": 100},
#     "Обявление за изменение": {"coding": 25, "value": 100},
#     "Обявление за изменение (ЗОП)": {"coding": 26, "value": 100},
#     "Обявление за възложена поръчка в областта на отбраната и сигурността": {"coding": 27, "value": 50},
#     "Партньорство за иновации": {"coding": 28, "value": 100},
# }
#
# # ----------------- helpers -----------------
#
# def _pick_delimiter(header_line: str) -> str:
#     candidates = [";", ",", "\t", "|"]
#     return max(candidates, key=lambda d: len(header_line.split(d)))
#
# def _read_csv_fallback(path: Path, limit: int = 5000):
#     rows, columns = [], []
#     with path.open("r", encoding="utf-8-sig", newline="") as f:
#         first = f.readline()
#         if not first:
#             return [], []
#         delim = _pick_delimiter(first.strip("\n\r"))
#         f.seek(0)
#         reader = csv.DictReader(f, delimiter=delim)
#         columns = reader.fieldnames or []
#         for i, row in enumerate(reader):
#             if i >= limit:
#                 break
#             rows.append(row)
#     return columns, rows
#
# def _normalize_eik(v):
#     if v is None:
#         return ""
#     return re.sub(r"\D", "", str(v)).lstrip("0") or ""
#
# def _find_column(columns, candidates):
#     low_map = {c.lower(): c for c in columns}
#     for cand in candidates:
#         if cand.lower() in low_map:
#             return low_map[cand.lower()]
#     for c in columns:
#         for cand in candidates:
#             if cand.lower() in c.lower():
#                 return c
#     return None
#
# def _reorder_columns(existing, preferred_first):
#     seen = set()
#     ordered = []
#     for c in preferred_first:
#         if c in existing and c not in seen:
#             ordered.append(c); seen.add(c)
#     for c in existing:
#         if c not in seen:
#             ordered.append(c); seen.add(c)
#     return ordered
#
# # ----------------- main view -----------------
#
# def data_table(request):
#     file = request.GET.get("file", "final.csv").strip()
#     path = DATA_DIR / file
#
#     preferred_order = [
#         "Уникален номер на поръчката",
#         "Дата на публикуване на обявлението",
#         "ЕИК на възложителя",
#         "Текуща стойност на договора",
#         "Номер на договора",
#         "ЕИК на изпълнителя",
#         "Преизчислена стойност в Евро",
#         "Стойност на договора",
#         "risky_by_type_of_procedure",
#         "risky_by_annex",
#         # you can add more fixed ones here later
#     ]
#
#     if not path.exists():
#         return render(request, "analytics/data_table.html", {
#             "error": f"File not found: {path}",
#             "columns": [], "rows": [], "filename": file,
#         })
#
#     # --- Load main CSV ---
#     try:
#         if pd is not None:
#             df = pd.read_csv(path, encoding="utf-8-sig", sep=None, engine="python", dtype=str)
#             df = df.fillna("")
#         else:
#             columns, dict_rows = _read_csv_fallback(path, limit=5000)
#     except Exception as e:
#         import traceback
#         return render(request, "analytics/data_table.html", {
#             "error": f"Failed to read CSV {file}: {e}\n{traceback.format_exc()}",
#             "columns": [], "rows": [], "filename": file,
#         })
#
#     map_warnings = []
#
#     # --- Map client names (ЕИК на възложителя -> Наименование на възложителя) as before ---
#     if file.lower() == "final.csv":
#         clients_path = DATA_DIR / "clients.csv"
#         if clients_path.exists():
#             try:
#                 if pd is not None:
#                     clients = pd.read_csv(clients_path, encoding="utf-8-sig", sep=None, engine="python", dtype=str).fillna("")
#                     c_eik = _find_column(list(clients.columns), ["ЕИК на възложителя", "ЕИК", "EIK"])
#                     c_name = _find_column(list(clients.columns), ["Наименование на възложителя", "Наименование", "Име на възложителя"])
#                     f_cols = list(df.columns)
#                     f_eik = _find_column(f_cols, ["ЕИК на възложителя", "ЕИК", "EIK"])
#
#                     if f_eik and c_eik and c_name:
#                         df["_eik_client"] = df[f_eik].map(_normalize_eik)
#                         clients["_eik_client"] = clients[c_eik].map(_normalize_eik)
#                         clients_small = clients[["_eik_client", c_name]].drop_duplicates("_eik_client")
#                         df = df.merge(clients_small, on="_eik_client", how="left")
#                         if c_name != "Наименование на възложителя":
#                             df.rename(columns={c_name: "Наименование на възложителя"}, inplace=True)
#                         df.drop(columns=["_eik_client"], inplace=True)
#                     else:
#                         map_warnings.append("Клиент: не успях да открия колони за ЕИК/Име.")
#                 else:
#                     c_cols, c_rows = _read_csv_fallback(clients_path, limit=200000)
#                     c_eik = _find_column(c_cols, ["ЕИК на възложителя", "ЕИК", "EIK"])
#                     c_name = _find_column(c_cols, ["Наименование на възложителя", "Наименование", "Име на възложителя"])
#                     f_eik = _find_column(columns, ["ЕИК на възложителя", "ЕИК", "EIK"])
#                     mapping = {}
#                     if c_eik and c_name:
#                         for r in c_rows:
#                             mapping[_normalize_eik(r.get(c_eik, ""))] = r.get(c_name, "")
#                     if f_eik:
#                         for r in dict_rows:
#                             r["Наименование на възложителя"] = mapping.get(_normalize_eik(r.get(f_eik, "")), "")
#                         if "Наименование на възложителя" not in columns:
#                             columns.append("Наименование на възложителя")
#             except Exception as e:
#                 map_warnings.append(f"Клиент мапинг: {e}")
#
#     # --- Map executor names (ЕИК на изпълнителя -> Наименование на изпълнителя) ---
#     if file.lower() == "final.csv":
#         exec_path = DATA_DIR / "executors.csv"
#         if exec_path.exists():
#             try:
#                 if pd is not None:
#                     ex = pd.read_csv(exec_path, encoding="utf-8-sig", sep=None, engine="python", dtype=str).fillna("")
#                     ex_eik = _find_column(list(ex.columns), ["ЕИК на изпълнителя", "ЕИК", "EIK"])
#                     ex_name = _find_column(list(ex.columns), ["Наименование на изпълнителя", "Наименование", "Име на изпълнителя"])
#                     f_cols = list(df.columns)
#                     f_eik_exec = _find_column(f_cols, ["ЕИК на изпълнителя", "ЕИК на изпълнител", "EIK изпълнител", "EIK"])
#
#                     if f_eik_exec and ex_eik and ex_name:
#                         df["_eik_exec"] = df[f_eik_exec].map(_normalize_eik)
#                         ex["_eik_exec"] = ex[ex_eik].map(_normalize_eik)
#                         ex_small = ex[["_eik_exec", ex_name]].drop_duplicates("_eik_exec")
#                         df = df.merge(ex_small, on="_eik_exec", how="left")
#                         if ex_name != "Наименование на изпълнителя":
#                             df.rename(columns={ex_name: "Наименование на изпълнителя"}, inplace=True)
#                         df.drop(columns=["_eik_exec"], inplace=True)
#                     else:
#                         map_warnings.append("Изпълнител: не успях да открия колони за ЕИК/Име.")
#                 else:
#                     e_cols, e_rows = _read_csv_fallback(exec_path, limit=200000)
#                     e_eik = _find_column(e_cols, ["ЕИК на изпълнителя", "ЕИК", "EIK"])
#                     e_name = _find_column(e_cols, ["Наименование на изпълнителя", "Наименование", "Име на изпълнителя"])
#                     f_eik_exec = _find_column(columns, ["ЕИК на изпълнителя", "ЕИК на изпълнител", "EIK изпълнител", "EIK"])
#                     mapping = {}
#                     if e_eik and e_name:
#                         for r in e_rows:
#                             mapping[_normalize_eik(r.get(e_eik, ""))] = r.get(e_name, "")
#                     if f_eik_exec:
#                         for r in dict_rows:
#                             r["Наименование на изпълнителя"] = mapping.get(_normalize_eik(r.get(f_eik_exec, "")), "")
#                         if "Наименование на изпълнителя" not in columns:
#                             columns.append("Наименование на изпълнителя")
#             except Exception as e:
#                 map_warnings.append(f"Изпълнител мапинг: {e}")
#
#     # --- Add criteria/procedure coding/value columns ---
#     crit_col_candidates = ["criteria", "критерий", "критерии", "Критерии за възлагане"]
#     proc_col_candidates = ["type_of_procedure", "Вид на поръчката/обявлението", "Тип процедура"]
#
#     if pd is not None:
#         cols = list(df.columns)
#         c_col = _find_column(cols, crit_col_candidates)
#         p_col = _find_column(cols, proc_col_candidates)
#
#         if c_col and c_col not in ("", None):
#             df["criteria_coding"] = df[c_col].map(lambda x: CRITERIA_MAP.get(str(x), {}).get("coding", None))
#             df["criteria_value"]  = df[c_col].map(lambda x: CRITERIA_MAP.get(str(x), {}).get("value", None))
#
#         if p_col and p_col not in ("", None):
#             df["procedure_coding"] = df[p_col].map(lambda x: PROCEDURES_MAP.get(str(x), {}).get("coding", None))
#             df["procedure_value"]  = df[p_col].map(lambda x: PROCEDURES_MAP.get(str(x), {}).get("value", None))
#     else:
#         c_col = _find_column(columns, crit_col_candidates)
#         p_col = _find_column(columns, proc_col_candidates)
#
#         if c_col and c_col not in columns:
#             pass
#         # add new fields and fill
#         for r in dict_rows:
#             crit = str(r.get(c_col, ""))
#             proc = str(r.get(p_col, ""))
#             r["criteria_coding"] = CRITERIA_MAP.get(crit, {}).get("coding", "")
#             r["criteria_value"]  = CRITERIA_MAP.get(crit, {}).get("value", "")
#             r["procedure_coding"] = PROCEDURES_MAP.get(proc, {}).get("coding", "")
#             r["procedure_value"]  = PROCEDURES_MAP.get(proc, {}).get("value", "")
#         for newc in ["criteria_coding", "criteria_value", "procedure_coding", "procedure_value"]:
#             if newc not in columns:
#                 columns.append(newc)
#
#     # --- Build final columns + rows for template ---
#     if pd is not None:
#         columns = list(df.columns)
#         # ensure preferred ordering
#         columns = _reorder_columns(columns, preferred_order)
#         records = df.astype(object).fillna("").to_dict(orient="records")
#     else:
#         columns = _reorder_columns(columns, preferred_order)
#         records = dict_rows
#
#     matrix_rows = []
#     for r in records:
#         matrix_rows.append([ r.get(c, "") for c in columns ])
#
#     warn = " | ".join(map_warnings) if map_warnings else None
#
#     return render(request, "analytics/data_table.html", {
#         "columns": columns,
#         "rows": matrix_rows,
#         "filename": file,
#         "error": warn,
#     })
