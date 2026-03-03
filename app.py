import streamlit as st
from streamlit_autorefresh import st_autorefresh
import datetime  # 用於類型檢查
from datetime import datetime as dt_class, date, timedelta # 統一使用 dt_class
import pytz
import streamlit.components.v1 as components
import base64
import json
import os

# ==========================================
# 1. 網頁基礎設定 (必須是第一個 Streamlit 指令)
# ==========================================
st.set_page_config(page_title="BnsNEO懶人小工具", layout="wide")

# ==========================================
# 2. 核心參數與路徑
# ==========================================
DB_FILE = "bns_data.json"
ADMIN_PASSWORD = "369963"
tw_tz = pytz.timezone('Asia/Taipei')

# 自動重新整理 (每 60 秒)
st_autorefresh(interval=60000, key="datarefresh")


# ==========================================
# 3. 數據系統 (載入與存檔邏輯)
# ==========================================

def load_data():
    """從檔案載入數據，若失敗則回傳預設值"""
    default_data = {
        "expire_date": "2026-03-31",
        "boss_data": {ch: {"last_death": None, "history": None, "auto_delay_hours": 0, "history_stats": []}
                      for ch in ["1 頻", "2 頻", "3 頻"]},
        "seals": [{"name": "攻擊印章", "value": 0}],
        "panel": {"red_atk": 0, "red_crit": 0, "yellow_atk": 0, "yellow_hp": 0, "blue_atk": 0, "blue_pierce": 0,
                  "spec_atk": 0},
        "loc_notes": {},
        "schedules": {
            # ✅ 修正：仙幻島與白青也必須是按星期分類的字典
            "仙幻島": {f"星期{d}": [] for d in "一二三四五六日"},
            "白青": {f"星期{d}": [] for d in "一二三四五六日"},
            "儀式": {f"星期{d}": [] for d in "一二三四五六日"}
        }
    }

    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 自動補齊缺失的 Key，防止程式升級後出錯
                for key in default_data:
                    if key not in data:
                        data[key] = default_data[key]
                return data
        except Exception as e:
            print(f"載入出錯: {e}")
    return default_data


def save_data():
    """將目前的狀態永久儲存至 JSON"""
    try:
        # 確保日期格式正確
        expire_str = st.session_state.expire_date.strftime("%Y-%m-%d") if isinstance(st.session_state.expire_date,
                                                                                     date) else "2026-03-31"

        payload = {
            "expire_date": expire_str,
            "boss_data": st.session_state.boss_data,
            "seals": st.session_state.seals,
            "panel": st.session_state.panel,
            "loc_notes": st.session_state.loc_notes,
            "schedules": st.session_state.schedules
        }

        # 處理 datetime 轉 JSON 字串的工具
        def json_serial(obj):
            if isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=4, default=json_serial)
        st.toast("💾 數據已成功存檔")
    except Exception as e:
        st.error(f"存檔失敗: {e}")

# 別名設定
save_all_data = save_data


def record_boss_event(ch, h, m, s):
    """
    這個工具會幫你更新時間點、計算間隔並存檔
    """
    # 1. 取得該頻道的資料參考
    ch_data = st.session_state.boss_data[ch]

    # 2. 存入顯示用的時間字串 (例如 "14:05:30")
    now_time_str = f"{h:02d}:{m:02d}:{s:02d}"
    ch_data["history_times"].append(now_time_str)
    ch_data["history_times"] = ch_data["history_times"][-10:]  # 只留 10 筆

    # 3. 計算重生間隔 (如果上次有紀錄)
    current_total_sec = h * 3600 + m * 60 + s
    last_sec = ch_data.get("last_report_seconds")
    if last_sec:
        diff = current_total_sec - last_sec
        if diff > 600:  # 過濾掉 10 分鐘內的重複點擊
            ch_data["history_stats"].append(diff)
            ch_data["history_stats"] = ch_data["history_stats"][-10:]

    ch_data["last_report_seconds"] = current_total_sec

    # 4. 更新最後死亡時間點 (為了計時器運作)
    # 這裡建議統一更新 last_death
    ch_data["last_death"] = dt_class.now(tw_tz).replace(hour=h, minute=m, second=s)

    # 5. 呼叫你原本那個寫好的 save_data() 存檔
    save_data()

# ==========================================
# 4. 關鍵：初始化 Session State (F5 不消失的核心)
# ==========================================

if 'init_fix_final' not in st.session_state:
    # 讀取存檔
    raw_data = load_data()

    # A. 處理日期物件 (統一使用 dt_class 或 date)
    try:
        # 從 JSON 讀取的日期是字串，轉回 date 物件
        st.session_state.expire_date = dt_class.strptime(raw_data["expire_date"], "%Y-%m-%d").date()
    except:
        st.session_state.expire_date = date(2026, 3, 31)

    # B. 處理 BOSS 時間 (關鍵修正：新增歷史紀錄初始化)
    bd = raw_data["boss_data"]
    for ch in bd:
        # --- 原有的 last_death 轉換邏輯保持不變 ---
        if bd[ch].get("last_death") and isinstance(bd[ch]["last_death"], str):
            try:
                bd[ch]["last_death"] = dt_class.fromisoformat(bd[ch]["last_death"])
            except:
                bd[ch]["last_death"] = None

        # --- ✅ 新增：確保 history_times (顯示用) 與 history_stats (間隔用) 存在 ---
        if "history_times" not in bd[ch]:
            bd[ch]["history_times"] = []  # 用來存 "14:05:30" 這種字串

        if "history_stats" not in bd[ch]:
            bd[ch]["history_stats"] = []  # 用來存 7200 這種秒數間隔

    # C. 寫入 Session State
    st.session_state.boss_data = bd
    st.session_state.seals = raw_data["seals"]
    st.session_state.panel = raw_data["panel"]
    st.session_state.loc_notes = raw_data["loc_notes"]
    st.session_state.schedules = raw_data["schedules"]

    st.session_state.is_admin = False
    st.session_state.init_fix_final = True

# ==========================================
# 5. UI 全域變數捷徑 (放在初始化之後，絕對不會爆炸)
# ==========================================
schedules_dict = st.session_state.schedules
date_display_str = st.session_state.expire_date.strftime('%Y/%m/%d')
now_tw = dt_class.now(tw_tz)


# ==========================================
# 6. 工具函數：Header 與 圖片處理
# ==========================================

def get_image_base64(path):
    try:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        return ""
    except:
        return ""


def render_custom_header(icon_path, title_text, title_color="#90cdf4"):
    col1, col2 = st.columns([3, 2])

    with col1:
        icon_data = get_image_base64(icon_path)
        st.markdown(f'''
            <div style="display: flex; align-items: center; height: 100px;">
                <img src="data:image/png;base64,{icon_data}" 
                     style="width: clamp(40px, 6vw, 60px); height: clamp(40px, 6vw, 60px); 
                            margin-right: 15px; border: none; background: transparent; object-fit: contain;">
                <div>
                    <h1 style='margin: 0; font-size: clamp(24px, 4vw, 45px); font-weight: 800; 
                               color: {title_color}; 
                               line-height: 1; white-space: nowrap; 
                               text-shadow: 2px 2px 10px rgba(0,0,0,0.5);'>
                        {title_text}
                    </h1>
                </div>
            </div>
        ''', unsafe_allow_html=True)

    with col2:
        # 這裡恢復了 image_0bc09b.png 中的霓虹發光效果與星期顯示
        components.html(f"""
            <div id="clock-container" style="text-align: right; line-height: 1.0; padding-right: 10px;">
                <div id="date-part" style="font-family: 'Segoe UI', sans-serif; font-size: 18px; font-weight: 600; color: #94a3b8; margin-bottom: 2px;"></div>
                <div id="time-part" style="font-family: 'Courier New', Courier, monospace; font-size: 52px; font-weight: 900; color: #00ffcc; text-shadow: 0 0 20px rgba(0, 255, 204, 0.8), 0 0 10px rgba(0, 255, 204, 0.5); letter-spacing: -1px; margin-top: -5px;"></div>
            </div>
            <script>
                function updateClock() {{
                    const now = new Date();
                    // 校正台灣時間 (UTC+8)
                    const twTime = new Date(now.getTime() + (now.getTimezoneOffset() + 480) * 60000);

                    const days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
                    const y = twTime.getFullYear();
                    const m = String(twTime.getMonth() + 1).padStart(2, '0');
                    const d = String(twTime.getDate()).padStart(2, '0');
                    const dayName = days[twTime.getDay()];

                    const hh = String(twTime.getHours()).padStart(2, '0');
                    const mm = String(twTime.getMinutes()).padStart(2, '0');
                    const ss = String(twTime.getSeconds()).padStart(2, '0');

                    // 格式：2026-02-27 (FRI)
                    document.getElementById('date-part').textContent = y + '-' + m + '-' + d + ' (' + dayName + ')';
                    // 格式：20:26:09
                    document.getElementById('time-part').textContent = hh + ':' + mm + ':' + ss;
                }}
                setInterval(updateClock, 1000);
                updateClock();
            </script>
        """, height=110)

    st.markdown("""
        <style>
            hr { margin-top: -15px !important; margin-bottom: 20px !important; }
            [data-testid="stHorizontalBlock"] { margin-bottom: -20px !important; }
        </style>
    """, unsafe_allow_html=True)
    st.divider()


# --- 3. CSS 樣式 ---
st.markdown("""
    <style>
    /* # --- 動態效果：定義閃爍動畫 --- */
    @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }

    /* # --- 標題樣式：使用 clamp 讓大小隨視窗縮放 --- */
    .main-title { 
        font-size: clamp(1.5rem, 4vw, 2.5rem) !important; /* 最小 1.5rem，隨視窗 4% 縮放，最大 2.5rem */
        font-weight: 800; 
        color: white; 
        text-shadow: 2px 2px 4px black; 
        margin-bottom: 5px; 
        text-align: center;
    }
    
    .boss-title { 
        font-size: clamp(1.1rem, 2.5vw, 1.8rem) !important; 
        font-weight: 850; 
        color: white; 
        text-align: center; 
        margin-bottom: 10px; 
    }

    /* # --- 計時器顯示：確保時間數字在縮放時不會破圖 --- */
    .timer-normal { 
        font-size: clamp(1.8rem, 5vw, 2.8rem) !important; 
        color: #00ff00 !important; 
        font-weight: bold; 
        font-family: monospace; 
        text-align: center;
    }
    
    .timer-alert { 
        font-size: clamp(1.8rem, 5vw, 2.8rem) !important; 
        color: #ff4b4b !important; 
        font-weight: bold; 
        font-family: monospace; 
        animation: blink 1s infinite; 
        text-align: center;
    }

    /* # --- 側邊欄單選按鈕(Radio)：美化成卡片式大型按鈕 --- */
    [data-testid="stSidebarUserContent"] div.stRadio div[role="radiogroup"] > label {
        background-color: #1e1e26 !important;
        border: 2px solid #464855 !important;
        border-radius: 12px !important;
        padding: 12px 20px !important;
        margin-bottom: 10px !important;
        width: 100% !important;
    }
/* 1. 確保整體容器不溢出 */
    .stMainBlockContainer {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* 2. 補報區專用容器：強化響應式彈性 */
.manual-time-container {
    width: 100% !important;
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important; /* 確保在極窄視窗下也不會掉行 */
    align-items: center !important;
    justify-content: space-between !important;
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid #464855 !important;
    padding: 0.4vw 0.2vw !important; /* 隨視窗寬度縮放內距 */
    border-radius: 8px !important;
    gap: 1px !important;
}

/* 3. 讓 Selectbox (時分秒) 隨寬度自動伸縮 */
.manual-time-container [data-testid="stSelectbox"] {
    /* 使用 min-width 確保數字不會被擠不見，但允許它隨寬度伸展 */
    flex: 1 1 auto !important;
    min-width: 42px !important; 
    max-width: 75px !important;
}

/* 4. 字體大小響應式：clamp(最小, 視窗相關值, 最大) */
.manual-time-container [role="button"], 
.manual-time-container div[data-baseweb="select"] {
    font-size: clamp(12px, 1.1vw, 16px) !important;
    padding: 0 !important;
    text-align: center !important;
}

/* 5. 冒號響應式調整 */
.time-sep {
    color: #00ffcc;
    font-weight: bold;
    font-size: clamp(14px, 1.2vw, 18px);
    width: auto;
    margin: 0 1px;
    text-align: center;
}

/* 6. ✈️ 按鈕響應式：確保寬度隨比例變動 */
.manual-time-container [data-testid="stButton"] button {
    flex: 0 1 50px !important; /* 按鈕不要伸展得太誇張 */
    min-width: 35px !important;
    height: clamp(32px, 3vw, 40px) !important;
    background-color: #8d51f5 !important;
    font-size: clamp(14px, 1.2vw, 18px) !important;
    padding: 0 !important;
    margin-left: 2px !important;
}

    /* # --- 容器區塊樣式：設定深色背景與圓角邊框 --- */
    [data-testid="stVVerticalBlockBorderConfigured"] { border-radius: 15px; border: 2px solid #464855; background-color: #1e1e26; }

    /* # --- 儀式時間表專用：外層容器與每一列的樣式 --- */
    .ritual-container { background-color: #1a1c24; border: 1px solid #333; border-radius: 10px; padding: 5px; margin-bottom: 20px; }
    .ritual-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 15px; border-bottom: 1px solid #2d2d2d; color: #ccc; }
    .ritual-row:last-child { border-bottom: none; }

    /* # --- 儀式時間表：下一場預備的高亮金色樣式 --- */
    .ritual-next { 
        background: linear-gradient(90deg, #ffd700, #ffa500); 
        color: black !important; 
        font-weight: bold; 
        border-radius: 8px; 
        box-shadow: 0 0 15px rgba(255, 215, 0, 0.4); 
        border: none; 
        margin: 5px; 
    }

    /* # --- 金幣與統計樣式：收益總結方框與數值顏色 --- */
    .gold-summary { text-align: center; padding: 12px; background: #262730; border-radius: 10px; width: 100%; border: 1px solid #464855; margin-bottom: 20px; }
    .gold-val { font-size: 1.8rem; color: #ff4b4b; font-weight: bold; }

    /* # --- 攻擊力顯示樣式：強化顯示總攻擊力特大字體 --- */
    .total-atk-val { font-size: 3.5rem !important; color: #ff4b4b !important; font-weight: bold; text-align: center; }

    /* # --- 數據方框樣式：帶有左側紅色粗邊條的資訊方框 --- */
    .stat-box { background: #262730; padding: 20px; border-radius: 15px; border-left: 8px solid #ff4b4b; }

    /* # --- 管理員專用樣式：平均值顯示盒(橘色調) --- */
    .admin-avg-box { background-color: rgba(255, 165, 0, 0.1); border: 1px solid #ffa500; border-radius: 8px; padding: 10px; color: #ffa500; font-weight: bold; text-align: center; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)


# --- 4. 彈跳視窗功能 (Dialogs) ---
@st.dialog("來者何人")
def admin_login_dialog():
    st.write("房間很亂不要亂解鎖啦QAQ")
    pwd = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Key...")
    if st.button("芝麻開門", use_container_width=True):
        if pwd == ADMIN_PASSWORD:
            st.session_state.is_admin = True
            st.success("解鎖成功！")
            st.rerun()
        else:
            st.error("哇！進不去")


@st.dialog("隨便看看")
def announcement_dialog():
    st.markdown("### 📢 最新幹話")
    st.divider()
    st.write("- 2026 工具版本已更新")
    st.write("- 備註存檔功能已修復")
    st.write("- 我想想要說些什麼ㄛ")
    if st.button("關閉", use_container_width=True):
        st.rerun()

# --- 5. 側邊欄 ---
with st.sidebar:
    st.title("BnsNEO小工具")
    all_pages = ["帝王木獵人", "野王時間表", "儀式時間表", "印章計算表"]

    if st.session_state.get("is_admin", False):
        display_pages = all_pages
    else:
        display_pages = [p for p in all_pages if p != "帝王木獵人"]# 如果不是管理員，就把 "帝王木獵人" 從列表中拿掉

    page = st.radio("功能選單", display_pages) #使用動態的 display_pages 作為選項
    st.markdown('<div style="flex-grow: 1;"></div>', unsafe_allow_html=True) # 核心：CSS 彈簧，這行會把後面的內容全部推到最底下

    st.divider()

    # --- 5. 管理員專屬工具 (僅登入顯示) ---
    if st.session_state.get("is_admin", False):
        with st.sidebar:
            st.divider()
            st.subheader("🛠️ 管理員控制台")

            # 讓管理員可以調整日期，調整完立刻存回 session_state
            new_expire = st.date_input("📅 調整公告截止日期", value=st.session_state.expire_date)
            if new_expire != st.session_state.expire_date:
                st.session_state.expire_date = new_expire
                st.rerun()  # 立刻重整讓公告顯示新日期

        m_col1, m_col2 = st.columns(2, gap="small")
        with m_col1:
            if st.button("💾 存檔", use_container_width=True, key="side_save"):
                # 在這裡呼叫你的 save_data() 函式
                # 確保你的 save_data 會把 st.session_state.expire_date 也存進 JSON
                save_data()
                st.success("已儲存！")
        with m_col2:
            if st.button("🔄 重整", use_container_width=True, key="side_reload"):
                st.rerun()

        st.write("")
        st.divider()  # 再次分隔，下方接你原本的鎖頭與喇叭按鈕
        st.write("")

    foot_col1, foot_col2 = st.columns(2, gap="small")
    with foot_col1:
        if st.button("🔒", help="秘密房間", use_container_width=True, key="admin_lock"):
            st.session_state.is_admin = False
            admin_login_dialog()
    with foot_col2:
        if st.button("📢", help="隨便看看", use_container_width=True, key="admin_ann"):
            announcement_dialog()

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align: center; color: #666; font-size: 0.7rem; opacity: 0.5; margin-top: 8px;'>"
        "酸酸 / 2026</div>",
        unsafe_allow_html=True
    )

# --- 6. 計時器邏輯 ---
@st.fragment(run_every=1)
def timer_logic(ch_name):
    data = st.session_state.boss_data[ch_name]
    # ✅ 固定高度為 180px
    box_style = "height: 180px; display: flex; flex-direction: column; justify-content: center; align-items: center; border-radius: 10px; padding: 15px; text-align: center;"

    if not data["last_death"]:
        st.markdown(f"""
            <div style="{box_style} background: rgba(255, 75, 75, 0.05); border: 2px solid #ff4b4b;">
                <div style="color: #ff4b4b; font-size: 20px; font-weight: bold;">❌ 尚無擊殺紀錄</div>
                <div style="color: #fff; font-size: 45px; font-family: monospace; margin: 10px 0;">-- : -- : --</div>
                <div style="color: #888; font-size: 13px;">請下方選擇時間並點擊上傳</div>
            </div>
        """, unsafe_allow_html=True)
        return  # 結束函式

    # --- 2. 有紀錄時的邏輯計算 ---
    last_death = data["last_death"]
    now = dt_class.now(tw_tz)

    # ✅ 核心修正：強制檢查 last_death 是否帶有時區
    if last_death is not None:
        # 如果 last_death 是 Naive (沒有時區)，就幫它補上台灣時區
        if last_death.tzinfo is None:
            last_death = last_death.replace(tzinfo=tw_tz)

        # 現在兩者都有時區了，計算就不會噴錯
        diff_delta = now - last_death
        elapsed_mins = diff_delta.total_seconds() / 60

        COOLING_LIMIT = 120  # 2小時
        WINDOW_LIMIT = 300  # 5小時

        # --- 階段 A: 冷卻中 (0 ~ 120 分鐘) ---
        if elapsed_mins < COOLING_LIMIT:
            # 修正：使用剛剛算好的 diff_delta 避免重複計算
            remaining_seconds = int((COOLING_LIMIT * 60) - diff_delta.total_seconds())
            # 格式化顯示 (00:00:00)
            time_display = str(timedelta(seconds=max(0, remaining_seconds)))

            st.markdown(f"""
                    <div style="{box_style} background: rgba(100, 100, 100, 0.1); border: 2px solid #666;">
                        <div style="color: #999; font-size: 16px; font-weight: bold;">❄️ BOSS 冷卻中</div>
                        <div style="color: #fff; font-size: 45px; font-family: 'Courier New', monospace; font-weight: bold; margin: 5px 0;">
                            {time_display}
                        </div>
                        <div style="color: #666; font-size: 13px;">距離監督窗口開啟還有一段時間</div>
                    </div>
                """, unsafe_allow_html=True)

        # --- 階段 B: 監督視窗開啟 (120 ~ 300 分鐘) ---
        elif COOLING_LIMIT <= elapsed_mins <= WINDOW_LIMIT:
            in_window_mins = int(elapsed_mins - COOLING_LIMIT)
            st.markdown(f"""
                <div style="{box_style} background: rgba(0, 255, 136, 0.1); border: 2px solid #00ff88; box-shadow: 0 0 20px rgba(0, 255, 136, 0.3);">
                    <div style="color: #00ff88; font-size: 20px; font-weight: bold;">👁️ 監督視窗已開啟</div>
                    <div style="color: #fff; font-size: 16px; margin: 10px 0;">BOSS 隨時可能重生，請守點</div>
                    <div style="background: #00ff88; color: #000; padding: 5px 15px; border-radius: 5px; font-size: 16px; font-weight: bold;">
                        窗口已持續: {in_window_mins} 分鐘
                    </div>
                </div>
            """, unsafe_allow_html=True)

        # --- 階段 C: 時間丟失 (超過 300 分鐘) ---
        else:
            st.markdown(f"""
                <div style="{box_style} background: rgba(255, 75, 75, 0.1); border: 2px solid #ff4b4b;">
                    <div style="color: #ff4b4b; font-size: 20px; font-weight: bold;">❌ 時間已丟失</div>
                    <div style="color: #fff; font-size: 45px; font-family: 'Courier New', monospace; font-weight: bold; margin: 5px 0;">00:00:00</div>
                    <div style="color: #888; font-size: 13px;">已超過 5 小時重生區間，請重新回報</div>
                </div>
            """, unsafe_allow_html=True)


# --- 7. 各頁面功能 ---
if page == "帝王木獵人":
    render_custom_header("boss_icon.png", "帝王木監視器")

    if st.session_state.is_admin:
        with st.container(border=True):
            st.markdown("#### 📊 內部數據監測 (最近 5 次通報與間隔)")
            sc = st.columns(3)
            for i, (ch, val) in enumerate(st.session_state.boss_data.items()):
                with sc[i % 3]:
                    # 1. 取得平均值
                    stats = val.get("history_stats", [])
                    if stats:
                        avg_val = sum(stats) / len(stats)
                        avg_txt = f"{int(avg_val // 3600)}h {int((avg_val % 3600) // 60)}m"
                    else:
                        avg_txt = "尚無數據"

                    # 2. 核心：計算間隔並建立時間軸 HTML
                    history_times = val.get("history_times", [])[-5:][::-1]  # 新到舊
                    time_軸_html = '<div style="display: flex; flex-direction: column; align-items: center; gap: 2px;">'

                    if history_times:
                        for idx in range(len(history_times)):
                            t_curr = history_times[idx]
                            # 時間點方塊
                            time_軸_html += f'<div style="background:#2d2d38; border:1px solid #6c5ce7; border-radius:4px; padding:2px 8px; font-size:18px; color:#fff; width:90%; text-align:center;">{t_curr}</div>'

                            # 計算與下一筆的間隔
                            if idx < len(history_times) - 1:
                                try:
                                    fmt = "%H:%M:%S"
                                    d1 = dt_class.strptime(t_curr, fmt)
                                    d2 = dt_class.strptime(history_times[idx + 1], fmt)
                                    diff_sec = (d1 - d2).total_seconds()
                                    if diff_sec < 0: diff_sec += 86400
                                    gap_h, gap_m = int(diff_sec // 3600), int((diff_sec % 3600) // 60)

                                    # 間隔標籤
                                    time_軸_html += f'''
                                        <div style="border-left:1px dashed #555; height:8px;"></div>
                                        <div style="background:rgba(255,165,0,0.1); color:#ffa500; border:0.5px solid #ffa500; border-radius:10px; padding:0px 6px; font-size:15px; font-weight:bold;">⏱️ {gap_h}h {gap_m}m</div>
                                        <div style="border-left:1px dashed #555; height:8px;"></div>
                                    '''
                                except:
                                    pass
                    else:
                        time_軸_html += '<div style="color:#666; font-size:12px; padding:10px;">暫無紀錄</div>'
                    time_軸_html += '</div>'

                    # 3. 渲染外框 (HTML 顯示部分)
                    st.markdown(f"""
                                        <div style="border: 1px solid #464855; border-radius: 10px; padding: 10px; background: rgba(255,165,0,0.05); margin-bottom: 10px;">
                                            <div style="color:#ffa500; font-weight:bold; text-align:center; margin-bottom:5px;">📍 {ch}</div>
                                            <div style="font-size:12px; color:#aaa; text-align:center; margin-bottom:8px;">平均間隔: {avg_txt}</div>
                                            <hr style="border:0.1px solid #444; margin:8px 0;">
                                            {time_軸_html}
                                        </div>
                                    """, unsafe_allow_html=True)

                    # ✅ 4. 新增：管理員手動刪除按鈕 (緊接在方框下方)
                    if st.button(f"🗑️ 刪除 {ch} 最後一筆", key=f"del_btn_{ch}", use_container_width=True):
                        # 取得該頻道的原始資料參考
                        target_ch = st.session_state.boss_data[ch]

                        if target_ch.get("history_times") and len(target_ch["history_times"]) > 0:
                            # A. 移除最上面(最新)的那筆時間紀錄
                            # 注意：因為顯示時用了 [::-1] 反轉，所以 history_times 的最後一筆就是最新的
                            target_ch["history_times"].pop()

                            # B. 同步移除最後一筆統計數據 (避免平均值錯誤)
                            if target_ch.get("history_stats"):
                                target_ch["history_stats"].pop()

                            # C. 重要：將計時器狀態復原到「刪除後」的最末端時間
                            if target_ch["history_times"]:
                                new_last_t = target_ch["history_times"][-1]
                                try:
                                    # 取得現在帶時區的時間
                                    now_dt = dt_class.now(tw_tz)

                                    # 先解析時間，然後用 replace 換成今天的年月日
                                    # 關鍵點：最後加上 .replace(tzinfo=tw_tz) 或是直接用 localize
                                    parsed_t = dt_class.strptime(new_last_t, "%H:%M:%S")

                                    target_ch["last_death"] = dt_class.now(tw_tz).replace(
                                        hour=parsed_t.hour,
                                        minute=parsed_t.minute,
                                        second=parsed_t.second,
                                        microsecond=0
                                    )
                                except Exception as e:
                                    st.error(f"時間轉換出錯: {e}")
                            else:
                                target_ch["last_death"] = None

                            # D. 存檔並刷新
                            save_data()
                            st.toast(f"✅ 已刪除 {ch} 的最後一筆通報")
                            st.rerun()
                        else:
                            st.error("此頻道目前沒有紀錄可以刪除")
                st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)  # 這是改按鈕與邊框距離

    cols = st.columns(3)
    for i, ch_name in enumerate(st.session_state.boss_data.keys()):
        with cols[i % 3]:
            data = st.session_state.boss_data[ch_name]
            with st.container(border=True):
                # 頻道標題
                st.markdown(
                    f'<div class="boss-title" style="text-align:center; font-size:20px; font-weight:bold; color:#8d51f5; margin-bottom:10px;">{ch_name}</div>',
                    unsafe_allow_html=True)

                # 1. 呼叫大框框邏輯 (冷卻/監督/丟失)
                timer_logic(ch_name)

                # 2. 顯示上次擊殺時間 (若無紀錄則顯示無人擊殺)
                last_val = data['last_death'].strftime('%H:%M:%S') if data['last_death'] else "無人擊殺"
                st.markdown(
                    f'<div style="text-align:center; color:#888; font-size:14px; margin: 10px 0;">💀 上次擊殺：{last_val}</div>',
                    unsafe_allow_html=True)

                st.divider()


                # ✅ 3. 手動修正區 (搬到 if 判斷之外，保證一定會出現)
                # --- 補報區開始 ---
                st.markdown(
                    '<p style="font-size:12px; color:#666; text-align:center; margin-bottom:2px; margin-top:10px;">🕒 補報擊殺時間</p>',
                    unsafe_allow_html=True)

                # 使用自定義 div 代替 st.container 以節省空間並整齊對齊
                st.markdown('<div class="manual-time-container">', unsafe_allow_html=True)

                # 直接分配 6 個欄位：[時, 冒號, 分, 冒號, 秒, 按鈕]
                # 比例經過微調，確保在側邊欄也能水平排整齊
                m_cols = st.columns([1.2, 0.2, 1.2, 0.2, 1.2, 1.2], gap="small", vertical_alignment="center")

                with m_cols[0]:
                    h = st.selectbox("H", [f"{x:02d}" for x in range(24)], key=f"h_{ch_name}",
                                     label_visibility="collapsed")
                with m_cols[1]:
                    st.markdown('<div class="time-sep">:</div>', unsafe_allow_html=True)
                with m_cols[2]:
                    m = st.selectbox("M", [f"{x:02d}" for x in range(60)], key=f"m_{ch_name}",
                                     label_visibility="collapsed")
                with m_cols[3]:
                    st.markdown('<div class="time-sep">:</div>', unsafe_allow_html=True)
                with m_cols[4]:
                    s = st.selectbox("S", [f"{x:02d}" for x in range(60)], key=f"s_{ch_name}",
                                     label_visibility="collapsed")
                with m_cols[5]:
                    if st.button("✈️", key=f"up_{ch_name}", use_container_width=True):
                        try:
                            # 1. 建立新的日期時間物件 (手動選的時間)
                            new_dt = dt_class.now(tw_tz).replace(
                                hour=int(h), minute=int(m), second=int(s), microsecond=0
                            )

                            # 2. 格式化為顯示字串 (例如 "14:05:30")
                            time_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

                            # 3. 取得頻道數據並更新
                            ch_data = st.session_state.boss_data[ch_name]
                            ch_data.update({"last_death": new_dt, "auto_delay_hours": 0})

                            # ✅ 新增：把手動補報的時間塞進歷史紀錄清單
                            if "history_times" not in ch_data:
                                ch_data["history_times"] = []

                            ch_data["history_times"].append(time_str)

                            # 限制只留最近 10 筆，避免資料過大
                            ch_data["history_times"] = ch_data["history_times"][-10:]

                            # 4. 存檔並刷新頁面
                            save_data()
                            st.rerun()
                        except Exception as e:
                            # st.error(f"補報出錯: {e}") # 調試用，正常運作後可註解掉
                            pass

                st.markdown('</div>', unsafe_allow_html=True)  # --- 隔離區結束 ---
                st.markdown('<div style="height: 10x;"></div>', unsafe_allow_html=True)  # 這是改按鈕與邊框距離
                # --- 補報區結束 ---

                st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)
                # 4. 原始擊殺按鈕 (恢復原本功能)
                if data["last_death"]:
                    b_col1, b_col2 = st.columns([1, 1])
                    with b_col1:
                        # 💀 現場擊殺按鈕
                        if st.button("💀 擊殺", key=f"kill_{ch_name}", use_container_width=True, type="primary"):
                            now = dt_class.now(tw_tz)
                            # 建立這次的時間紀錄 (如 "14:05:30")
                            now_str = now.strftime("%H:%M:%S")

                            # 更新數據
                            ch_data = st.session_state.boss_data[ch_name]
                            ch_data.update({
                                "history": data["last_death"],
                                "last_death": now,
                                "auto_delay_hours": 0
                            })

                            # ✅ 新增：把時間塞進歷史紀錄清單
                            if "history_times" not in ch_data: ch_data["history_times"] = []
                            ch_data["history_times"].append(now_str)
                            ch_data["history_times"] = ch_data["history_times"][-10:]  # 只留最近10筆

                            save_data()
                            st.rerun()

                    with b_col2:
                        # ↩️ 取消按鈕 (復原)
                        if st.button("↩️ 取消", key=f"undo_{ch_name}", use_container_width=True):
                            ch_data = st.session_state.boss_data[ch_name]
                            if ch_data.get("history"):
                                # 取得備份的歷史紀錄
                                old_death = ch_data["history"]

                                # ✅ 關鍵修正：確保如果是字串，就轉回 datetime 物件
                                if isinstance(old_death, str):
                                    try:
                                        old_death = dt_class.fromisoformat(old_death)
                                    except:
                                        # 如果格式不合，嘗試另一種常見格式
                                        old_death = dt_class.strptime(old_death, "%Y-%m-%d %H:%M:%S")

                                # 執行復原
                                ch_data.update({
                                    "last_death": old_death,
                                    "history": None
                                })

                                # 同時移除剛剛錯誤新增的一筆歷史顯示紀錄
                                if ch_data.get("history_times"):
                                    ch_data["history_times"].pop()

                                save_data()
                                st.rerun()
                else:
                    # 🏁 初始開始計時
                    if st.button("🏁 開始計時 ", key=f"start_{ch_name}", use_container_width=True, type="primary"):
                        now = dt_class.now(tw_tz)
                        now_str = now.strftime("%H:%M:%S")

                        ch_data = st.session_state.boss_data[ch_name]
                        ch_data.update({"last_death": now, "auto_delay_hours": 0})

                        # ✅ 新增：紀錄第一次開始的時間
                        if "history_times" not in ch_data: ch_data["history_times"] = []
                        ch_data["history_times"].append(now_str)

                        save_data()
                        st.rerun()

                # 💡 隱藏 selectbox 的部分邊框，讓它們看起來像連在一起 (可選)
                st.markdown("""
                                <style>
                                [data-testid="column"] div[data-baseweb="select"] {
                                    border-radius: 4px !important;
                                }
                                </style>
                            """, unsafe_allow_html=True)

                st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)


if page == "野王時間表":
    render_custom_header("野王.png", "野王重生動態紀錄")
# --- 分頁頂部公告區 ---
    st.markdown(f"""
        <div style="background-color: #0e1b36; padding: 15px; border-radius: 10px; border-left: 5px solid #3b82f6; margin-bottom: 20px;">
            <div style="font-size: 15px; font-weight: bold; color: white; margin-bottom: 5px;">📢 重生公告</div>
            <div style="font-size: 20px; color: #3b82f6; font-weight: bold; margin-bottom: 10px;">
                📅 本表預計適用至：{date_display_str}
            </div>
            <ul style="font-size: 15px; color: #d1d5db; line-height: 1.6; margin-left: -15px;">
                <li>此表為 <b>系統出字時間</b>。</li>
                <li>出字後 <b>5 分鐘</b> BOSS 才會出現。</li>
                <li>(?)出現為資料不確定。</li>
                <li>改版或更新後會重制時間，若無更新此表可使用到賽季結束。</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    # --- 2. 定義表格函式 (自動導向當日) ---
    def render_table(area_key, schedules_dict):
        week_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

        # 1. 修正時區：確保網頁知道現在是台灣幾點
        tw_tz = pytz.timezone('Asia/Taipei')
        now = dt_class.now(tw_tz)
        today_idx = now.weekday()
        today_str = week_map[today_idx]

        st.subheader(f"✨ {area_key}")
        view_day = today_str

        # 2. 安全抓取資料：解決之前 list get 的紅字錯誤
        if isinstance(schedules_dict, dict):
            raw_data_list = schedules_dict.get(view_day, [])
        else:
            raw_data_list = schedules_dict if isinstance(schedules_dict, list) else []

        # 建立全天完整排序表 (給下方展開選單用)
        sorted_all_day = sorted(raw_data_list, key=lambda x: x[0])

        # 管理員選單配置
        location_options = {"仙幻島": ["知性森林", "武神荒野", "力王山脈"], "白青": ["白樺林", "風之平原"]}
        options = location_options.get(area_key, ["新地點"])
        min_options = [f"{i:02d}" for i in range(60)]
        hour_options = [f"{i:02d}" for i in range(24)]

        # --- 管理員：編輯功能 ---
        if st.session_state.is_admin:
            with st.expander(f"🛠️ 編輯 {area_key}"):
                day_options = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
                target_day = st.radio("選擇日期：", day_options, index=day_options.index(view_day), horizontal=True,
                                      key=f"edit_day_{area_key}")

                st.divider()
                # ✅ 1. 先定義資料來源 (必須在 if 使用它之前)
                area_data_source = st.session_state.schedules.get(area_key, {})
                # ✅ 2. 判斷型態並取得當前編輯清單 (解決 image_bec800 的問題)
                if isinstance(area_data_source, dict):
                    current_edit_list = area_data_source.get(target_day, [])
                elif isinstance(area_data_source, list):
                    current_edit_list = area_data_source
                else:
                    # 萬一兩者都不是，給一個空列表防止後續出錯
                    current_edit_list = []

                updated_list = []# 建立全天完整排序表 (給下方展開選單用)


                for i, row in enumerate(current_edit_list):
                    c1, c2, c_ask, c3, c4, c5 = st.columns([0.5, 0.5, 0.4, 0.9, 0.5, 0.3])

                    try: h_val, m_val = row[0].split(":")
                    except:h_val, m_val = "00", "00"

                    new_h = c1.selectbox("時", hour_options,
                                         index=hour_options.index(h_val) if h_val in hour_options else 0,
                                         key=f"h_{area_key}_{target_day}_{i}",
                                         label_visibility="collapsed")  # 參數要在這裡
                    new_m = c2.selectbox("分", min_options,
                                         index=min_options.index(m_val) if m_val in min_options else 0,
                                         key=f"m_{area_key}_{target_day}_{i}",
                                         label_visibility="collapsed")  # 參數要在這裡

                    new_time_str = f"{new_h}:{new_m}" # ✅ 新增問號勾選框 (row[3] 預留位置，若無則預設 False)
                    is_unsure_val = row[3] if len(row) > 3 else False
                    new_is_unsure = c_ask.checkbox("❓", value=is_unsure_val, key=f"un_{area_key}_{target_day}_{i}")

                    current_loc = row[1]
                    item_options = options if current_loc in options else [current_loc] + options
                    new_loc = c3.selectbox(f"地點", item_options, index=item_options.index(current_loc),
                                           key=f"l_{area_key}_{target_day}_{i}", label_visibility="collapsed")

                    note_key = row[2] if len(row) > 2 else f"note_{area_key}_{target_day}_{i}"
                    new_note = c4.text_input("備註", value=st.session_state.loc_notes.get(note_key, ""),
                                             key=f"nt_{area_key}_{target_day}_{i}", label_visibility="collapsed")
                    st.session_state.loc_notes[note_key] = new_note

                    if c5.button("🗑️", key=f"del_{area_key}_{target_day}_{i}"):
                        current_edit_list.pop(i)
                        st.session_state.schedules[area_key][target_day] = current_edit_list
                        save_data()
                        st.rerun()
                    else:
                        updated_list.append([new_time_str, new_loc, note_key, new_is_unsure])
                    st.markdown('<div style="margin-bottom: 10px;"></div>', unsafe_allow_html=True)

                st.divider()
                col_btn1, col_btn2 = st.columns([1, 1])
                with col_btn1:
                    if st.button(f"➕ 新增 {target_day} 時段", key=f"add_{area_key}_{target_day}",
                 use_container_width=True):
                        # ✅ 安全取得區域資料 (確保它是字典)
                        if area_key not in st.session_state.schedules or not isinstance(
                                st.session_state.schedules[area_key], dict):
                            st.session_state.schedules[area_key] = {}
                        current_data = st.session_state.schedules[area_key].get(target_day, [])
                        current_data.append(["00:00", options[0], f"note_{len(current_data)}", False])
                        st.session_state.schedules[area_key][target_day] = current_data
                        save_data()
                        st.rerun()
                with col_btn2:
                    if st.button(f"💾 儲存 {target_day} 變更", key=f"save_{area_key}_{target_day}", type="primary", use_container_width=True):
                        # ✅ 儲存時同樣確保結構正確
                        if area_key not in st.session_state.schedules or not isinstance(
                                st.session_state.schedules[area_key], dict):
                            st.session_state.schedules[area_key] = {}
                        st.session_state.schedules[area_key][target_day] = sorted(updated_list, key=lambda x: x[0])
                        save_data()
                        st.rerun()
                st.markdown('<div style="height: 25px;"></div>', unsafe_allow_html=True)  # 這是改按鈕與邊框距離
                # --- ✨ 野王專用：管理員全週大表對帳區 ---
                st.divider()
                with st.expander(f"📋 管理員校對：{area_key} 野王全週總覽", expanded=False):
                    tabs = st.tabs(day_options)
                    for i, tab in enumerate(tabs):
                        day_name = day_options[i]
                        with tab:
                            # ✅ 安全修正校對資料抓取
                            if isinstance(area_data_source, dict):
                                area_day_data = area_data_source.get(day_name, [])
                            else:
                                area_day_data = area_data_source if day_name == view_day else []

                            if area_day_data:
                                # 排序時間 (過濾掉空行防止報錯)
                                sorted_boss_data = sorted([r for r in area_day_data if len(r) > 0], key=lambda x: x[0])

                                boss_rows_html = ""
                                for r in sorted_boss_data:
                                    time_str = r[0]
                                    # 處理問號變色 (野王通常在 r[3])
                                    if len(r) > 3 and r[3]:
                                        time_str = f"<span style='color: #b87012; font-weight: bold;'>{time_str} (?)</span>"

                                    boss_name = r[1]
                                    # 抓取備註/地點細節 (從 st.session_state.loc_notes 抓取)
                                    boss_note = st.session_state.loc_notes.get(r[2] if len(r) > 2 else "", "")
                                    note_html = f" <small style='color:#888;'>({boss_note})</small>" if boss_note else ""

                                    boss_rows_html += f"""
                                                <tr style="border-bottom:1px solid #333; color:#ccc;">
                                                    <td style="padding:8px; width:80px; font-weight:bold;">{time_str}</td>
                                                    <td style="padding:8px;">{boss_name}{note_html}</td>
                                                </tr>"""

                                # 渲染 HTML 表格
                                # ✅ 修正：把高度拉長，並移除內部捲軸限制
                                st.components.v1.html(
                                    f'''<div style="height: auto; overflow: visible;">
                                                                <table style="width:100%; border-collapse:collapse; color:white; font-family:sans-serif; font-size:14px;">
                                                                    {boss_rows_html}
                                                                </table>
                                                            </div>''',
                                    height=min(len(sorted_boss_data) * 42 + 40, 1000)  # 自動計算高度，最高 1000px
                                )
                            else:
                                st.caption(f"🍵 {day_name} 目前無野王排程")

        # --- 前台顯示：頂部 3 場 ---
        st.markdown(f"**🔥 {view_day} 即將重生 (前三場)**")

        # ✅ 修正 1：務必先初始化變數，避免 image_e801dd 報錯
        upcoming_rows = ""
        display_count = 0
        today_date = now.date()  # 取得今天日期

        for row in sorted_all_day:
            if len(row) < 2: continue
            s_time, loc = row[0], row[1]
            is_unsure = row[3] if len(row) > 3 else False

            try:
                # ✅ 修正 2：將「今天日期」與「場次時間」組合，否則 diff 會因年份(1900)錯誤而無法顯示
                target_t = dt_class.strptime(s_time, "%H:%M").time()
                target_dt = tw_tz.localize(dt_class.combine(today_date, target_t))

                # 計算現在與場次的差值（分鐘）
                diff = (target_dt - now).total_seconds() / 60

                # 邏輯：顯示 5 分鐘內重生中，或尚未開始的場次
                if diff > -5 and display_count < 3:
                    note = st.session_state.loc_notes.get(row[2] if len(row) > 2 else "", "")
                    s = {"bg": "rgba(255,255,255,0.05)", "c": "white", "txt": "等待中", "sh": "none"}

                    if view_day == today_str:
                        if -5 <= diff <= 0:
                            s.update({"bg": "#a63030", "txt": "🚨 重生中", "sh": "0px 0px 15px #a63030"})
                        elif diff > 0 and display_count == 0:
                            s.update(
                                {"bg": "#d1ba3d", "c": "black", "txt": "🔥 下一隻預備", "sh": "0px 0px 15px #d1ba3d"})

                    time_display = f"<span style='color: #b87012'>{s_time} (?)</span>" if is_unsure else s_time

                    upcoming_rows += f"""
                                <tr style="background:{s['bg']}; color:{s['c']}; box-shadow:{s['sh']}; border-bottom:1px solid #444;">
                                    <td style="padding:15px; font-weight:bold; width:90px; font-size:16px;">{time_display}</td>
                                    <td style="padding:10px;">{loc}<br><small style="color:#c7ffc7; opacity:0.8;">{note}</small></td>
                                    <td style="padding:15px; text-align:right; font-weight:bold;">{s['txt']}</td>
                                </tr>"""
                    display_count += 1
            except Exception:
                continue

        # ✅ 修正 3：渲染判斷
        if upcoming_rows:
            st.components.v1.html(
                f'<div style="background:#1e1e26; border-radius:10px; border:1px solid #464855;"><table style="width:100%; border-collapse:collapse; color:white; font-family:sans-serif;">{upcoming_rows}</table></div>',
                height=240)
        else:
            st.info(f"✨ {view_day} 目前無後續場次")

        with st.expander(f"📅 查看 {view_day} 全天完整時間表"):
            all_day_html_list = []
            for r in sorted_all_day:
                t_str = f"<span style='color: #b87012; font-weight: bold;'>{r[0]} (?)</span>" if (
                            len(r) > 3 and r[3]) else r[0]
                note_text = st.session_state.loc_notes.get(r[2] if len(r) > 2 else "", "")
                row_html = f'<tr style="border-bottom:1px solid #333; color:#ccc;"><td style="padding:10px; width:100px; font-weight:bold;">{t_str}</td><td style="padding:10px;">{r[1]} <span style="font-size:12px; color:#888; margin-left:15px;">{note_text}</span></td></tr>'
                all_day_html_list.append(row_html)

            all_day_rows_final = "".join(all_day_html_list)
            if all_day_rows_final:
                # ✅ 修正：確保使用 st.components.v1.html 並稍微增加高度
                st.components.v1.html(
                    f'<div style="max-height:350px; overflow-y:auto; background:#1e1e26;"><table style="width:100%; border-collapse:collapse; color:white; font-family:sans-serif;">{all_day_rows_final}</table></div>',
                    height=350)
            else:
                st.write("目前尚無資料")

    # --- 執行渲染 ---

    areas = list(st.session_state.schedules.keys())
    c_left, c_right = st.columns(2)
    if len(areas) > 0:
        with c_left: render_table(areas[0], st.session_state.schedules[areas[0]])
    if len(areas) > 1:
        with c_right: render_table(areas[1], st.session_state.schedules[areas[1]])
    st.write("")
    # 管理員新增區域功能
    if st.session_state.is_admin:
        with st.expander("➕ 新增地圖區域"):
            new_area_name = st.text_input("新區域名稱", placeholder="例如：水月平原")
            if st.button("確認新增"):
                if new_area_name and new_area_name not in st.session_state.schedules:
                    st.session_state.schedules[new_area_name] = {d: [] for d in
                                                                 ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六",
                                                                  "星期日"]}
                    save_data();
                    st.rerun()

elif page == "儀式時間表":
    render_custom_header("儀式.png", "儀式出現動態紀錄")

    # --- 1. 頂部公告區 ---
    st.markdown(f"""
            <div style="background-color:  #1a0e36; padding: 15px; border-radius: 10px; border-left: 5px solid #803bf6; margin-bottom: 20px;">
                <div style="font-size: 15px; font-weight: bold; color: white; margin-bottom: 5px;">📢 出現公告</div>
                <div style="font-size: 20px; color: #8957fa; font-weight: bold; margin-bottom: 10px;">
                    📅 本表預計適用至：{date_display_str}
                </div>
                <ul style="font-size: 15px; color: #d1d5db; line-height: 1.6; margin-left: -15px;">
                   <li>此表為 <b>系統出字時間</b>。</li>
                   <li>出字後 <b>5 分鐘</b> BOSS 才會出現。</li>
                   <li>改版或更新後會重制時間，若無更新此表可使用到賽季結束。</li>
               </ul>
           </div>
           """, unsafe_allow_html=True)

    # --- 2. 初始化資料 確保全域字典已定義 ---
    if "儀式" not in st.session_state.schedules:
        st.session_state.schedules["儀式"] = {f"星期{d}": [] for d in "一二三四五六日"}

    # 設定選項清單
    schedules_dict = st.session_state.schedules
    LOC_OPTS = ["???", "黑森林", "巨岩谷", "孤村", "土門客棧", "悲鳴村", "灰狼村", "海岸客棧", "鬼都", "北方雪原",
                "染坊"]
    week_list = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    # ✅ 強制設定台灣時區 (解決時差問題)
    tw_tz = pytz.timezone('Asia/Taipei')
    now_t = dt_class.now(tw_tz)
    today_week = week_list[now_t.weekday()]
    now_str = now_t.strftime("%H:%M")

    HOURS = [f"{i:02d}" for i in range(24)]
    MINS = [f"{i:02d}" for i in range(60)]

    # --- 3. 管理員編輯區 (修復新增/刪除/儲存) ---
    if st.session_state.get("is_admin", False):
        with st.expander("🛠️ 編輯儀式", expanded=False):
            # 這裡的 sel_week 僅供管理員切換
            sel_week = st.radio(
                "選擇要編輯的日期：",
                week_list,
                index=week_list.index(today_week),
                horizontal=True,
                key="rit_editor_radio"
            )
            st.divider()
            updated_data = []  # ✅ 統一名稱為 updated_rows
            day_data = schedules_dict["儀式"].get(sel_week, [])

            for i, row in enumerate(list(day_data)):
                # ✅ 比例調整：時(0.7), 分(0.7), 問號(0.5), 地1(1.2), 地2(1.2), 備註(1.5), 刪除(0.4)
                c1, c2, c3, c4, c5, c6, c7 = st.columns([0.7, 0.7, 0.5, 1.2, 1.2, 1.5, 0.4])

                time_parts = row[0].split(":") if ":" in row[0] else ["00", "00"]
                h_v, m_v = time_parts[0], time_parts[1]

                with c1:
                    h = st.selectbox("時", HOURS, index=HOURS.index(h_v), key=f"h_{sel_week}_{i}",
                                     label_visibility="collapsed")
                with c2:
                    m = st.selectbox("分", MINS, index=MINS.index(m_v), key=f"m_{sel_week}_{i}",
                                     label_visibility="collapsed")
                with c3:
                    is_q = st.checkbox("❓", value=row[4] if len(row) > 4 else False, key=f"q_{sel_week}_{i}")
                with c4:
                    l1 = st.selectbox("地1", LOC_OPTS, index=LOC_OPTS.index(row[1]) if row[1] in LOC_OPTS else 0,
                                      key=f"l1_{sel_week}_{i}", label_visibility="collapsed")
                with c5:
                    l2 = st.selectbox("地2", LOC_OPTS,
                                      index=LOC_OPTS.index(row[3]) if len(row) > 3 and row[3] in LOC_OPTS else 0,
                                      key=f"l2_{sel_week}_{i}", label_visibility="collapsed")
                with c6:
                    nt = st.text_input("備註", value=row[2], key=f"n_{sel_week}_{i}", label_visibility="collapsed",
                                       placeholder="備註")
                with c7:
                    if st.button("🗑️", key=f"del_{sel_week}_{i}"):
                        schedules_dict["儀式"][sel_week].pop(i)
                        save_data()
                        st.rerun()
                st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)  # 這是改按鈕與邊框距離
                updated_data.append([f"{h}:{m}", l1, nt, l2, is_q])

            st.divider()
            b1, b2 = st.columns([1, 1])
            with b1:
                if st.button(f"➕ 新增{sel_week}場次", use_container_width=True):
                    schedules_dict["儀式"][sel_week].append(["00:00", "???", "", "???", False])
                    save_data() # 💡 物理存檔
                    st.rerun()
            with b2:
                if st.button(f"💾 儲存{sel_week}變更", type="primary", use_container_width=True):
                    schedules_dict["儀式"][sel_week] = updated_data
                    save_data() # 💡 物理存檔
                    st.success(f"✅ {sel_week} 已儲存")
                    st.rerun()
            st.markdown('<div style="height: 25px;"></div>', unsafe_allow_html=True)  # 這是改按鈕與邊框距離
            # --- ✨ 新增：管理員專用的「一週大表對帳區」 ---
            st.divider()
            with st.expander(f"📋 儀式全週時程總覽", expanded=False):
                # 建立週一到週日的分頁
                tabs = st.tabs(week_list)

                for i, tab in enumerate(tabs):
                    day_name = week_list[i]
                    with tab:
                        # 抓取該星期的資料
                        check_data = schedules_dict["儀式"].get(day_name, [])
                        if check_data:
                            # 排序時間
                            check_data_sorted = sorted(check_data, key=lambda x: x[0])

                            # 建立簡易表格內容
                            review_rows = ""
                            for r in check_data_sorted:
                                time_str = r[0]
                                # 如果有問號，顯示橘色
                                if len(r) > 4 and r[4]:
                                    time_str = f"<span style='color: #b87012; font-weight: bold;'>{time_str} (?)</span>"

                                # 地點組合
                                loc_info = f"{r[1]} / {r[3]}" if (len(r) > 3 and r[3] != "???") else r[1]
                                note_info = f" <small style='color:#888;'>({r[2]})</small>" if r[2] else ""

                                review_rows += f"""
                                        <tr style="border-bottom:1px solid #333; color:#ccc;">
                                            <td style="padding:8px; width:80px; font-weight:bold;">{time_str}</td>
                                            <td style="padding:8px;">{loc_info}{note_info}</td>
                                        </tr>"""

                            # 渲染校對表格
                            st.components.v1.html(
                                f'''<div style="max-height:300px; overflow-y:auto;">
                                            <table style="width:100%; border-collapse:collapse; color:white; font-family:sans-serif; font-size:13px;">
                                                {review_rows}
                                            </table>
                                        </div>''', height=250)
                        else:
                            st.caption(f"🍵 {day_name} 目前無資料")
        # --- 這裡才是管理員區塊的結尾 ---
    else:
        # 非管理員預設顯示今天
        sel_week = today_week

    # --- 4. 前台顯示區 (左: 下一隻預備 / 右: 全天時程) ---
    st.markdown(f"### ✨️ 儀式")
    # 取得當天資料並排序
    day_sched = sorted(schedules_dict["儀式"].get(sel_week, []), key=lambda x: x[0])

    # 建立左右兩欄
    col_left, col_right = st.columns([1, 1])

    # --- 👈 左側：下一場預備 / 重生中 ---
    with col_left:
        # 標題縮小：直接用 markdown 指定 font-size
        st.markdown('<p style="font-size: 16px; font-weight: bold; margin-bottom: 8px; color: #fff;">🔥 下一場即將重生</p>',
                    unsafe_allow_html=True)
        upcoming_found = False

        # 僅在選擇的日期是今天時判斷重生狀態
        if sel_week == today_week:
            for r in day_sched:
                is_spawning = False
                is_future = False
                try:
                    # ✅ 正確轉換時間比對 (使用台灣時區)
                    target_dt = dt_class.strptime(r[0], "%H:%M").replace(
                        year=now_t.year, month=now_t.month, day=now_t.day
                    )
                    target_dt = tw_tz.localize(target_dt)

                    # 計算分鐘差
                    diff = (target_dt - now_t).total_seconds() / 60
                    # ✅ 判定條件：重生中 (0 到 -5 分鐘) 或 未來場次
                    is_spawning = -5 <= diff <= 0
                    is_future = diff > 0
                except Exception as e:
                    # ✅ 這裡必須有 except 塊，try 才能結束
                    continue

                if is_spawning or is_future:
                    q_text = " (?)" if len(r) > 4 and r[4] else ""
                    loc_display = f"{r[1]} / {r[3]}" if (len(r) > 3 and r[3] != "???") else r[1]

                    # 仙幻島發光樣式
                    tag_color = "#ff4b4b" if is_spawning else "#d4af37"
                    glow_color = "rgba(255, 75, 75, 0.6)" if is_spawning else "rgba(212, 175, 55, 0.6)"
                    status_text = "🚨 重生中" if is_spawning else "🔥 下一場預備"

                    st.markdown(f"""
                        <div style="padding: 15px; border-radius: 10px; border: 1px solid {tag_color}; 
                                    box-shadow: 0 0 15px {glow_color}; background: rgba(0,0,0,0.2);
                                    margin-bottom: 15px;">
                            <div style="font-size: 25px; font-weight: bold; color: {tag_color}; margin-bottom: 5px;">
                                {r[0]}{q_text}
                            </div>
                            <div style="color: white; font-size: 25px; margin-bottom: 10px;">{loc_display}</div>
                            <div style="background: {tag_color}; color: white; padding: 2px 10px; 
                                        border-radius: 15px; font-size: 12px; font-weight: bold; display: inline-block;">
                                {status_text}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    upcoming_found = True
                    break  # 找到最近的一場後跳出迴圈

        if not upcoming_found:
            st.info("目前無即將到來的儀式")

    # --- 👉 右側：全天完整時程 ---
    with col_right:
        st.markdown('<p style="font-size: 16px; font-weight: bold; margin-bottom: 8px; color: #fff;">📜 全天完整時程</p>',
                    unsafe_allow_html=True)
        with st.container(border=True):  # 使用外框包起來更有質感
            if day_sched:
                for r in day_sched:
                    q_m = " (?)" if len(r) > 4 and r[4] else ""
                    l_d = f"{r[1]} / {r[3]}" if (len(r) > 3 and r[3] != "???") else r[1]

                    # ✅ 判定是否已過期 (過期則字體變淡)
                    try:
                        target_t = dt_class.strptime(r[0], "%H:%M").time()
                        is_past = target_t < now_t.time() and not (-5 <= (
                                    dt_class.combine(now_t.date(), target_t).replace(
                                        tzinfo=tw_tz) - now_t).total_seconds() / 60 <= 0)
                    except:
                        is_past = False

                    opacity = "0.4" if is_past else "1.0"
                    # 列表顯示
                    st.markdown(f"""
                        <div style="padding: 8px 0; border-bottom: 1px solid #333; display: flex; justify-content: space-between;">
                            <div style="color: white; font-size: 25px;">
                                <b style="color: #8d51f5; margin-right: 8px;">{r[0]}{q_m}</b> {l_d}
                            </div>
                            <div style="color: #666; font-size: 11px;">{r[2]}</div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.write("暫無排程資料")


elif page == "印章計算表":
    render_custom_header("seal_icon.png", "印章計算懶人工具")
    # 2. 建立左右兩個欄位佈局
    left_col, right_col = st.columns([1, 3])

    # --- 左側欄位：消耗試算 ---
    with left_col:
        with st.container(border=True):  # 確保這塊被關在左邊
            st.subheader("💰 花費試算")
            g_c = st.number_input("綠印 (10.5金)", min_value=0, step=1, key="green_seal")
            b_c = st.number_input("藍印 (28金)", min_value=0, step=1, key="blue_seal")
            p_c = st.number_input("紫印 (56金)", min_value=0, step=1, key="purple_seal")

            # 計算結果顯示
            total_gold = round((g_c * 10.5) + (b_c * 28) + (p_c * 56), 1)
            st.markdown(f'''
                    <div style="text-align: center; background: rgba(255,75,75,0.1); padding: 15px; border-radius: 10px; border: 1px solid #ff4b4b; margin-top: 15px;">
                        <span style="font-size: 32px; font-weight: bold; color: #ff4b4b;">{total_gold}</span>
                        <span style="color: #ff4b4b; margin-left: 5px;">金</span>
                    </div>
                ''', unsafe_allow_html=True)

            # --- 右側欄位：印章清單 ---
            with right_col:
                with st.container(border=True):  # 確保這塊被關在右邊
                    st.subheader("📋 印章清單")

                    # 遍歷清單數據
                    for idx, seal in enumerate(st.session_state.seals):
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([2, 3, 1])
                            c1.write(f"#### {seal['name']}")

                            with c2:
                                bc = st.columns(3)
                                if bc[0].button("－", key=f"m_{idx}"):
                                    st.session_state.seals[idx]['value'] -= 1
                                    save_data();
                                    st.rerun()

                                bc[1].markdown(f"<h3 style='text-align:center;'>{int(seal['value'])}</h3>",
                                               unsafe_allow_html=True)

                                if bc[2].button("＋", key=f"a_{idx}"):
                                    st.session_state.seals[idx]['value'] += 1
                                    save_data();
                                    st.rerun()

                            if c3.button("🗑️", key=f"d_{idx}"):# 刪除按鈕
                                st.session_state.seals.pop(idx)
                                save_data();
                                st.rerun()

                    # 新增項目功能
                    st.divider()
                    new_n = st.text_input("新增項目名稱", key="new_seal_name")
                    if st.button("確認新增", key="add_seal_btn"):
                        if new_n:
                            st.session_state.seals.append({"name": new_n, "value": 0})
                            save_data();
                            st.rerun()

            st.divider()
    pan = st.session_state.panel
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown('<b style="color:#ff4b4b;">赤色</b>', unsafe_allow_html=True)
        pan["red_atk"] = st.number_input("攻擊力", value=int(pan["red_atk"]), key="p_ra")
        pan["red_crit"] = st.number_input("暴擊傷害", value=int(pan["red_crit"]), key="p_rc")
    with sc2:
        st.markdown('<b style="color:#ffd700;">黃色</b>', unsafe_allow_html=True)
        pan["yellow_atk"] = st.number_input("攻擊力 ", value=int(pan["yellow_atk"]), key="p_ya")
        pan["yellow_hp"] = st.number_input("生命值", value=int(pan["yellow_hp"]), key="p_yh")
    with sc3:
        st.markdown('<b style="color:#1e90ff;">青色</b>', unsafe_allow_html=True)
        pan["blue_atk"] = st.number_input("攻擊力  ", value=int(pan.get("blue_atk", 0)), key="p_ba")
        pan["blue_pierce"] = st.number_input("貫穿值", value=int(pan.get("blue_pierce", 0)), key="p_bp")
    if st.button("💾 儲存能力值"): save_data(); st.success("已存檔")