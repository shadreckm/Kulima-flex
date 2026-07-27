@echo off
cd /d "c:\Users\HP\Desktop\Kulima vc brain"
echo ===== SUITE 1: test_export_integrity.py =====
venv\Scripts\python.exe -m pytest test_export_integrity.py -v
echo EXIT1=%ERRORLEVEL%
echo.
echo ===== SUITE 2: test_ask_ic_integrity.py =====
venv\Scripts\python.exe -m pytest test_ask_ic_integrity.py -v
echo EXIT2=%ERRORLEVEL%
echo.
echo ===== SUITE 3: test_orchestrator_integrity.py =====
venv\Scripts\python.exe -m pytest test_orchestrator_integrity.py -v
echo EXIT3=%ERRORLEVEL%
echo.
echo ===== SUITE 4: test_evidence_integrity.py =====
venv\Scripts\python.exe -m pytest test_evidence_integrity.py -v
echo EXIT4=%ERRORLEVEL%
echo.
echo ===== SUITE 5: test_db_trust_layer.py =====
venv\Scripts\python.exe -m pytest test_db_trust_layer.py -v
echo EXIT5=%ERRORLEVEL%
echo.
echo ===== SUITE 6: test_models_trust_layer.py =====
venv\Scripts\python.exe -m pytest test_models_trust_layer.py -v
echo EXIT6=%ERRORLEVEL%
echo.
echo ===== SUITE 7: test_pipeline.py =====
venv\Scripts\python.exe -m pytest test_pipeline.py -v
echo EXIT7=%ERRORLEVEL%
echo.
echo ===== SUITE 8: test_comparison.py =====
venv\Scripts\python.exe -m pytest test_comparison.py -v
echo EXIT8=%ERRORLEVEL%
echo.
echo ===== ALL DONE =====
