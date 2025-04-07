@echo off
echo [INFO] Setting up Python environment...
python -m venv .venv
call .venv\Scripts\activate
echo [INFO] Installing packages...
pip install --upgrade pip
pip install -r requirements.txt
echo [INFO] Launching AI Compliance Assistant...
streamlit run app.py
pause
