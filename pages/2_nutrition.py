import streamlit as st
st.write("營養成分頁面載入成功")

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="營養成分分析", layout="wide")
st.title("📊 貓糧營養成分詳細分析")

# 檢查是否有計算結果
if 'selected_foods' not in st.session_state or not st.session_state.selected_foods:
    st.warning("⚠️ 尚未進行任何餵食計算。請先前往主頁面完成計算。")
    if st.button("🏠 前往主頁面"):
        st.switch_page("app.py")
    st.stop()

selected_foods = st.session_state.selected_foods

# 定義營養成分欄位（依使用者需求）
nutrient_cols = {
    '蛋白質(%)': '蛋白質',
    '脂肪(%)': '脂肪',
    '碳水化合物(%)': '碳水化合物',
    '水分(%)': '水分',
    '磷(%)': '磷',
    '纖維(%)': '纖維',
    '灰質(%)': '灰質',
    '鈣(%)': '鈣',
    '牛磺酸(%)': '牛磺酸'
}

# 輔助函數：安全取得數值
def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return np.nan

# 輔助函數：計算乾物比
def dry_matter_basis(row, moisture_col='水分(%)'):
    moisture = safe_float(row.get(moisture_col, np.nan))
    if pd.isna(moisture) or moisture == 0:
        return {}  # 無法計算
    factor = 100 / (100 - moisture)
    dry_values = {}
    for col, label in nutrient_cols.items():
        if col == moisture_col:
            continue
        val = safe_float(row.get(col, np.nan))
        if not pd.isna(val):
            dry_values[col] = val * factor
    return dry_values

# 輔助函數：計算 ME 熱量比
def me_ratios(row):
    # 優先使用直接提供的碳水化合物，否則用差值計算
    protein = safe_float(row.get('蛋白質(%)', np.nan))
    fat = safe_float(row.get('脂肪(%)', np.nan))
    carb = safe_float(row.get('碳水化合物(%)', np.nan))
    moisture = safe_float(row.get('水分(%)', np.nan))
    ash = safe_float(row.get('灰質(%)', np.nan))
    fiber = safe_float(row.get('纖維(%)', np.nan))
    
    # 若碳水化合物缺失，嘗試計算
    if pd.isna(carb):
        known_sum = 0
        count = 0
        for v in [protein, fat, moisture, ash, fiber]:
            if not pd.isna(v):
                known_sum += v
                count += 1
        if count >= 3:  # 至少有幾個已知
            carb = 100 - known_sum
        else:
            carb = np.nan
    
    # 能量係數 (kcal/g)
    energy_factors = {'protein': 4, 'fat': 9, 'carb': 4}
    
    if pd.isna(protein) or pd.isna(fat) or pd.isna(carb):
        return {}
    
    me_protein = protein * energy_factors['protein']
    me_fat = fat * energy_factors['fat']
    me_carb = carb * energy_factors['carb']
    total_me = me_protein + me_fat + me_carb
    
    if total_me == 0:
        return {}
    
    return {
        '蛋白質': me_protein / total_me * 100,
        '脂肪': me_fat / total_me * 100,
        '碳水化合物': me_carb / total_me * 100
    }

# 使用頁籤顯示每種食物
if len(selected_foods) == 1:
    # 只有一種食物，直接顯示
    food_type, row, daily_grams = selected_foods[0]
    display_foods = [selected_foods[0]]
else:
    # 多種食物，用頁籤
    tab_labels = [f"{row['品牌']} - {row['口味']}" for _, row, _ in selected_foods]
    tabs = st.tabs(tab_labels)
    display_foods = list(zip(tabs, selected_foods))

# 逐一顯示
for idx, item in enumerate(selected_foods):
    food_type, row, daily_grams = item
    # 如果有多個頁籤，需先取得對應的 tab
    if len(selected_foods) > 1:
        current_tab = tabs[idx]
        with current_tab:
            pass  # 以下內容會自動在該 tab 內
    else:
        current_tab = st.container()
    
    with (current_tab if len(selected_foods) > 1 else st.container()):
        st.subheader(f"{row['品牌']} - {row['口味']} ({food_type})")
        
        # 基本餵食資訊
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("每日建議克數", f"{daily_grams:.1f} g")
        with col2:
            meals = st.session_state.get('meals_per_day', 2)  # 從 session_state 取得餐數
            st.metric("每餐克數", f"{daily_grams/meals:.1f} g")
        with col3:
            st.metric("熱量密度", f"{row.get('熱量(kcal/100g)', 0):.0f} kcal/100g")
        
        st.divider()
        
        # ----- 濕基營養成分表 -----
        st.markdown("#### 🌊 濕基營養成分 (as fed)")
        wet_data = {}
        for col, label in nutrient_cols.items():
            val = row.get(col, None)
            if pd.notna(val) and val != '':
                wet_data[label] = f"{val:.1f}%"
            else:
                wet_data[label] = "—"
        # 額外顯示鈣磷比（如果有）
        ca = safe_float(row.get('鈣(%)', np.nan))
        p = safe_float(row.get('磷(%)', np.nan))
        if not pd.isna(ca) and not pd.isna(p) and p > 0:
            ca_p_ratio = ca / p
            wet_data["鈣磷比"] = f"{ca_p_ratio:.2f}"
        else:
            wet_data["鈣磷比"] = "—"
        
        # 以兩欄顯示營養成分
        cols = st.columns(2)
        items = list(wet_data.items())
        mid = len(items) // 2
        with cols[0]:
            for k, v in items[:mid]:
                st.markdown(f"**{k}**：{v}")
        with cols[1]:
            for k, v in items[mid:]:
                st.markdown(f"**{k}**：{v}")
        
        # ----- 乾物比 -----
        st.markdown("#### 🏜️ 乾物比 (Dry Matter Basis)")
        dry_values = dry_matter_basis(row)
        if dry_values:
            dry_cols = st.columns(2)
            dry_items = [(nutrient_cols.get(k, k), f"{v:.1f}%") for k, v in dry_values.items()]
            mid_dry = len(dry_items) // 2
            with dry_cols[0]:
                for label, val in dry_items[:mid_dry]:
                    st.markdown(f"**{label}**：{val}")
            with dry_cols[1]:
                for label, val in dry_items[mid_dry:]:
                    st.markdown(f"**{label}**：{val}")
        else:
            st.info("無法計算乾物比（缺少水分或相關數據）")
        
        # ----- ME 熱量比 -----
        st.markdown("#### 🔥 ME 熱量比 (Metabolizable Energy)")
        me_ratio = me_ratios(row)
        if me_ratio:
            me_cols = st.columns(3)
            with me_cols[0]:
                st.metric("蛋白質", f"{me_ratio['蛋白質']:.1f}%")
            with me_cols[1]:
                st.metric("脂肪", f"{me_ratio['脂肪']:.1f}%")
            with me_cols[2]:
                st.metric("碳水化合物", f"{me_ratio['碳水化合物']:.1f}%")
        else:
            st.info("無法計算 ME 熱量比（缺少必要數據）")
        
        st.divider()
