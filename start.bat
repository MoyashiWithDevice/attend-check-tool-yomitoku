@echo off
REM 出席確認ツール起動バッチファイル
REM UIサーバー（Vite）とバックエンドサーバー（Uvicorn）を同時に起動します
REM conda環境「ocr」を有効化してから各サーバーを起動します

echo Starting servers...

REM UIサーバーを新しいウィンドウで起動（conda activate ocr → uiディレクトリでnpm run dev）
start "UI Server (Vite)" cmd /k "conda activate ocr && cd /d %~dp0ui && npm run dev"

timeout /t 1 /nobreak > nul

REM バックエンドサーバーを新しいウィンドウで起動（conda activate ocr → ルートディレクトリでuvicorn）
start "Backend Server (Uvicorn)" cmd /k "conda activate ocr && cd /d %~dp0 && uvicorn backend.server:app --reload"

echo Both servers have been started in separate windows.
echo UI Server: http://localhost:5173 (default Vite port)
echo Backend Server: http://localhost:8000 (default Uvicorn port)
