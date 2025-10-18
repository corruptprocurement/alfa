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


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

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