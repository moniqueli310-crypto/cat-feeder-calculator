import streamlit as st
import pandas as pd
import plotly.graph_objects as go # 如果沒有安裝 plotly，可以用 st.bar_chart 代替

st.set_page_config(page_title="詳細營養分析", layout="wide")

st.title("📊 每日營養攝取分析")

# ---------- 1. 檢查是否有資料傳過來 ----------
if 'selected_foods_data' not in st.session_state or not st.session_state['selected_foods_data']:
    st.warning("⚠️ 尚未選擇飼料，請先回首頁計算。")
    if st.button("🏠 返回計算器"):
        st.switch_page("Home.py") # 確保你的主程式檔名正確
    st.stop()

# 取得資料
results = st.session_state['selected_foods_data']
cat_weight = st.session_state.get('cat_weight', 4.0)

# ---------- 2. 計算總營養攝取量 ----------
# 定義我們要分析的營養欄位
nutrients = ['蛋白質(%)', '脂肪(%)', '纖維(%)', '灰質(%)', '磷(%)', '鈣(%)', '碳水化合物(%)']
total_nutrients_grams = {n: 0.0 for n in nutrients}
total_grams = 0
total_kcal = 0

st.subheader("已選飼料組合")

# 顯示飼料清單並累加數值
display_list = []
for food_type, row, grams in results:
    display_list.append({
        "類型": food_type,
        "品牌": row['品牌'],
        "口味": row['口味'],
        "餵食量 (g)": f"{grams:.1f}"
    })
    
    total_grams += grams
    # 計算該項食物提供的總熱量
    if '熱量(kcal/100g)' in row:
        total_kcal += (row['熱量(kcal/100g)'] * grams) / 100

    # 累加各項營養素的絕對克數 (例如：吃了100g飼料，蛋白質40%，就是攝取了40g蛋白質)
    for n in nutrients:
        if n in row:
            # 處理可能出現的非數值資料 (Pandas read 之後有時會變成字串)
            try:
                val = float(row[n])
                total_nutrients_grams[n] += (val * grams) / 100
            except:
                pass # 忽略無法轉成數字的欄位

st.table(pd.DataFrame(display_list))

# ---------- 3. 顯示分析結果 ----------

# 計算「乾物重 (Dry Matter Basis)」或「代謝能佔比 (ME%)」會更專業，
# 但這裡先做最直觀的「每日攝取總重百分比」分析

st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("每日總攝取重量", f"{total_grams:.1f} g")
with col2:
    st.metric("每日總熱量", f"{total_kcal:.0f} kcal")
with col3:
    st.metric("貓咪體重", f"{cat_weight} kg")

st.subheader("營養成分佔比 (As Fed / 餵食狀態)")

# 準備圖表資料
labels = [n.replace('(%)', '') for n in total_nutrients_grams.keys()]
values = [total_nutrients_grams[n] for n in total_nutrients_grams.keys()]
# 計算水分 (總重 - 所有固體營養素) *粗略估算
water_content = total_grams - sum(values)
if water_content > 0:
    labels.append("水分估算")
    values.append(water_content)

# 使用 Plotly 畫圓餅圖 (如果不熟悉 Plotly，可以用 st.dataframe 直接顯示數值)
fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.3)])
fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
st.plotly_chart(fig, use_container_width=True)

# 顯示詳細數值表
st.caption("各營養素預估攝取克數：")
df_analysis = pd.DataFrame([total_nutrients_grams]).T
df_analysis.columns = ['攝取克數 (g)']
df_analysis['佔總重比例 (%)'] = (df_analysis['攝取克數 (g)'] / total_grams * 100).round(2)
st.dataframe(df_analysis)

# ---------- 4. 額外功能：磷含量警示 (選做) ----------
phos_g = total_nutrients_grams.get('磷(%)', 0)
if phos_g > 0 and total_kcal > 0:
    # 腎貓通常看 mg/100kcal
    phos_mg_per_100kcal = (phos_g * 1000) / (total_kcal / 100)
    st.info(f"💡 磷含量分析：約 **{phos_mg_per_100kcal:.0f} mg / 100kcal**")
    if phos_mg_per_100kcal > 250:
        st.caption("註：一般成貓標準。若為腎臟病貓，建議諮詢獸醫是否需控制在 250mg/100kcal 以下。")

# 返回按鈕
st.markdown("---")
if st.button("⬅️ 返回修改餵食計畫"):
    st.switch_page("Home.py")
