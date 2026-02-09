# SignalFrame Video Summarizer

A dual-mode video summarizer with a polished frontend and production-style Flask API:
- Summarize from YouTube URLs (transcript-based)
- Summarize uploaded media files (transcription + summarization)

## Features
- Unique dual-input UX (YouTube mode and Upload mode)
- Structured markdown summaries with configurable depth (`brief`, `standard`, `deep`)
- Optional focus control (guide the summary toward a topic)
- Metadata-rich responses (source, model, word count, language, video id/filename)
- Chunked summarization for long transcripts
- Better backend validation and error handling

## Project Structure
- `/Users/madhu/youtube_summarizer/backend/app.py` Flask API
- `/Users/madhu/youtube_summarizer/backend/summarizer.py` summarization/transcription services
- `/Users/madhu/youtube_summarizer/frontend/index.html` frontend app

## Backend Setup
1. Go to backend:
   ```bash
   cd /Users/madhu/youtube_summarizer/backend
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables:
   - Required for summarization:
     - `OPENROUTER_API_KEY`, or `OPENAI_API_KEY`, or `GEMINI_API_KEY` / `GOOGLE_API_KEY` (Google AI Studio)
   - Required for file uploads:
     - `OPENAI_API_KEY` (used for transcription)
   - Optional:
     - `OPENROUTER_MODEL` (default: `meta-llama/llama-3.3-70b-instruct:free`)
     - `OPENAI_SUMMARY_MODEL` (default: `gpt-4o-mini`)
     - `OPENAI_TRANSCRIPTION_MODEL` (default: `whisper-1`)
     - `GEMINI_MODEL` (default: `gemini-2.5-flash`)
     - `GEMINI_BASE_URL` (default: `https://generativelanguage.googleapis.com/v1beta/openai/`)
     - `MAX_UPLOAD_MB` (default: `200`)
     - `PORT` (default: `7860`)

4. Run server:
   ```bash
   python3 app.py
   ```

## Frontend Usage
Open:
- `/Users/madhu/youtube_summarizer/frontend/index.html`

If opened via `file://`, frontend automatically calls `http://127.0.0.1:7860`.
If served from the same origin as backend, it uses relative API routes.

## API Endpoints
- `GET /api/health`
- `POST /api/summarize/youtube`
  - JSON body:
    ```json
    {
      "url": "https://www.youtube.com/watch?v=...",
      "length": "standard",
      "focus": "optional focus"
    }
    ```
- `POST /api/summarize/upload`
  - `multipart/form-data`
  - Fields:
    - `video` (file)
    - `length` (`brief|standard|deep`)
    - `focus` (optional string)

## Notes
- YouTube summarization depends on caption availability for the target video.
- Upload transcription uses OpenAI audio transcription API, so a valid `OPENAI_API_KEY` is needed.
