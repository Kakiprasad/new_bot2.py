import os
import requests
import feedparser
import time
from html import unescape
import datetime
import pytz
import telebot
import threading
from deep_translator import GoogleTranslator  # --- UPDATED --- (కొత్త లైబ్రరీ)

# -------- RENDER ENVIRONMENT VARIABLES --------
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# -------- SETTINGS --------
IST = pytz.timezone('Asia/Kolkata')
bot = telebot.TeleBot(TOKEN)

sent_links = set()
summary_storage = []
last_sent_summary_time = ""

RSS_FEEDS = [
    {"url":"https://www.cnbctv18.com/commonfeeds/v1/cne/rss/latest.xml","source":"CNBC-TV18"},
    {"url":"https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms","source":"EconomicTimes"},
    {"url":"https://www.moneycontrol.com/rss/latestnews.xml","source":"Moneycontrol"}
]

# -------- TRANSLATOR FUNCTION --------
# --- UPDATED START --- (ఈ ఫంక్షన్ కొత్తగా చేర్చబడింది)
def translate_to_telugu(text):
    try:
        return GoogleTranslator(source='auto', target='te').translate(text)
    except Exception as e:
        print(f"Translation Error: {e}")
        return text
# --- UPDATED END ---

# -------- GEMINI CALL --------
def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=payload, timeout=25)
        if r.status_code == 429:
            return "⚠️ కోటా ముగిసింది! AI విశ్లేషణ అందుబాటులో లేదు."
        if r.status_code != 200:
            return "⚠️ AI విశ్లేషణ అందుబాటులో లేదు."
        data = r.json()
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        return "⚠️ AI విశ్లేషణ చేయడంలో సమస్య వచ్చింది."

# -------- ANALYSIS --------
def get_ai_analysis(title):
    prompt = f"""
వార్త: {title}
ఈ వార్తపై విశ్లేషణను ఈ క్రింది ఫార్మాట్ లో ఇవ్వండి (పూర్తిగా తెలుగులో):
📌 వార్త రకం: (Global / Indian / Stock / Other)
1️⃣ వార్త విషయం: 1-2 లైన్లలో.
2️⃣ Positive: లాభాలు.
3️⃣ Negative: ప్రతికూలతలు.
4️⃣ ఫండమెంటల్స్: (PE, ROE, M Cap) డేటా.
5️⃣ బ్రోకరేజ్ అభిప్రాయం: Buy/Sell రేటింగ్.
6️⃣ మార్కెట్ ప్రభావం: ధర పెరుగుతుందా లేదా తగ్గుతుందా?
9️⃣ AI వివరణ: భవిష్యత్తులో ఏం జరగవచ్చు?
"""
    return call_gemini(prompt)

# -------- SUMMARIES --------
def get_short_summary():
    if not summary_storage: return "ముఖ్యమైన వార్తలు ఏమీ లేవు."
    all_titles = "\n".join([f"- {t}" for t in summary_storage])
    prompt = f"ఈ వార్తల ఆధారంగా మార్కెట్ SMART SUMMARY తయారు చేయండి:\n{all_titles}"
    return f"📊 మార్కెట్ SMART SUMMARY & OUTLOOK\n\n{call_gemini(prompt)}"

def get_long_summary():
    if not summary_storage: return "స్టాక్ వార్తలు ఏమీ లేవు."
    all_titles = "\n".join([f"- {t}" for t in summary_storage])
    prompt = f"స్టాక్ వార్తలను 'Stock Name (English): వార్త (Telugu)' ఫార్మాట్ లో ఇవ్వండి:\n{all_titles}"
    return f"🚀 ముఖ్యమైన స్టాక్ వార్తలు:\n\n{call_gemini(prompt)}"

# -------- MAIN LOOP --------
def news_loop():
    global last_sent_summary_time
    print("🚀 న్యూస్ లూప్ రన్ అవుతోంది...")

    while True:
        try:
            now_ist = datetime.datetime.now(IST)
            now_str = now_ist.strftime("%H:%M")

            if now_str in ["04:00", "08:00", "13:30", "20:30"] and last_sent_summary_time != now_str:
                bot.send_message(CHAT_ID, get_short_summary())
                last_sent_summary_time = now_str
                summary_storage.clear()

            if now_str in ["06:00", "18:00"] and last_sent_summary_time != now_str:
                bot.send_message(CHAT_ID, get_long_summary())
                last_sent_summary_time = now_str
                summary_storage.clear()

            for feed in RSS_FEEDS:
                try:
                    resp = requests.get(feed["url"], timeout=15)
                    parsed = feedparser.parse(resp.content)
                    
                    for entry in reversed(parsed.entries[:10]): 
                        if entry.link in sent_links: continue
                        
                        original_title = unescape(entry.title)
                        
                        # --- UPDATED START ---
                        telugu_title = translate_to_telugu(original_title) # టైటిల్ తెలుగులోకి మార్పు
                        analysis = get_ai_analysis(telugu_title) # తెలుగు టైటిల్ తో AI విశ్లేషణ
                        
                        # కింద మెసేజ్ ఫార్మాట్ లో 'Source' అని మార్చబడింది
                        msg = f"📢 **Source:** {feed['source']}\n\n📰 **వార్త:** {telugu_title}\n\n🤖 **AI విశ్లేషణ:**\n{analysis}\n\n🔗 [లింక్]({entry.link})\n\n📡 Sent via: Render 🚀"
                        # --- UPDATED END ---
                        
                        try:
                            bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                        except:
                            bot.send_message(CHAT_ID, msg)

                        sent_links.add(entry.link)
                        summary_storage.append(telugu_title) # --- UPDATED --- (తెలుగు టైటిల్ సేవ్ అవుతుంది)
                        time.sleep(25) 
                except Exception as e:
                    print(f"⚠️ ఫీడ్ ఎర్రర్: {e}")

            time.sleep(60) 
        except Exception as e:
            print(f"❗ లూప్ ఎర్రర్: {e}")
            time.sleep(10)

if __name__ == "__main__":
    print("⌛ పాత వార్తలను లోడ్ చేస్తున్నాను...")
    for feed in RSS_FEEDS:
        try:
            resp = requests.get(feed["url"], timeout=10)
            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries:
                sent_links.add(entry.link)
        except: pass
    
    print(f"✅ సిద్ధంగా ఉంది. బాట్ రన్ అవుతోంది...")
    t1 = threading.Thread(target=news_loop)
    t1.daemon = True
    t1.start()
    bot.infinity_polling()