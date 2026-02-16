import streamlit as st
import pandas as pd
with col3:
    st.subheader("🔥 熱量佔比 (ME)")
    
    # 改用 Progress Bar 顯示 (輕量化)
    st.caption(f"蛋白質: {me_p:.1f}%")
    st.progress(int(me_p))
    
    st.caption(f"脂肪: {me_f:.1f}%")
    st.progress(int(me_f))
    
    st.caption(f"碳水: {me_c:.1f}%")
    st.progress(int(me_c))
# ==========================================
# 👇 請在這裡再次貼上你的 Google Sheets CSV 連結
# (為了確保直接開啟此頁面也能讀取資料，建議這邊也放連結)
# ==========================================
DRY_FOOD_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRE1dBL2TM_Jri1hjAAoRKsVwEz8C17Qz8S4V_287IvZW01nSxFsKH2UcFFv1TomIQFoKc49Lmmb-zq/pub?gid=0&single=true&output=csv"
WET_FOOD_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRE1dBL2TM_Jri1hjAAoRKsVwEz8C17Qz8S4V_287IvZW01nSxFsKH2UcFFv1TomIQFoKc49Lmmb-zq/pub?gid=1528481875&single=true&output=csv"
# ==========================================

st.set_page_config(page_title="貓糧營養資料庫", layout="wide")
st.title("📚 貓糧營養資料庫")
st.markdown("查詢各品牌貓糧的詳細營養成份、乾物比 (DM) 與代謝能 (ME) 分析。")

# ---------- 資料讀取函數 (與首頁相同) ----------
@st.cache_data(ttl=600)
def load_food_data():
    dry_data = pd.DataFrame()
    wet_data = pd.DataFrame()
    try:
        # 嘗試使用 pyodide (stlite 瀏覽器環境)
        try:
            from pyodide.http import open_url
            if DRY_FOOD_URL.startswith("http"):
                dry_data = pd.read_csv(open_url(DRY_FOOD_URL))
            if WET_FOOD_URL.startswith("http"):
                wet_data = pd.read_csv(open_url(WET_FOOD_URL))
        except ImportError:
            # 本地開發環境
            if DRY_FOOD_URL.startswith("http"):
                dry_data = pd.read_csv(DRY_FOOD_URL)
            if WET_FOOD_URL.startswith("http"):
                wet_data = pd.read_csv(WET_FOOD_URL)

        # 清理欄位
        for df in [dry_data, wet_data]:
            if not df.empty:
                df.columns = df.columns.str.strip()
                # 確保數值欄位是數字
                cols = ['蛋白質(%)', '脂肪(%)', '水分(%)', '纖維(%)', '灰質(%)', 
                        '磷(%)', '鈣(%)', '碳水化合物(%)', '熱量(kcal/100g)']
                for c in cols:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        
        return dry_data, wet_data
    except Exception as e:
        st.error(f"資料讀取失敗: {e}")
        return pd.DataFrame(), pd.DataFrame()

dry_foods, wet_foods = load_food_data()

# ---------- 側邊欄篩選 ----------
with st.sidebar:
    st.header("🔍 篩選條件")
    food_type = st.radio("選擇種類", ["乾糧", "濕糧"])
    
    # 根據種類選擇資料來源
    df = dry_foods if food_type == "乾糧" else wet_foods
    
    if df.empty:
        st.warning("讀取不到資料，請檢查 CSV 連結。")
        st.stop()
        
    all_brands = sorted(df['品牌'].unique())
    selected_brand = st.selectbox("選擇品牌", all_brands)
    
    # 過濾出該品牌的口味
    brand_df = df[df['品牌'] == selected_brand]
    all_flavors = sorted(brand_df['口味'].unique())
    selected_flavor = st.selectbox("選擇口味", all_flavors)

# 取得選定的那一行資料
row = brand_df[brand_df['口味'] == selected_flavor].iloc[0]

# ---------- 核心計算邏輯 ----------
# 1. 取得基本數值
moisture = row.get('水分(%)', 0)
protein = row.get('蛋白質(%)', 0)
fat = row.get('脂肪(%)', 0)
carbs = row.get('碳水化合物(%)', 0)
fiber = row.get('纖維(%)', 0)
ash = row.get('灰質(%)', 0)
phos = row.get('磷(%)', 0)
cal = row.get('鈣(%)', 0)
kcal_per_100g = row.get('熱量(kcal/100g)', 0)

# 2. 計算乾物比 (Dry Matter Basis)
# 公式: 營養素 / (100 - 水分) * 100
dry_matter_content = 100 - moisture
if dry_matter_content <= 0: dry_matter_content = 1 # 避免除以0
dm_protein = (protein / dry_matter_content) * 100
dm_fat = (fat / dry_matter_content) * 100
dm_carbs = (carbs / dry_matter_content) * 100
dm_phos = (phos / dry_matter_content) * 100
dm_cal = (cal / dry_matter_content) * 100

# 3. 計算代謝能比 (ME Ratio / Caloric Distribution)
# 使用 Modified Atwater 係數 (貓糧常用): 蛋白質3.5, 脂肪8.5, 碳水3.5
kcal_p = protein * 3.5
kcal_f = fat * 8.5
kcal_c = carbs * 3.5
total_est_kcal = kcal_p + kcal_f + kcal_c

if total_est_kcal > 0:
    me_p = (kcal_p / total_est_kcal) * 100
    me_f = (kcal_f / total_est_kcal) * 100
    me_c = (kcal_c / total_est_kcal) * 100
else:
    me_p = me_f = me_c = 0

# 4. 鈣磷比
ca_p_ratio = f"{cal/phos:.2f} : 1" if phos > 0 else "無法計算"

# ---------- 顯示介面 ----------

st.header(f"{selected_brand} - {selected_flavor}")

# --- 第一區塊：主要營養指標 (三欄佈局) ---
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("💧 基本數值 (As Fed)")
    st.caption("包裝標示/餵食狀態")
    base_df = pd.DataFrame({
        "營養素": ["蛋白質", "脂肪", "碳水化合物", "水分", "纖維", "灰質"],
        "含量 (%)": [f"{protein}%", f"{fat}%", f"{carbs}%", f"{moisture}%", f"{fiber}%", f"{ash}%"]
    })
    st.dataframe(base_df, hide_index=True, use_container_width=True)

with col2:
    st.subheader("🍂 乾物比 (DM Basis)")
    st.caption("扣除水分後的真實營養濃度")
    dm_df = pd.DataFrame({
        "營養素": ["蛋白質 (DM)", "脂肪 (DM)", "碳水化合物 (DM)", "磷 (DM)", "鈣 (DM)"],
        "含量 (%)": [f"{dm_protein:.1f}%", f"{dm_fat:.1f}%", f"{dm_carbs:.1f}%", f"{dm_phos:.2f}%", f"{dm_cal:.2f}%"]
    })
    st.dataframe(dm_df, hide_index=True, use_container_width=True)

with col3:
    st.subheader("🔥 熱量分析 (ME Ratio)")
    st.caption("熱量來源佔比 (蛋白質/脂肪/碳水)")
    
    # 繪製甜甜圈圖
    labels = ['蛋白質', '脂肪', '碳水化合物']
    values = [me_p, me_f, me_c]
    colors = ['#FF9999', '#FFCC99', '#99CCFF'] # 粉紅、粉橘、淺藍
    
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, marker=dict(colors=colors))])
    fig.update_layout(
        margin=dict(t=0, b=0, l=0, r=0), 
        height=180,
        showlegend=False,
        annotations=[dict(text=f'{int(kcal_per_100g)}<br>kcal', x=0.5, y=0.5, font_size=16, showarrow=False)]
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # 顯示文字數據
    st.text(f"蛋白質熱量比: {me_p:.1f}%")
    st.text(f"脂肪熱量比:   {me_f:.1f}%")
    st.text(f"碳水熱量比:   {me_c:.1f}%")

st.divider()

# --- 第二區塊：礦物質與關鍵指標 ---
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("磷 (Phosphorus)", f"{phos}%", help="腎臟病貓需注意此數值")
with m2:
    st.metric("鈣 (Calcium)", f"{cal}%")
with m3:
    st.metric("鈣磷比 (Ca:P)", ca_p_ratio, help="理想值約為 1.1:1 ~ 1.4:1")
with m4:
    st.metric("熱量密度", f"{kcal_per_100g:.0f} kcal/100g")

# --- 額外資訊 (如果 CSV 有更多欄位) ---
# 檢查是否有牛磺酸或其他欄位
extra_cols = []
for col in row.index:
    if col not in ['品牌', '口味', '蛋白質(%)', '脂肪(%)', '水分(%)', '纖維(%)', '灰質(%)', 
                   '磷(%)', '鈣(%)', '碳水化合物(%)', '熱量(kcal/100g)']:
        val = row[col]
        if str(val) != "" and str(val) != "0" and str(val) != "0.0":
            extra_cols.append((col, val))

if extra_cols:
    st.markdown("### 📝 其他標示成分")
    ex_cols = st.columns(len(extra_cols))
    for i, (col_name, val) in enumerate(extra_cols):
        with ex_cols[i]:
            st.metric(col_name, val)

st.caption("註：ME熱量比採用 Modified Atwater (3.5/8.5/3.5) 估算，可能與官方標示略有出入。")
