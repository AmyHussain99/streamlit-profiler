# pages/06_Incremental.py
import streamlit as st
import pandas as pd
import numpy as np
import io, csv, re
import altair as alt

# ---------- Page setup ----------
st.set_page_config(page_title="Incremental Profiling", layout="wide")
st.title("Incremental Profiling")

st.markdown("""
Compare a **new CSV** against the dataset you loaded on *Home*.  
Shows **schema changes** (columns added/removed, high-level type changes) and **row changes**.  
You can **replace** the dataset across all pages, or **undo** this to back to original.
""")
st.caption("💡 We coerce the new file to the baseline’s **type families** (Numeric/Text/Date-Time/Boolean/Category) to avoid false alarms from CSV type guessing.")

# ---------- Guards ----------
if "df" not in st.session_state or st.session_state["df"] is None:
    st.warning("No dataset loaded. Please go to Home and upload a CSV first.")
    st.stop()

BASE = st.session_state["df"]

# persistence for NEW + backup
st.session_state.setdefault("df_backup", None)
st.session_state.setdefault("inc_new_raw", None)   # raw bytes of NEW upload
st.session_state.setdefault("inc_new_df", None)    # coerced NEW dataframe
st.session_state.setdefault("inc_new_name", None)  # filename

# ---------- Okabe–Ito palette ----------
OKABE_ITO = {
    "blue":   "#0072B2",
    "orange": "#E69F00",
    "sky":    "#56B4E9",
    "green":  "#009E73",
    "yellow": "#F0E442",
    "red":    "#D55E00",
    "pink":   "#CC79A7",
    "black":  "#000000",
}
PRIMARY = "#2E86DE"

# ---------- Helpers ----------
def read_csv_safely_bytes(raw_bytes: bytes) -> pd.DataFrame:
    text = raw_bytes.decode("utf-8", errors="replace")
    bio = io.StringIO(text)
    df = pd.read_csv(
        bio, sep=None, engine="python",
        na_values=["", " ", "NA", "N/A", "na", "n/a", "?", "-", "--"],
        keep_default_na=True, skip_blank_lines=True,
        quoting=csv.QUOTE_MINIMAL, skipinitialspace=True,
        on_bad_lines="warn", header=0
    )
    # normalise headers & drop junk
    df.columns = (
        df.columns.astype(str)
        .str.replace(r"^\ufeff", "", regex=True)
        .str.strip()
    )
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed(:\s*\d+)?$", flags=re.I)]
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, df.columns.notna()]

    # --- match Home semantics for row count ---
    # treat whitespace-only cells as missing, then drop rows that are entirely missing
    df = df.replace(r"^\s*$", pd.NA, regex=True).dropna(how="all")

    return df


def dtype_family(dtype_str: str) -> str:
    if "datetime64" in dtype_str: return "datetime"
    if dtype_str in ("boolean", "bool"): return "boolean"
    if "Int" in dtype_str or "int" in dtype_str: return "int"
    if "float" in dtype_str: return "float"
    if dtype_str == "category": return "category"
    return "text"

BOOL_MAP = {"true": True, "false": False, "yes": True, "no": False, "y": True, "n": False, "1": True, "0": False}

def to_numeric_resilient(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    s = s.str.replace(r"[£$,]", "", regex=True).str.replace("%", "", regex=False)
    return pd.to_numeric(s, errors="coerce")

def coerce_to_schema(df_in: pd.DataFrame, schema_fam: dict) -> pd.DataFrame:
    """Align NEW to BASE type *families* to reduce false dtype diffs."""
    dfc = df_in.copy()
    for c, fam in schema_fam.items():
        if c not in dfc.columns:
            continue
        try:
            if fam == "datetime":
                dfc[c] = pd.to_datetime(dfc[c], errors="coerce", infer_datetime_format=True)
            elif fam == "boolean":
                vals = dfc[c].astype(str).str.strip().str.lower()
                dfc[c] = vals.map(BOOL_MAP).astype("boolean")
            elif fam == "int":
                dfc[c] = to_numeric_resilient(dfc[c]).round(0).astype("Int64")
            elif fam == "float":
                dfc[c] = to_numeric_resilient(dfc[c]).astype("float64")
            elif fam == "category":
                dfc[c] = dfc[c].astype("string").str.strip().astype("category")
            else:  # text
                dfc[c] = dfc[c].astype("string")
        except Exception:
            pass
    return dfc

def friendly_dtype(dtype_str: str) -> str:
    # Group ints/floats as "Numeric" to avoid noisy changes
    if "float" in dtype_str or "int" in dtype_str or "Int" in dtype_str:
        return "Numeric"
    mapping = {"object":"Text","string":"Text","category":"Category",
               "bool":"Boolean","boolean":"Boolean","datetime64[ns]":"Date/Time"}
    return mapping.get(dtype_str, dtype_str)

def type_counts(df: pd.DataFrame) -> pd.DataFrame:
    counts = pd.Series([friendly_dtype(str(t)) for t in df.dtypes], index=df.columns).value_counts().reset_index()
    counts.columns = ["Type", "Count"]
    return counts

def normalize_for_rowdiff(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Consistent string forms for fair, key-free row comparison (handles dates, numbers, blanks)."""
    out = pd.DataFrame(index=df.index)
    SENT = "__NA__"
    for c in cols:
        s = df[c]
        s_dt = pd.to_datetime(s, errors="coerce", infer_datetime_format=True)
        is_dt = s_dt.notna()
        s_num = pd.to_numeric(s, errors="coerce")
        is_num = s_num.notna() & ~is_dt
        col_norm = pd.Series("", index=df.index, dtype="string")
        if is_dt.any():
            col_norm[is_dt] = s_dt[is_dt].dt.strftime("%Y-%m-%d %H:%M:%S")
        if is_num.any():
            col_norm[is_num] = s_num[is_num].map(lambda x: f"{x:.6f}".rstrip("0").rstrip("."))
        other = ~(is_dt | is_num)
        if other.any():
            s_str = s.astype("string")
            col_norm[other] = s_str[other].fillna(SENT).str.strip()
        col_norm = col_norm.replace({"": SENT})
        out[c] = col_norm
    return out

# ---------- 1) Upload / persist NEW ----------
st.subheader("1) Upload new dataset")

col_up, col_keep = st.columns([3,1])
with col_up:
    new_file = st.file_uploader("Upload CSV", type=["csv"], key="inc_keyfree_uploader")
with col_keep:
    if st.button("Clear NEW", help="Forget the uploaded NEW file"):
        st.session_state["inc_new_raw"] = None
        st.session_state["inc_new_df"] = None
        st.session_state["inc_new_name"] = None
        st.success("Cleared the NEW upload for this session.")
        st.rerun()

# If user uploads, store in session; else reuse persisted NEW
if new_file is not None:
    st.session_state["inc_new_raw"] = new_file.read()
    st.session_state["inc_new_name"] = getattr(new_file, "name", "uploaded.csv")

if st.session_state["inc_new_raw"] is None:
    with st.expander("What’s compared?"):
        st.markdown("""
- **Columns**: **Added**, **Removed**.  
- **Data types (high-level)**: e.g., **Text ↔ Numeric**, **Text ↔ Date/Time**.  
- **Rows**: exact **added**/**removed** counts using a multiset match over **common columns** (no keys required).  
The NEW file is kept in session so you can switch pages and come back to Undo.
""")
    st.stop()

# Build NEW dataframe (from cache or from raw)
schema_family = {c: dtype_family(str(dt)) for c, dt in BASE.dtypes.items()}

if st.session_state["inc_new_df"] is None:
    NEW_raw_df = read_csv_safely_bytes(st.session_state["inc_new_raw"])
    st.session_state["inc_new_df"] = coerce_to_schema(NEW_raw_df, schema_family)

NEW = st.session_state["inc_new_df"]  # persisted NEW
new_name = st.session_state.get("inc_new_name") or "(uploaded)"

# Shapes + previews
st.markdown("**Shapes**")
st.write(f"Baseline: {BASE.shape}  |  New ({new_name}): {NEW.shape}")

c1, c2 = st.columns(2)
with c1:
    st.caption("Baseline (first 5)")
    st.dataframe(BASE.head(), use_container_width=True, height=220)
with c2:
    st.caption(f"New (first 5) — {new_name}")
    st.dataframe(NEW.head(), use_container_width=True, height=220)

# ---------- 2) Schema changes ----------
st.subheader("2) Schema changes")
st.markdown("Schema changes mean **differences in the structure** of the dataset — for example, "
"if columns have been added, removed, renamed, or changed in type compared to the original file.")

base_cols = set(BASE.columns)
new_cols  = set(NEW.columns)
added_cols   = sorted(list(new_cols - base_cols))
removed_cols = sorted(list(base_cols - new_cols))
common_cols  = sorted(list(base_cols & new_cols))

schema_cols_df = pd.DataFrame({
    "Added columns": pd.Series(added_cols, dtype="object"),
    "Removed columns": pd.Series(removed_cols, dtype="object"),
})
st.dataframe(schema_cols_df, use_container_width=True)

# Dtype changes after family coercion
dtype_base = pd.Series(BASE.dtypes.astype(str), name="Baseline dtype")
dtype_new  = pd.Series(NEW.dtypes.astype(str),  name="New dtype")

dtype_changes = []
for c in common_cols:
    fb = friendly_dtype(dtype_base[c])
    fn = friendly_dtype(dtype_new[c])
    if fb != fn:
        dtype_changes.append((c, fb, fn))

st.markdown("**Columns with data-type changes**")
if dtype_changes:
    dtype_df = pd.DataFrame(dtype_changes, columns=["Column", "Baseline type", "New type"])
    st.dataframe(dtype_df, use_container_width=True)
else:
    st.caption("No data-type changes detected (after family coercion).")

# Column type count bars (Baseline vs New)
st.caption("Column types (count by dataset)")
tc_base = type_counts(BASE); tc_base["Dataset"] = "Baseline"
tc_new  = type_counts(NEW);  tc_new["Dataset"]  = "New"
tc_both = pd.concat([tc_base, tc_new], ignore_index=True)

chart = (
    alt.Chart(tc_both)
    .mark_bar()
    .encode(
        x=alt.X("Type:N", sort="-y"),
        y=alt.Y("Count:Q"),
        color=alt.Color("Dataset:N",
                        scale=alt.Scale(domain=["Baseline","New"],
                                        range=[OKABE_ITO["blue"], OKABE_ITO["orange"]])),
        tooltip=["Dataset","Type","Count"]
    )
    .properties(height=240)
)
st.altair_chart(chart, use_container_width=True)

# ---------- 3) Row changes (exact multiset, key-free) ----------
st.subheader("3) Row changes")

if len(common_cols) == 0:
    st.info("No common columns between files, so row comparison isn’t possible.")
else:
    # Normalise both sides to avoid false diffs (1 vs 1.0, date formats, blanks)
    BASE_N = normalize_for_rowdiff(BASE, common_cols)
    NEW_N  = normalize_for_rowdiff(NEW,  common_cols)

    # Per-duplicate index per identical row (multiset trick)
    BASE_N["__dup_idx__"] = BASE_N.groupby(common_cols).cumcount()
    NEW_N["__dup_idx__"]  = NEW_N.groupby(common_cols).cumcount()

    join_cols = common_cols + ["__dup_idx__"]
    diff = BASE_N.merge(NEW_N, on=join_cols, how="outer", indicator=True)

    removed_rows = diff[diff["_merge"] == "left_only"].drop(columns=["_merge"])
    added_rows   = diff[diff["_merge"] == "right_only"].drop(columns=["_merge"])

    n_added   = len(added_rows)
    n_removed = len(removed_rows)

    st.write(f"**New rows**: {n_added}   |   **Removed rows**: {n_removed}")
    st.caption("Computed without keys using a multiset match across **common columns**; duplicates handled correctly.")

    cA, cB = st.columns(2)
    with cA:
        st.markdown("Preview: new rows (first 30)")
        if n_added:
            added_idx = (
                NEW_N.reset_index()
                .merge(added_rows.reset_index(drop=True), on=join_cols, how="inner")["index"]
            )
            st.dataframe(NEW.loc[added_idx].head(30), use_container_width=True)
        else:
            st.write("None")
    with cB:
        st.markdown("Preview: removed rows (first 30)")
        if n_removed:
            removed_idx = (
                BASE_N.reset_index()
                .merge(removed_rows.reset_index(drop=True), on=join_cols, how="inner")["index"]
            )
            st.dataframe(BASE.loc[removed_idx].head(30), use_container_width=True)
        else:
            st.write("None")

# ---------- 4) Apply or undo (persists across pages) ----------
st.subheader("4) Apply or undo")

colA, colB = st.columns(2)
with colA:
    if st.button("Replace dataset with NEW (apply to all pages)", type="primary"):
        # keep backup ONLY when replacing
        st.session_state["df_backup"] = BASE.copy()
        st.session_state["df"] = NEW.copy()
        st.success("Replaced current dataset with NEW. All pages will now use the new data.")
        st.rerun()

with colB:
    if st.button("Undo last replace"):
        if st.session_state.get("df_backup") is not None:
            # restore baseline; keep NEW in session so user can re-apply later
            st.session_state["df"], st.session_state["df_backup"] = st.session_state["df_backup"], None
            st.success("Restored the previous dataset.")
            st.rerun()
        else:
            st.info("Nothing to undo yet.")

# ---------- Definitions ----------
with st.expander("Definitions & guidance"):
    st.markdown(f"""
- **Added/Removed columns**: present only in one of the files.  
- **Data-type changes**: high-level (Text / Numeric / Date/Time / Boolean / Category).  
  Int and float are grouped as **Numeric** to avoid minor numeric-type noise.  
- **Row changes**: exact counts via **multiset** matching across common columns (duplicates preserved).  
- **Persistence**: the NEW upload is stored in session so it survives page switches; use **Clear NEW** to discard it.
""")

# ---------- CSS polish ----------
st.markdown(f"""
<style>
h1, h2, h3 {{ color: #111111; }}
.stButton>button {{
  background:{PRIMARY}; color:white; border-radius:12px; border:0; padding:0.6rem 1rem;
}}
.stButton>button:hover {{ filter: brightness(0.92); }}
.block-container {{ padding-top: 2rem; }}
.dataframe thead th {{ background: #f7f7f7; }}
</style>
""", unsafe_allow_html=True)
