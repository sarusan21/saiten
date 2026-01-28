import streamlit as st
import google.generativeai as genai
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

# --- 設定と初期化 ---
st.set_page_config(page_title="受験生向け英訳添削", layout="wide")

# --- CSS設定 (スマホ対応・全画面中央表示) ---
st.markdown("""
<style>
    /* 全画面ローディングオーバーレイ */
    .loading-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(255, 255, 255, 0.95);
        z-index: 99999;
        display: flex;
        flex-direction: column;
        justify_content: center;
        align-items: center;
        text-align: center;
        padding: 20px;
    }
    /* 豆知識のテキスト */
    .trivia-box {
        max-width: 600px;
        padding: 2rem;
        border-radius: 15px;
        background: #f8f9fa;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border: 2px solid #e9ecef;
    }
    .trivia-title {
        font-size: 1.5rem;
        color: #ff4b4b;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .trivia-content {
        font-size: 1.8rem; /* 大きく表示 */
        color: #333;
        font-weight: bold;
        line-height: 1.6;
    }
    .loading-spinner {
        margin-top: 2rem;
        font-size: 1.2rem;
        color: #666;
    }
    /* スマホ用調整 */
    @media (max-width: 600px) {
        .trivia-content {
            font-size: 1.4rem;
        }
    }
</style>
""", unsafe_allow_html=True)

st.title("受験生向け 英訳添削システム")

# --- 豆知識リスト (大幅増量) ---
TRIVIA_LIST = [
    # 文法・語法
    "💡 'I'm lovin' it' は文法的に例外！ 本来 love は進行形にしませんが、一時的な感情を強調する時はOK。",
    "💡 'news' は s がつくけど単数扱い！ 'a news' とは言わず 'a piece of news' と言います。",
    "💡 'suggest' は 'suggest me to do' とは言えません！ 'suggest that I do' や 'suggest doing' が正解。",
    "💡 'police'（警察）は常に複数扱い！ 'The police is coming' ではなく 'The police are coming'。",
    "💡 'advice' も数えられない名詞。'an advice' はダメ。'some advice' を使おう。",
    "💡 'discuss' は「～について議論する」だけど 'about' は不要！ 'discuss the problem' が正解。",
    "💡 'marry' に 'with' は不要！ 'marry him' が正解。ただし 'get married to him' なら to が必要。",
    "💡 'travel' は「旅行」という行為全体を指す不可算名詞。個別の旅行は 'trip' を使おう。",
    "💡 'homework' は数えられない！ 'many homeworks' は間違い。'much homework' です。",
    "💡 'staff' は集合名詞。職員一人は 'a staff member' と言おう。",

    # 単語のニュアンス
    "💡 日本語の「マンション」は英語で 'mansion'（大豪邸）！ 普通は 'apartment' や 'condo'。",
    "💡 'smart' はイギリス英語だと「身なりが整った」意味。アメリカ英語だと「頭が良い」。",
    "💡 'clever' は「ずる賢い」というネガティブな意味を含むことがあるので誉め言葉には注意。",
    "💡 'high spirits' は「上機嫌」という意味。お酒のことではないよ！",
    "💡 'history'（歴史）の語源は 'his story'… ではありません！ ギリシャ語の 'historia'（探求）です。",
    "💡 'salary'（給料）の語源は 'salt'（塩）。昔は塩が給料がわりに払われていたから。",
    "💡 'desert'（砂漠）と 'dessert'（デザート）。ssが2つのほうが「甘いもの（デザート）」。",
    
    # 勉強法・心理学
    "🧠 エビングハウスの忘却曲線：人間は1日経つと74%忘れる。復習は「今日中」にやるのが最強。",
    "🧠 ポモドーロ・テクニック：25分勉強＋5分休憩が、人間の集中力の限界に最適。",
    "🧠 英語は「寝る前」に暗記すると定着率アップ！ 脳は睡眠中に記憶を整理するから。",
    "🧠 音読は「黙読」の5倍の効果があると言われています。口と耳をフル活用しよう。",
    "🧠 「青ペン」で勉強すると記憶力が上がる？ 青色は鎮静効果があり集中しやすいらしい。",

    # 即アウト回避テクニック
    "⚠️ 英作文で困ったら 'get' を疑え。'obtain', 'become', 'arrive' など具体的な動詞に変えると点数アップ。",
    "⚠️ 'very' の使いすぎに注意！ 'very big' → 'huge', 'very good' → 'excellent' と言い換えよう。",
    "⚠️ 文頭の 'And' や 'But' は減点対象になりやすい。'In addition,' や 'However,' を使おう。",
    "⚠️ 主語が長すぎる文は嫌われる。無生物主語構文や It is ~ that 構文でスッキリさせよう。",
    "⚠️ 時制の一致は大丈夫？ 主節が過去形なら、従属節も過去形にするのが基本ルール。",
    "⚠️ 冠詞（a/the）に迷ったら、複数形に逃げるのも一つの手。",
    "⚠️ 接続詞 'because' は文頭に置かないほうが無難（会話ならOKだけど、記述式では避ける）。"
]

# --- APIキーの読み込み ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except FileNotFoundError:
    st.error("設定ファイル (.streamlit/secrets.toml) が見つかりません。")
    st.stop()
except KeyError:
    st.error("Secretsに 'GOOGLE_API_KEY' が設定されていません。")
    st.stop()

# --- サイドバー ---
with st.sidebar:
    st.header("⚙️ システム設定")
    
    st.subheader("しろねこ選択")
    model_choice = st.radio(
        "使用するモデルを選んでください",
        ["はいぱーしろねこ", "のーまるしろねこ"],
        index=0
    )
    
    # ご要望のモデル構成 (2.5 Pro / 2.0 Flash)
    model_map = {
        "はいぱーしろねこ": "models/gemini-2.5-pro",
        "のーまるしろねこ": "models/gemini-2.0-flash"
    }
    selected_model_name = model_map[model_choice]

    st.divider()
    
    st.subheader("📝 採点設定")
    difficulty = st.select_slider(
        "採点基準の厳しさ",
        options=["やさしめ", "ちゅうくらい", "厳しめ"],
        value="ちゅうくらい"
    )
    max_score = st.number_input("この問題の配点", min_value=10, max_value=200, value=100, step=10)

# --- 関数定義 ---

def get_gemini_response_sync(prompt, model_name):
    """Gemini APIを呼び出す同期関数（スレッド内で実行される）"""
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return response.text
    except Exception as e:
        return f"ERROR: {e}"

def image_to_text(image, model_name):
    """OCR関数"""
    try:
        model = genai.GenerativeModel(model_name)
        prompt = "この画像に書かれている文字をすべて読み取って、テキストとして出力してください。"
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except Exception as e:
        st.error(f"画像読み取りエラー: {e}")
        return ""

def generate_grading_prompt(problem_text, student_text, difficulty, max_score):
    """プロンプト作成"""
    strictness_instruction = ""
    if difficulty == "やさしめ":
        strictness_instruction = "受験生を励ますために、細かいミスは許容し、良い点を積極的に評価してください。"
    elif difficulty == "ちゅうくらい":
        strictness_instruction = "標準的な大学入試の基準で採点してください。"
    elif difficulty == "厳しめ":
        strictness_instruction = "難関大学レベルの非常に厳しい基準で採点してください。"

    prompt = f"""
    あなたはプロの英語教師です。以下の「問題文」に対する「生徒の解答」を採点・添削してください。
    【重要】出力は純粋なJSONデータのみにしてください。

    【設定】
    - 配点: {max_score}点満点に換算
    - 難易度設定: {difficulty} ({strictness_instruction})

    【問題文 (日本語)】
    {problem_text}

    【生徒の解答 (英語)】
    {student_text}

    【採点基準】
    1. 語彙・文法 (50点)
    2. 自然さ (25点)
    3. 日本語の反映度 (25点)

    【即アウトポイント (該当したら原則0点)】
    - 主語・動詞構造崩壊
    - 時制・冠詞・単数/複数ミス
    - 語彙の致命的な誤り
    - 直訳・不自然な表現
    - 抽象名詞の誤訳

    【出力JSONキー構成】
    {{
        "total_score": 整数,
        "is_instant_fail": true/false,
        "fail_reason": "理由またはnull",
        "breakdown": {{
            "grammar_score": 整数,
            "naturalness_score": 整数,
            "reflection_score": 整数
        }},
        "corrected_sentence": "修正後の英文",
        "correction_html": "HTML差分文字列 (<span style='color:red; text-decoration:line-through'>削除</span> <span style='color:green; font-weight:bold'>追加</span>)",
        "feedback": "講評",
        "improvement_points": ["改善点リスト"],
        "model_answer": "模範解答"
    }}
    """
    return prompt

# --- メイン UI ---

col1, col2 = st.columns(2)

# 1. 問題の入力
with col1:
    st.subheader("📝 問題文")
    input_method_prob = st.radio("入力方法", ["テキスト", "カメラ/画像"], key="prob_radio", horizontal=True)
    
    problem_text = ""
    if input_method_prob == "テキスト":
        problem_text = st.text_area("問題文を入力", height=150, placeholder="例：環境問題について...")
    else:
        uploaded_prob = st.file_uploader("問題画像をアップロード", type=["jpg", "png"], key="prob_img")
        if uploaded_prob:
            image = Image.open(uploaded_prob)
            st.image(image, caption="画像を確認", use_container_width=True)
            if st.button("文字を読み取る", key="ocr_prob"):
                with st.spinner(f"読み取り中..."):
                    extracted = image_to_text(image, selected_model_name)
                    st.session_state["ocr_prob_text"] = extracted
        problem_text = st.text_area("読み取ったテキスト", value=st.session_state.get("ocr_prob_text", ""), height=150)

# 2. 解答の入力
with col2:
    st.subheader("✍️ 生徒の解答")
    input_method_ans = st.radio("入力方法", ["テキスト", "カメラ/画像"], key="ans_radio", horizontal=True)
    
    student_text = ""
    if input_method_ans == "テキスト":
        student_text = st.text_area("解答を入力", height=150, placeholder="例：I think that...")
    else:
        uploaded_ans = st.file_uploader("解答画像をアップロード", type=["jpg", "png"], key="ans_img")
        if uploaded_ans:
            image = Image.open(uploaded_ans)
            st.image(image, caption="画像を確認", use_container_width=True)
            if st.button("文字を読み取る", key="ocr_ans"):
                with st.spinner(f"読み取り中..."):
                    extracted = image_to_text(image, selected_model_name)
                    st.session_state["ocr_ans_text"] = extracted
        student_text = st.text_area("読み取ったテキスト", value=st.session_state.get("ocr_ans_text", ""), height=150)

# --- 採点実行 ---
st.divider()

if st.button(f"💯 採点スタート ({model_choice})", type="primary", use_container_width=True):
    if not problem_text or not student_text:
        st.warning("問題文と解答の両方を入力してください。")
    else:
        # プロンプト作成
        prompt = generate_grading_prompt(problem_text, student_text, difficulty, max_score)
        
        # --- ここから非同期処理 & 豆知識ループ ---
        
        # 1. 表示用のプレースホルダーを作成（全画面オーバーレイ用）
        overlay_placeholder = st.empty()
        
        # 2. 別スレッドでAPIを呼び出す
        executor = ThreadPoolExecutor()
        future = executor.submit(get_gemini_response_sync, prompt, selected_model_name)
        
        # 3. APIが終わるまでループして豆知識を表示・更新
        start_time = time.time()
        last_switch_time = 0
        current_trivia = random.choice(TRIVIA_LIST)
        
        while not future.done():
            current_time = time.time()
            elapsed = current_time - start_time
            
            # 10秒ごとに豆知識を切り替える
            if current_time - last_switch_time > 10:
                current_trivia = random.choice(TRIVIA_LIST)
                last_switch_time = current_time
            
            # 全画面HTMLを更新
            html_content = f"""
            <div class="loading-overlay">
                <div class="trivia-box">
                    <div class="trivia-title">しろねこ先生の豆知識タイム</div>
                    <div class="trivia-content">{current_trivia}</div>
                </div>
                <div class="loading-spinner">
                    <br>採点中... {int(elapsed)}秒経過<br>
                    {model_choice} が添削中...
                </div>
            </div>
            """
            overlay_placeholder.markdown(html_content, unsafe_allow_html=True)
            
            # ループの負荷を下げるために少し待機（画面更新は頻繁に行うが、豆知識変更は10秒ごと）
            time.sleep(0.1)
        
        # --- 処理完了後 ---
        
        # 結果を取得
        result_json_str = future.result()
        
        # オーバーレイを削除（結果表示へ）
        overlay_placeholder.empty()

        if result_json_str and not result_json_str.startswith("ERROR"):
            try:
                # JSON整形
                json_str = result_json_str.strip()
                if json_str.startswith("```json"):
                    json_str = json_str[7:]
                if json_str.endswith("```"):
                    json_str = json_str[:-3]
                
                data = json.loads(json_str)

                # --- 結果表示 ---
                st.success("採点完了！")
                
                score_col1, score_col2 = st.columns([1, 2])
                with score_col1:
                    st.metric(label="獲得スコア", value=f"{data['total_score']} / {max_score}")
                    if data['is_instant_fail']:
                        st.error(f"⚠️ 即アウト判定: {data['fail_reason']}")
                
                with score_col2:
                    bd = data['breakdown']
                    st.write("📊 **項目別評価 (100点満点換算)**")
                    st.progress(bd['grammar_score'] / 50, text=f"語彙・文法: {bd['grammar_score']}/50")
                    st.progress(bd['naturalness_score'] / 25, text=f"自然さ: {bd['naturalness_score']}/25")
                    st.progress(bd['reflection_score'] / 25, text=f"日本語反映度: {bd['reflection_score']}/25")

                st.divider()

                st.subheader("🔍 添削結果")
                st.markdown(f"<div style='font-size:18px; line-height:1.6; padding:15px; background-color:#f0f2f6; border-radius:10px;'>{data['correction_html']}</div>", unsafe_allow_html=True)
                st.caption("赤字取り消し線：削除 / 緑字太字：追加・修正")

                st.subheader("しろねこアドバイス")
                st.info(data['feedback'])
                
                with st.expander("詳細な改善ポイントを見る", expanded=True):
                    for point in data['improvement_points']:
                        st.write(f"- {point}")

                st.subheader("✨ 模範解答例")
                st.code(data['model_answer'], language='text')

            except json.JSONDecodeError:
                st.error("データの解析に失敗しました。")
                st.text(result_json_str)
        else:
            st.error(f"エラーが発生しました: {result_json_str}")