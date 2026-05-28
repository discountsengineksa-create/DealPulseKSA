api: uvicorn api.main:app --host 0.0.0.0 --port $PORT
bot: uvicorn bot_app:app --host 0.0.0.0 --port $PORT
dashboard: streamlit run dashboard.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false
