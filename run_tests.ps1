Set-Location 'c:\Users\HP\Desktop\Kulima vc brain'
$python = 'c:\Users\HP\Desktop\Kulima vc brain\venv\Scripts\python.exe'

Write-Host "=== TEST 1: test_ask_signals.py ===" 
$out1 = & $python -m pytest test_ask_signals.py -v 2>&1
$out1 | Out-File -FilePath 'pytest_out_1.txt' -Encoding utf8
Write-Host "TEST 1 DONE"

Write-Host "=== TEST 2: test_trust_graph_visualization.py ===" 
$out2 = & $python -m pytest test_trust_graph_visualization.py -v 2>&1
$out2 | Out-File -FilePath 'pytest_out_2.txt' -Encoding utf8
Write-Host "TEST 2 DONE"

Write-Host "=== TEST 3: test_export_integrity.py ===" 
$out3 = & $python -m pytest test_export_integrity.py -v 2>&1
$out3 | Out-File -FilePath 'pytest_out_3.txt' -Encoding utf8
Write-Host "TEST 3 DONE"

Write-Host "=== TEST 4: test_ask_ic_integrity.py ===" 
$out4 = & $python -m pytest test_ask_ic_integrity.py -v 2>&1
$out4 | Out-File -FilePath 'pytest_out_4.txt' -Encoding utf8
Write-Host "TEST 4 DONE"

Write-Host "=== TEST 5: test_evidence_integrity.py ===" 
$out5 = & $python -m pytest test_evidence_integrity.py -v 2>&1
$out5 | Out-File -FilePath 'pytest_out_5.txt' -Encoding utf8
Write-Host "TEST 5 DONE"

Write-Host "=== TEST 6: test_orchestrator_integrity.py ===" 
$out6 = & $python -m pytest test_orchestrator_integrity.py -v 2>&1
$out6 | Out-File -FilePath 'pytest_out_6.txt' -Encoding utf8
Write-Host "TEST 6 DONE"

Write-Host "=== TEST 7: test_pipeline.py ===" 
$out7 = & $python -m pytest test_pipeline.py -v 2>&1
$out7 | Out-File -FilePath 'pytest_out_7.txt' -Encoding utf8
Write-Host "TEST 7 DONE"

Write-Host "ALL TESTS DONE"
