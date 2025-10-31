# Data Profiling Tool 

This is an interactive **Streamlit-based data profiling tool** that helps users explore data quality across key dimensions:
- **Completeness** — identify missing or incomplete values  
- **Cardinality** — understand column uniqueness and duplication  
- **Distribution** — visualise numeric and categorical distributions  
- **Correctness** — detect values outside valid ranges or formats  
- **Incremental Profiling** — compare two datasets to detect changes  

---

## Features
- Upload and analyse any CSV file  
- Automatic type detection and data cleaning  
- Downloadable tables of missing or incorrect values  
- Regex-based pattern checks for emails, postcodes, dates, etc.  
- Incremental dataset comparison (adds, updates, deletions)  
- Fully interactive UI — no coding required  

---

## Requirements
See requirements.txt for dependencies

---

## Project structure
.
├── Home.py
├── pages/
│   ├── 01_Completeness.py
│   ├── 02_Cardinality.py
│   ├── 03_Distribution.py
│   └── 04_Correctness.py
├── requirements.txt
└── README.md

----

## Live App
To launch on streamlit cloud, please click the link below
[Launch on Streamlit Cloud](https://amy-data-profiler.streamlit.app/)

---

## Installation (for local use)
1. Clone the repository:
   ```bash
   git clone https://github.com/AmyHussain99/streamlit-profiler.git
   cd streamlit-profiler
   pip install -r requirements.txt
   streamlit run Home.py

---

## Licence
This project is licensed under the MIT License – see the [LICENSE](./LICENSE) file for details.

---

## Acknowledgements
This project was developed as part of my MSc Data Science dissertation at Newcastle University, United Kingdom.  
I would like to thank my supervisor Dr Sara Johansson Fernstad for their guidance, and the testers who provided feedback during user evaluation.

