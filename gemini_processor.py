"""
Google Gemini API processor for intelligent lead extraction.
Uses Gemini AI to parse natural language and extract structured lead information.
"""

import json
import logging
from typing import Dict, Optional

import google.generativeai as genai
from pydantic import BaseModel, Field, ValidationError

from config import Config

logger = logging.getLogger(__name__)


# System prompt for Gemini to extract lead information
SYSTEM_PROMPT = """You are an intelligent lead extraction assistant for Attio CRM.

Your tasks:
1. Determine what type of Attio object to create based on the message context
2. Extract relevant information for that object type

**Object Types:**
- "person": Individual contacts (e.g., "Met Sarah Johnson", "Talked to John Smith")
- "company": Organizations/businesses (e.g., "Working with Acme Corp", "Contacted Stripe")
- "deal": Sales opportunities (e.g., "$50k deal with Acme", "Potential contract worth $100k")
- "user": Team members/internal users (e.g., "New team member Sarah", "Hired John as engineer")

**Fields to extract:**
- object_type: One of ["person", "company", "deal", "user"] (required)
- name: Full name or company name (required)
- email: Email address (if mentioned)
- phone: Phone number (if mentioned)
- company: Company/organization name (for person type)
- job_title: Their role/position (for person/user)
- location: City/country (if mentioned)
- linkedin_url: LinkedIn profile URL (if mentioned, extract the full URL)
- deal_value: Monetary value (for deal type, extract number only)
- deal_stage: Stage like "prospect", "negotiation", "closed" (for deal type)
- notes: Any additional context

**Examples:**

Input: "Met Sarah Chen, VP of Engineering at Stripe"
Output:
{
  "object_type": "person",
  "name": "Sarah Chen",
  "company": "Stripe",
  "job_title": "VP of Engineering",
  "notes": "Met today"
}

Input: "John Doe from TechCorp, linkedin.com/in/johndoe, email john@techcorp.com"
Output:
{
  "object_type": "person",
  "name": "John Doe",
  "company": "TechCorp",
  "email": "john@techcorp.com",
  "linkedin_url": "https://linkedin.com/in/johndoe"
}

Input: "Working with Acme Corp, they're a SaaS company in SF"
Output:
{
  "object_type": "company",
  "name": "Acme Corp",
  "location": "San Francisco",
  "notes": "SaaS company"
}

Input: "Potential $50k deal with TechCo for our enterprise plan"
Output:
{
  "object_type": "deal",
  "name": "TechCo Enterprise Deal",
  "company": "TechCo",
  "deal_value": 50000,
  "deal_stage": "prospect",
  "notes": "Enterprise plan"
}

Input: "Hired John Smith as senior engineer"
Output:
{
  "object_type": "user",
  "name": "John Smith",
  "job_title": "Senior Engineer",
  "notes": "New hire"
}

Return ONLY valid JSON, no explanatory text before or after.
"""


class LeadData(BaseModel):
    """Pydantic model for validated lead data."""
    object_type: str = Field(..., description="Type of Attio object: person, company, deal, or user")
    name: str = Field(..., description="Full name or company name")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    company: Optional[str] = Field(None, description="Company name")
    job_title: Optional[str] = Field(None, description="Job title/role")
    location: Optional[str] = Field(None, description="Location (city/country)")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    deal_value: Optional[float] = Field(None, description="Deal value in dollars (for deals)")
    deal_stage: Optional[str] = Field(None, description="Deal stage (for deals)")
    notes: Optional[str] = Field(None, description="Additional notes")


class GeminiProcessingError(Exception):
    """Raised when Gemini API processing fails."""
    pass


# Configure Gemini API
genai.configure(api_key=Config.GOOGLE_API_KEY)


def _is_quota_error(error: Exception) -> bool:
    """
    Check if an error is a quota/rate limit error.

    Args:
        error: Exception from Gemini API

    Returns:
        True if it's a quota error, False otherwise
    """
    error_str = str(error).lower()
    quota_indicators = [
        'quota',
        'rate limit',
        'resource exhausted',
        '429',
        'too many requests',
        'limit exceeded'
    ]
    return any(indicator in error_str for indicator in quota_indicators)


async def call_gemini_api(message: str, use_fallback: bool = False) -> str:
    """
    Call Gemini API with the user message.
    Automatically falls back to lite model if quota is exceeded.

    Args:
        message: User message to process
        use_fallback: If True, use the fallback model directly

    Returns:
        Gemini's response text

    Raises:
        GeminiProcessingError: If API call fails
    """
    # Choose model based on fallback flag
    model_name = Config.GOOGLE_FALLBACK_MODEL if use_fallback else Config.GOOGLE_MODEL

    try:
        logger.info(f"Calling Gemini API ({model_name}) with message: {message[:100]}...")

        # Create the model
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "temperature": 0.1,  # Low temperature for consistent JSON output
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": Config.GOOGLE_MAX_TOKENS,
            }
        )

        # Combine system prompt and user message
        full_prompt = f"{SYSTEM_PROMPT}\n\nUser message: {message}"

        # Generate response
        response = model.generate_content(full_prompt)

        if not response.text:
            raise GeminiProcessingError("Empty response from Gemini API")

        logger.info(f"Gemini API call successful using {model_name}")
        return response.text

    except Exception as e:
        logger.error(f"Gemini API call failed with {model_name}: {e}")

        # If primary model failed due to quota and we haven't tried fallback yet
        if not use_fallback and _is_quota_error(e):
            logger.warning(f"Quota exceeded on {Config.GOOGLE_MODEL}, falling back to {Config.GOOGLE_FALLBACK_MODEL}")
            try:
                return await call_gemini_api(message, use_fallback=True)
            except Exception as fallback_error:
                logger.error(f"Fallback model also failed: {fallback_error}")
                raise GeminiProcessingError(f"Both models failed. Primary: {e}, Fallback: {fallback_error}")

        raise GeminiProcessingError(f"API request failed: {e}")


def parse_gemini_response(response_text: str) -> Dict[str, any]:
    """
    Parse JSON response from Gemini.

    Args:
        response_text: Raw text response from Gemini

    Returns:
        Parsed JSON dictionary

    Raises:
        GeminiProcessingError: If JSON parsing fails
    """
    # Try to extract JSON from response
    # Sometimes Gemini might include extra text, so we look for JSON pattern
    try:
        # First, try direct JSON parsing
        data = json.loads(response_text)
        logger.info("Successfully parsed Gemini response")
        return data

    except json.JSONDecodeError:
        # Try to find JSON in the text
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                logger.info("Successfully extracted JSON from Gemini response")
                return data
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse JSON from response: {response_text}")
        raise GeminiProcessingError("Could not parse JSON from Gemini response")


async def process_lead_message(message: str) -> LeadData:
    """
    Process a natural language message and extract structured lead data.

    This is the main entry point for lead extraction. It:
    1. Calls Gemini API to extract information
    2. Parses and validates the response
    3. Returns structured lead data

    Args:
        message: Natural language message containing lead information

    Returns:
        LeadData object with extracted information

    Raises:
        GeminiProcessingError: If processing fails
    """
    try:
        # Call Gemini API
        response_text = await call_gemini_api(message)

        # Parse JSON response
        data = parse_gemini_response(response_text)

        # Validate and convert to LeadData model
        lead_data = LeadData(**data)
        logger.info(f"Successfully extracted lead data for: {lead_data.name}")

        return lead_data

    except ValidationError as e:
        logger.error(f"Lead data validation failed: {e}")
        raise GeminiProcessingError(f"Invalid lead data format: {e}")

    except Exception as e:
        logger.error(f"Lead processing failed: {e}")
        raise GeminiProcessingError(f"Processing failed: {e}")


# For testing
if __name__ == "__main__":
    import asyncio

    async def test_processor():
        """Test lead extraction."""
        test_message = "I just met Sarah Johnson, she's the VP of Sales at Acme Corp"

        try:
            lead_data = await process_lead_message(test_message)
            print("\nExtracted Lead Data:")
            print(f"Name: {lead_data.name}")
            print(f"Company: {lead_data.company}")
            print(f"Title: {lead_data.job_title}")
            print(f"Email: {lead_data.email}")
            print(f"Phone: {lead_data.phone}")
            print(f"Location: {lead_data.location}")
            print(f"Notes: {lead_data.notes}")

        except GeminiProcessingError as e:
            print(f"Processing failed: {e}")

    asyncio.run(test_processor())
