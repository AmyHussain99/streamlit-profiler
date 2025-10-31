# Data Profiling Tool v1.0

An interactive **Streamlit-based data profiling tool** that helps users explore data quality across key dimensions:
- **Completeness** — identify missing or incomplete values  
- **Cardinality** — understand column uniqueness and duplication  
- **Distribution** — visualise numeric and categorical distributions  
- **Correctness** — detect values outside valid ranges or formats  
- **Incremental Profiling** — compare two datasets to detect changes  

---

## Live App
[Launch on Streamlit Cloud](https://share.streamlit.io)

---

## Features
- Upload and analyse any CSV file  
- Automatic type detection and data cleaning  
- Downloadable tables of missing or incorrect values  
- Regex-based pattern checks for emails, postcodes, dates, etc.  
- Incremental dataset comparison (adds, updates, deletions)  
- Fully interactive UI — no coding required  

---

## Installation (for local use)
1. Clone the repository:
   ```bash
   git clone https://github.com/AmyHussain99/streamlit-profiler.git
   cd streamlit-profiler
