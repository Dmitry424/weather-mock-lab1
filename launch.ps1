param([ValidateSet('server','tcp','udp','alerts','test')][string]$Mode='server')
$pythonRuntime = 'C:/Users/snoel/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
Set-Location -LiteralPath $PSScriptRoot
if ($Mode -eq 'test') { & $pythonRuntime -X utf8 -m unittest -v test_weather }
else { & $pythonRuntime -X utf8 weather_mock.py $Mode }
