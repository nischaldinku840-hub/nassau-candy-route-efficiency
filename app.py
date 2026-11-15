"""
Nassau Candy Distributor - Shipping Route Efficiency Dashboard
Run with:  streamlit run app.py
"""
import os
import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import (load_clean, default_threshold, route_table, group_table,
                      ship_mode_table, bottleneck_states)

st.set_page_config(page_title="Nassau Candy - Route Efficiency", layout="wide")

DATA_FILES = ["data.csv", "Nassau Candy Distributor.csv", "Nassau_Candy_Distributor.csv"]


@st.cache_data
def get_data(path):
    return load_clean(path)


path = next((p for p in DATA_FILES if os.path.exists(p)), None)
if path is None:
    st.error("Put the dataset next to app.py and name it data.csv")
    st.stop()
df_all, clean_log = get_data(path)

# ------------------------------------------------------------------ sidebar filters
st.sidebar.title("Filters")
dmin, dmax = df_all["Order Date"].min().date(), df_all["Order Date"].max().date()
dr = st.sidebar.date_input("Order date range", (dmin, dmax), min_value=dmin, max_value=dmax)
if isinstance(dr, (tuple, list)) and len(dr) == 2:
    d_from, d_to = dr
else:  # user is mid-selection
    d_from, d_to = dmin, dmax

regions = sorted(df_all["Region"].unique())
sel_regions = st.sidebar.multiselect("Region", regions, default=regions)

states_avail = sorted(df_all.loc[df_all["Region"].isin(sel_regions), "State/Province"].unique())
sel_states = st.sidebar.multiselect("State / Province (empty = all)", states_avail)

modes = sorted(df_all["Ship Mode"].unique())
sel_modes = st.sidebar.multiselect("Ship mode", modes, default=modes)

lt_min, lt_max = int(df_all["Lead Time"].min()), int(df_all["Lead Time"].max())
threshold = st.sidebar.slider("Delay threshold (days)", lt_min, lt_max,
                              int(default_threshold(df_all)),
                              help="A shipment counts as delayed when its lead time is above this value.")
min_ship = st.sidebar.slider("Minimum shipments per route", 1, 100, 10,
                             help="Routes with fewer shipments are hidden from rankings (too little data).")

df = df_all[
    (df_all["Order Date"].dt.date >= d_from) & (df_all["Order Date"].dt.date <= d_to)
    & df_all["Region"].isin(sel_regions)
    & df_all["Ship Mode"].isin(sel_modes)
]
if sel_states:
    df = df[df["State/Province"].isin(sel_states)]

st.title("Factory-to-Customer Shipping Route Efficiency")
st.caption("Nassau Candy Distributor  |  lead time = Ship Date - Order Date (days)")
st.warning(
    "Data note: lead times in this dataset are ~900-1,640 days and ship dates run to 2030, "
    "so the date columns look shifted at the source. Use the dashboard for relative comparisons "
    "between routes, not as real delivery times.", icon="⚠️")

if df.empty:
    st.info("No shipments match the current filters.")
    st.stop()

# ------------------------------------------------------------------ KPI row
routes_state = route_table(df, "Route (State)", threshold, min_ship)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Shipments", f"{len(df):,}")
c2.metric("Avg lead time (days)", f"{df['Lead Time'].mean():,.0f}")
c3.metric("Delay frequency", f"{100 * (df['Lead Time'] > threshold).mean():.1f}%")
c4.metric("Routes ranked", f"{len(routes_state)}")
c5.metric("Fastest route", routes_state.iloc[0]["Route (State)"] if len(routes_state) else "n/a")

tab1, tab2, tab3, tab4 = st.tabs(["Route Efficiency Overview", "Geographic Map",
                                  "Ship Mode Comparison", "Route Drill-Down"])

# ------------------------------------------------------------------ tab 1: overview
with tab1:
    level = st.radio("Route level", ["Factory -> State", "Factory -> Region"], horizontal=True)
    col = "Route (State)" if level == "Factory -> State" else "Route (Region)"
    rt = route_table(df, col, threshold, min_ship)
    if rt.empty:
        st.info("No routes have enough shipments. Lower 'Minimum shipments per route'.")
    else:
        n = st.slider("Routes to show in chart", 5, min(40, len(rt)), min(15, len(rt))) if len(rt) > 5 else len(rt)
        left, right = st.columns(2)
        fig = px.bar(rt.head(n).iloc[::-1], x="Avg_Lead_Time", y=col, orientation="h",
                     title=f"Fastest {n} routes (avg lead time, days)", color="Efficiency_Score",
                     color_continuous_scale="RdYlGn", hover_data=["Shipments", "Delay_Frequency_%"])
        left.plotly_chart(fig, use_container_width=True)
        fig = px.bar(rt.tail(n), x="Avg_Lead_Time", y=col, orientation="h",
                     title=f"Slowest {n} routes (avg lead time, days)", color="Efficiency_Score",
                     color_continuous_scale="RdYlGn", hover_data=["Shipments", "Delay_Frequency_%"])
        right.plotly_chart(fig, use_container_width=True)

        st.subheader("Route performance leaderboard")
        st.dataframe(rt, hide_index=True, use_container_width=True)
        st.download_button("Download leaderboard (CSV)", rt.to_csv(index=False), "route_leaderboard.csv")
        st.caption("Efficiency score: 100 = fastest route in the current view, 0 = slowest. "
                   "Avg_vs_Year_Baseline: days slower (+) or faster (-) than the average order placed in the same year.")

# ------------------------------------------------------------------ tab 2: map
with tab2:
    metric = st.selectbox("Colour the map by",
                          ["Avg_Lead_Time", "Delay_Frequency_%", "Shipments"],
                          format_func=lambda m: {"Avg_Lead_Time": "Average lead time (days)",
                                                 "Delay_Frequency_%": "Delay frequency (%)",
                                                 "Shipments": "Shipment volume"}[m])
    st_tbl = group_table(df, "State/Province", threshold)
    us = st_tbl.merge(df[["State/Province", "State Code"]].drop_duplicates(), on="State/Province")
    us = us.dropna(subset=["State Code"])
    scale = "Blues" if metric == "Shipments" else "RdYlGn_r"
    fig = px.choropleth(us, locations="State Code", locationmode="USA-states", scope="usa",
                        color=metric, color_continuous_scale=scale, hover_name="State/Province",
                        hover_data=["Shipments", "Avg_Lead_Time", "Delay_Frequency_%"])
    st.plotly_chart(fig, use_container_width=True)
    st.caption("US states only. Canadian provinces appear in the tables but not on the map.")

    st.subheader("Regional bottlenecks")
    reg = group_table(df, "Region", threshold)
    left, right = st.columns(2)
    left.plotly_chart(px.bar(reg, x="Region", y="Avg_Lead_Time", color="Delay_Frequency_%",
                             color_continuous_scale="RdYlGn_r", title="Average lead time by region"),
                      use_container_width=True)
    bt = bottleneck_states(df, threshold)
    bt = bt[bt["Shipments"] >= 5]
    right.plotly_chart(px.scatter(bt, x="Shipments", y="Avg_Lead_Time", color="Bottleneck", log_x=True,
                                  hover_name="State/Province",
                                  color_discrete_map={True: "#d9822b", False: "#2f6db5"},
                                  title="Volume vs lead time (orange = bottleneck)"),
                       use_container_width=True)
    st.markdown("**Bottleneck states** = shipment volume at or above the median state AND average lead time above the overall average.")
    st.dataframe(bt[bt["Bottleneck"]].sort_values("Shipments", ascending=False),
                 hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ tab 3: ship mode
with tab3:
    mt = ship_mode_table(df, threshold)
    left, right = st.columns(2)
    left.plotly_chart(px.box(df, x="Ship Mode", y="Lead Time", color="Ship Mode",
                             title="Lead time distribution by ship mode"), use_container_width=True)
    right.plotly_chart(px.bar(mt, x="Ship Mode", y="Avg_Lead_Time", color="Delay_Frequency_%",
                              color_continuous_scale="RdYlGn_r", title="Average lead time by ship mode"),
                       use_container_width=True)
    st.subheader("Standard vs Expedited")
    st.dataframe(group_table(df, "Ship Mode Group", threshold), hide_index=True, use_container_width=True)
    st.subheader("Cost-time trade-off (descriptive)")
    st.dataframe(mt, hide_index=True, use_container_width=True)
    st.caption("The dataset has no shipping fee. 'Cost' is the manufacturing cost of the order, "
               "so this table shows whether faster modes are linked to different sales, cost or margin - not shipping cost.")

# ------------------------------------------------------------------ tab 4: drill-down
with tab4:
    choices = sorted(df["State/Province"].unique())
    state = st.selectbox("Choose a state / province", choices)
    sd = df[df["State/Province"] == state]
    a, b, c, d = st.columns(4)
    a.metric("Shipments", f"{len(sd):,}")
    b.metric("Avg lead time", f"{sd['Lead Time'].mean():,.0f} days",
             f"{sd['Lead Time'].mean() - df['Lead Time'].mean():+,.0f} vs all", delta_color="inverse")
    c.metric("Delay frequency", f"{100 * (sd['Lead Time'] > threshold).mean():.1f}%")
    d.metric("Lead-time std dev", f"{sd['Lead Time'].std():,.0f}")

    st.subheader(f"Routes into {state}")
    st.dataframe(route_table(sd, "Route (State)", threshold, 1), hide_index=True, use_container_width=True)

    left, right = st.columns(2)
    left.plotly_chart(px.bar(group_table(sd, "Ship Mode", threshold), x="Ship Mode", y="Avg_Lead_Time",
                             title=f"{state}: lead time by ship mode"), use_container_width=True)
    city = group_table(sd, "City", threshold).sort_values("Shipments", ascending=False).head(10)
    right.plotly_chart(px.bar(city, x="City", y="Avg_Lead_Time", hover_data=["Shipments"],
                              title=f"{state}: top cities by volume"), use_container_width=True)

    st.subheader("Order-level shipment timeline")
    n_orders = st.slider("Orders to show", 5, min(100, len(sd)), min(25, len(sd))) if len(sd) > 5 else len(sd)
    sample = sd.sort_values("Order Date").tail(n_orders).copy()
    sample["Label"] = sample["Order ID"]
    fig = px.timeline(sample, x_start="Order Date", x_end="Ship Date", y="Label", color="Ship Mode",
                      hover_data=["Factory", "City", "Lead Time"])
    fig.update_yaxes(autorange="reversed", title="Order ID")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(sample[["Order ID", "Order Date", "Ship Date", "Lead Time", "Ship Mode", "Factory", "City", "Product Name"]],
                 hide_index=True, use_container_width=True)

with st.expander("Data cleaning log"):
    st.dataframe(pd.DataFrame(clean_log, columns=["Step", "Rows"]), hide_index=True)
