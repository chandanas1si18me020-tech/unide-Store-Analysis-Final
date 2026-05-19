import streamlit as st
import streamlit.components.v1 as components
import folium
import json
import os
import math
import pandas as pd

st.set_page_config(
    page_title="Unide Store Analysis",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE = "./"

@st.cache_data
def load_data():
    with open(BASE + "unide_app_data.json") as f:
        data = json.load(f)
    geojson = None
    if os.path.exists(BASE + "census_boundaries.geojson"):
        with open(BASE + "census_boundaries.geojson") as f:
            geojson = json.load(f)
    return data, geojson

APP_DATA, GEOJSON = load_data()
STORES     = APP_DATA["stores"]
COMPS      = APP_DATA["competitors"]
SPOILAGE   = APP_DATA["spoilage"]
SHELF_LIFE = APP_DATA["shelf_life"]
LOOKUP     = {s["store_id"]: s for s in STORES}

RC = {0:"#1A7A4A", 1:"#B7770D", 2:"#C0550A", 3:"#A93226"}
RL = {0:"Well Matched", 1:"Low Risk", 2:"Medium Risk", 3:"High Risk"}

SNAMES = {
    s["store_id"]: f"{s['brand']}  —  {s['city']}  ({s['province']})"
    for s in STORES
}
SOPTS = [SNAMES[s["store_id"]] for s in sorted(STORES, key=lambda x: int(x["store_id"]))]
NID   = {v: k for k, v in SNAMES.items()}

def gs(name):
    return LOOKUP.get(NID.get(name))

def md_card(label, value, sub=""):
    sub_html = f"<p style='margin:2px 0 0;font-size:11px;color:#555555;'>{sub}</p>" if sub else ""
    st.markdown(
        f"""<div style="background:#FFFFFF;border:1.5px solid #D0D0D0;
        border-radius:10px;padding:14px 10px;text-align:center;margin-bottom:10px;
        box-shadow:0 1px 4px rgba(0,0,0,0.08);">
        <p style="margin:0 0 5px;font-size:10px;color:#C0550A;
        text-transform:uppercase;letter-spacing:1.5px;font-weight:700;">{label}</p>
        <p style="margin:0;font-size:22px;font-weight:800;color:#1A1A1A;">{value}</p>
        {sub_html}</div>""",
        unsafe_allow_html=True
    )

def haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lng2-lng1)/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def make_map(store, show_stores, show_comps, show_census):
    slat, slng = store["lat"], store["lng"]
    m = folium.Map(location=[slat, slng], zoom_start=13, tiles="OpenStreetMap")

    # 2km radius circle — shows analysis boundary
    folium.Circle(
        location=[slat, slng],
        radius=2000,
        color="#1A5276",
        weight=2.5,
        fill=True,
        fill_color="#1A5276",
        fill_opacity=0.05,
    ).add_to(m)

    # All Unide stores
    if show_stores:
        for s in STORES:
            try:
                lat, lng = float(s["lat"]), float(s["lng"])
                if math.isnan(lat) or math.isnan(lng): continue
                sel = s["store_id"] == store["store_id"]
                col = "#C0550A" if sel else RC.get(s["mismatch_score"], "#1B4F72")
                sz  = 28 if sel else 16
                bdr = "4px solid #1A1A1A" if sel else "2px solid rgba(0,0,0,0.35)"
                shadow = "0 0 10px rgba(192,85,10,0.5)" if sel else "0 2px 6px rgba(0,0,0,0.25)"
                folium.Marker(
                    location=[lat, lng],
                    icon=folium.DivIcon(
                        html=(
                            f"<div style='width:{sz}px;height:{sz}px;"
                            f"background:{col};border:{bdr};"
                            f"border-radius:4px;transform:rotate(45deg);"
                            f"box-shadow:{shadow};'></div>"
                        ),
                        icon_size=(sz, sz), icon_anchor=(sz//2, sz//2)
                    ),
                    tooltip=folium.Tooltip(
                        f"{s['brand']} — {s['city']} | {s['mismatch_flag']}",
                        sticky=True
                    )
                ).add_to(m)
            except: continue

    # Census section points — all dots, lines only top 10
    if show_census:
        secs = store.get("census_sections", [])
        mw   = max((s["weight"] for s in secs), default=1) if secs else 1
        for sec in secs:
            try:
                sl, sln   = float(sec["lat"]), float(sec["lng"])
                if math.isnan(sl) or math.isnan(sln): continue
                norm      = sec["weight"] / max(mw, 0.001)
                show_line = sec.get("show_line", False)
                sz        = max(9, int(norm * 18))

                if show_line:
                    folium.PolyLine(
                        locations=[[sl, sln],[slat, slng]],
                        color="#C0550A",
                        weight=max(3, norm * 7),
                        opacity=0.65,
                        dash_array="5 3"
                    ).add_to(m)

                dot_col  = "#1A5276" if show_line else "#5DADE2"
                border_w = "3px" if show_line else "2px"

                folium.Marker(
                    location=[sl, sln],
                    icon=folium.DivIcon(
                        html=(
                            f"<div style='width:{sz}px;height:{sz}px;"
                            f"background:{dot_col};"
                            f"border:{border_w} solid white;"
                            f"border-radius:50%;"
                            f"box-shadow:0 1px 4px rgba(0,0,0,0.3);'></div>"
                        ),
                        icon_size=(sz, sz), icon_anchor=(sz//2, sz//2)
                    ),
                    tooltip=folium.Tooltip(
                        f"Section: {sec['section_id']} | {sec['distance_km']}km | "
                        f"weight={sec['weight']:.3f} | "
                        f"{'Primary' if show_line else 'Extended'}",
                        sticky=True
                    )
                ).add_to(m)
            except: continue

    # Competitors
    if show_comps:
        bbox  = 0.08
        shown = set()
        for comp in store.get("competitors_nearby", []):
            try:
                clat = float(comp["comp_lat"])
                clng = float(comp["comp_lng"])
                if math.isnan(clat) or math.isnan(clng): continue
                key = f"{round(clat,4)}_{round(clng,4)}"
                shown.add(key)
                folium.Marker(
                    location=[clat, clng],
                    icon=folium.DivIcon(
                        html=(
                            "<div style='width:0;height:0;"
                            "border-left:13px solid transparent;"
                            "border-right:13px solid transparent;"
                            "border-bottom:24px solid #B7770D;'></div>"
                        ),
                        icon_size=(26, 24), icon_anchor=(13, 12)
                    ),
                    tooltip=folium.Tooltip(
                        f"{comp['comp_name']} | {comp['distance_km']}km | {int(comp['floor_size'])}m²",
                        sticky=True
                    )
                ).add_to(m)
            except: continue

        for comp in COMPS:
            try:
                clat = float(comp["lat"])
                clng = float(comp["lng"])
                if math.isnan(clat) or math.isnan(clng): continue
                if not (slat-bbox <= clat <= slat+bbox and slng-bbox <= clng <= slng+bbox): continue
                key = f"{round(clat,4)}_{round(clng,4)}"
                if key in shown: continue
                folium.Marker(
                    location=[clat, clng],
                    icon=folium.DivIcon(
                        html=(
                            "<div style='width:0;height:0;"
                            "border-left:8px solid transparent;"
                            "border-right:8px solid transparent;"
                            "border-bottom:15px solid #A93226;'></div>"
                        ),
                        icon_size=(16, 15), icon_anchor=(8, 8)
                    ),
                    tooltip=folium.Tooltip(
                        f"{comp['comp_name']} | {int(comp['floor_size'])}m²",
                        sticky=True
                    )
                ).add_to(m)
            except: continue

    return f"<div style='width:100%;height:680px;border-radius:10px;overflow:hidden;border:1.5px solid #D0D0D0;'>{m._repr_html_()}</div>"

# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("Unide Store Analysis")
    st.caption("Neighbourhood Demand & Spoilage Analysis")
    st.divider()
    sel   = st.selectbox("SELECT STORE", SOPTS, index=0)
    store = gs(sel)
    st.divider()
    st.caption("MAP LAYERS")
    show_stores = st.checkbox("All Unide Stores", value=True)
    show_comps  = st.checkbox("Competitors",      value=True)
    show_census = st.checkbox("Census Points",    value=True)
    st.divider()

    if store:
        mc     = store["mismatch_score"]
        mc_col = RC.get(mc, "#888")
        st.markdown(
            f"<div style='background:{mc_col}22;border-left:4px solid {mc_col};"
            f"padding:10px;border-radius:6px;'>"
            f"<p style='margin:0;font-size:14px;font-weight:700;color:#1A1A1A;'>"
            f"{store['mismatch_flag']}</p>"
            f"<p style='margin:4px 0 0;font-size:11px;color:#444;'>Score {mc}/3</p>"
            f"</div>",
            unsafe_allow_html=True
        )
        st.divider()
        st.caption(f"📍 {store.get('address','')}")
        st.caption(f"Store ID: {store['store_id']}")
        st.caption(f"Floor: {int(store['floor_size'])} m²  |  {store['replenishment']}x/week")
        st.caption(f"Best match: {store['best_y']}x/week")

if not store:
    st.info("Select a store from the sidebar")
    st.stop()

# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
st.title(f"{store['brand']}  —  {store['city']}, {store['province']}")
if store.get("address"):
    st.caption(f"📍 {store['address']}  |  Store ID: {store['store_id']}")

t1, t2, t3, t4, t5, t6 = st.tabs([
    "🗺  Map & Overview",
    "📊  What-If Analysis",
    "⚔  Competitor Threat",
    "🛒  Category Risk",
    "📦  Spoilage Overview",
    "🔄  Store Comparison"
])

# ── TAB 1 ──────────────────────────────────────────────────────────
with t1:
    a, b, c, d, e, f = st.columns(6)
    with a: md_card("Spending Power",   f"{store['spending_power']}",   "/ 100")
    with b: md_card("Market Share",     f"{store['market_share']}%",    "local area")
    with c: md_card("Potential Demand", f"{store['potential_demand']}",  "/ 100")
    with d: md_card("Replenishment",    f"{store['replenishment']}x/wk", store['y_group'])
    with e: md_card("Competitors",      str(store["num_competitors_2km"]), "within 2km")
    with f: md_card("Threat Level",     store["threat_level"])

    mc     = store["mismatch_score"]
    mc_col = RC.get(mc, "#888")
    st.markdown(
        f"<div style='background:{mc_col}15;border:1.5px solid {mc_col}88;"
        f"border-left:5px solid {mc_col};border-radius:8px;"
        f"padding:12px 16px;margin-bottom:14px;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<span style='font-size:16px;font-weight:700;color:#1A1A1A;'>"
        f"{store['mismatch_flag']}</span>"
        f"<span style='font-size:12px;color:#444;'>"
        f"Floor: {store['x_group']} | Demand: {store['pd_band']} | Best Y: {store['best_y']}x/week"
        f"</span>"
        f"<span style='background:{mc_col};padding:4px 14px;border-radius:4px;"
        f"font-size:12px;font-weight:700;color:white;'>Score {mc}/3</span>"
        f"</div></div>",
        unsafe_allow_html=True
    )

    with st.spinner("Loading map..."):
        components.html(
            make_map(store, show_stores, show_comps, show_census),
            height=700
        )

# ── TAB 2 ──────────────────────────────────────────────────────────
with t2:
    st.subheader("What-If Replenishment Analysis")
    st.caption(f"Current: {store['replenishment']}x per week  |  Best match: {store['best_y']}x per week")

    sel_y = st.selectbox(
        "SIMULATE REPLENISHMENT",
        [f"{i}x per week" for i in range(1, 8)],
        index=store["replenishment"] - 1
    )
    y = int(sel_y.split("x")[0])
    w = store["whatif"].get(str(y), {})

    if w:
        if y == store["replenishment"]:
            st.info("This is the current replenishment frequency")
        if y == store["best_y"]:
            st.success("✓ Recommended best-match frequency")

        a, b, c, d = st.columns(4)
        with a: md_card("Coverage",   f"{w.get('coverage',0)}%",   "demand served")
        with b: md_card("Waste Rate", f"{w.get('waste_rate',0)}%", "est. spoilage")
        with c: md_card("Gap Days",   f"{w.get('gap_days',0)}d",   "between deliveries")
        with d: md_card("Risk Score", f"{w.get('score',0)}/3",     RL.get(w.get('score',0),""))

        st.divider()
        c1, c2 = st.columns([2, 1])
        with c1:
            sup = w.get("supply_level", 0)
            dem = w.get("demand_level", 0)
            gap = w.get("gap", 0)
            st.caption(f"Supply Level — {sup}%")
            st.progress(min(sup/100, 1.0))
            st.caption(f"Demand Level — {dem}%")
            st.progress(min(dem/100, 1.0))
            gap_col = "#1A7A4A" if -5 <= gap <= 20 else "#A93226"
            st.markdown(
                f"<p style='color:{gap_col};font-weight:700;font-size:14px;'>"
                f"Supply–Demand Gap: {'+' if gap>=0 else ''}{gap}%</p>",
                unsafe_allow_html=True
            )
        with c2:
            flag_col = RC.get(w.get("score",0),"#888")
            st.markdown(
                f"<div style='background:{flag_col}15;border:1.5px solid {flag_col}88;"
                f"border-left:4px solid {flag_col};border-radius:8px;padding:14px;'>"
                f"<p style='margin:0 0 6px;font-size:14px;font-weight:700;color:#1A1A1A;'>"
                f"{w.get('flag','')}</p>"
                f"<p style='margin:0;font-size:11px;color:#444;'>"
                f"{w.get('recommendation','')}</p></div>",
                unsafe_allow_html=True
            )

        ar = w.get("at_risk_categories", [])
        if ar:
            st.divider()
            st.subheader(f"Categories at Risk ({len(ar)})")
            cols = st.columns(min(len(ar), 4))
            for i, cat in enumerate(ar[:8]):
                sl = SHELF_LIFE.get(cat, 0)
                with cols[i % min(len(ar), 4)]:
                    st.markdown(
                        f"<div style='background:#FDEDEC;border:1.5px solid #A93226;"
                        f"border-radius:6px;padding:10px;text-align:center;'>"
                        f"<p style='margin:0;font-size:12px;font-weight:700;color:#1A1A1A;'>{cat}</p>"
                        f"<p style='margin:4px 0 0;font-size:10px;color:#A93226;font-weight:600;'>{sl}d shelf life</p>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
        else:
            st.success("No categories at risk at this replenishment frequency")

# ── TAB 3 ──────────────────────────────────────────────────────────
with t3:
    st.subheader("Competitor Threat — Within 2km")
    a, b, c, d = st.columns(4)
    with a: md_card("Threat Level",   store["threat_level"])
    with b: md_card("Competitors",    str(store["num_competitors_2km"]), "within 2km")
    with c: md_card("Combined Floor", f"{int(store['combined_comp_floor'])}m²")
    with d: md_card("Threat Ratio",   f"{store['threat_ratio']}x")

    st.divider()
    nearby = store.get("competitors_nearby", [])
    if nearby:
        st.subheader(f"Nearby Competitors ({len(nearby)} closest)")
        for comp in nearby:
            cs = comp.get("competitor_score", 0)
            fa = comp.get("floor_adjustment", 1.0)
            st.markdown(
                f"<div style='background:#FDFEFE;border:1.5px solid #D5D8DC;"
                f"border-radius:8px;padding:14px;margin-bottom:8px;"
                f"border-left:5px solid #A93226;'>"
                f"<div style='display:flex;justify-content:space-between;'>"
                f"<div>"
                f"<p style='margin:0;font-size:15px;font-weight:700;color:#1A1A1A;'>{comp['comp_name']}</p>"
                f"<p style='margin:4px 0 0;font-size:12px;color:#555;'>"
                f"{comp.get('comp_city','')} — {comp['distance_km']} km away</p>"
                f"</div>"
                f"<div style='text-align:right;'>"
                f"<p style='margin:0;font-size:15px;color:#C0550A;font-weight:700;'>{int(comp['floor_size'])} m²</p>"
                f"<p style='margin:3px 0 0;font-size:11px;color:#777;'>"
                f"Score: {cs:.1f} | Adj: {fa:.2f}x</p>"
                f"</div></div></div>",
                unsafe_allow_html=True
            )
    else:
        st.success("No competitors within 2km — store has full local market share")

# ── TAB 4 ──────────────────────────────────────────────────────────
with t4:
    st.subheader("Category Spoilage Risk")
    risks = store.get("category_risk", [])
    if risks:
        risk_counts = {}
        for r in risks:
            risk_counts[r["risk"]] = risk_counts.get(r["risk"], 0) + 1
        a, b, c, d = st.columns(4)
        with a: md_card("High Risk",   str(risk_counts.get("High",0)),        "categories")
        with b: md_card("Medium Risk", str(risk_counts.get("Medium",0)),      "categories")
        with c: md_card("Low Risk",    str(risk_counts.get("Low",0)),         "categories")
        with d: md_card("Opportunity", str(risk_counts.get("Opportunity",0)), "categories")
        st.divider()

        for r in risks:
            risk   = r.get("risk","Low")
            cat    = r.get("category","")
            reason = r.get("reason","")
            sl     = r.get("shelf_life_days",0)
            yoy    = r.get("yoy_change",0)
            rate   = r.get("rate_2025",0)
            col    = {"High":"#A93226","Medium":"#B7770D",
                      "Low":"#1A7A4A","Opportunity":"#1A5276"}.get(risk,"#555")
            bg     = {"High":"#FDEDEC","Medium":"#FEF9E7",
                      "Low":"#EAFAF1","Opportunity":"#EBF5FB"}.get(risk,"#FDFEFE")
            yc     = "#A93226" if yoy>0.5 else "#1A7A4A" if yoy<-0.5 else "#B7770D"
            sign   = "+" if yoy>=0 else ""
            rate_p = (
                f"<p style='margin:8px 0 0;padding-top:6px;"
                f"border-top:1px solid #D5D8DC;"
                f"font-size:11px;color:#444;'>"
                f"Rate 2025: <b style='color:#1A1A1A;'>{rate}%</b>  —  "
                f"YoY: <b style='color:{yc};'>{sign}{yoy}%</b></p>"
            ) if rate else ""
            sl_p = (
                f"<p style='margin:3px 0 0;font-size:10px;color:#777;'>"
                f"Shelf life: {sl} days</p>"
            ) if sl > 0 else ""
            st.markdown(
                f"<div style='background:{bg};border:1.5px solid #D5D8DC;"
                f"border-radius:8px;padding:13px;margin-bottom:7px;"
                f"border-left:5px solid {col};'>"
                f"<div style='display:flex;justify-content:space-between;align-items:flex-start;'>"
                f"<div style='flex:1;'>"
                f"<p style='margin:0;font-size:15px;font-weight:700;color:#1A1A1A;'>{cat}</p>"
                f"<p style='margin:4px 0 0;font-size:12px;color:#444;'>{reason}</p>"
                f"{sl_p}</div>"
                f"<span style='background:{col};padding:4px 12px;border-radius:4px;"
                f"font-size:12px;font-weight:700;color:white;margin-left:12px;'>{risk}</span>"
                f"</div>{rate_p}</div>",
                unsafe_allow_html=True
            )
    else:
        st.info("No category risk data available")

# ── TAB 5 ──────────────────────────────────────────────────────────
with t5:
    st.subheader("Warehouse Spoilage Overview — All 18 Categories")
    df  = pd.DataFrame(SPOILAGE).sort_values("rate_2025", ascending=False)
    t24 = df["spoilage_2024"].sum()
    s24 = df["sales_2024"].sum()
    t25 = df["spoilage_2025"].sum()
    s25 = df["sales_2025"].sum()
    r24 = round(t24/s24*100,2) if s24>0 else 0
    r25 = round(t25/s25*100,2) if s25>0 else 0
    yov = round(r25-r24,2)

    a, b, c = st.columns(3)
    with a: md_card("Overall Rate 2024", f"{r24}%")
    with b: md_card("Overall Rate 2025", f"{r25}%")
    with c: md_card("YoY Change", f"{'+' if yov>0 else ''}{yov}%")

    st.divider()
    rows = []
    for _, row in df.iterrows():
        y2    = row.get("yoy_change",0)
        sl    = SHELF_LIFE.get(row["Category"],0)
        trend = "📈 Worse" if y2>0.5 else "📉 Better" if y2<-0.5 else "➡ Stable"
        sign  = "+" if y2>=0 else ""
        rows.append({
            "Category"  : row["Category"],
            "Shelf Life": f"{sl}d",
            "Rate 2024" : f"{round(row.get('rate_2024',0),2)}%",
            "Rate 2025" : f"{round(row.get('rate_2025',0),2)}%",
            "YoY"       : f"{sign}{round(y2,2)}%",
            "Trend"     : trend
        })

    table_rows = ""
    for i, row in enumerate(rows):
        yoy_val = row["YoY"].replace("+","").replace("%","")
        try:
            yoy_f   = float(yoy_val)
            yoy_col = "#A93226" if yoy_f>0.5 else "#1A7A4A" if yoy_f<-0.5 else "#B7770D"
        except:
            yoy_col = "#1A1A1A"
        bg = "#F8F9FA" if i%2==0 else "#FFFFFF"
        table_rows += (
            f"<tr style='border-bottom:1px solid #E0E0E0;background:{bg};'>"
            f"<td style='padding:10px 14px;color:#1A1A1A;font-weight:600;'>{row['Category']}</td>"
            f"<td style='padding:10px 14px;color:#555;text-align:center;'>{row['Shelf Life']}</td>"
            f"<td style='padding:10px 14px;color:#444;text-align:center;'>{row['Rate 2024']}</td>"
            f"<td style='padding:10px 14px;color:#1A1A1A;font-weight:700;text-align:center;'>{row['Rate 2025']}</td>"
            f"<td style='padding:10px 14px;color:{yoy_col};font-weight:700;text-align:center;'>{row['YoY']}</td>"
            f"<td style='padding:10px 14px;color:#444;text-align:center;'>{row['Trend']}</td>"
            f"</tr>"
        )
    st.markdown(
        f"<div style='overflow-x:auto;border:1.5px solid #D0D0D0;border-radius:8px;'>"
        f"<table style='width:100%;border-collapse:collapse;background:white;'>"
        f"<thead><tr style='background:#F0F0F0;'>"
        f"<th style='padding:12px 14px;color:#C0550A;text-align:left;font-size:12px;letter-spacing:1px;border-bottom:2px solid #D0D0D0;'>CATEGORY</th>"
        f"<th style='padding:12px 14px;color:#C0550A;text-align:center;font-size:12px;letter-spacing:1px;border-bottom:2px solid #D0D0D0;'>SHELF LIFE</th>"
        f"<th style='padding:12px 14px;color:#C0550A;text-align:center;font-size:12px;letter-spacing:1px;border-bottom:2px solid #D0D0D0;'>RATE 2024</th>"
        f"<th style='padding:12px 14px;color:#C0550A;text-align:center;font-size:12px;letter-spacing:1px;border-bottom:2px solid #D0D0D0;'>RATE 2025</th>"
        f"<th style='padding:12px 14px;color:#C0550A;text-align:center;font-size:12px;letter-spacing:1px;border-bottom:2px solid #D0D0D0;'>YOY</th>"
        f"<th style='padding:12px 14px;color:#C0550A;text-align:center;font-size:12px;letter-spacing:1px;border-bottom:2px solid #D0D0D0;'>TREND</th>"
        f"</tr></thead>"
        f"<tbody>{table_rows}</tbody>"
        f"</table></div>",
        unsafe_allow_html=True
    )

# ── TAB 6 ──────────────────────────────────────────────────────────
with t6:
    st.subheader("Store Comparison")
    ca, cb = st.columns(2)
    with ca: na = st.selectbox("STORE A", SOPTS, index=0, key="sa")
    with cb: nb = st.selectbox("STORE B", SOPTS, index=1, key="sb")
    a = gs(na)
    b = gs(nb)

    if a and b and na != nb:
        st.divider()
        mc_a = RC.get(a["mismatch_score"],"#888")
        mc_b = RC.get(b["mismatch_score"],"#888")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f"<div style='background:{mc_a}15;border:1.5px solid {mc_a}88;"
                f"border-radius:8px;padding:16px;text-align:center;'>"
                f"<p style='margin:0 0 4px;font-size:10px;color:#C0550A;font-weight:700;letter-spacing:1px;'>STORE A</p>"
                f"<p style='margin:0;font-size:17px;font-weight:800;color:#1A1A1A;'>{a['brand']}</p>"
                f"<p style='margin:3px 0;font-size:13px;color:#444;'>{a['city']}, {a['province']}</p>"
                f"<p style='margin:0;font-size:11px;color:#777;'>{a.get('address','')}</p>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c2:
            st.markdown(
                f"<div style='background:{mc_b}15;border:1.5px solid {mc_b}88;"
                f"border-radius:8px;padding:16px;text-align:center;'>"
                f"<p style='margin:0 0 4px;font-size:10px;color:#C0550A;font-weight:700;letter-spacing:1px;'>STORE B</p>"
                f"<p style='margin:0;font-size:17px;font-weight:800;color:#1A1A1A;'>{b['brand']}</p>"
                f"<p style='margin:3px 0;font-size:13px;color:#444;'>{b['city']}, {b['province']}</p>"
                f"<p style='margin:0;font-size:11px;color:#777;'>{b.get('address','')}</p>"
                f"</div>",
                unsafe_allow_html=True
            )

        st.divider()
        metrics = [
            ("Floor Size (m²)",   a["floor_size"],         b["floor_size"],         True),
            ("Spending Power",    a["spending_power"],      b["spending_power"],      True),
            ("Market Share (%)",  a["market_share"],        b["market_share"],        True),
            ("Potential Demand",  a["potential_demand"],    b["potential_demand"],    True),
            ("Competitors (2km)", a["num_competitors_2km"], b["num_competitors_2km"], False),
            ("Mismatch Score",    a["mismatch_score"],      b["mismatch_score"],      False),
            ("Best Y (x/week)",   a["best_y"],              b["best_y"],              False),
        ]
        h1, h2, h3, h4 = st.columns([2,1,1,1])
        h1.write("**Metric**")
        h2.write("**Store A**")
        h3.write("**Store B**")
        h4.write("**Better**")
        st.divider()
        for label, va, vb, higher in metrics:
            c1, c2, c3, c4 = st.columns([2,1,1,1])
            if isinstance(va, float) and isinstance(vb, float):
                better = "🅰" if (va>vb)==higher else "🅱"
                va_s = f"{va:.1f}"; vb_s = f"{vb:.1f}"
            else:
                better = "🅰" if (va<vb)==(not higher) else "🅱"
                va_s = str(va); vb_s = str(vb)
            c1.caption(label)
            c2.write(va_s)
            c3.write(vb_s)
            c4.write(f"**{better}**")

        st.divider()
        better  = "A" if a["potential_demand"] > b["potential_demand"] else "B"
        riskier = ("A" if a["mismatch_score"]  > b["mismatch_score"]  else
                   "B" if b["mismatch_score"]  > a["mismatch_score"]  else "neither")
        st.info(
            f"Store {better} has higher potential demand.  " +
            (f"Store {riskier} carries higher mismatch risk."
             if riskier != "neither" else "Both stores carry equal mismatch risk.")
        )
    elif na == nb:
        st.warning("Please select two different stores to compare")
