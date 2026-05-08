import subprocess
import sys
import time
import os

def run_project():
    print("🚀 جاري تشغيل مشروع Deal Pulse...")
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. تشغيل البوت
    print("🤖 تشغيل بوت التليجرام...")
    bot_process = subprocess.Popen([sys.executable, "deal_pulse_bot.py"], cwd=current_dir)

    # 2. تشغيل لوحة التحكم (التعديل هنا)
    print("📊 تشغيل لوحة تحكم ستريمليت...")
    # نستخدم sys.executable -m streamlit لضمان التشغيل الصحيح
    dashboard_process = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "dashboard.py"], cwd=current_dir)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 جاري إيقاف جميع العمليات...")
        bot_process.terminate()
        dashboard_process.terminate()
        print("✅ تم الإغلاق بنجاح.")

if __name__ == "__main__":
    run_project()