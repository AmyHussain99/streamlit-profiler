# pages/02_Cardinality.py
import streamlit as st
import pandas as pd
import itertools
import plotly.express as px

st.set_page_config(page_title="Cardinality", layout="wide")
st.title("Cardinality")
st.markdown(
    """
This page looks at **how varied each column is**.  
**Cardinality** tells you **how many different values** a column has — lots of different values looks like an ID, while just a few repeating values looks like a category.

Use it to spot **IDs/keys** (lots of different values), **categories/labels** (few repeating values), and **duplicates**.
"""
)

# Guard: dataset must exist
if "df" not in st.session_state:
    st.warning("No dataset loaded. Please go to Home and upload a CSV first.")
    st.stop()

df = st.session_state["df"]
n_rows = len(df)

# ---- Palette (Okabe–Ito bands for distinct ratio) ----
OKABE_ITO = {
    "blue": "#0072B2",
    "sky": "#56B4E9",
    "orange": "#E69F00",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "green": "#009E73",
    "yellow": "#F0E442",
    "black": "#000000",
}

def band_distinct_ratio(r):
    if r >= 0.90: return "High (key-like)"
    if r >= 0.10: return "Medium"
    return "Low (category-like)"

# Same hues as Completeness bands
CARD_COLOR_MAP = {
    "High (key-like)": OKABE_ITO["vermillion"],   # High → vermillion
    "Medium": OKABE_ITO["orange"],                # Medium → orange
    "Low (category-like)": OKABE_ITO["sky"],      # Low → sky
}
BAND_ORDER = ["High (key-like)", "Medium", "Low (category-like)"]

# --- Column cardinality (table + bar) ---
st.subheader("Column cardinality")

# 1) Build the summary table
card = pd.DataFrame({
    "Column": df.columns,
    "Unique": [df[c].nunique(dropna=True) for c in df.columns],
    "Missing": [df[c].isna().sum() for c in df.columns],
})
card["Distinct ratio"] = (card["Unique"] / max(n_rows, 1)).round(4)
card["Band"] = card["Distinct ratio"].apply(band_distinct_ratio)
card = card.sort_values(by=["Distinct ratio", "Unique"], ascending=[False, False], ignore_index=True)

# 2) Bar chart (first)
card["Unique_label"] = card["Unique"].map(lambda x: f"{x:,}")
fig = px.bar(
    card,
    x="Column", y="Unique",
    color="Band",
    color_discrete_map=CARD_COLOR_MAP,
    category_orders={"Band": BAND_ORDER},  # ensure legend/order matches Completeness
    hover_data=["Distinct ratio", "Missing"],
    title="Unique count per column",
    text="Unique_label"
)

fig.update_traces(textposition="outside", cliponaxis=False)
fig.update_layout(
    xaxis_tickangle=-45,
    legend_title_text="Distinctness band",
    uniformtext_minsize=8, uniformtext_mode="hide",
    yaxis_title="Unique values",
)
st.plotly_chart(fig, use_container_width=True)
st.markdown("The bar chart above shows a quick view of how varied each column is.")


# 3) Table (under the chart)
st.markdown("The table below shows more detail of each column's cardinality.")
st.dataframe(card[["Column", "Unique", "Missing", "Distinct ratio", "Band"]], use_container_width=True)

# 4) Definitions under the table
st.markdown(
    """
  **Definitions:**
- **Unique values**: how many **different** values a column has (ignores blanks).  
- **Missing values**: how many rows are **blank** in that column.  
- **Distinct ratio**: Unique number of values ÷ Total rows — close to **1.0** looks like an **ID/key**; near **0** looks like a **category/label**.
"""
)
st.caption("💡 Tip: Very high ratios (≈1.0) often mean identifiers; very low ratios suggest categories or fixed pick-lists.")


# --- Duplicate rows (with Undo) ---
st.subheader("Duplicate rows")

# If we just changed the dataset in a previous run, show a toast + Undo
if st.session_state.get("dups_action") == "dropped":
    removed_n = st.session_state.get("dups_removed_n", 0)
    st.success(f"Removed {removed_n} exact duplicate rows.")
    # Undo button
    if st.button("Undo duplicate removal"):
        if "df_backup_before_dups" in st.session_state:
            st.session_state["df"] = st.session_state["df_backup_before_dups"]
        # Clean up flags/backups
        for k in ("df_backup_before_dups", "dups_action", "dups_removed_n", "dups_removed_rows"):
            st.session_state.pop(k, None)
        st.rerun()

# Always compute from current df
df = st.session_state["df"]
dup_mask = df.duplicated(keep="first")
n_dups = int(dup_mask.sum())
st.markdown(
    f"Duplicate rows (excluding first occurrence): "
    f"<span style='color:#D55E00; font-weight:700;'>{n_dups}</span>",
    unsafe_allow_html=True
)


if n_dups > 0:
    with st.expander("Preview duplicate rows"):
        preview = df[dup_mask].head(50)
        st.dataframe(preview, use_container_width=True)
        st.caption("Showing up to the first 50 duplicate rows (excluding the first occurrence).")

    cA, cB = st.columns([1, 1])
    with cA:
        if st.button("Drop exact duplicate rows from session dataset"):
            # Backup current df for undo
            st.session_state["df_backup_before_dups"] = df.copy()
            # Keep removed rows (optional: for audit/export)
            removed_rows = df[dup_mask].copy()
            st.session_state["dups_removed_rows"] = removed_rows
            st.session_state["dups_removed_n"] = int(dup_mask.sum())

            # Perform drop and rerun
            st.session_state["df"] = df.drop_duplicates(keep="first").reset_index(drop=True)
            st.session_state["dups_action"] = "dropped"
            st.rerun()

    with cB:
        # Optional: let user download the duplicates that would be/just were removed
        if n_dups > 0:
            dup_csv = df[dup_mask].to_csv(index=False).encode("utf-8")
            st.download_button("Download duplicate rows (CSV)", dup_csv, file_name="duplicates_removed.csv")
else:
    st.info("No exact duplicate rows found.")

# --- Value-frequency explorer ---
st.subheader("Column value frequency explorer")
st.markdown("Pick a column to see which values appear most often (helps confirm categories or spot odd codes).")
col_select = st.selectbox("Choose a column", options=df.columns)

if col_select:
    vc = (
        df[col_select]
        .astype("string")
        .fillna("<NA>")
        .value_counts(dropna=False)
        .rename_axis(col_select)
        .reset_index(name="Count")
    )
    vc["Share of rows (%)"] = (vc["Count"] / max(n_rows, 1) * 100).round(2)

    # Table first
    st.dataframe(vc.head(50), use_container_width=True)




# --- Light CSS polish (keeps your theme) ---
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
