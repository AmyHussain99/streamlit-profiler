# pages/01_Completeness.py
# Import relevant libraries 
import streamlit as st
import pandas as pd
import plotly.express as px
import altair as alt

st.set_page_config(page_title="Completeness", layout="wide")
st.title("Completeness")
st.markdown(
    """
This page shows **what’s missing and where**.  
Use it to spot columns with gaps, see how complete each row is, and scan a heatmap of missing cells.  
💡Tip: Filter or search the column list to focus on trouble spots.
"""
)

# Guard: dataset must exist
if "df" not in st.session_state:
    st.warning("No dataset loaded. Please go to Home and upload a CSV first.")
    st.stop()

df = st.session_state["df"]

# Colour constants
OKABE_ITO = {
    "blue": "#0072B2",
    "sky": "#56B4E9",
    "orange": "#E69F00",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "green": "#009E73",
    "yellow": "#F0E442",
    "black": "#000000"
}
COLOR_BANDS = {
    "0% (None)": "#EAEAEA",              # neutral grey for zero missing
    "Low (≤5%)": OKABE_ITO["sky"],       # 👁️ CB-safe, gentle
    "Moderate (5–20%)": OKABE_ITO["orange"],
    "High (20–50%)": OKABE_ITO["vermillion"],
    "Severe (>50%)": OKABE_ITO["purple"],
}
def _band(p):
    if p == 0: return "0% (None)"
    if p <= 5: return "Low (≤5%)"
    if p <= 20: return "Moderate (5–20%)"
    if p <= 50: return "High (20–50%)"
    return "Severe (>50%)"

# Column-level missingness (Plotly bar)
st.subheader("Missingness by column")
st.markdown(
    "This chart shows **how much data is missing in each column** as a percentage, so you can quickly spot the worst-affected columns."
)

# Compute % missing and band it
miss_pct = df.isna().mean().sort_values(ascending=False) * 100
miss_tbl = pd.DataFrame({
    "Column": miss_pct.index,
    "Missing %": miss_pct.values.round(2)
})
miss_tbl["Band"] = miss_tbl["Missing %"].apply(_band)

# Plot with Okabe–Ito bands and % labels
fig = px.bar(
    miss_tbl,
    x="Column",
    y="Missing %",
    color="Band",
    color_discrete_map=COLOR_BANDS,
    title="Missing % per column"
)
fig.update_traces(texttemplate="%{y:.1f}%", textposition="outside", cliponaxis=False)
fig.update_layout(
    xaxis_tickangle=-45,
    uniformtext_minsize=10, uniformtext_mode="hide",
    legend_title_text="Missingness band"
)
st.plotly_chart(fig, use_container_width=True)

# Row completeness
st.subheader("Row completeness")
st.markdown(
    "Shows how much of each row is **filled in** (100% = no blanks). "
    "The box below summarises a *typical* row."
)

# Palette bits (Okabe–Ito)
OKI_ORANGE = "#E69F00"   # Missing
OKI_BLUE   = "#0072B2"   # Present (neutral)

row_complete = df.notna().mean(axis=1) * 100
median_rc = float(row_complete.median())

# Median card (stands out)
PRIMARY = "#56B4E9"  
st.markdown(f"""
<div class="metric-card">
  <div class="metric-label">Median row completeness</div>
  <div class="metric-value">{median_rc:.1f}%</div>
  <div class="metric-help">A typical row has this % of fields filled.</div>
</div>
""", unsafe_allow_html=True)

# CSS for the card (once per page is fine)
st.markdown(f"""
<style>
.metric-card {{
  background: #F8F9FA;
  border: 1px solid #ECECEC;
  border-left: 6px solid {PRIMARY};
  border-radius: 14px;
  padding: 14px 18px;
  display: inline-block;
  margin-bottom: 0.75rem;
}}
.metric-label {{ font-weight: 600; color: #333; margin-bottom: 4px; }}
.metric-value {{ font-size: 2.8rem; line-height: 1; font-weight: 800; color: #111; }}
.metric-help {{ color: #666; font-size: 0.9rem; margin-top: 6px; }}
</style>
""", unsafe_allow_html=True)

# New line / section for the threshold
st.markdown("**Row completion threshold (%)**")
st.caption("This will highlight the number of rows below a chosen completeness level "
"(e.g., 90% will highlight rows with more than 10% of data blank).")

thr = st.slider(
    label="", min_value=0, max_value=100, value=90, step=1,
    help="Choose the minimum percentage of non-missing cells a row must have." 
     "Rows below this level are considered incomplete."
)

missing_cutoff = 100 - thr
below_mask = (row_complete < thr)

st.metric("Rows below threshold", f"{int(below_mask.sum())} / {len(df)}")
st.caption(f"Rows with less than **{thr}%** cells filled (i.e. more than **{missing_cutoff}%** cells missing) are flagged")

 # --- Row inspector (for flagged rows) ---
flagged_idx = row_complete[below_mask].sort_values().index
flagged_n = len(flagged_idx)

if flagged_n == 0:
    st.info("No rows fall below the threshold. Increase the threshold or check back after cleaning.")
else:
    st.markdown("**Inspect a row** below the threshold to see which cells are present vs missing.**")

    # Legend
    legend_html = f"""
    <div style="margin-top:6px;margin-bottom:12px;">
      <div style="display:inline-flex;align-items:center;gap:14px;background:#F8F9FA;border:1px solid #ECECEC;border-radius:10px;padding:6px 12px;">
        <span style="font-weight:600;">Legend:</span>
        <span style="display:inline-flex;align-items:center;gap:6px;">
          <span style="display:inline-block;min-width:28px;text-align:center;padding:2px 10px;border-radius:999px;background:{OKI_BLUE};color:white;font-weight:700;'>✓</span>
          Present
        </span>
        <span style="display:inline-flex;align-items:center;gap:6px;">
          <span style="display:inline-block;min-width:28px;text-align:center;padding:2px 10px;border-radius:999px;background:{OKI_ORANGE};color:black;font-weight:700;'>✕</span>
          Missing
        </span>
      </div>
    </div>
    """
    st.markdown(legend_html, unsafe_allow_html=True)

    # Picker
    pick = st.selectbox("Choose a row to inspect", flagged_idx, index=0)

    # Build a one-row boolean mask (True = Missing, False = Present)
    status_bool = df.loc[pick].isna()

    # Convert to HTML badges
    def _badge(v: bool) -> str:
        return (f"<span style='display:inline-block;min-width:28px;text-align:center;padding:2px 10px;"
                f"border-radius:999px;background:{OKI_ORANGE};color:black;font-weight:700;'>✕</span>"
                if v else
                f"<span style='display:inline-block;min-width:28px;text-align:center;padding:2px 10px;"
                f"border-radius:999px;background:{OKI_BLUE};color:white;font-weight:700;'>✓</span>")

    display_df = (
        pd.DataFrame([status_bool], index=[f"Row {pick}"])
        .astype(object)
        .applymap(_badge)
    )

    # Table CSS + render
    table_css = """
    <style>
    .badge-table { border-collapse: separate; border-spacing: 0; width: 100%; }
    .badge-table th, .badge-table td { border: 1px solid #ECECEC; padding: 6px 8px; text-align: center; background: white; }
    .badge-table th { background: #F8F9FA; font-weight: 600; }
    .badge-wrap { overflow-x: auto; border-radius: 10px; }
    </style>
    """
    html = table_css + "<div class='badge-wrap'>" + display_df.to_html(escape=False, classes='badge-table') + "</div>"

    st.markdown(f"**Row {pick} detail** — {row_complete.loc[pick]:.1f}% complete")
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Scroll horizontally to scan all columns.")

    # Download button only if flagged rows exist
    csv_bytes = df.loc[below_mask].to_csv(index=True).encode("utf-8")
    st.download_button("Download rows below threshold (CSV)", 
                       data=csv_bytes, file_name="rows_below_threshold.csv")

# Heatmap sidebar
with st.sidebar:
    st.subheader("Heatmap options")
    max_cap = min(len(df), 10000)
    default_n = min(len(df), 500)
    sample_n = st.slider("Rows to sample", 50, max_cap, default_n, 50)
    seed = st.number_input("Random seed", value=42, step=1)

    st.caption(
        "“Rows to sample” controls how many rows appear in the heatmap. "
        "Sampling keeps the chart fast and readable on large files. "
        "If your dataset is small, slide it up to show all rows; "
        "if your browser feels slow, slide it down. "
        "The seed fixes which random rows are shown so you can compare runs."
    )

# Missingness heatmap plot
st.subheader("Missingness heatmap")
st.markdown(
    "Each square shows whether a **cell is filled or missing**. "
    "Rows run left-to-right; columns run top-to-bottom. "
    "Use it to spot patterns, like whole columns or blocks of rows with gaps."
)

# Sample for speed (sample_n and seed come from the sidebar)
sample = df.sample(n=sample_n, random_state=int(seed))

# Checkbox to hide fully complete rows/columns
hide_full = st.checkbox("Hide rows/columns that are 100% complete", value=False, help="Removes rows and columns with no missing cells to make patterns easier to see.")

if hide_full:
    col_miss = sample.isna().mean()          # per-column missing rate
    row_miss = sample.isna().mean(axis=1)    # per-row missing rate

    cols_keep = col_miss[col_miss > 0].index
    rows_keep = row_miss[row_miss > 0].index

    sample = sample.loc[rows_keep, cols_keep]

    if sample.shape[0] == 0 or sample.shape[1] == 0:
        st.info("Nothing to show after filtering — all rows/columns are fully complete. Untick the filter to see everything.")
        # Skip the heatmap if nothing left to plot
        st.stop()

# Prepare data
heat_df = (
    sample.isna()
    .reset_index(names="Row")
    .melt(id_vars="Row", var_name="Column", value_name="Missing")
)
heat_df["Missing"] = heat_df["Missing"].map({False: "Present", True: "Missing"})

# Order columns by % missing (descending) for readability
col_order = (
    sample.isna().mean().sort_values(ascending=False).index.tolist()
)

# Order rows by % missing (most → least)
row_order = sample.isna().mean(axis=1).sort_values(ascending=False).index.tolist()

# Dynamic height
height = min(600, max(220, 18 * df.shape[1]))

# Okabe–Ito colours
OKI_BLUE   = "#0072B2"   # Present (neutral)
OKI_ORANGE = "#E69F00"   # Missing (salient, CB-safe)

heat = (
    alt.Chart(heat_df)
    .mark_rect()
    .encode(
        x=alt.X("Row:O", sort=row_order, axis=None),
        y=alt.Y("Column:O", sort=col_order),
        color=alt.Color(
            "Missing:N",
            legend=alt.Legend(title="Cell status"),
            scale=alt.Scale(domain=["Present", "Missing"], range=[OKI_BLUE, OKI_ORANGE])
        ),
        tooltip=["Row:O", "Column:O", "Missing:N"]
    )
    .properties(title="Rows × Columns", height=height)
    .configure_axis(labelLimit=300)
)

st.altair_chart(heat, use_container_width=True)

# Clear sampling note (uses your actual totals)
st.caption(
    f"Use the sidebar on the left to adjust the number of sampled rows "
    f"(dataset has a total of **{len(df)}** rows; heatmap currently shows **{sample_n}**). "
    "Sampling keeps the chart fast and readable — plotting every row in very large datasets can slow down or crash your browser."
)

st.markdown(
    "The heatmap orders **columns** from the **highest** percentage of missing values to the **lowest**, "
    "and **rows** from the **most missing** to the **least** (within the sampled rows). "
    "This puts the biggest gaps at the top and left for quicker scanning."
)
