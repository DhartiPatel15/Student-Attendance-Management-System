@echo off
title AttendEase - Student Attendance Management System
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
 echo Python was not found. Install Python 3.10 or newer first.
 pause
 exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
 echo Creating Python environment...
 python -m venv .venv
 if errorlevel 1 goto setup_error
)

".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 (
 echo Repairing Python pip...
 rmdir /s /q .venv
 python -m venv .venv
 if errorlevel 1 goto setup_error
)

".venv\Scripts\python.exe" -m ensurepip --upgrade
if errorlevel 1 goto setup_error

echo Installing/checking Flask...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto setup_error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto setup_error

start "" http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py
pause
exit /b 0

:setup_error
echo.
echo Setup failed. Please check that Python is installed correctly and internet is available.
pause
exit /b 1
