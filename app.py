import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 頁面設定（必須在第一個 st 指令之前）
st.set_page_config(page_title="貓咪每日餵食計算器", layout="wide")

st.title("🐱 貓咪每日餵食計算器")
st.markdown("根據貓咪體重與生命階段計算每日熱量需求，並從Google Sheets取得飼料營養資料。")

# ---------- 連接 Google Sheets ----------
@st.cache_data(ttl=600)
def load_food_data():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open("貓咪飼料資料庫")  # 請修改為您的試算表名稱
        dry_sheet = spreadsheet.worksheet("乾糧")
        wet_sheet = spreadsheet.worksheet("濕糧")
        
        dry_data = pd.DataFrame(dry_sheet.get_all_records())
        wet_data = pd.DataFrame(wet_sheet.get_all_records())
        
        numeric_cols = ['熱量(kcal/100g)', '蛋白質(%)', '脂肪(%)', '水分(%)', '纖維(%)']
        for col in numeric_cols:
            if col in dry_data.columns:
                dry_data[col] = pd.to_numeric(dry_data[col], errors='coerce')
            if col in wet_data.columns:
                wet_data[col] = pd.to_numeric(wet_data[col], errors='coerce')
        
        return dry_data, wet_data
    except Exception as e:
        st.error(f"無法讀取Google Sheets：{e}")
        return pd.DataFrame(), pd.DataFrame()

dry_foods, wet_foods = load_food_data()

if dry_foods.empty and wet_foods.empty:
    st.stop()

# ---------- 側邊欄：貓咪基本資料 ----------
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
    
    rer = 70 * (weight ** 0.75)          # 靜止能量需求
    der = rer * factor                    # 每日能量需求
    st.metric("每日建議熱量", f"{der:.0f} kcal")
    
    st.divider()
    meals_per_day = st.number_input("每日餐數", min_value=1, max_value=10, value=2, step=1)
    st.caption(f"每餐將依此數平分每日總量")
    st.divider()
    st.caption("資料來源：Google Sheets (僅所有者可編輯)")

# ---------- 模式選擇 ----------
mode = st.radio(
    "選擇餵食模式",
    ["只吃乾糧", "只吃濕糧", "乾糧 + 濕糧", "兩種乾糧 + 濕糧"],
    horizontal=True
)

results = []   # 儲存 (食物類型, 資料列, 每日克數) 用於後續顯示營養成分

# ---------- 輔助函數：根據品牌篩選口味 ----------
def get_brand_options(df):
    """取得所有不重複的品牌，排序後回傳"""
    if df.empty:
        return []
    brands = df['品牌'].dropna().unique()
    return sorted(brands)

def get_flavor_options(df, brand):
    """根據品牌篩選口味，回傳口味列表（保持原始順序）"""
    if df.empty or not brand:
        return []
    flavors = df[df['品牌'] == brand]['口味'].tolist()
    return flavors

def get_food_row_by_brand_flavor(df, brand, flavor):
    """根據品牌和口味取得完整的資料列"""
    if df.empty:
        return None
    row = df[(df['品牌'] == brand) & (df['口味'] == flavor)]
    if len(row) == 0:
        return None
    return row.iloc[0]

# ==============================================================================
# 情境1：只吃乾糧
# ==============================================================================
if mode == "只吃乾糧":
    if dry_foods.empty:
        st.warning("目前無乾糧資料")
        st.stop()
    
    # 品牌選擇
    dry_brands = get_brand_options(dry_foods)
    selected_dry_brand = st.selectbox("選擇乾糧品牌", dry_brands, key="dry_brand_1")
    
    # 口味選擇（根據品牌動態更新）
    dry_flavors = get_flavor_options(dry_foods, selected_dry_brand)
    if not dry_flavors:
        st.error("該品牌下無口味資料")
        st.stop()
    selected_dry_flavor = st.selectbox("選擇乾糧口味", dry_flavors, key="dry_flavor_1")
    
    # 取得選中的資料列
    selected_row = get_food_row_by_brand_flavor(dry_foods, selected_dry_brand, selected_dry_flavor)
    if selected_row is None:
        st.error("無法取得所選乾糧資料")
        st.stop()
    
    kcal_per_100g = selected_row['熱量(kcal/100g)']
    if kcal_per_100g > 0:
        daily_grams = (der * 100) / kcal_per_100g
        per_meal_grams = daily_grams / meals_per_day
        st.success(
            f"建議每日餵食 **{daily_grams:.1f} 克** 的 {selected_dry_brand} - {selected_dry_flavor}\n\n"
            f"🍽️ 每餐約 **{per_meal_grams:.1f} 克** (每日 {meals_per_day} 餐)"
        )
        results.append(("乾糧", selected_row, daily_grams))
    else:
        st.error("所選乾糧熱量資料有誤")

# ==============================================================================
# 情境2：只吃濕糧（自動計算份量）
# ==============================================================================
elif mode == "只吃濕糧":
    if wet_foods.empty:
        st.warning("目前無濕糧資料")
        st.stop()
    
    # 品牌選擇
    wet_brands = get_brand_options(wet_foods)
    selected_wet_brand = st.selectbox("選擇濕糧品牌", wet_brands, key="wet_brand_2")
    
    # 口味選擇（根據品牌動態更新）
    wet_flavors = get_flavor_options(wet_foods, selected_wet_brand)
    if not wet_flavors:
        st.error("該品牌下無口味資料")
        st.stop()
    selected_wet_flavor = st.selectbox("選擇濕糧口味", wet_flavors, key="wet_flavor_2")
    
    # 取得選中的資料列
    selected_row = get_food_row_by_brand_flavor(wet_foods, selected_wet_brand, selected_wet_flavor)
    if selected_row is None:
        st.error("無法取得所選濕糧資料")
        st.stop()
    
    kcal_per_100g = selected_row['熱量(kcal/100g)']
    if kcal_per_100g <= 0:
        st.error("所選濕糧熱量資料有誤")
        st.stop()
    
    # 自動計算每日克數
    daily_grams = (der * 100) / kcal_per_100g
    per_meal_grams = daily_grams / meals_per_day
    
    st.success(
        f"建議每日餵食 **{daily_grams:.1f} 克** 的 {selected_wet_brand} - {selected_wet_flavor}\n\n"
        f"🍽️ 每餐約 **{per_meal_grams:.1f} 克** (每日 {meals_per_day} 餐)"
    )
    
    results.append(("濕糧", selected_row, daily_grams))

# ==============================================================================
# 情境3：乾糧 + 濕糧（手動輸入濕糧克數）
# ==============================================================================
elif mode == "乾糧 + 濕糧":
    if dry_foods.empty or wet_foods.empty:
        st.warning("需要同時有乾糧和濕糧資料")
        st.stop()
    
    col1, col2 = st.columns(2)
    
    # ---------- 乾糧選擇 ----------
    with col1:
        st.subheader("乾糧")
        dry_brands = get_brand_options(dry_foods)
        selected_dry_brand = st.selectbox("選擇品牌", dry_brands, key="dry_brand_3")
        dry_flavors = get_flavor_options(dry_foods, selected_dry_brand)
        if not dry_flavors:
            st.error("該品牌下無口味資料")
            st.stop()
        selected_dry_flavor = st.selectbox("選擇口味", dry_flavors, key="dry_flavor_3")
        dry_row = get_food_row_by_brand_flavor(dry_foods, selected_dry_brand, selected_dry_flavor)
        if dry_row is None:
            st.error("無法取得所選乾糧資料")
            st.stop()
        dry_kcal = dry_row['熱量(kcal/100g)']
        if dry_kcal <= 0:
            st.error("所選乾糧熱量資料有誤")
            st.stop()
    
    # ---------- 濕糧選擇 ----------
    with col2:
        st.subheader("濕糧")
        wet_brands = get_brand_options(wet_foods)
        selected_wet_brand = st.selectbox("選擇品牌", wet_brands, key="wet_brand_3")
        wet_flavors = get_flavor_options(wet_foods, selected_wet_brand)
        if not wet_flavors:
            st.error("該品牌下無口味資料")
            st.stop()
        selected_wet_flavor = st.selectbox("選擇口味", wet_flavors, key="wet_flavor_3")
        wet_row = get_food_row_by_brand_flavor(wet_foods, selected_wet_brand, selected_wet_flavor)
        if wet_row is None:
            st.error("無法取得所選濕糧資料")
            st.stop()
        wet_kcal = wet_row['熱量(kcal/100g)']
        if wet_kcal <= 0:
            st.error("所選濕糧熱量資料有誤")
            st.stop()
    
    # 輸入濕糧克數
    wet_grams = st.number_input(
        "請輸入每日餵食濕糧的克數",
        min_value=0.0,
        value=100.0,
        step=10.0,
        key="wet_grams_input3"
    )
    
    wet_kcal_provided = (wet_grams * wet_kcal) / 100
    remaining_kcal = der - wet_kcal_provided
    
    if remaining_kcal < 0:
        st.error(f"❌ 濕糧提供的熱量 ({wet_kcal_provided:.0f} kcal) 已超過總需求 ({der:.0f} kcal)，無法搭配乾糧。請減少濕糧。")
        st.stop()
    elif remaining_kcal == 0:
        st.warning("⚠️ 濕糧提供的熱量剛好等於總需求，不需要額外餵食乾糧。")
        dry_daily = 0
    else:
        dry_daily = (remaining_kcal * 100) / dry_kcal
        dry_per_meal = dry_daily / meals_per_day
        st.success(
            f"**濕糧 ({selected_wet_brand} - {selected_wet_flavor})**：每日 **{wet_grams:.1f} 克** (每餐 **{wet_grams/meals_per_day:.1f} 克**)\n\n"
            f"**乾糧 ({selected_dry_brand} - {selected_dry_flavor})**：每日 **{dry_daily:.1f} 克** (每餐 **{dry_per_meal:.1f} 克**)\n\n"
            f"剩餘熱量：{remaining_kcal:.0f} kcal"
        )
        results.append(("乾糧", dry_row, dry_daily))
    
    results.append(("濕糧", wet_row, wet_grams))

# ==============================================================================
# 情境4：兩種乾糧 + 濕糧（手動輸入濕糧克數，兩種乾糧按重量比例分配）
# ==============================================================================
elif mode == "兩種乾糧 + 濕糧":
    if dry_foods.empty or len(dry_foods) < 2 or wet_foods.empty:
        st.warning("需要至少兩種乾糧和一種濕糧")
        st.stop()
    
    col1, col2, col3 = st.columns(3)
    
    # ---------- 乾糧 A 選擇 ----------
    with col1:
        st.subheader("乾糧 A")
        dry_brands = get_brand_options(dry_foods)
        selected_dry1_brand = st.selectbox("選擇品牌", dry_brands, key="dry1_brand_4")
        dry1_flavors = get_flavor_options(dry_foods, selected_dry1_brand)
        if not dry1_flavors:
            st.error("該品牌下無口味資料")
            st.stop()
        selected_dry1_flavor = st.selectbox("選擇口味", dry1_flavors, key="dry1_flavor_4")
        dry1_row = get_food_row_by_brand_flavor(dry_foods, selected_dry1_brand, selected_dry1_flavor)
        if dry1_row is None:
            st.error("無法取得所選乾糧 A 資料")
            st.stop()
        dry1_kcal = dry1_row['熱量(kcal/100g)']
        if dry1_kcal <= 0:
            st.error("乾糧 A 熱量資料有誤")
            st.stop()
    
    # ---------- 乾糧 B 選擇（排除 A 已選的品牌與口味組合）----------
    with col2:
        st.subheader("乾糧 B")
        # 取得所有乾糧，排除已選的（品牌+口味完全相同的組合）
        remaining_dry = dry_foods[~((dry_foods['品牌'] == selected_dry1_brand) & (dry_foods['口味'] == selected_dry1_flavor))]
        if remaining_dry.empty:
            st.error("沒有其他乾糧可選")
            st.stop()
        
        # 從剩餘資料中取得品牌列表
        remaining_brands = remaining_dry['品牌'].dropna().unique()
        selected_dry2_brand = st.selectbox("選擇品牌", sorted(remaining_brands), key="dry2_brand_4")
        
        # 根據所選品牌，從剩餘資料中篩選口味
        dry2_flavors = remaining_dry[remaining_dry['品牌'] == selected_dry2_brand]['口味'].tolist()
        if not dry2_flavors:
            st.error("該品牌下無口味資料")
            st.stop()
        selected_dry2_flavor = st.selectbox("選擇口味", dry2_flavors, key="dry2_flavor_4")
        
        # 取得完整資料列
        dry2_row = get_food_row_by_brand_flavor(remaining_dry, selected_dry2_brand, selected_dry2_flavor)
        if dry2_row is None:
            st.error("無法取得所選乾糧 B 資料")
            st.stop()
        dry2_kcal = dry2_row['熱量(kcal/100g)']
        if dry2_kcal <= 0:
            st.error("乾糧 B 熱量資料有誤")
            st.stop()
    
    # ---------- 濕糧選擇 ----------
    with col3:
        st.subheader("濕糧")
        wet_brands = get_brand_options(wet_foods)
        selected_wet_brand = st.selectbox("選擇品牌", wet_brands, key="wet_brand_4")
        wet_flavors = get_flavor_options(wet_foods, selected_wet_brand)
        if not wet_flavors:
            st.error("該品牌下無口味資料")
            st.stop()
        selected_wet_flavor = st.selectbox("選擇口味", wet_flavors, key="wet_flavor_4")
        wet_row = get_food_row_by_brand_flavor(wet_foods, selected_wet_brand, selected_wet_flavor)
        if wet_row is None:
            st.error("無法取得所選濕糧資料")
            st.stop()
        wet_kcal = wet_row['熱量(kcal/100g)']
        if wet_kcal <= 0:
            st.error("濕糧熱量資料有誤")
            st.stop()
    
    # 輸入濕糧克數
    wet_grams = st.number_input(
        "請輸入每日餵食濕糧的克數",
        min_value=0.0,
        value=100.0,
        step=10.0,
        key="wet_grams_input4"
    )
    
    wet_kcal_provided = (wet_grams * wet_kcal) / 100
    remaining_kcal = der - wet_kcal_provided
    
    if remaining_kcal < 0:
        st.error(f"❌ 濕糧提供的熱量 ({wet_kcal_provided:.0f} kcal) 已超過總需求 ({der:.0f} kcal)，無法搭配乾糧。請減少濕糧。")
        st.stop()
    elif remaining_kcal == 0:
        st.warning("⚠️ 濕糧提供的熱量剛好等於總需求，不需要額外餵食乾糧。")
        dry1_daily = 0
        dry2_daily = 0
    else:
        st.markdown("**設定兩種乾糧的重量比例**")
        st.caption("請指定乾糧 A 佔乾糧總重量的百分比，乾糧 B 將佔剩餘比例。")
        weight_pct = st.slider(f"{selected_dry1_brand} - {selected_dry1_flavor} 佔乾糧總重量百分比 (%)", 0, 100, 50, step=1)
        alpha = weight_pct / 100  # 乾糧A的重量佔比
        
        # 計算加權平均熱量密度 (kcal/100g)
        weighted_avg_kcal = alpha * dry1_kcal + (1 - alpha) * dry2_kcal
        if weighted_avg_kcal <= 0:
            st.error("計算錯誤：加權平均熱量無效")
            st.stop()
        
        # 總乾糧重量 (克)
        total_dry_grams = (remaining_kcal * 100) / weighted_avg_kcal
        
        dry1_daily = alpha * total_dry_grams
        dry2_daily = (1 - alpha) * total_dry_grams
        
        # 驗算提供的熱量（因浮點數可能有小誤差）
        check_kcal = (dry1_daily * dry1_kcal / 100) + (dry2_daily * dry2_kcal / 100)
        if abs(check_kcal - remaining_kcal) > 0.5:
            st.warning(f"⚠️ 計算有小誤差，建議人工確認。驗算熱量：{check_kcal:.1f} kcal，目標：{remaining_kcal:.1f} kcal")
        
        dry1_per_meal = dry1_daily / meals_per_day
        dry2_per_meal = dry2_daily / meals_per_day
        
        st.success(
            f"**濕糧 ({selected_wet_brand} - {selected_wet_flavor})**：每日 **{wet_grams:.1f} 克** (每餐 **{wet_grams/meals_per_day:.1f} 克**)\n\n"
            f"**乾糧 A ({selected_dry1_brand} - {selected_dry1_flavor})**：每日 **{dry1_daily:.1f} 克** (每餐 **{dry1_per_meal:.1f} 克**)\n\n"
            f"**乾糧 B ({selected_dry2_brand} - {selected_dry2_flavor})**：每日 **{dry2_daily:.1f} 克** (每餐 **{dry2_per_meal:.1f} 克**)\n\n"
            f"剩餘熱量：{remaining_kcal:.0f} kcal，乾糧總重：{total_dry_grams:.1f} 克，乾糧 A 重量佔比：{weight_pct}%"
        )
        results.append(("乾糧", dry1_row, dry1_daily))
        results.append(("乾糧", dry2_row, dry2_daily))
    
    results.append(("濕糧", wet_row, wet_grams))

# ==============================================================================
# 顯示營養成分
# ==============================================================================
if results:
    st.divider()
    st.header("📊 營養成分")
    for food_type, row, daily_grams in results:
        per_meal_grams = daily_grams / meals_per_day if meals_per_day > 0 else 0
        st.subheader(f"{row['品牌']} - {row['口味']} ({food_type})")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**熱量**：{row['熱量(kcal/100g)']:.0f} kcal/100g")
            st.markdown(f"**建議餵食**：每日 {daily_grams:.1f} 克")
            st.markdown(f"**每餐 ({meals_per_day} 餐)**：{per_meal_grams:.1f} 克")
        with col_b:
            st.markdown(f"**蛋白質**：{row['蛋白質(%)']:.1f} %")
            st.markdown(f"**脂肪**：{row['脂肪(%)']:.1f} %")
            if '水分(%)' in row:
                st.markdown(f"**水分**：{row['水分(%)']:.1f} %")
            if '纖維(%)' in row:
                st.markdown(f"**纖維**：{row['纖維(%)']:.1f} %")
        st.divider()

st.markdown("---")
st.caption("📌 所有計算僅供參考，請依貓咪實際狀況調整。資料來源為您自行維護的Google Sheets。")
