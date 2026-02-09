"""
OpenAI Service
Integration with OpenAI API for AI-generated content.
"""

from openai import OpenAI, OpenAIError
from typing import Optional, Tuple
from bot.config import logger, OPENAI_API_KEY, OPENAI_ENABLED
from bot.utils.i18n import DEFAULT_LOCALE, t


class OpenAIServiceError(Exception):
    """Custom exception for OpenAI service errors"""
    pass


class OpenAIService:
    """Service for interacting with OpenAI API"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        self.client = None
        self.enabled = OPENAI_ENABLED
        
        if self.enabled:
            try:
                self.client = OpenAI(api_key=OPENAI_API_KEY)
                logger.info("OpenAI API initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI API: {e}")
                self.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if OpenAI service is enabled"""
        return self.enabled and self.client is not None
    
    def generate_post(
        self,
        prompt: str,
        max_length: Optional[int] = None,
        style: str = "professional",
        locale: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Generate social media post content using AI.
        
        Args:
            prompt: User's prompt describing what they want
            max_length: Maximum length for the generated content
            style: Writing style (professional, casual, funny, etc.)
            
        Returns:
            Tuple of (success, generated_content, error_message)
        """
        locale = locale or DEFAULT_LOCALE
        if not self.is_enabled():
            return False, None, t("errors.openai_disabled", locale)
        
        try:
            # Build system message based on parameters
            system_message = self._build_system_message(max_length, style)
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500,
            )
            
            generated_content = response.choices[0].message.content.strip()
            
            # Remove quotes if AI wrapped the content
            if generated_content.startswith('"') and generated_content.endswith('"'):
                generated_content = generated_content[1:-1]

            if not generated_content:
                logger.error("OpenAI returned empty content")
                try:
                    logger.error(f"OpenAI response: {response}")
                except Exception:
                    logger.error("OpenAI response: <unprintable>")
                return False, None, t("errors.openai_empty_content", locale)
            
            logger.info(f"Generated content successfully ({len(generated_content)} chars)")
            return True, generated_content, None
            
        except OpenAIError as e:
            error_msg = self._parse_openai_error(e, locale)
            logger.error(f"Failed to generate content: {error_msg}")
            return False, None, error_msg
        except Exception as e:
            error_msg = t("errors.openai_unexpected", locale, error=str(e))
            logger.error(f"Failed to generate content: {error_msg}")
            return False, None, error_msg
    
    def generate_post_with_topic(
        self,
        topic_name: str,
        max_length: Optional[int] = None,
        locale: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Generate social media post content using a topic preset.
        
        Args:
            topic_name: Name of the topic preset
            max_length: Maximum length for the generated content
            
        Returns:
            Tuple of (success, generated_content, error_message)
        """
        locale = locale or DEFAULT_LOCALE
        if not self.is_enabled():
            return False, None, t("errors.openai_disabled", locale)
        
        # Build a professional prompt for the topic
        target_length = max_length or 280

        prompt = f"""Generate a professional and engaging single post for Twitter/X about: {topic_name}

    The post must be {target_length} characters or fewer and should not be a thread.

    The post should:
    - Be informative and provide value
    - Have a professional yet approachable tone
    - Include an interesting fact or insight
    - May start with an appropriate emoji
    - Be engaging to capture attention

    Create quality content that the audience will find valuable."""

        return self.generate_post(prompt, target_length, style="professional", locale=locale)
    
    def improve_post(self, content: str, instruction: str = "improve", locale: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Improve existing post content.
        
        Args:
            content: Existing post content
            instruction: What to improve (grammar, clarity, engagement, etc.)
            
        Returns:
            Tuple of (success, improved_content, error_message)
        """
        locale = locale or DEFAULT_LOCALE
        if not self.is_enabled():
            return False, None, t("errors.openai_disabled", locale)
        
        try:
            system_message = (
                "You are a social media expert. Improve the given post while maintaining its core message. "
                "Make it more engaging, clear, and effective. Don't add hashtags unless they were in the original."
            )
            user_message = f"Improve this post ({instruction}):\n\n{content}"
            
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=500,
            )
            
            improved_content = response.choices[0].message.content.strip()
            
            # Remove quotes if AI wrapped the content
            if improved_content.startswith('"') and improved_content.endswith('"'):
                improved_content = improved_content[1:-1]
            
            logger.info("Post improved successfully")
            return True, improved_content, None
            
        except OpenAIError as e:
            error_msg = self._parse_openai_error(e, locale)
            logger.error(f"Failed to improve post: {error_msg}")
            return False, None, error_msg
        except Exception as e:
            error_msg = t("errors.openai_unexpected", locale, error=str(e))
            logger.error(f"Failed to improve post: {error_msg}")
            return False, None, error_msg
    
    def _build_system_message(self, max_length: Optional[int], style: str) -> str:
        """Build system message for AI based on parameters"""
        base_message = (
            "You are a professional social media content creator. "
            "Create engaging, clear, and effective posts for Twitter/X. "
        )
        
        if max_length:
            base_message += f"Keep the content under {max_length} characters. "
        
        style_instructions = {
            "professional": "Use a professional and informative tone.",
            "casual": "Use a casual and friendly tone.",
            "funny": "Use humor and wit to make it entertaining.",
            "inspirational": "Use an inspirational and motivational tone.",
            "educational": "Use a clear and educational tone.",
        }
        
        base_message += style_instructions.get(style, style_instructions["professional"])
        base_message += " Do not add hashtags unless specifically requested. Provide ONLY the post content, no explanations."
        
        return base_message
    
    def _parse_openai_error(self, error: OpenAIError, locale: Optional[str] = None) -> str:
        """
        Parse OpenAI error into user-friendly message.
        
        Args:
            error: OpenAI exception
            
        Returns:
            User-friendly error message
        """
        locale = locale or DEFAULT_LOCALE
        error_str = str(error)
        
        # Rate limit
        if "rate_limit" in error_str.lower() or "429" in error_str:
            return t("errors.openai_rate_limit", locale)
        
        # Authentication
        if "authentication" in error_str.lower() or "401" in error_str:
            return t("errors.openai_auth", locale)
        
        # Content filter
        if "content_filter" in error_str.lower() or "content policy" in error_str.lower():
            return t("errors.openai_content_filter", locale)
        
        # Insufficient quota
        if "insufficient_quota" in error_str.lower() or "quota" in error_str.lower():
            return t("errors.openai_quota", locale)
        
        # Connection errors
        if "connection" in error_str.lower() or "timeout" in error_str.lower():
            return t("errors.openai_connection", locale)
        
        # Generic error
        return t("errors.openai_generic", locale, error=error_str[:200])

    def test_connection(self, locale: Optional[str] = None) -> Tuple[bool, str]:
        """
        Test OpenAI API connection.
        
        Returns:
            Tuple of (success, message)
        """
        locale = locale or DEFAULT_LOCALE
        if not self.enabled:
            return False, t("errors.openai_key_not_configured", locale)
        
        try:
            # Try a minimal API call
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
            )
            return True, t("errors.openai_connected", locale)
            
        except OpenAIError as e:
            error_msg = self._parse_openai_error(e, locale)
            return False, error_msg
        except Exception as e:
            return False, t("errors.openai_connection_detail", locale, error=str(e))
