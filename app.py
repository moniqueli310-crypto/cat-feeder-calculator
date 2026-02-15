import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 必須在第一個 st 指令之前設定頁面
st.set_page_config(page_title="貓咪每日餵食計算器", layout="wide")

# ---------- 注入 PWA 相關標籤 ----------
st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black">
    <meta name="apple-mobile-web-app-title" content="貓咪餵食計算">
    <link rel="apple-touch-icon" href="/icons/icon-192.png">
    
    <!-- 註冊 Service Worker -->
    <script>
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', function() {
                navigator.serviceWorker.register('/service-worker.js')
                    .then(function(registration) {
                        console.log('ServiceWorker 註冊成功：', registration.scope);
                    })
                    .catch(function(err) {
                        console.log('ServiceWorker 註冊失敗：', err);
                    });
            });
        }
    </script>
""", unsafe_allow_html=True)

st.title("🐱 貓咪每日餵食計算器")
st.markdown("根據貓咪體重與生命階段計算每日熱量需求，並從Google Sheets取得飼料營養資料。")

# ---------- 連線至 Google Sheets ----------
@st.cache_data(ttl=600)
def load_food_data():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        
        # 開啟試算表（請替換為您的試算表名稱）
        spreadsheet = client.open("貓咪飼料資料庫")
        
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

# ---------- 左側輸入區 ----------
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
    
    st.divider()
    st.caption("資料來源：Google Sheets (僅所有者可編輯)")

# ---------- 主要功能選擇 ----------
mode = st.radio(
    "選擇餵食模式",
    ["只吃乾糧", "只吃濕糧", "乾糧 + 濕糧", "兩種乾糧 + 濕糧"],
    horizontal=True
)

results = []

# ---------- 情境1：只吃乾糧 ----------
if mode == "只吃乾糧":
    if dry_foods.empty:
        st.warning("目前無乾糧資料")
    else:
        dry_options = dry_foods.apply(lambda x: f"{x['品牌']} - {x['口味']}", axis=1).tolist()
        selected_dry = st.selectbox("選擇乾糧", dry_options)
        idx = dry_options.index(selected_dry)
        selected_row = dry_foods.iloc[idx]
        
        kcal_per_100g = selected_row['熱量(kcal/100g)']
        if kcal_per_100g > 0:
            daily_grams = (der * 100) / kcal_per_100g
            per_meal_grams = daily_grams / meals_per_day
            st.success(
                f"建議每日餵食 **{daily_grams:.1f} 克** 的 {selected_dry}\n\n"
                f"🍽️ 每餐約 **{per_meal_grams:.1f} 克** (每日 {meals_per_day} 餐)"
            )
            results.append(("乾糧", selected_row, daily_grams))
        else:
            st.error("所選乾糧熱量資料有誤")

# ---------- 情境2：只吃濕糧 ----------
elif mode == "只吃濕糧":
    if wet_foods.empty:
        st.warning("目前無濕糧資料")
    else:
        wet_options = wet_foods.apply(lambda x: f"{x['品牌']} - {x['口味']}", axis=1).tolist()
        selected_wet = st.selectbox("選擇濕糧", wet_options)
        idx = wet_options.index(selected_wet)
        selected_row = wet_foods.iloc[idx]
        
        kcal_per_100g = selected_row['熱量(kcal/100g)']
        if kcal_per_100g > 0:
            daily_grams = (der * 100) / kcal_per_100g
            per_meal_grams = daily_grams / meals_per_day
            st.success(
                f"建議每日餵食 **{daily_grams:.1f} 克** 的 {selected_wet}\n\n"
                f"🍽️ 每餐約 **{per_meal_grams:.1f} 克** (每日 {meals_per_day} 餐)"
            )
            results.append(("濕糧", selected_row, daily_grams))
        else:
            st.error("所選濕糧熱量資料有誤")

# ---------- 情境3：乾糧 + 濕糧 ----------
elif mode == "乾糧 + 濕糧":
    col1, col2 = st.columns(2)
    with col1:
        if dry_foods.empty:
            st.warning("無乾糧資料")
        else:
            dry_options = dry_foods.apply(lambda x: f"{x['品牌']} - {x['口味']}", axis=1).tolist()
            selected_dry = st.selectbox("選擇乾糧", dry_options, key="dry3")
            idx_dry = dry_options.index(selected_dry)
            dry_row = dry_foods.iloc[idx_dry]
    with col2:
        if wet_foods.empty:
            st.warning("無濕糧資料")
        else:
            wet_options = wet_foods.apply(lambda x: f"{x['品牌']} - {x['口味']}", axis=1).tolist()
            selected_wet = st.selectbox("選擇濕糧", wet_options, key="wet3")
            idx_wet = wet_options.index(selected_wet)
            wet_row = wet_foods.iloc[idx_wet]
    
    if dry_foods.empty or wet_foods.empty:
        st.stop()
    
    dry_pct = st.slider("乾糧佔總熱量百分比 (%)", 0, 100, 50)
    wet_pct = 100 - dry_pct
    
    dry_kcal = dry_row['熱量(kcal/100g)']
    wet_kcal = wet_row['熱量(kcal/100g)']
    
    if dry_kcal <= 0 or wet_kcal <= 0:
        st.error("部分糧食熱量資料有誤，無法計算")
    else:
        dry_daily = (der * dry_pct / 100 * 100) / dry_kcal
        wet_daily = (der * wet_pct / 100 * 100) / wet_kcal
        dry_per_meal = dry_daily / meals_per_day
        wet_per_meal = wet_daily / meals_per_day
        
        st.success(
            f"乾糧 ({selected_dry})：每日 **{dry_daily:.1f} 克**  (每餐 **{dry_per_meal:.1f} 克**)\n\n"
            f"濕糧 ({selected_wet})：每日 **{wet_daily:.1f} 克**  (每餐 **{wet_per_meal:.1f} 克**)\n\n"
            f"🍽️ 依每日 {meals_per_day} 餐計算"
        )
        results.append(("乾糧", dry_row, dry_daily))
        results.append(("濕糧", wet_row, wet_daily))

# ---------- 情境4：兩種乾糧 + 濕糧 ----------
elif mode == "兩種乾糧 + 濕糧":
    if dry_foods.empty or len(dry_foods) < 2:
        st.warning("需要至少兩種乾糧")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            dry_options = dry_foods.apply(lambda x: f"{x['品牌']} - {x['口味']}", axis=1).tolist()
            selected_dry1 = st.selectbox("選擇乾糧 A", dry_options, key="dryA")
            idx1 = dry_options.index(selected_dry1)
            dry1_row = dry_foods.iloc[idx1]
        with col2:
            remaining_dry = [opt for opt in dry_options if opt != selected_dry1]
            selected_dry2 = st.selectbox("選擇乾糧 B", remaining_dry, key="dryB")
            idx2 = dry_options.index(selected_dry2)
            dry2_row = dry_foods.iloc[idx2]
        with col3:
            if wet_foods.empty:
                st.warning("無濕糧資料")
            else:
                wet_options = wet_foods.apply(lambda x: f"{x['品牌']} - {x['口味']}", axis=1).tolist()
                selected_wet = st.selectbox("選擇濕糧", wet_options, key="wet4")
                idx_wet = wet_options.index(selected_wet)
                wet_row = wet_foods.iloc[idx_wet]
    
    if wet_foods.empty:
        st.stop()
    
    st.markdown("設定三種糧食的熱量佔比 (總和需為100%)")
    col_pct1, col_pct2, col_pct3 = st.columns(3)
    with col_pct1:
        pct1 = st.number_input(f"{selected_dry1} %", min_value=0, max_value=100, value=40, step=1)
    with col_pct2:
        pct2 = st.number_input(f"{selected_dry2} %", min_value=0, max_value=100, value=30, step=1)
    with col_pct3:
        pct3 = st.number_input(f"{selected_wet} %", min_value=0, max_value=100, value=30, step=1)
    
    total_pct = pct1 + pct2 + pct3
    if total_pct != 100:
        st.error(f"總和必須為100%，目前 {total_pct}%")
    else:
        kcal1 = dry1_row['熱量(kcal/100g)']
        kcal2 = dry2_row['熱量(kcal/100g)']
        kcal3 = wet_row['熱量(kcal/100g)']
        
        if any(k <= 0 for k in [kcal1, kcal2, kcal3]):
            st.error("部分糧食熱量資料有誤")
        else:
            daily1 = (der * pct1 / 100 * 100) / kcal1
            daily2 = (der * pct2 / 100 * 100) / kcal2
            daily3 = (der * pct3 / 100 * 100) / kcal3
            per_meal1 = daily1 / meals_per_day
            per_meal2 = daily2 / meals_per_day
            per_meal3 = daily3 / meals_per_day
            
            st.success(
                f"{selected_dry1}：每日 **{daily1:.1f} 克** (每餐 **{per_meal1:.1f} 克**)\n\n"
                f"{selected_dry2}：每日 **{daily2:.1f} 克** (每餐 **{per_meal2:.1f} 克**)\n\n"
                f"{selected_wet}：每日 **{daily3:.1f} 克** (每餐 **{per_meal3:.1f} 克**)\n\n"
                f"🍽️ 依每日 {meals_per_day} 餐計算"
            )
            results.append(("乾糧", dry1_row, daily1))
            results.append(("乾糧", dry2_row, daily2))
            results.append(("濕糧", wet_row, daily3))

# ---------- 顯示營養成分 ----------
if results:
    st.divider()
    st.header("📊 營養成分")
    for food_type, row, daily_grams in results:
        per_meal_grams = daily_grams / meals_per_day
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
