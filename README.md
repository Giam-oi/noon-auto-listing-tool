# Noon Auto Listing Tool

An experimental pipeline for turning supplier product data into Noon ZSKU listing drafts and Content API payloads.

The tool currently supports:

- 1688 product collection with anti-bot detection
- saved HTML ingestion for browser-verified 1688 pages
- product normalization and category classification
- rule-based listing generation with optional OpenAI-compatible or native Gemini AI generation
- image suite generation for local review
- UAE/KSA price and virtual stock calculation
- Noon bulk workbook/CSV export
- Noon Content API category/attribute sync
- Noon Content API upsert and GetContent status checks
- Windows desktop GUI for bulk pasted 1688 URLs and Excel URL import

## Status

This project is an MVP. It can submit content through Noon Content API when credentials and category metadata are configured. Final activation on Noon still depends on marketplace requirements such as public image URLs, Arabic content, QC, and account permissions.

Do not commit credentials, business spreadsheets, generated runs, or downloaded marketplace metadata.

## Requirements

- Python 3.11+
- Noon partner API credentials
- Network access to Noon APIs
- Optional: OpenAI-compatible API key for AI-generated listing content, including Gemini

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Configuration

Copy the example config and edit local values:

```powershell
Copy-Item config.example.json config.local.json
```

Sensitive values should be supplied outside Git:

- Noon credentials: pass with `--credentials path\to\api.json`
- OpenAI key: set `OPENAI_API_KEY`
- Gemini key: set `GEMINI_API_KEY`
- 1688 cookie, if needed: set `ALI1688_COOKIE`

`config.local.json`, `.env*`, `api.json`, run outputs, and spreadsheets are ignored by Git.

## Desktop GUI

Start the desktop app from source:

```powershell
python desktop_app.py
```

In the app:

- paste only the Gemini API key, not the full curl command
- select the Noon `api.json` credential file if you want API probing or live submission
- paste the 1688 cookie only if 1688 blocks public collection
- keep auto-submit off until generated files have been reviewed

The desktop app saves local settings to `%APPDATA%\NoonListingTool\desktop.local.json`.

Build the Windows EXE:

```powershell
.\scripts\build_exe.ps1
```

The output will be:

```text
dist\NoonListingTool\NoonListingTool.exe
```

## Basic Usage

Run a sample product:

```powershell
python run.py sample --config config.local.json
```

Build from a 1688 URL:

```powershell
python run.py build-url "https://detail.1688.com/offer/xxxx.html" --config config.local.json
```

Build from saved 1688 HTML:

```powershell
python run.py build-html path\to\product.html --source-url "https://detail.1688.com/offer/xxxx.html" --config config.local.json
```

Build from Excel:

```powershell
python run.py build-excel path\to\input.xlsx --config config.local.json
```

Each run is written to:

```text
runs/<run_id>/
```

Typical outputs:

- `standard_products.json`
- `validation_report.json`
- `exports/review_workbook.xlsx`
- `exports/noon_bulk_UAE.xlsx`
- `exports/noon_bulk_KSA.xlsx`
- `content_api_payloads/*.json`
- `images/<sku>/`

## Noon Content API

Probe credentials and API access:

```powershell
python run.py probe-api --credentials path\to\api.json --config config.local.json
```

Sync categories:

```powershell
python run.py sync-content-categories --credentials path\to\api.json --config config.local.json
```

Sync category attributes:

```powershell
python run.py sync-content-categories --credentials path\to\api.json --attributes --workers 2 --config config.local.json
```

Generated category metadata is stored under `templates/content_api/` and is intentionally ignored by Git.

Build payloads without submitting:

```powershell
python run.py submit-content runs\<run_id> --credentials path\to\api.json --config config.local.json
```

Submit live:

```powershell
python run.py submit-content runs\<run_id> --credentials path\to\api.json --live --config config.local.json
```

Check Noon content status:

```powershell
python run.py get-content <sku_parent> --credentials path\to\api.json --config config.local.json
```

## AI Listing Generation

By default, listing generation is rule-based and does not require an API key.

To enable OpenAI-compatible generation:

1. Set `ai.enabled` to `true` in `config.local.json`.
2. Set `OPENAI_API_KEY`.
3. Configure `ai.base_url` and `ai.model` if using a compatible provider.

Gemini can be used through Google's native `generateContent` endpoint. For local Gemini 3 Flash configuration:

```powershell
Copy-Item config.gemini.example.json config.local.json
$env:GEMINI_API_KEY="your-gemini-api-key"
python run.py sample --config config.local.json
```

The Gemini example config uses:

```json
{
  "ai": {
    "enabled": true,
    "provider": "gemini_native",
    "base_url": "https://generativelanguage.googleapis.com/v1beta",
    "api_key_env": "GEMINI_API_KEY",
    "model": "gemini-3-flash-preview"
  }
}
```

Do not commit real API keys. If the Gemini API rejects the preview model name, change `ai.model` to the currently enabled Flash model for your API key.

## Image Publishing

Noon Content API requires public `http(s)` image URLs. Local generated images are useful for review but cannot activate a product on Noon.

Two supported patterns:

- configure `images.publish_dir` and `images.public_base_url` for a static server/CDN
- add an uploader for Cloudinary, Cloudflare R2, S3, or another image host

## Repository Hygiene

This repository excludes:

- API keys and private keys
- local config
- business spreadsheets
- generated runs and images
- downloaded Noon category metadata
- Python caches

Before publishing, run:

```powershell
git status --short
git ls-files
```
