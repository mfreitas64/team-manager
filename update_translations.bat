@echo off
echo 🔍 Extracting new translation strings...
pybabel extract -F babel.cfg -o messages.pot app/templates

echo 🔁 Updating existing .po files...
pybabel update -i messages.pot -d translations

echo 🧹 Removing messages.pot...
del messages.pot

echo 🔧 Compiling translations...
pybabel compile -d translations

echo ✅ Translations updated!
pause