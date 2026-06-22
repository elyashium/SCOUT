@echo off
echo Setting up virtual environment...
py -m venv venv
call venv\Scripts\activate.bat

echo Installing requirements...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt


echo Launching Dashboard...
py -m streamlit run dashboard_app.py
pause
