#!/bin/bash
echo "Setting up virtual environment..."
# Detect python command
PYTHON_CMD="python"
if command -v py &> /dev/null; then
    PYTHON_CMD="py"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
fi

$PYTHON_CMD -m venv venv

# Activate venv (handles both bash on Windows and Linux/Mac)
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

echo "Installing requirements..."
$PYTHON_CMD -m pip install --upgrade pip
$PYTHON_CMD -m pip install -r requirements.txt


echo "Launching Dashboard..."
$PYTHON_CMD -m streamlit run dashboard_app.py
