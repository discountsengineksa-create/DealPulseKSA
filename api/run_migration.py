import psycopg2

# رابط قاعدة البيانات الحية الخاص بك في Railway
db_url = "postgresql://postgres:IFGbiGZYhMVYobPybdIaBaOrxkHpUAVt@turntable.proxy.rlwy.net:18475/railway"

try:
    print("🔄 جاري الاتصال بقاعدة بيانات Railway وحقن الـ View...")
    
    # قراءة ملف الـ SQL
    with open("migration_018_social_leads_view.sql", "r", encoding="utf-8") as file:
        sql_script = file.read()
    
    # الاتصال وتنفيذ الكود
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    cursor.execute(sql_script)
    conn.commit()
    
    cursor.close()
    conn.close()
    print("✅ تم بنجاح! تم إنشاء الـ v_social_leads VIEW وتنظيف قاعدة البيانات.")

except Exception as e:
    print(f"❌ حدث خطأ أثناء الحقن: {e}")