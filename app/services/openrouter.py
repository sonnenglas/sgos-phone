import httpx
from dataclasses import dataclass
from typing import Optional
from app.config import get_settings


@dataclass
class SummaryResult:
    corrected_text: str
    summary: str
    sentiment: str  # positive, negative, neutral
    emotion: str  # angry, frustrated, happy, confused, calm, urgent
    category: str  # sales_inquiry, existing_order, new_inquiry, complaint, general
    is_urgent: bool


class OpenRouterService:
    """LLM-powered transcript correction, summarization, and classification via OpenRouter."""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.openrouter_api_key
        self.base_url = self.settings.openrouter_base_url
        self.model = self.settings.openrouter_model

    async def process_transcript(self, transcript: str, language: str = "de") -> SummaryResult:
        """
        Process a voicemail transcript:
        1. Correct obvious transcription errors
        2. Generate a concise summary for customer support
        3. Classify sentiment, emotion, category, and urgency
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://phone.sgos.local",
            "X-Title": "SGOS Phone - Voicemail Processing",
        }

        system_prompt = """You are an assistant that processes voicemail transcriptions for a customer support team.

Your task is to:
1. CORRECT the transcript: Fix obvious speech-to-text errors (wrong words, missing punctuation, unclear sentences). Keep the meaning intact.
2. SUMMARIZE for support: Create a brief, actionable summary (2-3 sentences max) that tells a support agent:
   - Who is calling (name if mentioned)
   - What they want/need
   - Any callback number or urgency
3. CLASSIFY the voicemail:
   - sentiment: "positive", "negative", or "neutral"
   - emotion: "angry", "frustrated", "happy", "confused", "calm", or "urgent"
   - category: One of:
     * "sales_inquiry" - Questions about products/services, pricing, availability
     * "existing_order" - Questions about an existing order, delivery, tracking
     * "new_inquiry" - New customer, first contact, general interest
     * "complaint" - Unhappy customer, issues, problems
     * "general" - Other/general questions
   - is_urgent: true if the caller needs immediate attention (angry, time-sensitive, emergency)

Output format (JSON):
{
  "corrected_text": "The corrected transcript text...",
  "summary": "Brief summary for support agent...",
  "sentiment": "positive|negative|neutral",
  "emotion": "angry|frustrated|happy|confused|calm|urgent",
  "category": "sales_inquiry|existing_order|new_inquiry|complaint|general",
  "is_urgent": true|false
}

Important:
- Preserve the caller's intent and key details
- The corrected text should be readable and professional
- The summary should be concise and actionable
- Be conservative with is_urgent - only mark true for genuinely urgent situations
- If the transcript is very short or empty, use neutral/calm/general as defaults"""

        user_prompt = f"""Process this voicemail transcript (language: {language}):

TRANSCRIPT:
{transcript}

Return JSON with corrected_text, summary, sentiment, emotion, category, and is_urgent."""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Parse JSON response
            import json
            try:
                parsed = json.loads(content)
                return SummaryResult(
                    corrected_text=parsed.get("corrected_text", transcript),
                    summary=parsed.get("summary", "No summary available"),
                    sentiment=parsed.get("sentiment", "neutral"),
                    emotion=parsed.get("emotion", "calm"),
                    category=parsed.get("category", "general"),
                    is_urgent=parsed.get("is_urgent", False),
                )
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return SummaryResult(
                    corrected_text=transcript,
                    summary=content[:500] if content else "Processing failed",
                    sentiment="neutral",
                    emotion="calm",
                    category="general",
                    is_urgent=False,
                )
