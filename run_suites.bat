@echo off
cd /d "c:\Users\HP\Desktop\Kulima vc brain"
echo === Suite 1: test_export_integrity.py === > suite_results.txt
venv\Scripts\python.exe -m pytest test_export_integrity.py -v >> suite_results.txt 2>&1
echo EXITCODE=%ERRORLEVEL% >> suite_results.txt
if %ERRORLEVEL% neq 0 goto :done

echo. >> suite_results.txt
echo === Suite 2: test_ask_ic_integrity.py === >> suite_results.txt
venv\Scripts\python.exe -m pytest test_ask_ic_integrity.py -v >> suite_results.txt 2>&1
echo EXITCODE=%ERRORLEVEL% >> suite_results.txt
if %ERRORLEVEL% neq 0 goto :done

echo. >> suite_results.txt
echo === Suite 3: test_orchestrator_integrity.py === >> suite_results.txt
venv\Scripts\python.exe -m pytest test_orchestrator_integrity.py -v >> suite_results.txt 2>&1
echo EXITCODE=%ERRORLEVEL% >> suite_results.txt
if %ERRORLEVEL% neq 0 goto :done

echo. >> suite_results.txt
echo === Suite 4: test_evidence_integrity.py === >> suite_results.txt
venv\Scripts\python.exe -m pytest test_evidence_integrity.py -v >> suite_results.txt 2>&1
echo EXITCODE=%ERRORLEVEL% >> suite_results.txt
if %ERRORLEVEL% neq 0 goto :done

echo. >> suite_results.txt
echo === Suite 5: test_db_trust_layer.py === >> suite_results.txt
venv\Scripts\python.exe -m pytest test_db_trust_layer.py -v >> suite_results.txt 2>&1
echo EXITCODE=%ERRORLEVEL% >> suite_results.txt
if %ERRORLEVEL% neq 0 goto :done

echo. >> suite_results.txt
echo === Suite 6: test_models_trust_layer.py === >> suite_results.txt
venv\Scripts\python.exe -m pytest test_models_trust_layer.py -v >> suite_results.txt 2>&1
echo EXITCODE=%ERRORLEVEL% >> suite_results.txt
if %ERRORLEVEL% neq 0 goto :done

echo. >> suite_results.txt
echo === Suite 7: test_pipeline.py === >> suite_results.txt
venv\Scripts\python.exe -m pytest test_pipeline.py -v >> suite_results.txt 2>&1
echo EXITCODE=%ERRORLEVEL% >> suite_results.txt
if %ERRORLEVEL% neq 0 goto :done

echo. >> suite_results.txt
echo === Suite 8: test_comparison.py === >> suite_results.txt
venv\Scripts\python.exe -m pytest test_comparison.py -v >> suite_results.txt 2>&1
echo EXITCODE=%ERRORLEVEL% >> suite_results.txt
if %ERRORLEVEL% neq 0 goto :done

echo. >> suite_results.txt
echo === Suite 9: test_trust_layer_ui.py === >> suite_results.txt
venv\Scripts\python.exe -m pytest test_trust_layer_ui.py -v >> suite_results.txt 2>&1
echo EXITCODE=%ERRORLEVEL% >> suite_results.txt

:done
echo BATCH DONE >> suite_results.txt
