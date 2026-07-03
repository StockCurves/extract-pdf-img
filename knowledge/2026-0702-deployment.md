# 2026-07-02 部署可行性與方案評估

## 結論

這個網頁可以 deploy 到網路上供人使用，但目前比較像「可公開 demo 的 Flask 工具」，還不是可以直接放到公網任人上傳 PDF 的 production 服務。

目前架構是：

- 前端把 PDF 上傳到 `/upload`
- 後端用 `extract_figures.extract(...)` 與 PyMuPDF 處理 PDF
- 輸出 PDF/PNG 到本機 `output/`
- 再用 `/output/<path>` 直接提供預覽與下載

這個架構適合快速 demo，但公開上線前要先處理暫存清理、檔名隔離、上傳大小、併發、隱私與安全風險。

## 目前部署限制

這不是純靜態頁。核心功能需要 Python/Flask 後端與 PyMuPDF，因此不能只丟到 GitHub Pages 或其他純靜態 hosting，除非把後端抽掉或把 PDF extraction 重寫成瀏覽器端處理。

Flask production 部署也不應使用 `app.run(debug=True)` 或內建 development server。正式上線應改用 WSGI server 或 hosting platform，例如 Gunicorn、Waitress、container platform 或雲端 PaaS。

## 方案與 Tradeoff

### 1. PaaS / Container 平台

代表平台：Fly.io、Render、Railway、Google Cloud Run。

這是目前最適合第一版公開 demo 的方案。

優點：

- 改動量小，可以保留 Flask + PyMuPDF 架構
- 補 `requirements.txt`、`gunicorn`、可能再加 `Dockerfile` 就能部署
- 比 serverless 更適合 PDF 這種 CPU、記憶體與暫存檔需求比較重的工作
- 後續可逐步加 worker、object storage、health check

Tradeoff：

- 要處理 ephemeral disk，不能假設 `output/` 永久存在
- 要做暫存檔清理，避免 PDF 與 PNG 越堆越多
- 大 PDF 會消耗 CPU/RAM，可能需要付費方案
- 可能有 cold start、region、免費額度與 timeout 限制

建議：第一版 demo 優先選這條路。

### 2. VPS / 自管 Docker

代表平台：Hetzner、DigitalOcean、AWS Lightsail。

這是最穩、最可控的部署方式。

優點：

- 適合 CPU/記憶體/暫存檔比較重的 PDF 處理
- 可以掛磁碟、設定 Nginx + Gunicorn、控制 worker 數
- 長任務、檔案清理、背景 queue 都比較容易掌控

Tradeoff：

- 要自己維護 OS、TLS、Nginx、安全更新、監控
- 初期 DevOps 成本比 PaaS 高
- 如果只是要快速分享 demo，會稍微過重

建議：若要長期穩定公開服務，或要處理較大 PDF，可以考慮。

### 3. Vercel / Netlify Serverless

技術上可以做，但不建議作為主方案。

Vercel Python runtime 支援 Flask/WSGI entrypoint，這個 repo 的 `app.py` 與 `app` 形式上符合。但 PDF 上傳與輸出很容易碰到 request/response payload、timeout、bundle size、ephemeral filesystem 等限制。

優點：

- 部署體驗好，網址與 preview deployment 很方便
- 適合輕量 API 或前端靜態頁

Tradeoff：

- PDF 檔案常超過 serverless request body 限制
- 處理時間可能超過 function duration
- 本機 `output/` 檔案輸出不適合 serverless 模型
- 需要重構成 object storage + signed upload/download 才比較合理

建議：不作為第一版主路線。除非之後拆成「靜態前端 + 獨立後端 API」。

### 4. 純靜態 Hosting

代表平台：GitHub Pages、Cloudflare Pages、Netlify static hosting。

目前不適合。

優點：

- 便宜、穩、部署簡單
- 適合展示頁、說明文件、純前端工具

Tradeoff：

- 不能直接跑 Python/Flask
- 不能使用目前的 PyMuPDF extraction 後端
- 若要使用，需要重寫成瀏覽器端 PDF 處理，或只放前端，後端另部署

建議：可作為前端 hosting，但不能單獨承載目前完整功能。

### 5. 前端靜態 + 後端 API 分離

前端放 GitHub Pages / Vercel / Cloudflare Pages，後端 API 放 Fly.io / Cloud Run / VPS。

優點：

- 長期架構最乾淨
- 前端部署便宜且快速
- 後端可以獨立調整 CPU、RAM、timeout、queue、storage
- 比較容易逐步加入 object storage、job status、background worker

Tradeoff：

- 初期工程量中等
- 要處理 CORS、API URL、上傳流程、結果存取權限
- 若沒有多人或大量使用需求，第一版可能有點早

建議：若目標是正式公開產品，這是長期方向；若只是先給人試用，先用單體 Flask container 比較快。

## 公開前建議補強

部署前至少應補：

- `requirements.txt` 或 `pyproject.toml`
- production WSGI 啟動方式，例如 `gunicorn app:app`
- `MAX_CONTENT_LENGTH` 限制 PDF 上傳大小
- 每次上傳使用隨機 job id 目錄，不要只用原始檔名轉目錄
- 定期刪除上傳 PDF、輸出 PNG、metadata 與 QA artifact
- 不要用可猜測路徑長期公開使用者檔案
- rate limit，避免被大量上傳拖垮
- 錯誤處理與使用者可讀的錯誤訊息
- logging 與 health check endpoint
- 公開服務前做安全檢查，特別是任意 PDF 上傳與檔案 serving

若要正式多人使用，應再考慮：

- object storage，例如 S3/R2/GCS
- background job queue
- job status API
- 使用者 session 或短效 token
- 處理完成後自動清除檔案
- privacy policy 或明確告知檔案保存時間

## gstack 適合的 Skills

這個部署評估適合使用下列 gstack skills：

- `/plan-eng-review`：評估單體 Flask、前後端分離、worker queue、storage 架構。
- `/cso`：公開 PDF 上傳前做安全檢查，包含檔案處理、路徑、上傳限制、依賴風險。
- `/setup-deploy`：選平台、設定 production URL、health check、部署命令。
- `/qa-only` 或 `/qa`：部署後實際上傳 PDF、檢查 viewer、下載 ZIP、錯誤流程。
- `/benchmark`：測大 PDF 的處理時間、頁面載入、記憶體與效能風險。
- `/canary`：上線後監控公開站是否壞掉。
- `/ship`：部署策略定案後，包 commit / PR / release 流程。

建議使用順序：

1. `/plan-eng-review`：先決定部署架構。
2. `/cso`：先找公開上傳 PDF 的安全風險。
3. `/setup-deploy`：再做實際平台與部署設定。
4. `/qa-only` 或 `/qa`：部署後驗證真實使用流程。
5. `/benchmark`：用較大 PDF 測效能與 timeout。
6. `/canary`：若真的公開，加入上線後監控。

## 推薦路線

第一版公開 demo：選 Fly.io、Render、Railway 或 Cloud Run 類的 container hosting，保留單體 Flask 架構，先補 production 啟動、上傳限制、隨機 job id、暫存清理與基本安全限制。

正式產品方向：改成前端靜態 hosting + 後端 API/container + object storage + background job queue。

不建議第一版就用 Vercel serverless 承載整個 PDF extraction 流程，因為大 PDF 上傳、處理時間、本機輸出檔與下載流程都不太符合 serverless 的限制。
