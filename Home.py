import streamlit as st
import pandas as pd

# ==========================================
# 👇 請在這裡貼上你的 Google Sheets CSV 連結
# ==========================================
DRY_FOOD_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRE1dBL2TM_Jri1hjAAoRKsVwEz8C17Qz8S4V_287IvZW01nSxFsKH2UcFFv1TomIQFoKc49Lmmb-zq/pub?gid=0&single=true&output=csv"
WET_FOOD_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRE1dBL2TM_Jri1hjAAoRKsVwEz8C17Qz8S4V_287IvZW01nSxFsKH2UcFFv1TomIQFoKc49Lmmb-zq/pub?gid=1528481875&single=true&output=csv"
# ==========================================

st.set_page_config(page_title="貓咪每日餵食計算器", layout="wide")

st.title("🐱 貓咪每日餵食計算器")
st.markdown("根據貓咪體重與生命階段計算每日熱量需求，並從 Google Sheets (CSV) 取得飼料營養資料。")

# ---------- 讀取資料 (專為 stlite 優化) ----------
@st.cache_data(ttl=600)
def load_food_data():
    dry_data = pd.DataFrame()
    wet_data = pd.DataFrame()
    
    try:
        # 嘗試使用 pyodide (stlite 瀏覽器環境)
        try:
            from pyodide.http import open_url
            # 使用 open_url 讀取網址
            if DRY_FOOD_URL.startswith("http"):
                dry_data = pd.read_csv(open_url(DRY_FOOD_URL))
            if WET_FOOD_URL.startswith("http"):
                wet_data = pd.read_csv(open_url(WET_FOOD_URL))
        except ImportError:
            # 如果是在本地電腦開發 (非 stlite)，直接讀取
            if DRY_FOOD_URL.startswith("http"):
                dry_data = pd.read_csv(DRY_FOOD_URL)
            if WET_FOOD_URL.startswith("http"):
                wet_data = pd.read_csv(WET_FOOD_URL)

        # 資料清理與轉換
        if not dry_data.empty:
            dry_data.columns = dry_data.columns.str.strip() # 去除欄位名稱的空白
        if not wet_data.empty:
            wet_data.columns = wet_data.columns.str.strip()

        numeric_cols = ['熱量(kcal/100g)', '蛋白質(%)', '脂肪(%)', '水分(%)', '纖維(%)', 
                        '灰質(%)', '磷(%)', '鈣(%)', '牛磺酸(%)', '碳水化合物(%)']
        
        for col in numeric_cols:
            if not dry_data.empty and col in dry_data.columns:
                dry_data[col] = pd.to_numeric(dry_data[col], errors='coerce')
            if not wet_data.empty and col in wet_data.columns:
                wet_data[col] = pd.to_numeric(wet_data[col], errors='coerce')
        
        return dry_data, wet_data

    except Exception as e:
        st.error(f"無法讀取資料，請檢查 CSV 連結是否正確且已發佈到網路。錯誤訊息：{e}")
        return pd.DataFrame(), pd.DataFrame()

dry_foods, wet_foods = load_food_data()

# 檢查資料是否讀取成功
if dry_foods.empty and wet_foods.empty:
    st.warning("⚠️ 尚未讀取到資料，請確認程式碼上方的 CSV URL 是否已填寫正確。")
    st.stop()

# ---------- 側邊欄 (貓咪資料) ----------
with st.sidebar:
    st.header("🐈 貓咪資料")
    weight = st.number_input("體重 (kg)", min_value=0.5, max_value=20.0, value=4.0, step=0.1)
    
    factor_options = {
        "幼貓 (<4個月)": 2.5,
        "幼貓 (4-12個月)": 2.0,
        "成年貓 (絕育)": 1.2,
        "成年貓 (未絕育)": 1.4,
        "活躍/戶外貓": 1.6,
        "老年貓": 1.1,
        "肥胖傾向/減肥": 0.8
    }
    life_stage = st.selectbox("生命階段 / 活動量", list(factor_options.keys()))
    factor = factor_options[life_stage]
    
    rer = 70 * (weight ** 0.75)
    der = rer * factor
    st.metric("每日建議熱量", f"{der:.0f} kcal")
    
    st.divider()
    meals_per_day = st.number_input("每日餐數", min_value=1, max_value=10, value=2, step=1)
    st.session_state['meals_per_day'] = meals_per_day
    st.caption(f"每餐將依此數平分每日總量")
    
    st.divider()
    st.caption("資料來源：Google Sheets (CSV 發佈模式)")

# ---------- 模式選擇 ----------
mode = st.radio(
    "選擇餵食模式",
    ["只吃乾糧", "只吃濕糧", "乾糧 + 濕糧", "兩種乾糧 + 濕糧"],
    horizontal=True
)

# ---------- 輔助函數 ----------
def get_brand_options(df):
    if df.empty: return []
    return sorted(df['品牌'].dropna().unique())

def get_flavor_options(df, brand):
    if df.empty or not brand: return []
    return df[df['品牌'] == brand]['口味'].tolist()

def get_food_row_by_brand_flavor(df, brand, flavor):
    if df.empty: return None
    row = df[(df['品牌'] == brand) & (df['口味'] == flavor)]
    return row.iloc[0] if len(row) > 0 else None

results = []

# ---------- 核心計算邏輯 ----------
# (這部分與你原本的邏輯幾乎一樣，只做少量優化)

# 1. 只吃乾糧
if mode == "只吃乾糧":
    if dry_foods.empty: st.stop()
    brand = st.selectbox("選擇乾糧品牌", get_brand_options(dry_foods), key="d1_b")
    flavor = st.selectbox("選擇乾糧口味", get_flavor_options(dry_foods, brand), key="d1_f")
    
    row = get_food_row_by_brand_flavor(dry_foods, brand, flavor)
    if row is not None:
        kcal = row['熱量(kcal/100g)']
        if kcal > 0:
            daily_g = (der * 100) / kcal
            st.success(f"建議每日：**{daily_g:.1f}g** (每餐 {daily_g/meals_per_day:.1f}g)")
            results.append(("乾糧", row, daily_g))

# 2. 只吃濕糧
elif mode == "只吃濕糧":
    if wet_foods.empty: st.stop()
    brand = st.selectbox("選擇濕糧品牌", get_brand_options(wet_foods), key="w1_b")
    flavor = st.selectbox("選擇濕糧口味", get_flavor_options(wet_foods, brand), key="w1_f")
    
    row = get_food_row_by_brand_flavor(wet_foods, brand, flavor)
    if row is not None:
        kcal = row['熱量(kcal/100g)']
        if kcal > 0:
            daily_g = (der * 100) / kcal
            st.success(f"建議每日：**{daily_g:.1f}g** (每餐 {daily_g/meals_per_day:.1f}g)")
            results.append(("濕糧", row, daily_g))

# 3. 乾糧 + 濕糧
elif mode == "乾糧 + 濕糧":
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("乾糧")
        d_brand = st.selectbox("品牌", get_brand_options(dry_foods), key="mix_d_b")
        d_flavor = st.selectbox("口味", get_flavor_options(dry_foods, d_brand), key="mix_d_f")
        d_row = get_food_row_by_brand_flavor(dry_foods, d_brand, d_flavor)
    
    with c2:
        st.subheader("濕糧")
        w_brand = st.selectbox("品牌", get_brand_options(wet_foods), key="mix_w_b")
        w_flavor = st.selectbox("口味", get_flavor_options(wet_foods, w_brand), key="mix_w_f")
        w_row = get_food_row_by_brand_flavor(wet_foods, w_brand, w_flavor)
    
    if d_row is not None and w_row is not None:
        wet_g = st.number_input("每日濕糧克數", value=100.0, step=10.0)
        w_kcal_val = w_row['熱量(kcal/100g)']
        d_kcal_val = d_row['熱量(kcal/100g)']
        
        provided = (wet_g * w_kcal_val) / 100
        remain = der - provided
        
        if remain < 0:
            st.error(f"濕糧熱量已超標！({provided:.0f} > {der:.0f})")
        else:
            dry_g = (remain * 100) / d_kcal_val if d_kcal_val > 0 else 0
            st.success(f"濕糧：**{wet_g:.1f}g** + 乾糧：**{dry_g:.1f}g**")
            results.append(("乾糧", d_row, dry_g))
            results.append(("濕糧", w_row, wet_g))

# 4. 兩種乾糧 + 濕糧
elif mode == "兩種乾糧 + 濕糧":
    c1, c2, c3 = st.columns(3)
    # 乾糧 A
    with c1:
        st.caption("乾糧 A")
        d1_b = st.selectbox("品牌", get_brand_options(dry_foods), key="mix2_d1_b")
        d1_f = st.selectbox("口味", get_flavor_options(dry_foods, d1_b), key="mix2_d1_f")
        d1_row = get_food_row_by_brand_flavor(dry_foods, d1_b, d1_f)
    # 乾糧 B
    with c2:
        st.caption("乾糧 B")
        d2_b = st.selectbox("品牌", get_brand_options(dry_foods), key="mix2_d2_b")
        d2_f = st.selectbox("口味", get_flavor_options(dry_foods, d2_b), key="mix2_d2_f")
        d2_row = get_food_row_by_brand_flavor(dry_foods, d2_b, d2_f)
    # 濕糧
    with c3:
        st.caption("濕糧")
        w_b = st.selectbox("品牌", get_brand_options(wet_foods), key="mix2_w_b")
        w_f = st.selectbox("口味", get_flavor_options(wet_foods, w_b), key="mix2_w_f")
        w_row = get_food_row_by_brand_flavor(wet_foods, w_b, w_f)

    if all([d1_row is not None, d2_row is not None, w_row is not None]):
        wet_g = st.number_input("每日濕糧克數", value=80.0, step=10.0)
        ratio = st.slider(f"{d1_b} 佔乾糧比例 (%)", 0, 100, 50)
        
        w_kcal_val = w_row['熱量(kcal/100g)']
        provided = (wet_g * w_kcal_val) / 100
        remain = der - provided
        
        if remain < 0:
            st.error("濕糧熱量已超標！")
        else:
            # 混合乾糧熱量計算
            alpha = ratio / 100
            d1_k = d1_row['熱量(kcal/100g)']
            d2_k = d2_row['熱量(kcal/100g)']
            avg_k = alpha * d1_k + (1-alpha) * d2_k
            
            total_dry = (remain * 100) / avg_k if avg_k > 0 else 0
            d1_g = total_dry * alpha
            d2_g = total_dry * (1-alpha)
            
            st.success(f"濕糧：**{wet_g:.1f}g**\n乾糧A：**{d1_g:.1f}g**\n乾糧B：**{d2_g:.1f}g**")
            results.append(("乾糧", d1_row, d1_g))
            results.append(("乾糧", d2_row, d2_g))
            results.append(("濕糧", w_row, wet_g))

# ---------- 儲存結果並跳轉 ----------
st.markdown("---")

if results:
    # 存入 Session State 供下一頁使用
    st.session_state['selected_foods_data'] = results 
    st.session_state['cat_weight'] = weight

    if st.button("👉 查看詳細營養成份分析", type="primary", use_container_width=True):
        st.switch_page("pages/2_nutrition.py")
else:
    st.info("👈 請選擇飼料以開始計算")

st.markdown("---")
st.caption("📌 這是 stlite (PWA) 版本，資料讀取自 Google Sheets CSV。")
