"""
Template Service
Business logic for managing post templates.
"""

from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from bot.config import logger
from bot.utils.i18n import DEFAULT_LOCALE, t
from bot.database.database import SessionLocal
from bot.database.models import Template


MAX_TEMPLATES_PER_USER = 20
MIN_TEMPLATE_NAME_LENGTH = 3
MAX_TEMPLATE_NAME_LENGTH = 50
MAX_TEMPLATE_CONTENT_LENGTH = 2000


class TemplateService:
    """Service for managing post templates"""

    @staticmethod
    def create_template(
        user_id: int,
        name: str,
        content: str,
        locale: Optional[str] = None
    ) -> Tuple[bool, Optional[Template], Optional[str]]:
        """Create a new template for a user."""
        db: Session = SessionLocal()
        try:
            locale = locale or DEFAULT_LOCALE
            name = name.strip()
            content = content.strip()

            if len(name) < MIN_TEMPLATE_NAME_LENGTH:
                return False, None, t("errors.template_name_too_short", locale, min=MIN_TEMPLATE_NAME_LENGTH)
            if len(name) > MAX_TEMPLATE_NAME_LENGTH:
                return False, None, t("errors.template_name_too_long", locale, max=MAX_TEMPLATE_NAME_LENGTH)
            if len(content) == 0:
                return False, None, t("errors.template_content_empty", locale)
            if len(content) > MAX_TEMPLATE_CONTENT_LENGTH:
                return False, None, t("errors.template_content_too_long", locale, max=MAX_TEMPLATE_CONTENT_LENGTH)

            template_count = db.query(func.count(Template.id)).filter(
                Template.user_id == user_id
            ).scalar()
            if template_count >= MAX_TEMPLATES_PER_USER:
                return False, None, t("errors.template_max_reached", locale, max=MAX_TEMPLATES_PER_USER)

            existing = db.query(Template).filter(
                Template.user_id == user_id,
                func.lower(Template.name) == func.lower(name)
            ).first()
            if existing:
                return False, None, t("errors.template_already_exists", locale, name=name)

            template = Template(user_id=user_id, name=name, content=content)
            db.add(template)
            db.commit()
            db.refresh(template)

            logger.info(f"Created template '{name}' for user {user_id}")
            return True, template, None
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating template: {e}")
            return False, None, t("errors.template_create_failed", locale, error=str(e))
        finally:
            db.close()

    @staticmethod
    def get_user_templates(user_id: int) -> List[Template]:
        """Get all templates for a user."""
        db: Session = SessionLocal()
        try:
            return db.query(Template).filter(
                Template.user_id == user_id
            ).order_by(Template.name).all()
        except Exception as e:
            logger.error(f"Error fetching templates: {e}")
            return []
        finally:
            db.close()

    @staticmethod
    def get_template_for_user(template_id: int, user_id: int) -> Optional[Template]:
        """Get a specific template by ID for a user."""
        db: Session = SessionLocal()
        try:
            return db.query(Template).filter(
                Template.id == template_id,
                Template.user_id == user_id
            ).first()
        except Exception as e:
            logger.error(f"Error fetching template: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def update_template_content(
        template_id: int,
        user_id: int,
        content: str,
        locale: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Update template content."""
        db: Session = SessionLocal()
        try:
            locale = locale or DEFAULT_LOCALE
            content = content.strip()
            if len(content) == 0:
                return False, t("errors.template_content_empty", locale)
            if len(content) > MAX_TEMPLATE_CONTENT_LENGTH:
                return False, t("errors.template_content_too_long", locale, max=MAX_TEMPLATE_CONTENT_LENGTH)

            template = db.query(Template).filter(
                Template.id == template_id,
                Template.user_id == user_id
            ).first()
            if not template:
                return False, t("errors.template_not_found", locale)

            template.content = content
            template.updated_at = datetime.utcnow()
            db.commit()

            logger.info(f"Updated template {template_id} for user {user_id}")
            return True, None
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating template: {e}")
            return False, t("errors.template_update_failed", locale, error=str(e))
        finally:
            db.close()

    @staticmethod
    def delete_template(template_id: int, user_id: int, locale: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Delete a template."""
        db: Session = SessionLocal()
        try:
            locale = locale or DEFAULT_LOCALE
            template = db.query(Template).filter(
                Template.id == template_id,
                Template.user_id == user_id
            ).first()
            if not template:
                return False, t("errors.template_not_found", locale)

            name = template.name
            db.delete(template)
            db.commit()
            logger.info(f"Deleted template '{name}' (ID: {template_id}) for user {user_id}")
            return True, None
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting template: {e}")
            return False, t("errors.template_delete_failed", locale, error=str(e))
        finally:
            db.close()

    @staticmethod
    def delete_all_templates(user_id: int, locale: Optional[str] = None) -> Tuple[bool, int, Optional[str]]:
        """Delete all templates for a user."""
        db: Session = SessionLocal()
        try:
            deleted_count = db.query(Template).filter(
                Template.user_id == user_id
            ).delete()
            db.commit()
            logger.info(f"Deleted {deleted_count} templates for user {user_id}")
            return True, deleted_count, None
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting all templates: {e}")
            locale = locale or DEFAULT_LOCALE
            return False, 0, t("errors.template_delete_all_failed", locale, error=str(e))
        finally:
            db.close()

    @staticmethod
    def get_template_count(user_id: int) -> int:
        """Get the count of templates for a user."""
        db: Session = SessionLocal()
        try:
            count = db.query(func.count(Template.id)).filter(
                Template.user_id == user_id
            ).scalar()
            return count or 0
        except Exception as e:
            logger.error(f"Error counting templates: {e}")
            return 0
        finally:
            db.close()

    @staticmethod
    def has_reached_max_templates(user_id: int) -> bool:
        """Check if user has reached maximum templates."""
        return TemplateService.get_template_count(user_id) >= MAX_TEMPLATES_PER_USER
