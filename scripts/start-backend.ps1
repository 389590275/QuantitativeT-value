Set-Location $PSScriptRoot\..
& .\venv\Scripts\Activate.ps1
pip install -q -r backend\requirements.txt
Set-Location backend
python main.py
