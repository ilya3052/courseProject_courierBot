@echo off
chcp 65001

python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt

mkdir logs

echo @echo off > .\scripts\run.bat
echo chcp 65001 >> .\scripts\run.bat
echo echo Для завершения программы нажмите Ctrl+C >> .\scripts\run.bat
echo call .venv\Scripts\activate.bat >> .\scripts\run.bat
echo python main.py >> .\scripts\run.bat
echo pause >> .\scripts\run.bat

if not exist ".env" (
    copy .env.example .env 2>nul
    echo Заполните .env файл своими значениями!
)

del .env.example
del "%~f0"