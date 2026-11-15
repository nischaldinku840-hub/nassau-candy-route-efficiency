"""Runs the full analysis and saves result tables (CSV) and charts (PNG) into ./outputs"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from analysis import *

OUT = "outputs"
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
BLUE, ORANGE, GREY = "#2f6db5", "#d9822b", "#8a8a8a"

df, log = load_clean("data.csv")
TH = default_threshold(df)

# ---------- tables
route_state = route_table(df, "Route (State)", TH, 10)
route_region = route_table(df, "Route (Region)", TH, 10)
state_tbl = bottleneck_states(df, TH)
region_tbl = group_table(df, "Region", TH)
mode_tbl = ship_mode_table(df, TH)
group_tbl = group_table(df, "Ship Mode Group", TH)
factory_tbl = group_table(df, "Factory", TH)
year_tbl = group_table(df, "Order Year", TH)

pd.DataFrame(log, columns=["Step", "Rows"]).to_csv(f"{OUT}/cleaning_log.csv", index=False)
route_state.to_csv(f"{OUT}/route_state_ranking.csv", index=False)
route_region.to_csv(f"{OUT}/route_region_ranking.csv", index=False)
route_state.head(10).to_csv(f"{OUT}/top10_routes.csv", index=False)
route_state.tail(10).iloc[::-1].to_csv(f"{OUT}/bottom10_routes.csv", index=False)
state_tbl.to_csv(f"{OUT}/state_performance.csv", index=False)
mode_tbl.to_csv(f"{OUT}/ship_mode_performance.csv", index=False)
df.to_csv(f"{OUT}/cleaned_data.csv", index=False)

# ---------- charts
# 1. data-quality chart: lead time by order year
fig, ax = plt.subplots(figsize=(7, 3.6))
for y, c in zip(sorted(df["Order Year"].unique()), [BLUE, ORANGE]):
    ax.hist(df.loc[df["Order Year"] == y, "Lead Time"], bins=40, alpha=.75, color=c, label=f"Ordered in {y}")
ax.set_xlabel("Lead time (days)"); ax.set_ylabel("Orders"); ax.legend()
ax.set_title("Lead time distribution by order year")
fig.tight_layout(); fig.savefig(f"{OUT}/01_lead_time_distribution.png", dpi=160); plt.close(fig)

# 2. top 10 / bottom 10
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharex=True)
for ax, d, col, ttl in [(axes[0], route_state.head(10).iloc[::-1], BLUE, "Top 10 most efficient routes"),
                        (axes[1], route_state.tail(10), ORANGE, "Bottom 10 least efficient routes")]:
    ax.barh(d["Route (State)"], d["Avg_Lead_Time"], color=col)
    ax.set_title(ttl); ax.set_xlabel("Average lead time (days)")
axes[0].set_xlim(1100, 1520)
fig.tight_layout(); fig.savefig(f"{OUT}/02_top_bottom_routes.png", dpi=160); plt.close(fig)

# 3. region routes
d = route_region.sort_values("Avg_Lead_Time", ascending=False)
fig, ax = plt.subplots(figsize=(8, 5))
ax.barh(d["Route (Region)"], d["Avg_Lead_Time"], color=BLUE)
ax.set_xlim(1250, 1400); ax.set_xlabel("Average lead time (days)"); ax.set_title("Factory to customer region routes")
fig.tight_layout(); fig.savefig(f"{OUT}/03_region_routes.png", dpi=160); plt.close(fig)

# 4. ship mode
fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))
m = mode_tbl.sort_values("Avg_Lead_Time")
axes[0].bar(m["Ship Mode"], m["Avg_Lead_Time"], color=BLUE); axes[0].set_ylim(1250, 1360)
axes[0].set_title("Average lead time (days)"); axes[0].tick_params(axis="x", rotation=20)
axes[1].bar(m["Ship Mode"], m["Delay_Frequency_%"], color=ORANGE)
axes[1].set_title(f"Delay frequency % (lead time > {TH:.0f} days)"); axes[1].tick_params(axis="x", rotation=20)
fig.tight_layout(); fig.savefig(f"{OUT}/04_ship_mode.png", dpi=160); plt.close(fig)

# 5. bottleneck scatter
s = state_tbl[state_tbl["Shipments"] >= 10]
fig, ax = plt.subplots(figsize=(8, 5))
cols = [ORANGE if b else BLUE for b in s["Bottleneck"]]
ax.scatter(s["Shipments"], s["Avg_Lead_Time"], c=cols, s=40, alpha=.85)
ax.axhline(df["Lead Time"].mean(), color=GREY, ls="--", lw=1)
ax.axvline(state_tbl["Shipments"].median(), color=GREY, ls="--", lw=1)
for _, r in s[s["Bottleneck"]].nlargest(8, "Shipments").iterrows():
    ax.annotate(r["State/Province"], (r["Shipments"], r["Avg_Lead_Time"]), fontsize=8, xytext=(4, 3), textcoords="offset points")
ax.set_xscale("log"); ax.set_xlabel("Shipments (log scale)"); ax.set_ylabel("Average lead time (days)")
ax.set_title("Bottleneck states (orange = high volume and slower than average)")
fig.tight_layout(); fig.savefig(f"{OUT}/05_bottleneck_states.png", dpi=160); plt.close(fig)

# ---------- key numbers for the write-up
if __name__ == "__main__":
    print(log)
    print("threshold", TH)
    print(factory_tbl)
    print(year_tbl)
    print(region_tbl)
    print(mode_tbl)
    print(group_tbl)
    print(state_tbl[state_tbl.Bottleneck].sort_values("Shipments", ascending=False).head(12))
    print("slowest big states"); print(state_tbl[state_tbl.Shipments >= 100].head(6))
    print("fastest big states"); print(state_tbl[state_tbl.Shipments >= 100].tail(6))
    print("country", group_table(df, "Country/Region", TH))
    print("overall avg", df["Lead Time"].mean(), df["Lead Time"].std(), df["Lead Time"].min(), df["Lead Time"].max())
    print("n states w >=10:", (state_tbl.Shipments >= 10).sum(), "bottlenecks", state_tbl.Bottleneck.sum())
    print("route std range", route_state["Std_Lead_Time"].describe())
    print("spread top-bottom days", route_state.Avg_Lead_Time.max() - route_state.Avg_Lead_Time.min())
    # year-adjusted check: route avg lead time within each order year
    d1 = df.groupby(["Order Year", "Region"])["Lead Time"].mean().unstack(0).round(1); print(d1)
    d2 = df.groupby(["Order Year", "Ship Mode"])["Lead Time"].mean().unstack(0).round(1); print(d2)
    print(df.groupby("Order Year")["Ship Date"].agg(["min", "max"]))
