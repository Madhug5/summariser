from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi


SUPPORTED_UPLOAD_EXTENSIONS = {
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".m4a",
    ".wav",
    ".webm",
}
ALLOWED_LENGTHS = {"brief", "standard", "deep"}
DEFAULT_CHUNK_SIZE = int(os.getenv("SUMMARY_CHUNK_CHARS", "12000"))


class SummarizerError(Exception):
    status_code = 500


class ValidationError(SummarizerError):
    status_code = 400


class ProviderConfigurationError(SummarizerError):
    status_code = 500


class TranscriptError(SummarizerError):
    status_code = 422


@dataclass
class SummaryOptions:
    length: str = "standard"
    focus: str = ""


@dataclass
class RuntimeConfig:
    summary_client: OpenAI
    summary_model: str
    summary_provider: str
    transcription_client: OpenAI | None
    transcription_model: str | None


def _build_runtime() -> RuntimeConfig:
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if openrouter_key:
        summary_client = OpenAI(
            api_key=openrouter_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )
        summary_model = os.getenv(
            "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"
        )
        summary_provider = "openrouter"
    elif gemini_key:
        # Gemini is exposed through an OpenAI-compatible endpoint for chat completions.
        summary_client = OpenAI(
            api_key=gemini_key,
            base_url=os.getenv(
                "GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
        )
        summary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        summary_provider = "google-gemini"
    elif openai_key:
        summary_client = OpenAI(api_key=openai_key)
        summary_model = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")
        summary_provider = "openai"
    else:
        raise ProviderConfigurationError(
            "Set OPENROUTER_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, or GOOGLE_API_KEY before summarizing."
        )

    transcription_client = OpenAI(api_key=openai_key) if openai_key else None
    transcription_model = (
        os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")
        if transcription_client
        else None
    )

    return RuntimeConfig(
        summary_client=summary_client,
        summary_model=summary_model,
        summary_provider=summary_provider,
        transcription_client=transcription_client,
        transcription_model=transcription_model,
    )


def normalize_options(length: str | None, focus: str | None) -> SummaryOptions:
    normalized_length = (length or "standard").strip().lower()
    if normalized_length not in ALLOWED_LENGTHS:
        supported = ", ".join(sorted(ALLOWED_LENGTHS))
        raise ValidationError(f"Invalid length. Choose one of: {supported}.")

    normalized_focus = (focus or "").strip()
    if len(normalized_focus) > 240:
        raise ValidationError("Focus should be 240 characters or less.")

    return SummaryOptions(length=normalized_length, focus=normalized_focus)


def _is_valid_youtube_id(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"[0-9A-Za-z_-]{11}", value))


def extract_video_id(youtube_url: str) -> str:
    if not youtube_url or not youtube_url.strip():
        raise ValidationError("Please provide a YouTube URL.")

    youtube_url = youtube_url.strip()
    parsed = urlparse(youtube_url)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host.endswith("youtu.be") and path_parts and _is_valid_youtube_id(path_parts[0]):
        return path_parts[0]

    if "youtube.com" in host:
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if _is_valid_youtube_id(query_id):
            return query_id

        if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live", "v"}:
            if _is_valid_youtube_id(path_parts[1]):
                return path_parts[1]

    fallback_match = re.search(r"([0-9A-Za-z_-]{11})", youtube_url)
    if fallback_match:
        return fallback_match.group(1)

    raise ValidationError("Invalid YouTube URL.")


def _extract_snippet_text(snippet: object) -> str:
    if isinstance(snippet, dict):
        text = snippet.get("text", "")
    else:
        text = getattr(snippet, "text", "")
    return re.sub(r"\s+", " ", text or "").strip()


def get_youtube_transcript(video_id: str) -> tuple[str, str]:
    api = YouTubeTranscriptApi()
    language_preferences = [lang.strip() for lang in os.getenv("YT_LANGS", "en,en-US").split(",") if lang.strip()]

    try:
        transcript_list = api.list(video_id)
    except Exception as exc:
        raise TranscriptError(f"Could not read transcripts for this video: {exc}") from exc

    transcript = None
    for finder in ("find_manually_created_transcript", "find_generated_transcript", "find_transcript"):
        try:
            transcript = getattr(transcript_list, finder)(language_preferences)
            break
        except Exception:
            continue

    if transcript is None:
        try:
            transcript = next(iter(transcript_list))
        except StopIteration as exc:
            raise TranscriptError("This video does not have captions available.") from exc
        except Exception as exc:
            raise TranscriptError(f"Could not locate a usable transcript: {exc}") from exc

    try:
        transcript_data = transcript.fetch()
    except Exception as exc:
        raise TranscriptError(f"Transcript fetch failed: {exc}") from exc

    chunks = [_extract_snippet_text(item) for item in transcript_data]
    full_text = " ".join(part for part in chunks if part).strip()
    if not full_text:
        raise TranscriptError("Transcript was empty for this video.")

    language = getattr(transcript, "language_code", "unknown")
    return full_text, language


def validate_upload_filename(filename: str) -> None:
    suffix = Path(filename or "").suffix.lower()
    if suffix in SUPPORTED_UPLOAD_EXTENSIONS:
        return

    allowed = ", ".join(sorted(ext.lstrip(".") for ext in SUPPORTED_UPLOAD_EXTENSIONS))
    raise ValidationError(f"Unsupported file type. Allowed: {allowed}.")


def transcribe_uploaded_media(file_path: str) -> str:
    runtime = _build_runtime()
    if not runtime.transcription_client or not runtime.transcription_model:
        raise ProviderConfigurationError(
            "File uploads require OPENAI_API_KEY so the media can be transcribed."
        )

    try:
        with open(file_path, "rb") as media_file:
            response = runtime.transcription_client.audio.transcriptions.create(
                model=runtime.transcription_model,
                file=media_file,
                response_format="text",
            )
    except Exception as exc:
        raise TranscriptError(f"Failed to transcribe uploaded media: {exc}") from exc

    if isinstance(response, str):
        transcript = response.strip()
    else:
        transcript = getattr(response, "text", "").strip()

    if not transcript:
        raise TranscriptError("Transcription completed but no text was returned.")

    return transcript


def _split_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for word in words:
        word_length = len(word) + 1
        if current and current_length + word_length > chunk_size:
            chunks.append(" ".join(current))
            current = [word]
            current_length = len(word)
        else:
            current.append(word)
            current_length += word_length

    if current:
        chunks.append(" ".join(current))

    return chunks


def _length_hint(length: str) -> str:
    hints = {
        "brief": "Keep each section short and punchy. Prioritize clarity over depth.",
        "standard": "Balance clarity and depth. Give enough detail to stand alone.",
        "deep": "Provide dense insights, context, and practical takeaways.",
    }
    return hints[length]


def _summary_blueprint(options: SummaryOptions) -> str:
    focus_line = (
        f"Primary focus requested by the user: {options.focus}."
        if options.focus
        else "No special focus provided; infer the most useful focus."
    )
    return f"""
Create a structured markdown summary with this exact section order:
1. Signal: one paragraph TL;DR.
2. Core Frames: 4-7 bullet points with the main ideas.
3. Edge Insights: 3 bullet points with non-obvious takeaways.
4. Action Plan: 3 concrete next actions for a learner or builder.

Constraints:
- Use plain language.
- Avoid filler and repetition.
- Highlight only evidence-backed claims from the transcript.
- {focus_line}
- {_length_hint(options.length)}
""".strip()


def _chat_completion(client: OpenAI, model: str, system_prompt: str, user_prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
    except Exception as exc:
        raise SummarizerError(f"Summarization request failed: {exc}") from exc

    message = response.choices[0].message.content
    if not message:
        raise SummarizerError("Summarization response was empty.")
    return message.strip()


def summarize_transcript(transcript: str, options: SummaryOptions) -> tuple[str, str, str]:
    runtime = _build_runtime()
    chunks = _split_text(transcript)
    if not chunks:
        raise TranscriptError("Transcript is empty.")

    system_prompt = (
        "You are SignalFrame, a high-precision video summarizer. "
        "Write concise, useful markdown."
    )

    if len(chunks) == 1:
        user_prompt = f"""
{_summary_blueprint(options)}

Transcript:
{chunks[0]}
""".strip()
        summary = _chat_completion(
            runtime.summary_client, runtime.summary_model, system_prompt, user_prompt
        )
        return summary, runtime.summary_model, runtime.summary_provider

    chunk_summaries: list[str] = []
    total_chunks = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        chunk_prompt = f"""
You are summarizing chunk {index} of {total_chunks}.
Return 6-10 bullets that preserve facts and important context.
{_length_hint(options.length)}

Chunk text:
{chunk}
""".strip()
        chunk_summary = _chat_completion(
            runtime.summary_client, runtime.summary_model, system_prompt, chunk_prompt
        )
        chunk_summaries.append(f"Chunk {index}:\n{chunk_summary}")

    merge_prompt = f"""
{_summary_blueprint(options)}

Consolidate these chunk summaries into one coherent final output:
{os.linesep.join(chunk_summaries)}
""".strip()
    final_summary = _chat_completion(
        runtime.summary_client, runtime.summary_model, system_prompt, merge_prompt
    )
    return final_summary, runtime.summary_model, runtime.summary_provider


def _count_words(text: str) -> int:
    return len(text.split())


def summarize_youtube_url(
    youtube_url: str, length: str | None = None, focus: str | None = None
) -> dict:
    options = normalize_options(length=length, focus=focus)
    video_id = extract_video_id(youtube_url)
    transcript, language = get_youtube_transcript(video_id)
    summary, model, provider = summarize_transcript(transcript, options)

    return {
        "summary": summary,
        "meta": {
            "source": "youtube",
            "video_id": video_id,
            "language": language,
            "word_count": _count_words(transcript),
            "length": options.length,
            "focus": options.focus or None,
            "model": model,
            "provider": provider,
        },
    }


def summarize_uploaded_video(
    file_path: str,
    original_filename: str,
    length: str | None = None,
    focus: str | None = None,
) -> dict:
    options = normalize_options(length=length, focus=focus)
    validate_upload_filename(original_filename)
    transcript = transcribe_uploaded_media(file_path)
    summary, model, provider = summarize_transcript(transcript, options)

    return {
        "summary": summary,
        "meta": {
            "source": "upload",
            "filename": original_filename,
            "word_count": _count_words(transcript),
            "length": options.length,
            "focus": options.focus or None,
            "model": model,
            "provider": provider,
        },
    }


def summarize_video(youtube_url: str) -> str:
    """Backward-compatible helper used by older code paths."""
    return summarize_youtube_url(youtube_url)["summary"]
