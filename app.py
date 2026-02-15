import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 頁面設定（必須在第一個 st 指令之前）
st.set_page_config(page_title="貓咪每日餵食計算器", layout="wide")

# ---------- 注入 PWA 支援 ----------
st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black">
    <meta name="apple-mobile-web-app-title" content="貓咪餵食計算">
    <link rel="apple-touch-icon" href="/icons/icon-192.png">
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

# ---------- 情境2：只吃濕糧（手動輸入濕糧克數）----------
elif mode == "只吃濕糧":
    if wet_foods.empty:
        st.warning("目前無濕糧資料")
    else:
        wet_options = wet_foods.apply(lambda x: f"{x['品牌']} - {x['口味']}", axis=1).tolist()
        selected_wet = st.selectbox("選擇濕糧", wet_options)
        idx = wet_options.index(selected_wet)
        selected_row = wet_foods.iloc[idx]
        kcal_per_100g = selected_row['熱量(kcal/100g)']
        
        if kcal_per_100g <= 0:
            st.error("所選濕糧熱量資料有誤")
            st.stop()
        
        wet_grams = st.number_input(
            "請輸入每日餵食濕糧的克數",
            min_value=0.0,
            value=100.0,
            step=10.0,
            help="根據您的貓咪習慣或包裝建議輸入"
        )
        
        wet_kcal_provided = (wet_grams * kcal_per_100g) / 100
        diff = wet_kcal_provided - der
        
        if wet_kcal_provided > der:
            st.warning(f"⚠️ 濕糧提供的熱量 ({wet_kcal_provided:.0f} kcal) 已超過每日需求 ({der:.0f} kcal)，超出 {diff:.0f} kcal。請考慮減少濕糧。")
        elif abs(diff) < 1:
            st.success(f"✅ 濕糧提供的熱量 ({wet_kcal_provided:.0f} kcal) 剛好符合每日需求！")
        else:
            st.info(f"ℹ️ 濕糧提供的熱量 ({wet_kcal_provided:.0f} kcal) 少於每日需求，不足 {abs(diff):.0f} kcal。如需補足，請搭配乾糧。")
        
        per_meal_grams = wet_grams / meals_per_day
        st.info(
            f"**每日濕糧克數**：{wet_grams:.1f} 克\n\n"
            f"**每餐 ({meals_per_day} 餐)**：{per_meal_grams:.1f} 克"
        )
        
        results.append(("濕糧", selected_row, wet_grams))

# ---------- 情境3：乾糧 + 濕糧（手動輸入濕糧克數）----------
elif mode == "乾糧 + 濕糧":
    if dry_foods.empty or wet_foods.empty:
        st.warning("需要同時有乾糧和濕糧資料")
        st.stop()
    
    col1, col2 = st.columns(2)
    with col1:
        dry_options = dry_foods.apply(lambda x: f"{x['品牌']} - {x['口味']}", axis=1).tolist()
        selected_dry = st.selectbox("選擇乾糧", dry_options, key="dry3")
        idx_dry = dry_options.index(selected_dry)
        dry_row = dry_foods.iloc[idx_dry]
        dry_kcal = dry_row['熱量(kcal/100g)']
        if dry_kcal <= 0:
            st.error("所選乾糧熱量資料有誤")
            st.stop()
    
    with col2:
        wet_options = wet_foods.apply(lambda x: f"{x['品牌']} - {x['口味']}", axis=1).tolist()
        selected_wet = st.selectbox("選擇濕糧", wet_options, key="wet3")
        idx_wet = wet_options.index(selected_wet)
        wet_row = wet_foods.iloc[idx_wet]
        wet_kcal = wet_row['熱量(kcal/100g)']
        if wet_kcal <= 0:
            st.error("所選濕糧熱量資料有誤")
            st.stop()
    
    wet_grams = st.number_input(
        "請輸入每日餵食濕糧的克數",
        min_value=0.0,
        value=100.0,
        step=10.0,
        key="wet_grams_input"
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
            f"**濕糧 ({selected_wet})**：每日 **{wet_grams:.1f} 克** (每餐 **{wet_grams/meals_per_day:.1f} 克**)\n\n"
            f"**乾糧 ({selected_dry})**：每日 **{dry_daily:.1f} 克** (每餐 **{dry_per_meal:.1f} 克**)\n\n"
            f"剩餘熱量：{remaining_kcal:.0f} kcal"
        )
        results.append(("乾糧", dry_row, dry_daily))
    
    results.append(("濕糧", wet_row, wet_grams))

# ---------- 情境4：兩種乾糧 + 濕糧（手動輸入濕糧克數，兩種乾糧按重量比例分配）----------
elif mode == "兩種乾糧 + 濕糧":
    if dry_foods.empty or len(dry_foods) < 2 or wet_foods.empty:
        st.warning("需要至少兩種乾糧和一種濕糧")
        st.stop()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        dry_options = dry_foods.apply(lambda x: f"{x['品牌']} - {x['口味']}", axis=1).tolist()
        selected_dry1 = st.selectbox("選擇乾糧 A", dry_options, key="dryA")
        idx1 = dry_options.index(selected_dry1)
        dry1_row = dry_foods.iloc[idx1]
        dry1_kcal = dry1_row['熱量(kcal/100g)']
        if dry1_kcal <= 0:
            st.error("乾糧 A 熱量資料有誤")
            st.stop()
    
    with col2:
        remaining_dry = [opt for opt in dry_options if opt != selected_dry1]
        if not remaining_dry:
            st.error("沒有其他乾糧可選")
            st.stop()
        selected_dry2 = st.selectbox("選擇乾糧 B", remaining_dry, key="dryB")
        idx2 = dry_options.index(selected_dry2)
        dry2_row = dry_foods.iloc[idx2]
        dry2_kcal = dry2_row['熱量(kcal/100g)']
        if dry2_kcal <= 0:
            st.error("乾糧 B 熱量資料有誤")
            st.stop()
    
    with col3:
        wet_options = wet_foods.apply(lambda x: f"{x['品牌']} - {x['口味']}", axis=1).tolist()
        selected_wet = st.selectbox("選擇濕糧", wet_options, key="wet4")
        idx_wet = wet_options.index(selected_wet)
        wet_row = wet_foods.iloc[idx_wet]
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
        key="wet_grams_input2"
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
        weight_pct = st.slider(f"{selected_dry1} 佔乾糧總重量百分比 (%)", 0, 100, 50, step=1)
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
            f"**濕糧 ({selected_wet})**：每日 **{wet_grams:.1f} 克** (每餐 **{wet_grams/meals_per_day:.1f} 克**)\n\n"
            f"**乾糧 A ({selected_dry1})**：每日 **{dry1_daily:.1f} 克** (每餐 **{dry1_per_meal:.1f} 克**)\n\n"
            f"**乾糧 B ({selected_dry2})**：每日 **{dry2_daily:.1f} 克** (每餐 **{dry2_per_meal:.1f} 克**)\n\n"
            f"剩餘熱量：{remaining_kcal:.0f} kcal，乾糧總重：{total_dry_grams:.1f} 克，"
            f"乾糧 A 重量佔比：{weight_pct}%"
        )
        results.append(("乾糧", dry1_row, dry1_daily))
        results.append(("乾糧", dry2_row, dry2_daily))
    
    results.append(("濕糧", wet_row, wet_grams))
    
# ---------- 顯示營養成分 ----------
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
