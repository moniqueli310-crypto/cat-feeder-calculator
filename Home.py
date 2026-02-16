import streamlit as st
import pandas as pd

# ==========================================
# 👇 這裡設定你的 Icon
# page_icon 可以是 emoji "🐱" 也可以是圖檔路徑 "icon.png"
# ==========================================
st.set_page_config(
    page_title="貓咪全方位助手", 
    layout="wide", 
    page_icon="https://raw.githubusercontent.com/moniqueli310-crypto/cat-feeder-calculator/main/icon.png"
)

# ==========================================
# 👇 讀取 GitHub 上的 CSV (Cloud 模式)
# ==========================================
@st.cache_data(ttl=600)
def load_data():
    dry = pd.DataFrame()
    wet = pd.DataFrame()
    try:
        # 在 Streamlit Cloud 上，直接讀取同目錄下的檔案即可
        dry = pd.read_csv("dry_food.csv")
        wet = pd.read_csv("wet_food.csv")
        
        # 資料清理
        for df in [dry, wet]:
            if not df.empty:
                df.columns = df.columns.str.strip()
                cols = ['熱量(kcal/100g)', '蛋白質(%)', '脂肪(%)', '水分(%)', '纖維(%)', 
                        '灰質(%)', '磷(%)', '鈣(%)', '碳水化合物(%)']
                for c in cols:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    except Exception as e:
        st.error(f"讀取失敗: {e}")
    return dry, wet

# ... (後面的程式碼完全不用改，照舊即可) ...
# 初始化 Session State
if 'dry_foods' not in st.session_state:
    d, w = load_data()
    st.session_state['dry_foods'] = d
    st.session_state['wet_foods'] = w

dry_foods = st.session_state['dry_foods']
wet_foods = st.session_state['wet_foods']

# ==========================================
# 2. 側邊欄導航 (取代多頁面)
# ==========================================
with st.sidebar:
    st.title("🐱 貓咪全方位助手")
    page = st.radio("選擇功能", ["🧮 餵食計算器", "📚 營養資料庫", "🛠️ 資料管理"], label_visibility="collapsed")
    st.divider()

# ==========================================
# 3. 功能 A: 餵食計算器
# ==========================================
if page == "🧮 餵食計算器":
    st.title("🧮 貓咪每日餵食計算器")
    
    if dry_foods.empty and wet_foods.empty:
        st.error("讀取不到資料，請先至「資料管理」或檢查 CSV 檔案。")
        st.stop()

    with st.expander("🐈 設定貓咪資料", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            weight = st.number_input("體重 (kg)", 0.5, 20.0, 4.0, 0.1)
            meals = st.number_input("每日餐數", 1, 10, 2)
        with col2:
            factors = {
                "幼貓 (<4個月)": 2.5, "幼貓 (4-12個月)": 2.0, "成年貓 (絕育)": 1.2,
                "成年貓 (未絕育)": 1.4, "活躍/戶外貓": 1.6, "老年貓": 1.1, "減肥中": 0.8
            }
            stage = st.selectbox("生命階段", list(factors.keys()))
            factor = factors[stage]
            
        rer = 70 * (weight ** 0.75)
        der = rer * factor
        st.metric("每日熱量需求 (DER)", f"{der:.0f} kcal")

    mode = st.radio("餵食模式", ["只吃乾糧", "只吃濕糧", "乾糧 + 濕糧", "兩種乾糧 + 濕糧"], horizontal=True)
    st.divider()

    # --- 輔助函式 ---
    def get_opts(df): return sorted(df['品牌'].unique()) if not df.empty else []
    def get_flavs(df, b): return df[df['品牌']==b]['口味'].tolist() if not df.empty else []
    def get_row(df, b, f): 
        res = df[(df['品牌']==b) & (df['口味']==f)]
        return res.iloc[0] if not res.empty else None

    # --- 計算邏輯 (簡化顯示) ---
    if mode == "只吃乾糧":
        b = st.selectbox("品牌", get_opts(dry_foods))
        f = st.selectbox("口味", get_flavs(dry_foods, b))
        row = get_row(dry_foods, b, f)
        if row is not None:
            kcal = row['熱量(kcal/100g)']
            daily = (der*100)/kcal if kcal>0 else 0
            st.success(f"建議每日：**{daily:.1f}g** (每餐 {daily/meals:.1f}g)")

    elif mode == "只吃濕糧":
        b = st.selectbox("品牌", get_opts(wet_foods))
        f = st.selectbox("口味", get_flavs(wet_foods, b))
        row = get_row(wet_foods, b, f)
        if row is not None:
            kcal = row['熱量(kcal/100g)']
            daily = (der*100)/kcal if kcal>0 else 0
            st.success(f"建議每日：**{daily:.1f}g** (每餐 {daily/meals:.1f}g)")

    elif mode == "乾糧 + 濕糧":
        c1, c2 = st.columns(2)
        with c1:
            db = st.selectbox("乾糧品牌", get_opts(dry_foods))
            df_ = st.selectbox("乾糧口味", get_flavs(dry_foods, db))
        with c2:
            wb = st.selectbox("濕糧品牌", get_opts(wet_foods))
            wf = st.selectbox("濕糧口味", get_flavs(wet_foods, wb))
        
        d_row = get_row(dry_foods, db, df_)
        w_row = get_row(wet_foods, wb, wf)
        
        if d_row is not None and w_row is not None:
            w_g = st.number_input("濕糧重量 (g)", 0.0, 500.0, 100.0, 10.0)
            w_k = w_row['熱量(kcal/100g)']
            provided = (w_g * w_k) / 100
            remain = der - provided
            if remain < 0: st.error("濕糧熱量已超標！")
            else:
                d_k = d_row['熱量(kcal/100g)']
                d_g = (remain*100)/d_k if d_k>0 else 0
                st.success(f"濕糧：**{w_g:.1f}g** + 乾糧：**{d_g:.1f}g**")

    elif mode == "兩種乾糧 + 濕糧":
        c1, c2, c3 = st.columns(3)
        with c1: 
            d1b = st.selectbox("乾糧A", get_opts(dry_foods))
            d1f = st.selectbox("口味", get_flavs(dry_foods, d1b), key="d1")
        with c2:
            d2b = st.selectbox("乾糧B", get_opts(dry_foods))
            d2f = st.selectbox("口味", get_flavs(dry_foods, d2b), key="d2")
        with c3:
            wb = st.selectbox("濕糧", get_opts(wet_foods))
            wf = st.selectbox("口味", get_flavs(wet_foods, wb), key="w")
            
        d1r = get_row(dry_foods, d1b, d1f)
        d2r = get_row(dry_foods, d2b, d2f)
        wr = get_row(wet_foods, wb, wf)
        
        if all([d1r is not None, d2r is not None, wr is not None]):
            w_g = st.number_input("濕糧重量 (g)", 80.0)
            ratio = st.slider(f"{d1b} 比例 (%)", 0, 100, 50)
            provided = (w_g * wr['熱量(kcal/100g)']) / 100
            remain = der - provided
            if remain < 0: st.error("熱量超標")
            else:
                avg_k = (ratio/100)*d1r['熱量(kcal/100g)'] + (1-ratio/100)*d2r['熱量(kcal/100g)']
                total_d = (remain*100)/avg_k if avg_k>0 else 0
                st.success(f"濕糧：**{w_g:.1f}g**\n乾糧A：**{total_d*(ratio/100):.1f}g**\n乾糧B：**{total_d*(1-ratio/100):.1f}g**")

# ==========================================
# 4. 功能 B: 營養資料庫
# ==========================================
elif page == "📚 營養資料庫":
    st.title("📚 貓糧營養資料庫")
    
    type_ = st.radio("種類", ["乾糧", "濕糧"], horizontal=True)
    df = dry_foods if type_ == "乾糧" else wet_foods
    
    if df.empty: st.stop()
    
    c1, c2 = st.columns(2)
    with c1: b = st.selectbox("品牌", sorted(df['品牌'].unique()))
    with c2: f = st.selectbox("口味", sorted(df[df['品牌']==b]['口味'].unique()))
    
    row = df[(df['品牌']==b) & (df['口味']==f)].iloc[0]
    
    # 計算邏輯
    mst = row.get('水分(%)', 0)
    prot = row.get('蛋白質(%)', 0)
    fat = row.get('脂肪(%)', 0)
    carb = row.get('碳水化合物(%)', 0)
    phos = row.get('磷(%)', 0)
    cal = row.get('鈣(%)', 0)
    kcal = row.get('熱量(kcal/100g)', 0)
    
    dm = 100 - mst
    if dm <= 0: dm = 1
    
    kp, kf, kc = prot*3.5, fat*8.5, carb*3.5
    tot_k = kp + kf + kc
    mep = (kp/tot_k*100) if tot_k>0 else 0
    mef = (kf/tot_k*100) if tot_k>0 else 0
    mec = (kc/tot_k*100) if tot_k>0 else 0
    
    st.divider()
    st.subheader(f"{b} - {f}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption("💧 基本 (As Fed)")
        st.dataframe(pd.DataFrame({"%": [prot, fat, carb, mst, phos, cal]}, 
                     index=["蛋白", "脂肪", "碳水", "水分", "磷", "鈣"]).T, hide_index=True)
    with col2:
        st.caption("🍂 乾物比 (DM)")
        st.dataframe(pd.DataFrame({"%": [prot/dm*100, fat/dm*100, carb/dm*100, phos/dm*100]}, 
                     index=["蛋白", "脂肪", "碳水", "磷"]).T.round(1), hide_index=True)
    with col3:
        st.caption("🔥 熱量比 (ME)")
        st.markdown(f"蛋白 **{mep:.1f}%** | 脂肪 **{mef:.1f}%** | 碳水 **{mec:.1f}%**")
        st.progress(int(mep))
        st.progress(int(mef))
        st.progress(int(mec))

# ==========================================
# 5. 功能 C: 資料管理
# ==========================================
elif page == "🛠️ 資料管理":
    st.title("🛠️ 資料管理")
    st.info("修改後請下載 CSV 並上傳回 GitHub。")
    
    t1, t2 = st.tabs(["乾糧", "濕糧"])
    with t1:
        ed = st.data_editor(dry_foods, num_rows="dynamic", use_container_width=True, key="ed1")
        st.download_button("📥 下載 dry_food.csv", ed.to_csv(index=False).encode('utf-8'), "dry_food.csv", "text/csv")
    with t2:
        ew = st.data_editor(wet_foods, num_rows="dynamic", use_container_width=True, key="ed2")
        st.download_button("📥 下載 wet_food.csv", ew.to_csv(index=False).encode('utf-8'), "wet_food.csv", "text/csv")
