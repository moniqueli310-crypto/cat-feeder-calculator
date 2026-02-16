import streamlit as st
import pandas as pd

st.set_page_config(page_title="貓咪每日餵食計算器", layout="wide")

st.title("🐱 貓咪每日餵食計算器")
st.markdown("根據貓咪體重與生命階段計算每日熱量需求。")

# ---------- 讀取本地資料 (極速版) ----------
@st.cache_data(ttl=600)
def load_food_data():
    try:
        # 直接讀取本地檔案，速度最快
        # 只要 index.html 有設定 files，這裡就能直接讀到
        dry_data = pd.read_csv("dry_food.csv")
        wet_data = pd.read_csv("wet_food.csv")

        # 資料清理
        for df in [dry_data, wet_data]:
            if not df.empty:
                df.columns = df.columns.str.strip()
                cols = ['熱量(kcal/100g)', '蛋白質(%)', '脂肪(%)', '水分(%)', '纖維(%)', 
                        '灰質(%)', '磷(%)', '鈣(%)', '牛磺酸(%)', '碳水化合物(%)']
                for c in cols:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c], errors='coerce')
        
        return dry_data, wet_data

    except Exception as e:
        st.error(f"讀取資料失敗: {e}")
        st.info("請確認 dry_food.csv 和 wet_food.csv 已上傳到 GitHub 並且在 index.html 設定了 files。")
        return pd.DataFrame(), pd.DataFrame()

dry_foods, wet_foods = load_food_data()

if dry_foods.empty and wet_foods.empty:
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
    st.caption(f"每餐將依此數平分每日總量")

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

# ---------- 計算邏輯 ----------
if mode == "只吃乾糧":
    if not dry_foods.empty:
        brand = st.selectbox("選擇乾糧品牌", get_brand_options(dry_foods))
        flavor = st.selectbox("選擇乾糧口味", get_flavor_options(dry_foods, brand))
        row = get_food_row_by_brand_flavor(dry_foods, brand, flavor)
        if row is not None:
            kcal = row['熱量(kcal/100g)']
            if kcal > 0:
                daily = (der * 100) / kcal
                st.success(f"建議每日：**{daily:.1f}g** (每餐 {daily/meals_per_day:.1f}g)")

elif mode == "只吃濕糧":
    if not wet_foods.empty:
        brand = st.selectbox("選擇濕糧品牌", get_brand_options(wet_foods))
        flavor = st.selectbox("選擇濕糧口味", get_flavor_options(wet_foods, brand))
        row = get_food_row_by_brand_flavor(wet_foods, brand, flavor)
        if row is not None:
            kcal = row['熱量(kcal/100g)']
            if kcal > 0:
                daily = (der * 100) / kcal
                st.success(f"建議每日：**{daily:.1f}g** (每餐 {daily/meals_per_day:.1f}g)")

elif mode == "乾糧 + 濕糧":
    c1, c2 = st.columns(2)
    with c1:
        d_brand = st.selectbox("乾糧品牌", get_brand_options(dry_foods))
        d_flavor = st.selectbox("乾糧口味", get_flavor_options(dry_foods, d_brand))
        d_row = get_food_row_by_brand_flavor(dry_foods, d_brand, d_flavor)
    with c2:
        w_brand = st.selectbox("濕糧品牌", get_brand_options(wet_foods))
        w_flavor = st.selectbox("濕糧口味", get_flavor_options(wet_foods, w_brand))
        w_row = get_food_row_by_brand_flavor(wet_foods, w_brand, w_flavor)
    
    if d_row is not None and w_row is not None:
        wet_g = st.number_input("每日濕糧 (g)", value=100.0, step=10.0)
        w_k = w_row['熱量(kcal/100g)']
        d_k = d_row['熱量(kcal/100g)']
        
        provided = (wet_g * w_k) / 100
        remain = der - provided
        
        if remain < 0:
            st.error(f"濕糧熱量已超標！")
        else:
            dry_g = (remain * 100) / d_k if d_k > 0 else 0
            st.success(f"濕糧：**{wet_g:.1f}g** + 乾糧：**{dry_g:.1f}g**")

elif mode == "兩種乾糧 + 濕糧":
    c1, c2, c3 = st.columns(3)
    with c1:
        d1_b = st.selectbox("乾糧A", get_brand_options(dry_foods))
        d1_f = st.selectbox("口味A", get_flavor_options(dry_foods, d1_b))
        d1_row = get_food_row_by_brand_flavor(dry_foods, d1_b, d1_f)
    with c2:
        d2_b = st.selectbox("乾糧B", get_brand_options(dry_foods))
        d2_f = st.selectbox("口味B", get_flavor_options(dry_foods, d2_b))
        d2_row = get_food_row_by_brand_flavor(dry_foods, d2_b, d2_f)
    with c3:
        w_b = st.selectbox("濕糧", get_brand_options(wet_foods))
        w_f = st.selectbox("口味", get_flavor_options(wet_foods, w_b))
        w_row = get_food_row_by_brand_flavor(wet_foods, w_b, w_f)

    if all([d1_row is not None, d2_row is not None, w_row is not None]):
        wet_g = st.number_input("每日濕糧 (g)", value=80.0, step=10.0)
        ratio = st.slider(f"{d1_b} 佔乾糧比例 (%)", 0, 100, 50)
        
        provided = (wet_g * w_row['熱量(kcal/100g)']) / 100
        remain = der - provided
        
        if remain < 0:
            st.error("濕糧熱量已超標！")
        else:
            alpha = ratio / 100
            avg_k = alpha * d1_row['熱量(kcal/100g)'] + (1-alpha) * d2_row['熱量(kcal/100g)']
            total_dry = (remain * 100) / avg_k if avg_k > 0 else 0
            
            st.success(f"濕糧：**{wet_g:.1f}g**\n乾糧A：**{total_dry*alpha:.1f}g**\n乾糧B：**{total_dry*(1-alpha):.1f}g**")

st.markdown("---")
# 按鈕前往貓糧資料庫
if st.button("👉 查詢貓糧營養資料庫 (乾物比/ME)", type="primary", use_container_width=True):
    st.switch_page("pages/2_nutrition.py")

st.caption("📌 極速版：資料讀取自本地 CSV。")
