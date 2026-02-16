import streamlit as st
import pandas as pd

st.set_page_config(page_title="資料管理", layout="wide")
st.title("🛠️ 貓糧資料庫管理")
st.info("在此頁面新增、修改或刪除貓糧資料。完成後下載 CSV，並上傳回 GitHub 覆蓋原檔即可更新 App。")

# ---------- 讀取原始資料 ----------
# 使用 session_state 避免每次操作都重新讀取檔案，導致編輯內容重置
if 'dry_df' not in st.session_state:
    try:
        st.session_state['dry_df'] = pd.read_csv("dry_food.csv")
    except:
        st.session_state['dry_df'] = pd.DataFrame(columns=["品牌", "口味", "熱量(kcal/100g)", "蛋白質(%)", "脂肪(%)", "水分(%)", "纖維(%)", "灰質(%)", "磷(%)", "鈣(%)", "碳水化合物(%)"])

if 'wet_df' not in st.session_state:
    try:
        st.session_state['wet_df'] = pd.read_csv("wet_food.csv")
    except:
        st.session_state['wet_df'] = pd.DataFrame(columns=["品牌", "口味", "熱量(kcal/100g)", "蛋白質(%)", "脂肪(%)", "水分(%)", "纖維(%)", "灰質(%)", "磷(%)", "鈣(%)", "碳水化合物(%)"])

# ---------- 頁面佈局 ----------
tab1, tab2 = st.tabs(["乾燥飼料 (Dry Food)", "濕食罐頭 (Wet Food)"])

# === 乾糧編輯區 ===
with tab1:
    st.subheader("編輯乾糧清單")
    st.caption("👇 直接點擊表格內容修改，或點擊表格下方的 `+` 新增一列，選取該行按 `Del` 刪除。")
    
    # data_editor 是 Streamlit 超強的表格編輯器
    edited_dry = st.data_editor(
        st.session_state['dry_df'],
        num_rows="dynamic",  # 允許新增/刪除列
        use_container_width=True,
        key="editor_dry",
        height=500
    )
    
    # 準備下載按鈕
    csv_dry = edited_dry.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 下載更新後的 dry_food.csv",
        data=csv_dry,
        file_name='dry_food.csv',
        mime='text/csv',
        type="primary",
        help="點擊下載後，請將此檔案上傳至 GitHub 覆蓋原檔"
    )

# === 濕糧編輯區 ===
with tab2:
    st.subheader("編輯濕糧清單")
    st.caption("👇 直接點擊表格內容修改，或點擊表格下方的 `+` 新增一列，選取該行按 `Del` 刪除。")
    
    edited_wet = st.data_editor(
        st.session_state['wet_df'],
        num_rows="dynamic",
        use_container_width=True,
        key="editor_wet",
        height=500
    )
    
    # 準備下載按鈕
    csv_wet = edited_wet.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 下載更新後的 wet_food.csv",
        data=csv_wet,
        file_name='wet_food.csv',
        mime='text/csv',
        type="primary",
        help="點擊下載後，請將此檔案上傳至 GitHub 覆蓋原檔"
    )

st.divider()
st.markdown("""
### 🔄 如何讓 App 更新資料？
1. 在上面的表格中完成編輯。
2. 點擊紅色的 **「下載更新後的 .csv」** 按鈕。
3. 前往你的 GitHub 儲存庫 (Repository)。
4. 點擊 **Add file** -> **Upload files**。
5. 將下載的 `dry_food.csv` 或 `wet_food.csv` 拖進去。
6. 點擊 **Commit changes**。
7. 等待約 1~2 分鐘，重新整理你的 App，新資料就會出現了！
""")
