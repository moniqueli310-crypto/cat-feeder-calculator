import streamlit as st
import pandas as pd

# ==========================================
# 👇 請在這裡貼上你的 CSV 連結
# ==========================================
DRY_FOOD_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRE1dBL2TM_Jri1hjAAoRKsVwEz8C17Qz8S4V_287IvZW01nSxFsKH2UcFFv1TomIQFoKc49Lmmb-zq/pub?gid=0&single=true&output=csv"
WET_FOOD_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRE1dBL2TM_Jri1hjAAoRKsVwEz8C17Qz8S4V_287IvZW01nSxFsKH2UcFFv1TomIQFoKc49Lmmb-zq/pub?gid=1528481875&single=true&output=csv"
# ==========================================

st.set_page_config(page_title="貓糧營養資料庫", layout="wide")
st.title("📚 貓糧營養資料庫")

# ---------- 1. 資料讀取函數 ----------
@st.cache_data(ttl=600)
def load_food_data():
    try:
        # 直接讀檔
        dry_data = pd.read_csv("dry_food.csv")
        wet_data = pd.read_csv("wet_food.csv")
        # ... (後面的清理邏輯一樣)
        return dry_data, wet_data
    except:
        return pd.DataFrame(), pd.DataFrame()
            
        # 資料清理
        for df in [dry_data, wet_data]:
            if not df.empty:
                df.columns = df.columns.str.strip()
                cols = ['蛋白質(%)', '脂肪(%)', '水分(%)', '纖維(%)', '灰質(%)', 
                        '磷(%)', '鈣(%)', '碳水化合物(%)', '熱量(kcal/100g)']
                for c in cols:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return dry_data, wet_data
    except Exception:
        # 本地測試用 (如果不使用 stlite)
        try:
            if DRY_FOOD_URL.startswith("http"): dry_data = pd.read_csv(DRY_FOOD_URL)
            if WET_FOOD_URL.startswith("http"): wet_data = pd.read_csv(WET_FOOD_URL)
            return dry_data, wet_data
        except:
            return pd.DataFrame(), pd.DataFrame()

dry_foods, wet_foods = load_food_data()

# 檢查是否有資料
if dry_foods.empty and wet_foods.empty:
    st.warning("⚠️ 讀取不到資料，請檢查程式碼最上方的 CSV 連結是否正確。")
    st.stop()

# ---------- 2. 側邊欄篩選 ----------
with st.sidebar:
    st.header("🔍 篩選條件")
    food_type = st.radio("選擇種類", ["乾糧", "濕糧"])
    df = dry_foods if food_type == "乾糧" else wet_foods
    
    if df.empty: st.stop()
        
    all_brands = sorted(df['品牌'].unique())
    selected_brand = st.selectbox("選擇品牌", all_brands)
    
    brand_df = df[df['品牌'] == selected_brand]
    all_flavors = sorted(brand_df['口味'].unique())
    selected_flavor = st.selectbox("選擇口味", all_flavors)

# 取得選定的那一行資料
row = brand_df[brand_df['口味'] == selected_flavor].iloc[0]

# ---------- 3. 核心數值計算 ----------
moisture = row.get('水分(%)', 0)
protein = row.get('蛋白質(%)', 0)
fat = row.get('脂肪(%)', 0)
carbs = row.get('碳水化合物(%)', 0)
fiber = row.get('纖維(%)', 0)
ash = row.get('灰質(%)', 0)
phos = row.get('磷(%)', 0)
cal = row.get('鈣(%)', 0)
kcal_per_100g = row.get('熱量(kcal/100g)', 0)

# 計算乾物比 (DM)
dm = 100 - moisture
if dm <= 0: dm = 1
dm_p = (protein / dm) * 100
dm_f = (fat / dm) * 100
dm_c = (carbs / dm) * 100
dm_phos = (phos / dm) * 100
dm_cal = (cal / dm) * 100

# 計算 ME 熱量比
kp = protein * 3.5
kf = fat * 8.5
kc = carbs * 3.5
total_k = kp + kf + kc

me_p = (kp / total_k * 100) if total_k > 0 else 0
me_f = (kf / total_k * 100) if total_k > 0 else 0
me_c = (kc / total_k * 100) if total_k > 0 else 0

ca_p_ratio = f"{cal/phos:.2f} : 1" if phos > 0 else "N/A"

# ---------- 4. 顯示介面 (無 Plotly 版) ----------
st.header(f"{selected_brand} - {selected_flavor}")

# ⚠️ 關鍵：這裡必須先定義 col1, col2, col3，後面才能用 with col3
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("💧 基本數值")
    st.dataframe(pd.DataFrame({
        "項目": ["蛋白質", "脂肪", "碳水", "水分", "纖維", "灰質"],
        "%": [protein, fat, carbs, moisture, fiber, ash]
    }), hide_index=True, use_container_width=True)

with col2:
    st.subheader("🍂 乾物比 (DM)")
    st.dataframe(pd.DataFrame({
        "項目": ["蛋白質", "脂肪", "碳水", "磷", "鈣"],
        "DM%": [f"{dm_p:.1f}", f"{dm_f:.1f}", f"{dm_c:.1f}", f"{dm_phos:.2f}", f"{dm_cal:.2f}"]
    }), hide_index=True, use_container_width=True)

with col3:
    st.subheader("🔥 熱量佔比 (ME)")
    st.caption("熱量來源分佈")
    
    st.markdown(f"**蛋白質 {me_p:.1f}%**")
    st.progress(min(int(me_p), 100))
    
    st.markdown(f"**脂肪 {me_f:.1f}%**")
    st.progress(min(int(me_f), 100))
    
    st.markdown(f"**碳水 {me_c:.1f}%**")
    st.progress(min(int(me_c), 100))
    
    st.caption(f"熱量密度: {kcal_per_100g:.0f} kcal/100g")

st.divider()

m1, m2, m3 = st.columns(3)
m1.metric("磷 (P)", f"{phos}%")
m2.metric("鈣 (Ca)", f"{cal}%")
m3.metric("鈣磷比", ca_p_ratio)

st.caption("註：ME 熱量比採 Modified Atwater (3.5/8.5/3.5) 估算。")
