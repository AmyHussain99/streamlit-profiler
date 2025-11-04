# pages/03_Distribution.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import altair as alt

st.set_page_config(page_title="Distribution", layout="wide")
st.title("Distribution")
st.markdown(
    """
This page shows **how values are spread** in your data.  
Use it to spot **typical ranges**, **outliers**, and **patterns** between columns.
"""
)

# Guard
if "df" not in st.session_state:
    st.warning("No dataset loaded. Please go to Home and upload a CSV first.")
    st.stop()

df = st.session_state["df"]

# Okabe–Ito palette (same across the app)
OKI = {
    "blue": "#0072B2",
    "sky": "#56B4E9",
    "orange": "#E69F00",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "green": "#009E73",
    "yellow": "#F0E442",
    "black": "#000000",
}

# Identify types
num_cols = df.select_dtypes(include=["number", "Float64", "Int64"]).columns.tolist()
cat_cols = df.select_dtypes(exclude=["number", "Float64", "Int64", "datetime64[ns]"]).columns.tolist()

with st.sidebar:
    st.subheader("Display options")
    view = st.radio("View", ["Numeric", "Categorical"], horizontal=True)
    if view == "Numeric":
        sel_num = st.multiselect("Numeric columns", options=num_cols, default=num_cols[:3])
        bins = st.slider("Bins", 5, 100, 30)
        logy = st.checkbox("Log Y-axis", value=False,
                           help="Helpful when counts vary a lot between bins.")
        kde = st.checkbox("Show density curve", value=False,
                          help="Smooth curve to show overall shape of the distribution.")
        show_outliers = st.checkbox("Flag outliers (IQR method)", value=True,
                                    help="Uses Q1±1.5×IQR rule to estimate outliers.")
        sample_for_matrix = st.slider("Scatter matrix sample (rows)", 500, 10000, 2000, step=500)
    else:
        sel_cat = st.multiselect("Categorical columns", options=cat_cols, default=cat_cols[:1])
        top_k = st.slider("Show top K values", 5, 100, 30)
        normalise = st.checkbox("Show % instead of counts", value=False)

st.caption("💡 Tip: Use the sidebar to switch between **Numeric** and **Categorical** views.")

# ---------- NUMERIC ----------
if view == "Numeric":
    if not num_cols or not sel_num:
        st.info("No numeric columns found or selected.")
        st.stop()

    # One-time explainer for the stats table (lay + brief)
    stats_help = pd.DataFrame({
        "Metric": ["count", "mean", "std (Standard Deviation)", "min", "5%", "25%", "50% (median)", "75%", "95%", "max"],
        "What it means": [
            "Number of non-blank values",
            "Average value",
            "Spread (how far values vary)",
            "Smallest value",
            "Value above 5% of the data",
            "Lower quartile (bottom 25%)",
            "Middle value (half above, half below)",
            "Upper quartile (top 25%)",
            "Value below 95% of the data",
            "Largest value",
        ],
        "Why it matters": [
            "Shows how much data is available",
            "Gives the ‘typical’ level",
            "Large std hints at high variability",
            "Lower bound of your data",
            "Helpful to spot low-end outliers",
            "Start of the ‘typical’ range",
            "Robust centre for skewed data",
            "End of the ‘typical’ range",
            "Helpful to spot high-end outliers",
            "Upper bound of your data",
        ]
    })

    st.subheader("How to read the summary table")
    st.markdown(
        "The table below explains each statistic you’ll see for numeric columns and why it’s useful."
    )
    st.dataframe(stats_help, use_container_width=True)
    st.caption("💡 You’ll see these metrics shown for each numeric column you select.")

    # Short histogram explainer
    st.markdown(
        "**What a histogram shows:** bars count how many rows fall into each value range (bin). "
        "Tall bars = common ranges; tiny bars = rare ranges."
    )

    for col in sel_num:
        s = pd.to_numeric(df[col], errors="coerce")
        n = s.notna().sum()
        if n == 0:
            st.warning(f"‘{col}’ has no valid numeric values.")
            continue

        st.subheader(f"{col}")

        # Summary metrics for this column
        stats = s.describe(percentiles=[.05, .25, .5, .75, .95]).to_frame(name=col)
        st.dataframe(stats.T, use_container_width=True)

        # Outlier mask (IQR)
        if show_outliers:
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            out_rate = (s.lt(lower) | s.gt(upper)).mean() * 100
            st.caption(f"Outliers by IQR (±1.5×IQR): ~{out_rate:.2f}%")

        # Histogram (Altair) with Okabe–Ito colouring
        base_df = pd.DataFrame({col: s.dropna()})
        y_scale = alt.Scale(type='log') if logy else alt.Undefined

        hist = (
            alt.Chart(base_df)
            .mark_bar(color=OKI["sky"])  # bars = sky
            .encode(
                alt.X(col, bin=alt.Bin(maxbins=bins), title=col),
                alt.Y('count()', title='Count', scale=y_scale),
                tooltip=['count()']
            )
            .properties(title=f"Histogram: {col}")
        )

        if kde:
            density = (
                alt.Chart(base_df)
                .transform_density(col, as_=[col, 'density'])
                .mark_line(color=OKI["green"], strokeWidth=2)  # density = green
                .encode(
                    x=alt.X(col, title=col),
                    y=alt.Y('density:Q', axis=alt.Axis(title='Density')),
                    tooltip=[alt.Tooltip('density:Q', format='.3f')]
                )
            )
            # Stack vertically for clarity
            chart = hist & density
        else:
            chart = hist

        st.altair_chart(chart, use_container_width=True)

    # Pairwise scatter
    st.subheader("Pairwise scatter (relationships)")
    st.markdown(
        "Shows a grid of scatter plots to reveal **relationships** between numeric columns "
        "(e.g., trends, clusters). Colour by a category to see group differences."
    )
    few = st.multiselect("Pick numeric columns (up to 5)", options=num_cols, default=num_cols[:3], max_selections=5)
    hue = st.selectbox("Colour by (optional categorical)", options=["<None>"] + cat_cols, index=0)
    if few:
        sample_df = df[few + ([hue] if hue != "<None>" else [])].dropna()
        # sample to keep it snappy
        max_rows = st.session_state.get("sample_for_matrix", 2000)
        if len(sample_df) > max_rows:
            sample_df = sample_df.sample(max_rows, random_state=42)
        if len(few) >= 2:
            fig = px.scatter_matrix(
                sample_df,
                dimensions=few,
                color=None if hue == "<None>" else hue,
                title=None
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select at least two numeric columns for a scatter matrix.")

# ---------- CATEGORICAL ----------
else:
    if not cat_cols or not sel_cat:
        st.info("No categorical columns found or selected.")
        st.stop()

    st.markdown(
        "For each selected column, you’ll see the **most common values** and how often they appear. "
        "This helps confirm categories and spot odd codes."
    )

    for col in sel_cat:
        s = df[col].astype("string").fillna("<NA>")
        vc = (
            s.value_counts(dropna=False)
             .rename_axis(col)
             .reset_index(name="Count")
        )
        vc["%"] = (vc["Count"] / max(len(df), 1) * 100).round(2)

        st.subheader(f"{col}")
        c1, c2 = st.columns([1.2, 2])

        with c1:
            st.dataframe(vc.head(top_k), use_container_width=True)

        with c2:
            y = "%" if normalise else "Count"
            fig = px.bar(
                vc.head(top_k),
                x=col,
                y=y,
                title=f"Top {top_k} values in ‘{col}’"
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

        # --- Category vs numeric (boxplot) ---
        st.subheader("Category vs numeric (boxplot)")
        st.markdown(
            "A **boxplot** shows the spread of a number for each category: " \
            "the box covers the middle 50%, " "the line is the **median**, and dots mark **outliers**."
        )

        # Need at least one of each type
        if len(cat_cols) == 0 or len(num_cols) == 0:
            st.info("Need at least one categorical and one numeric column for a box plot.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                cat_col = st.selectbox("Categorical", options=cat_cols, index=0)
            with c2:
                num_col  = st.selectbox("Numeric", options=num_cols, index=0)

            # Extra safety: ensure selected names still exist
            if (cat_col not in df.columns) or (num_col not in df.columns):
                st.warning("Selected columns are not in the dataset.")
            else:
                sample_n = st.slider("Max rows (sample)", 500, 20000, 5000, step=500)

                # Build data safely
                plot_df = df[[cat_col, num_col]].dropna()
                if plot_df.empty:
                    st.warning("Nothing to plot: all rows are missing for the selected pair.")
                elif plot_df[cat_col].nunique() < 2:
                    st.warning("The selected categorical column has only one category.")
                elif plot_df[num_col].nunique() < 2:
                    st.warning("The selected numeric column is constant.")
                else:
                    if len(plot_df) > sample_n:
                        plot_df = plot_df.sample(sample_n, random_state=42)

                    fig = px.box(
                        plot_df, x=cat_col, y=num_col, points="outliers",
                        title=f"{num_col} by {cat_col}",
                        color_discrete_sequence=[OKI["sky"]],
                    )
                    fig.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)





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
