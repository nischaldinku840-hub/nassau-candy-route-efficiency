# Nassau Candy - Shipping Route Efficiency

## Files
- `data.csv` - the dataset
- `analysis.py` - cleaning, route table, KPIs (used by everything else)
- `make_outputs.py` - runs the analysis, saves tables + charts into `outputs/`
- `app.py` - Streamlit dashboard
- `build_docs.js` - builds the Word documents (optional, needs Node + `docx`)
- `Research_Paper.docx`, `Executive_Summary.docx` - written deliverables

## Run it
```
pip install -r requirements.txt
python make_outputs.py        # tables and charts into outputs/
streamlit run app.py          # dashboard opens in your browser
```

## Notes
- Lead time = Ship Date - Order Date. Dates are day-month-year.
- Factory is not in the dataset; it is mapped from Product Name (see `PRODUCT_FACTORY` in analysis.py).
- Kazookles (96 orders) has no factory in the brief and is excluded from route analysis.
- Lead times in this file are 904-1,642 days (ship dates up to 2030), so use results as relative comparisons.
