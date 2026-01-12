import httpx
from dataclasses import dataclass
from typing import Optional
from app.config import get_settings


@dataclass
class SummaryResult:
    corrected_text: str
    summary: str  # Summary in original language
    summary_en: str  # English translation
    sentiment: str  # positive, negative, neutral
    emotion: str  # angry, frustrated, happy, confused, calm, urgent
    category: str  # sales_inquiry, existing_order, new_inquiry, complaint, general
    priority: str  # low, default, high
    email_subject: str  # Short email subject line for notifications


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
1. CORRECT the transcript: Fix obvious speech-to-text errors (wrong words, missing punctuation, unclear sentences). Keep the meaning intact. Keep in the original language.
2. SUMMARIZE for support: Create a brief, actionable summary (2-3 sentences max) that tells a support agent:
   - Who is calling (name if mentioned)
   - What they want/need
   - Any callback number or urgency
   Write TWO summaries:
   - "summary": In the SAME LANGUAGE as the voicemail (e.g., German if the caller spoke German)
   - "summary_en": Always in ENGLISH (translation of the summary)
3. CREATE an email subject line (5-10 words max):
   - Format: "Caller Name - Topic" (e.g., "Max Müller - Order status inquiry")
   - If no name mentioned, use "Anruf" or "Call"
   - Keep it SHORT and scannable
   - Always in the ORIGINAL LANGUAGE of the voicemail
4. CLASSIFY the voicemail:
   - sentiment: "positive", "negative", or "neutral"
   - emotion: "angry", "frustrated", "happy", "confused", "calm", or "urgent"
   - category: One of:
     * "sales_inquiry" - Questions about products/services, pricing, availability
     * "existing_order" - Questions about an existing order, delivery, tracking
     * "new_inquiry" - New customer, first contact, general interest
     * "complaint" - Unhappy customer, issues, problems
     * "general" - Other/general questions
   - priority: "low", "default", or "high"
     * "low" - Non-urgent, informational, can wait
     * "default" - Normal priority, standard response time
     * "high" - Urgent, angry caller, time-sensitive, needs immediate attention

Output format (JSON):
{
  "corrected_text": "The corrected transcript in original language...",
  "summary": "Brief summary in ORIGINAL LANGUAGE...",
  "summary_en": "Brief summary in ENGLISH...",
  "email_subject": "Caller Name - Topic",
  "sentiment": "positive|negative|neutral",
  "emotion": "angry|frustrated|happy|confused|calm|urgent",
  "category": "sales_inquiry|existing_order|new_inquiry|complaint|general",
  "priority": "low|default|high"
}

Important:
- Preserve the caller's intent and key details
- The corrected text should be readable and professional
- The summary should be concise and actionable
- The email_subject must be very short (5-10 words max)
- Be conservative with high priority - only for genuinely urgent situations
- If the transcript is very short or empty, use neutral/calm/general/default as defaults"""

        user_prompt = f"""Process this voicemail transcript (language: {language}):

TRANSCRIPT:
{transcript}

Return JSON with corrected_text, summary (in original language), summary_en (English), email_subject, sentiment, emotion, category, and priority."""

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
                summary = parsed.get("summary", "No summary available")
                summary_en = parsed.get("summary_en", summary)  # Fallback to original if no translation
                return SummaryResult(
                    corrected_text=parsed.get("corrected_text", transcript),
                    summary=summary,
                    summary_en=summary_en,
                    sentiment=parsed.get("sentiment", "neutral"),
                    emotion=parsed.get("emotion", "calm"),
                    category=parsed.get("category", "general"),
                    priority=parsed.get("priority", "default"),
                    email_subject=parsed.get("email_subject", "Voicemail"),
                )
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return SummaryResult(
                    corrected_text=transcript,
                    summary=content[:500] if content else "Processing failed",
                    summary_en=content[:500] if content else "Processing failed",
                    sentiment="neutral",
                    emotion="calm",
                    category="general",
                    priority="default",
                    email_subject="Voicemail",
                )
