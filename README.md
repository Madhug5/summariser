# YouTube Summariser

AI-powered video summarizer for:
- YouTube links (transcript-based)
- Uploaded media files (transcription + summarization)

The app includes:
- Flask backend API
- Single-page frontend UI
- Support for multiple summary providers (OpenRouter, Google Gemini via AI Studio key, OpenAI)

## Features

- Summarize YouTube videos using available captions/transcripts.
- Upload media files (`mp4`, `webm`, `mp3`, `wav`, `m4a`, `mpeg`, `mpga`) and summarize them.
- Summary depth control: `brief`, `standard`, `deep`.
- Optional focus prompt to guide summary output.
- Structured markdown output:
  - Signal (TL;DR)
  - Core Frames
  - Edge Insights
  - Action Plan
- Metadata returned with each summary (provider, model, word count, source details).

## Tech Stack

- Python 3
- Flask + Flask-CORS
- OpenAI SDK (used for OpenAI, OpenRouter, and Gemini OpenAI-compatible endpoint)
- youtube-transcript-api
- python-dotenv
- HTML/CSS/JS frontend

## Project Structure

```text
youtube_summarizer/
  backend/
    app.py
    summarizer.py
    requirements.txt
    .env.example
  frontend/
    index.html
  README.md
```

## Setup

### 1) Backend setup

```bash
cd /Users/madhu/youtube_summarizer/backend
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

### 2) Configure environment variables

Create env file:

```bash
cp /Users/madhu/youtube_summarizer/backend/.env.example /Users/madhu/youtube_summarizer/backend/.env
```

Edit `/Users/madhu/youtube_summarizer/backend/.env` and set keys:

- For summarization (any one is enough):
  - `OPENROUTER_API_KEY`
  - `GEMINI_API_KEY` or `GOOGLE_API_KEY` (Google AI Studio)
  - `OPENAI_API_KEY`
- For upload transcription:
  - `OPENAI_API_KEY` (required because transcription uses OpenAI audio API)

Optional model/env settings:

- `OPENROUTER_MODEL` (default: `meta-llama/llama-3.3-70b-instruct:free`)
- `OPENAI_SUMMARY_MODEL` (default: `gpt-4o-mini`)
- `OPENAI_TRANSCRIPTION_MODEL` (default: `whisper-1`)
- `GEMINI_MODEL` (default: `gemini-2.5-flash`)
- `GEMINI_BASE_URL` (default: `https://generativelanguage.googleapis.com/v1beta/openai/`)
- `MAX_UPLOAD_MB` (default: `200`)
- `SUMMARY_CHUNK_CHARS` (default: `12000`)
- `YT_LANGS` (default: `en,en-US`)
- `PORT` (default: `7860`)

### 3) Run backend

```bash
cd /Users/madhu/youtube_summarizer/backend
source .venv/bin/activate
python3 app.py
```

Backend runs at:
- `http://127.0.0.1:7860`

### 4) Open frontend

Open:
- `/Users/madhu/youtube_summarizer/frontend/index.html`

If opened as `file://`, frontend targets `http://127.0.0.1:7860` automatically.

## API Endpoints

### Health

- `GET /api/health`

Example response:

```json
{
  "status": "ok",
  "version": "2.0.0"
}
```

### Summarize YouTube

- `POST /api/summarize/youtube`
- Content-Type: `application/json`

Request:

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "length": "standard",
  "focus": "optional focus text"
}
```

### Summarize Upload

- `POST /api/summarize/upload`
- Content-Type: `multipart/form-data`

Form fields:
- `video` (file)
- `length` (`brief|standard|deep`)
- `focus` (optional text)

### Backward-compatible route

- `POST /summarize` (YouTube flow compatibility route)

## Provider Priority

Summary provider is selected in this order:
1. `OPENROUTER_API_KEY`
2. `GEMINI_API_KEY` / `GOOGLE_API_KEY`
3. `OPENAI_API_KEY`

## Notes

- YouTube summaries require available captions/transcripts for the video.
- If transcript is long, the backend chunk-summarizes and merges final output.
- Never commit real API keys to Git.

## Troubleshooting

### Error: `Set OPENROUTER_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, or GOOGLE_API_KEY before summarizing.`

Check:
1. `/Users/madhu/youtube_summarizer/backend/.env` exists.
2. At least one summary key is set and non-empty.
3. Backend was restarted after env updates.

### Upload summarization fails with transcription error

Ensure `OPENAI_API_KEY` is set (required for media transcription).

### `zsh: command not found: #`

You pasted a comment line. Run only actual commands, or enable:

```bash
setopt interactive_comments
```

## License

This project is for educational/personal use. Add your preferred license before public distribution.
