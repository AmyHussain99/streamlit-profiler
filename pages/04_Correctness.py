# pages/04_Correctness.py
import streamlit as st
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="Correctness", layout="wide")
st.title("Correctness")
st.markdown(
    """
This page checks whether values **look plausible** against simple rules you set.  
Use it to spot **out-of-range numbers**, **values that don’t match a pattern** (e.g. emails/postcodes), and quick **cross-field sanity checks**.  
You can also try a **custom rule** for anything not covered below.
"""
)

# Guard
if "df" not in st.session_state:
    st.warning("No dataset loaded. Please go to Home and upload a CSV first.")
    st.stop()

df = st.session_state["df"]

# --- Numeric range rules ---
st.subheader("Numeric range checks")
st.markdown(
    "Pick a numeric column and set the **minimum** and **maximum** allowed values. "
    "Anything outside that range is flagged."
)

num_cols = df.select_dtypes(include=["number", "Float64", "Int64"]).columns.tolist()
if num_cols:
    col = st.selectbox("Select numeric column", options=num_cols, help="Only numeric columns are shown.")
    if col:
        observed_min = float(pd.to_numeric(df[col], errors="coerce").min(skipna=True))
        observed_max = float(pd.to_numeric(df[col], errors="coerce").max(skipna=True))
        c1, c2 = st.columns(2)
        with c1:
            lo = st.number_input("Minimum acceptable", value=observed_min)
        with c2:
            hi = st.number_input("Maximum acceptable", value=observed_max)

        s = pd.to_numeric(df[col], errors="coerce")
        invalid_mask = ~s.between(lo, hi)
        n_bad = int(invalid_mask.sum())
        st.write(f"Out-of-range values: **{n_bad}** / {len(df)} ({n_bad/len(df)*100:.2f}%)")
        st.caption("💡 Tip: Start with the observed min/max above, then tighten to policy or domain limits as needed.")

        if n_bad > 0:
            bad_rows = df.loc[invalid_mask, [col]]
            st.dataframe(bad_rows.head(50), use_container_width=True)
            st.markdown("The table previews *50* invalid values. Please download as a CSV to view the full range of invalid values.")
            csv = bad_rows.to_csv(index=False).encode("utf-8")
            st.download_button("Download all invalid values (CSV)", csv, file_name="out_of_range.csv")
        else:
            st.info("No numeric columns available.")


# --- Regex / pattern checks ---
st.subheader("Regex / pattern checks")
st.markdown(
    "Use patterns to check text columns follow a format (e.g., emails, postcodes, dates). "
    "Pick a preset or enter your own."
)

# Preset library (simple, practical patterns)
PRESETS = [
    {
        "Name": "Email",
        "Pattern": r"^[\w.%+\-]+@[\w.\-]+\.[A-Za-z]{2,}$",
        "Examples": "example@site.com; name.surname@nhs.uk",
        "Notes": "Basic email format"
    },
    {
        "Name": "UK Postcode (simplified)",
        "Pattern": r"^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$",
        "Examples": "SW1A 2AA; NE1 4LP",
        "Notes": "Not 100% exhaustive but practical"
    },
    {
        "Name": "UK Mobile (07… 10–11 digits)",
        "Pattern": r"^07\d{8,10}$",
        "Examples": "07123456789",
        "Notes": "Digits only version"
    },
    {
        "Name": "Date (YYYY-MM-DD)",
        "Pattern": r"^\d{4}-\d{2}-\d{2}$",
        "Examples": "2025-10-30",
        "Notes": "Format check only (not calendar validation)"
    },
    {
        "Name": "Date (DD/MM/YYYY)",
        "Pattern": r"^\d{2}/\d{2}/\d{4}$",
        "Examples": "30/10/2025",
        "Notes": "Format check only"
    },
    {
        "Name": "Time (24h HH:MM)",
        "Pattern": r"^(?:[01]\d|2[0-3]):[0-5]\d$",
        "Examples": "09:30; 23:59",
        "Notes": "Valid hour/minute ranges"
    },
    {
        "Name": "URL (simple)",
        "Pattern": r"^(https?://)?[\w\-]+(\.[\w\-]+)+[/\w\-.~:?#[\]@!$&'()*+,;=%]*$",
        "Examples": "https://example.com/path",
        "Notes": "Loose, practical URL"
    },
    {
        "Name": "Integer (whole number)",
        "Pattern": r"^-?\d+$",
        "Examples": "0; 42; -7",
        "Notes": "No decimals"
    },
    {
        "Name": "Decimal number",
        "Pattern": r"^-?\d+(\.\d+)?$",
        "Examples": "3.14; -0.5; 10",
        "Notes": "Optional decimals"
    },
    {
        "Name": "Percentage (with %)",
        "Pattern": r"^\d+(\.\d+)?%$",
        "Examples": "12%; 99.5%",
        "Notes": "Number followed by %"
    },
    {
        "Name": "Uppercase letters only",
        "Pattern": r"^[A-Z]+$",
        "Examples": "ABC; NHS",
        "Notes": "A–Z only"
    },
    {
        "Name": "Alphanumeric code (6–12 chars)",
        "Pattern": r"^[A-Za-z0-9]{6,12}$",
        "Examples": "AB12CD; user007",
        "Notes": "Letters/digits only"
    },
]

# Show the library table
preset_df = pd.DataFrame(PRESETS)[["Name", "Pattern", "Examples", "Notes"]]
st.dataframe(preset_df, use_container_width=True)
st.caption("💡 Tip: Click a preset below to insert its pattern, then pick your column to check.")

# Preset picker + pattern box
left, right = st.columns([1.2, 2])
with left:
    chosen = st.selectbox("Insert a preset", options=["<None>"] + [p["Name"] for p in PRESETS], index=0)

with right:
    if chosen != "<None>":
        pattern_default = next(p["Pattern"] for p in PRESETS if p["Name"] == chosen)
    else:
        pattern_default = ""
    pattern = st.text_input("Regex pattern", value=pattern_default, placeholder=r"e.g. ^\d{4}-\d{2}-\d{2}$")


# Column selector + options (allow any dtype)
all_cols  = df.columns.tolist()
text_cols = df.select_dtypes(include=["object", "string", "category"]).columns.tolist()

use_all = st.checkbox("Show all columns (cast to text)", value=not bool(text_cols))
choose_from = text_cols if (text_cols and not use_all) else all_cols

if not choose_from:
    st.info("No columns available to check.")
    st.stop()

col = st.selectbox("Column to check", options=choose_from, key="regex_col")
treat_blank_valid = st.checkbox("Treat blanks as valid", value=True,
                                help="If ticked, empty cells won't be counted as mismatches.")


# Tiny tester
test_value = st.text_input("Try a sample value (optional)", value="")
if pattern and test_value != "":
    try:
        ok = bool(re.match(pattern, str(test_value)))
        st.write("Test result:", "✅ **Matches**" if ok else "❌ **Does not match**")
    except re.error as e:
        st.error(f"Invalid regex: {e}")

# Run the check
if pattern and col:
    try:
        series = df[col].astype("string")
        if treat_blank_valid:
            # blanks are considered valid → only test non-blanks
            mask_to_test = series.notna() & (series.str.len() > 0)
            mismatches = pd.Series(False, index=series.index)
            mismatches.loc[mask_to_test] = ~series.loc[mask_to_test].str.match(pattern, na=False)
        else:
            # blanks must also match → test everything, NaNs treated as fail
            mismatches = ~series.str.match(pattern, na=False)

        n_bad = int(mismatches.sum())
        st.write(f"Pattern mismatches: **{n_bad}** / {len(df)} ({n_bad/len(df)*100:.2f}%)")

        if n_bad > 0:
            bad_rows = df.loc[mismatches, [col]]
            st.dataframe(bad_rows.head(50), use_container_width=True)
            st.markdown("The table previews 50 mismatches. Please download as a CSV to view all mismatches.")
            csv_bad = bad_rows.to_csv(index=False).encode("utf-8")
            st.download_button("Download all mismatches (CSV)", data=csv_bad, file_name="regex_mismatches.csv")
    except re.error as e:
        st.error(f"Invalid regex: {e}")

# Custom validation rule 
st.subheader("Custom rule (Python expression)")
st.markdown(
    """
Not all datasets contain standard or clean formats that can be covered by the preset checks above.  
In this section, you can define your own **True/False (boolean)** rule using Python syntax to perform a custom correctness check.  

This feature is intended for users familiar with Python expressions.  
For guidance on writing pattern-matching rules, see the official 
[Python `re` (regular expressions) documentation](https://docs.python.org/3/library/re.html).
"""
)

st.markdown(
    "Write a **True/False rule** using `df` to reference columns. "
    "Rows where the rule is **False** are shown as failures."
)
st.caption(
    "Examples:  \n"
    "`(df['age'] >= 18) & (df['age'] <= 100)`  |  `df['chol'] < 600`  |  "
    "`df['start_date'] <= df['end_date']`"
)

expr = st.text_input("Enter a boolean expression", value="")
if expr:
    try:
        # very restricted eval environment
        allowed_globals = {"df": df, "np": np, "pd": pd}
        result = eval(expr, {"__builtins__": {}}, allowed_globals)

        # Validate result
        if not isinstance(result, (pd.Series, np.ndarray, list)):
            raise ValueError("Expression must return a True/False series for each row.")
        mask_ok = pd.Series(result, index=df.index).astype(bool)
        if len(mask_ok) != len(df):
            raise ValueError("Result length does not match number of rows.")

        # Fail rows are where the rule is False
        fail_mask = ~mask_ok
        n_bad = int(fail_mask.sum())
        st.write(f"Custom rule failures: **{n_bad}** / {len(df)} ({n_bad/len(df)*100:.2f}%)")
        if n_bad > 0:
            st.dataframe(df.loc[fail_mask].head(50), use_container_width=True)
        st.caption("Tip: Think of it as ‘**keep** rows where this is True’; everything else is flagged.")
    except Exception as e:
        st.error(f"Error in expression: {e}")

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
