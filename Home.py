# ---------------- Home.py ----------------
# Import relevant libraries
import streamlit as st
import pandas as pd
import io, csv, re

# Page config & title 
st.set_page_config(page_title="Data Profiling Tool", layout="wide")
st.title("Data Profiling Tool")

st.markdown(
    """
Welcome to this data-profiling tool.  
Upload a CSV to explore **completeness**, **cardinality**, **distribution**, and **correctness**.

Use the **menu on the left** to switch between checks.  
💡 Tip: Start by uploading a tidy CSV.
"""
)

# Helpers 
def read_csv_safely(file):
    """Read CSV with delimiter sniffing, BOM handling, and header cleanup."""
    raw = file.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    bio = io.StringIO(raw)

    df = pd.read_csv(
        bio,
        sep=None,                # autodetect delimiter
        engine="python",
        na_values=["", " ", "NA", "N/A", "na", "n/a", "?", "-", "--"],
        keep_default_na=True,
        skip_blank_lines=True,
        quoting=csv.QUOTE_MINIMAL,
        skipinitialspace=True,
        on_bad_lines="warn",
        header=0
    )

    # normalise headers
    cols = (
        df.columns.astype(str)
          .str.replace(r"^\ufeff", "", regex=True)   # strip BOM
          .str.strip()
    )
    df.columns = cols

    # drop junk columns
    before_cols = df.shape[1]
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed(:\s*\d+)?$", flags=re.I)]
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, df.columns.notna()]
    dropped_cols = before_cols - df.shape[1]

    return df, dropped_cols

def to_numeric_resilient(series: pd.Series, pct_to_unit: bool = True) -> pd.Series:
    """Parse numbers robustly: handle %, currency symbols, commas; keep NaNs."""
    s = series.astype(str).str.strip()
    s = s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})

    pct_mask = s.str.endswith("%", na=False)
    s_clean = (
        s.str.replace(r"[£$,]", "", regex=True)  # remove currency symbols and commas
         .str.replace("%", "", regex=False)
    )
    num = pd.to_numeric(s_clean, errors="coerce")

    if pct_to_unit:
        num.loc[pct_mask] = num.loc[pct_mask] / 100.0

    return num

def looks_categorical(series: pd.Series, n_rows: int) -> bool:
    """Heuristic to decide if a text column is a Category."""
    s = series.dropna().astype(str).str.strip()
    if n_rows == 0 or len(s) == 0:
        return False

    uniq = s.nunique()

    # reject IDs / near-unique
    if (uniq / n_rows) > 0.5:
        return False
    if s.str.match(r"^[A-Za-z0-9_-]{6,}$").mean() > 0.3:
        return False

    # positive signals
    short_labels = (s.str.len().median() <= 25)
    abs_low = uniq <= 50
    rel_low = (uniq / max(n_rows, 1)) <= 0.2
    coverage = s.value_counts(normalize=True).head(10).sum() >= 0.8

    positive = sum([short_labels, abs_low, rel_low, coverage])
    return positive >= 3  # need at least 3 signals

def friendly_dtype_name(dtype_str: str) -> str:
    mapping = {
        "object": "Text",
        "string": "Text",
        "category": "Category",
        "bool": "Boolean",
        "boolean": "Boolean",
        "int64": "Whole number",
        "Int64": "Whole number",
        "float64": "Number (decimals)",
        "datetime64[ns]": "Date/Time"
    }
    return mapping.get(dtype_str, dtype_str)

DTYPE_EXPLAINER = {
    "Whole number": "Numbers without decimals (e.g., 1, 42, -7).",
    "Number (decimals)": "Numbers that can include decimals or converted into decimal (e.g., percentages, fractions).",
    "Text": "Words or labels (e.g., names, comments).",
    "Category": "A fixed set of labels (e.g., Male/Female, UK/US/FR).",
    "Boolean": "Logical values (Yes/No, True/False, 1/0 etc).",
    "Date/Time": "Dates and times (e.g., 2020-12-31)."
}

# ---------- Persist dataset across pages ----------
if "df" not in st.session_state:
    st.session_state["df"] = None
if "dropped_cols" not in st.session_state:
    st.session_state["dropped_cols"] = 0
if "filename" not in st.session_state:
    st.session_state["filename"] = None
if "file_bytes" not in st.session_state:
    st.session_state["file_bytes"] = None

# ---------- Uploader ----------
uploaded_file = st.file_uploader("Upload a CSV", type=["csv"], key="uploader")
st.caption("Note: Refresh webpage to clear CSV upload")

# If a new file is uploaded, parse and store in session
if uploaded_file is not None:
    raw = uploaded_file.read()
    st.session_state["file_bytes"] = raw
    st.session_state["filename"] = uploaded_file.name

    df_new, dropped_cols_new = read_csv_safely(io.BytesIO(raw))
    st.session_state["df"] = df_new
    st.session_state["dropped_cols"] = dropped_cols_new

# ---------- Main content ----------
if st.session_state["df"] is None:
    st.info("Upload a CSV to enable the pages.")
else:
    df = st.session_state["df"]
    dropped_cols = st.session_state.get("dropped_cols", 0)

    st.success(f"Dataset loaded: {st.session_state.get('filename', '(in memory)')}")
    
    st.markdown(
        "Below is a **quick snapshot** of your dataset, showing the **first few rows**, "
        "its **size**, **columns**, and a **brief profiling summary** to help you get familiar "
        "with the data before running the checks."
    )
    st.dataframe(df.head())
    st.write("Shape:", df.shape)
    st.caption(f"Note: This count excludes entirely empty rows during import to keep the dataset tidy.")

    st.write("Columns:", df.columns.tolist())
    if dropped_cols:
        st.caption(f"Parsed with delimiter detection. Dropped {dropped_cols} empty/unnamed columns.")

    # ---- Auto type conversions (after cleaning) ----
    conversions = []
    for col in df.columns:
        s = df[col]

        # 1) Date/Time
        if s.dtype == "object":
            parsed = pd.to_datetime(s, errors="coerce", infer_datetime_format=True)
            if parsed.notna().mean() >= 0.6:  # tolerant threshold
                df[col] = parsed
                conversions.append(f"{col} → datetime")

        # 2) True/False
        if df[col].dtype == "object":
            vals = df[col].dropna().astype(str).str.strip().str.lower()
            bool_map = {
                "true": True, "false": False, "yes": True, "no": False,
                "y": True, "n": False, "1": True, "0": False
            }
            if len(vals) and vals.isin(bool_map.keys()).mean() >= 0.9:
                df[col] = vals.map(bool_map).astype("boolean")
                conversions.append(f"{col} → bool")

        # 3) Numeric (robust: %, currency, commas) — evaluate only on non-blanks
        if df[col].dtype == "object":
            raw = df[col].astype(str).str.strip()
            nonblank = raw.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA}).notna()

            num = to_numeric_resilient(df[col])  # already handles %, £, $, commas
            if nonblank.sum() > 0:
                parsed_rate = num[nonblank].notna().mean()   # % of filled cells that parse as number
            else:
                parsed_rate = 0.0

            # require strong evidence on filled cells (e.g., ≥90% parse), ignore blanks
            if parsed_rate >= 0.9 and nonblank.mean() >= 0.05:  # at least 5% of rows non-blank
                if (num[nonblank] % 1 == 0).all():
                    df[col] = num.astype("Int64")
                    conversions.append(f"{col} → Int64")
                else:
                    df[col] = num.astype("float64")
                    conversions.append(f"{col} → float64")


        # 4) Category detection (after numeric/bool/date attempts)
        if df[col].dtype == "object":
            if looks_categorical(df[col], len(df)):
                df[col] = df[col].astype("category")
                conversions.append(f"{col} → category")

    # Save back for other pages
    st.session_state["df"] = df
    if conversions:
        st.caption("Auto-conversions: " + ", ".join(conversions))

    # ---- Profiling summary ----
    st.subheader("Profiling summary")
    st.markdown(
        "This table shows each column’s **data type** (e.g., text, number, date), the **number of unique values**,"
        "the **number of missing values** and **numerical statistics for numerical values** to help spot issues quickly."
    )
    # Build summary with user-friendly names
    dtype_friendly = df.dtypes.astype(str).map(friendly_dtype_name)
    summary = pd.DataFrame({
        "Data Type": dtype_friendly,
        "Unique Values": df.nunique(dropna=True),
        "Missing Values": df.isna().sum()
    })

    # Add hover-tooltips for the user-friendly types
    summary["Data Type"] = summary["Data Type"].apply(
        lambda nice: f"<abbr title='{DTYPE_EXPLAINER.get(nice, 'No description')}'>{nice}</abbr>"
    )

    # Numeric stats
    num_cols = df.select_dtypes(include=["number", "Float64", "Int64"]).columns
    if len(num_cols):
        summary.loc[num_cols, "Mean"] = df[num_cols].mean(numeric_only=True)
        summary.loc[num_cols, "Min"]  = df[num_cols].min(numeric_only=True)
        summary.loc[num_cols, "Max"]  = df[num_cols].max(numeric_only=True)

    st.markdown(summary.to_html(escape=False), unsafe_allow_html=True)
    st.caption(
        "Note 1: Columns with symbols (%, £, $, commas) are parsed as numbers where possible; "
        "blanks remain as missing values."
    )
    st.caption(
                "Note 2: A column is marked as Category when it mostly repeats a small set of short labels "
        "(e.g., Male/Female, UK/US) rather than having lots of unique codes or long text")

# ---------- Global CSS (polish) ----------
PRIMARY = "#2E86DE"
st.markdown(f"""
<style>
h1, h2, h3 {{ color: #111111; }}
.stButton>button {{
  background:{PRIMARY}; color:white; border-radius:12px; border:0; padding:0.6rem 1rem;
}}
.stButton>button:hover {{ filter: brightness(0.92); }}
.block-container {{ padding-top: 2rem; }}
</style>
""", unsafe_allow_html=True)

# Run:
# 1) cd c:\users\amy_t\streamlit-profiler
# 2) py -m streamlit run Home.py
# -----------------------------------------
