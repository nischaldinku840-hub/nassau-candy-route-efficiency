"""
Nassau Candy Distributor - Shipping Route Efficiency Analysis
Core data cleaning + route analytics. Used by both the report script and the dashboard.
"""
import numpy as np
import pandas as pd

# ---------------------------------------------------------------- reference data
FACTORY_COORDS = {
    "Lot's O' Nuts":     (32.881893, -111.768036),
    "Wicked Choccy's":   (32.076176, -81.088371),
    "Sugar Shack":       (48.11914,  -96.18115),
    "Secret Factory":    (41.446333, -90.565487),
    "The Other Factory": (35.1175,   -89.971107),
}

# Product -> Factory (from the project brief). Kazookles has no factory in the brief.
PRODUCT_FACTORY = {
    "Wonka Bar - Nutty Crunch Surprise": "Lot's O' Nuts",
    "Wonka Bar - Fudge Mallows": "Lot's O' Nuts",
    "Wonka Bar -Scrumdiddlyumptious": "Lot's O' Nuts",
    "Wonka Bar - Milk Chocolate": "Wicked Choccy's",
    "Wonka Bar - Triple Dazzle Caramel": "Wicked Choccy's",
    "Laffy Taffy": "Sugar Shack",
    "SweeTARTS": "Sugar Shack",
    "Nerds": "Sugar Shack",
    "Fun Dip": "Sugar Shack",
    "Fizzy Lifting Drinks": "Sugar Shack",
    "Everlasting Gobstopper": "Secret Factory",
    "Hair Toffee": "The Other Factory",
    "Lickable Wallpaper": "Secret Factory",
    "Wonka Gum": "Secret Factory",
}

STATE_ABBR = {
    'Alabama': 'AL', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA', 'Colorado': 'CO',
    'Connecticut': 'CT', 'Delaware': 'DE', 'District of Columbia': 'DC', 'Florida': 'FL',
    'Georgia': 'GA', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
    'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH',
    'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC',
    'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA',
    'Rhode Island': 'RI', 'South Carolina': 'SC', 'South Dakota': 'SD', 'Tennessee': 'TN',
    'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA',
    'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
}

SHIP_MODE_GROUP = {
    "Standard Class": "Standard",
    "Second Class": "Expedited",
    "First Class": "Expedited",
    "Same Day": "Expedited",
}


# ---------------------------------------------------------------- cleaning
def load_clean(path):
    """Load the CSV, clean it, add features. Returns (df, log) where log is a list of cleaning steps."""
    df = pd.read_csv(path)
    log = [("Rows loaded", len(df))]

    # standardise text fields
    for c in ["Ship Mode", "Country/Region", "City", "State/Province", "Region",
              "Division", "Product Name", "Product ID"]:
        df[c] = df[c].astype(str).str.strip()
    df["State/Province"] = df["State/Province"].str.title().replace({"District Of Columbia": "District of Columbia"})
    df["Postal Code"] = df["Postal Code"].astype(str).str.strip()

    # validate dates (file uses dd-mm-yyyy)
    df["Order Date"] = pd.to_datetime(df["Order Date"], format="%d-%m-%Y", errors="coerce")
    df["Ship Date"] = pd.to_datetime(df["Ship Date"], format="%d-%m-%Y", errors="coerce")
    n = len(df)
    df = df.dropna(subset=["Order Date", "Ship Date"])
    log.append(("Rows removed: missing/invalid dates", n - len(df)))

    # lead time + remove negative
    df["Lead Time"] = (df["Ship Date"] - df["Order Date"]).dt.days
    n = len(df)
    df = df[df["Lead Time"] >= 0]
    log.append(("Rows removed: negative lead time", n - len(df)))

    n = len(df)
    df = df.drop_duplicates()
    log.append(("Rows removed: exact duplicates", n - len(df)))

    # factory mapping
    df["Factory"] = df["Product Name"].map(PRODUCT_FACTORY)
    n = len(df)
    df = df.dropna(subset=["Factory"])
    log.append(("Rows removed: product has no factory in brief (Kazookles)", n - len(df)))

    # features
    df["Ship Mode Group"] = df["Ship Mode"].map(SHIP_MODE_GROUP)
    df["State Code"] = df["State/Province"].map(STATE_ABBR)  # NaN for Canadian provinces
    df["Route (State)"] = df["Factory"] + " -> " + df["State/Province"]
    df["Route (Region)"] = df["Factory"] + " -> " + df["Region"]
    df["Order Year"] = df["Order Date"].dt.year
    # lead time relative to the average of orders placed in the same year (removes the order-year effect)
    df["Lead vs Year Avg"] = df["Lead Time"] - df.groupby("Order Year")["Lead Time"].transform("mean")
    df["Cost per Unit"] = df["Cost"] / df["Units"].replace(0, np.nan)
    df["Profit Margin %"] = 100 * df["Gross Profit"] / df["Sales"].replace(0, np.nan)
    log.append(("Rows kept for analysis", len(df)))
    return df.reset_index(drop=True), log


# ---------------------------------------------------------------- KPIs
def default_threshold(df):
    """Delay threshold = 75th percentile of lead time (a shipment is 'delayed' if slower than this)."""
    return float(df["Lead Time"].quantile(0.75))


def route_table(df, route_col="Route (State)", threshold=None, min_shipments=10):
    """One row per route with volume, average / std lead time, delay frequency, efficiency score."""
    if threshold is None:
        threshold = default_threshold(df)
    g = df.groupby(route_col)
    t = g["Lead Time"].agg(Shipments="count", Avg_Lead_Time="mean",
                           Median_Lead_Time="median", Std_Lead_Time="std").reset_index()
    t["Std_Lead_Time"] = t["Std_Lead_Time"].fillna(0)
    t["Delay_Frequency_%"] = g["Lead Time"].apply(lambda s: 100 * (s > threshold).mean()).values
    t["Avg_vs_Year_Baseline"] = g["Lead vs Year Avg"].mean().values  # + = slower than same-year average
    t = t[t["Shipments"] >= min_shipments].copy()
    if len(t) > 1 and t["Avg_Lead_Time"].max() > t["Avg_Lead_Time"].min():
        rng = t["Avg_Lead_Time"].max() - t["Avg_Lead_Time"].min()
        t["Efficiency_Score"] = 100 * (1 - (t["Avg_Lead_Time"] - t["Avg_Lead_Time"].min()) / rng)
    else:
        t["Efficiency_Score"] = 100.0
    t = t.sort_values("Avg_Lead_Time").reset_index(drop=True)
    t.insert(0, "Rank", np.arange(1, len(t) + 1))
    return t.round(2)


def group_table(df, col, threshold=None):
    """Same KPIs grouped by any column (state, region, ship mode...)."""
    if threshold is None:
        threshold = default_threshold(df)
    g = df.groupby(col)
    t = g["Lead Time"].agg(Shipments="count", Avg_Lead_Time="mean", Std_Lead_Time="std").reset_index()
    t["Delay_Frequency_%"] = g["Lead Time"].apply(lambda s: 100 * (s > threshold).mean()).values
    return t.round(2)


def ship_mode_table(df, threshold=None):
    """Lead time and cost/profit side by side for each ship mode (descriptive cost-time trade-off)."""
    if threshold is None:
        threshold = default_threshold(df)
    g = df.groupby("Ship Mode")
    t = g.agg(Shipments=("Lead Time", "count"), Avg_Lead_Time=("Lead Time", "mean"),
              Std_Lead_Time=("Lead Time", "std"), Avg_Sales=("Sales", "mean"),
              Avg_Cost=("Cost", "mean"), Avg_Gross_Profit=("Gross Profit", "mean"),
              Avg_Margin_Pct=("Profit Margin %", "mean")).reset_index()
    t["Delay_Frequency_%"] = g["Lead Time"].apply(lambda s: 100 * (s > threshold).mean()).values
    return t.round(2)


def bottleneck_states(df, threshold=None):
    """States with above-average volume AND above-average lead time (poor performance + high volume)."""
    t = group_table(df, "State/Province", threshold)
    vol_cut = t["Shipments"].median()
    lt_cut = df["Lead Time"].mean()
    t["Bottleneck"] = (t["Shipments"] >= vol_cut) & (t["Avg_Lead_Time"] > lt_cut)
    return t.sort_values("Avg_Lead_Time", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    import sys
    d, log = load_clean(sys.argv[1])
    for k, v in log:
        print(f"{k}: {v}")
    print(route_table(d).head())
