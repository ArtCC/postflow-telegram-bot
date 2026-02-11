"""
Keyboard Utilities
Helper functions for creating inline keyboards.
"""

from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.utils.i18n import DEFAULT_LOCALE, t


def get_main_menu_keyboard(locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create the main menu keyboard with inline buttons."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [
            InlineKeyboardButton(t("buttons.new", locale), callback_data="new_post"),
            InlineKeyboardButton(t("buttons.drafts", locale), callback_data="drafts"),
        ],
        [
            InlineKeyboardButton(t("buttons.scheduled", locale), callback_data="scheduled"),
            InlineKeyboardButton(t("buttons.stats", locale), callback_data="statistics"),
        ],
        [
            InlineKeyboardButton(t("buttons.topics", locale), callback_data="topics_menu"),
            InlineKeyboardButton(t("buttons.templates", locale), callback_data="templates_menu"),
        ],
        [
            InlineKeyboardButton(t("buttons.status", locale), callback_data="status"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard(locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create a keyboard with a back button."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [[InlineKeyboardButton(t("buttons.back_menu", locale), callback_data="menu")]]
    return InlineKeyboardMarkup(keyboard)


def get_new_post_keyboard(locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for new post options."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [InlineKeyboardButton(t("buttons.plan_week", locale), callback_data="plan_week")],
        [InlineKeyboardButton(t("buttons.templates", locale), callback_data="post_template")],
        [InlineKeyboardButton(t("buttons.image", locale), callback_data="post_image")],
        [InlineKeyboardButton(t("buttons.write_manual", locale), callback_data="post_manual")],
    ]
    
    # Add AI option only if OpenAI is enabled
    from bot.config import OPENAI_ENABLED
    if OPENAI_ENABLED:
        keyboard.insert(0, [InlineKeyboardButton(t("buttons.ai", locale), callback_data="post_ai")])
    
    keyboard.append([InlineKeyboardButton(t("buttons.back", locale), callback_data="menu")])
    return InlineKeyboardMarkup(keyboard)


def get_templates_menu_keyboard(user_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for templates management menu."""
    locale = locale or DEFAULT_LOCALE
    from bot.services.template_service import TemplateService, MAX_TEMPLATES_PER_USER

    has_max = TemplateService.has_reached_max_templates(user_id)
    template_count = TemplateService.get_template_count(user_id)

    keyboard = []

    if has_max:
        keyboard.append([InlineKeyboardButton(t("buttons.add_template_max", locale, max=MAX_TEMPLATES_PER_USER), callback_data="templates_add_disabled")])
    else:
        keyboard.append([InlineKeyboardButton(t("buttons.add_template", locale), callback_data="templates_add")])

    if template_count > 0:
        keyboard.append([InlineKeyboardButton(t("buttons.list_templates", locale, count=template_count), callback_data="templates_list")])
        keyboard.append([InlineKeyboardButton(t("buttons.use_template", locale), callback_data="templates_use")])
        keyboard.append([InlineKeyboardButton(t("buttons.delete_template", locale), callback_data="templates_delete")])
        keyboard.append([InlineKeyboardButton(t("buttons.delete_all", locale), callback_data="templates_delete_all")])
    else:
        keyboard.append([InlineKeyboardButton(t("buttons.list_templates", locale, count=0), callback_data="templates_list_empty")])
        keyboard.append([InlineKeyboardButton(t("buttons.use_template", locale), callback_data="templates_use_empty")])

    keyboard.append([InlineKeyboardButton(t("buttons.back_menu", locale), callback_data="menu")])
    return InlineKeyboardMarkup(keyboard)


def get_templates_list_keyboard(user_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard showing list of templates."""
    locale = locale or DEFAULT_LOCALE
    from bot.services.template_service import TemplateService

    templates = TemplateService.get_user_templates(user_id)
    keyboard = []

    for template in templates:
        keyboard.append([InlineKeyboardButton(f"🧩 {template.name}", callback_data=f"templates_view_{template.id}")])

    keyboard.append([InlineKeyboardButton(t("buttons.back", locale), callback_data="templates_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_templates_use_keyboard(
    user_id: int,
    locale: Optional[str] = None,
    back_callback: str = "templates_menu"
) -> InlineKeyboardMarkup:
    """Create keyboard for choosing a template to use."""
    locale = locale or DEFAULT_LOCALE
    from bot.services.template_service import TemplateService

    templates = TemplateService.get_user_templates(user_id)
    keyboard = []

    for template in templates:
        keyboard.append([InlineKeyboardButton(f"🧩 {template.name}", callback_data=f"templates_use_{template.id}")])

    keyboard.append([InlineKeyboardButton(t("buttons.back", locale), callback_data=back_callback)])
    return InlineKeyboardMarkup(keyboard)


def get_templates_delete_keyboard(user_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for deleting templates."""
    locale = locale or DEFAULT_LOCALE
    from bot.services.template_service import TemplateService

    templates = TemplateService.get_user_templates(user_id)
    keyboard = []

    for template in templates:
        keyboard.append([InlineKeyboardButton(f"🗑️ {template.name}", callback_data=f"templates_delete_confirm_{template.id}")])

    keyboard.append([InlineKeyboardButton(t("buttons.back", locale), callback_data="templates_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_template_delete_confirm_keyboard(template_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for template deletion confirmation."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [
            InlineKeyboardButton(t("buttons.delete_confirm", locale), callback_data=f"templates_delete_execute_{template_id}"),
            InlineKeyboardButton(t("buttons.cancel", locale), callback_data="templates_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_templates_delete_all_confirm_keyboard(locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for delete all templates confirmation."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [
            InlineKeyboardButton(t("buttons.delete_all_confirm", locale), callback_data="templates_delete_all_execute"),
            InlineKeyboardButton(t("buttons.cancel", locale), callback_data="templates_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_template_view_keyboard(template_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for template details view."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [InlineKeyboardButton(t("buttons.use_template", locale), callback_data=f"templates_use_{template_id}")],
        [InlineKeyboardButton(t("buttons.edit", locale), callback_data=f"templates_edit_{template_id}")],
        [InlineKeyboardButton(t("buttons.delete", locale), callback_data=f"templates_delete_confirm_{template_id}")],
        [InlineKeyboardButton(t("buttons.back", locale), callback_data="templates_list")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_weekday_selection_keyboard(selected_days: List[int], locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create weekday selection keyboard with toggles."""
    locale = locale or DEFAULT_LOCALE
    labels = [
        t("weekdays.mon", locale),
        t("weekdays.tue", locale),
        t("weekdays.wed", locale),
        t("weekdays.thu", locale),
        t("weekdays.fri", locale),
        t("weekdays.sat", locale),
        t("weekdays.sun", locale),
    ]
    keyboard = []

    row = []
    for idx, label in enumerate(labels):
        marker = " ✅" if idx in selected_days else ""
        row.append(InlineKeyboardButton(f"{label}{marker}", callback_data=f"plan_day_{idx}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton(t("buttons.next", locale), callback_data="plan_days_next"),
        InlineKeyboardButton(t("buttons.cancel", locale), callback_data="plan_cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_posts_per_day_keyboard(locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard to select posts per day."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="plan_ppd_1"),
            InlineKeyboardButton("2", callback_data="plan_ppd_2"),
            InlineKeyboardButton("3", callback_data="plan_ppd_3"),
        ],
        [
            InlineKeyboardButton(t("buttons.previous", locale), callback_data="plan_days_back"),
            InlineKeyboardButton(t("buttons.cancel", locale), callback_data="plan_cancel"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_plan_post_mode_keyboard(locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard to choose manual or AI for a planned post."""
    locale = locale or DEFAULT_LOCALE
    keyboard = []

    from bot.config import OPENAI_ENABLED
    if OPENAI_ENABLED:
        keyboard.append([
            InlineKeyboardButton(t("buttons.ai", locale), callback_data="plan_mode_ai"),
            InlineKeyboardButton(t("buttons.manual", locale), callback_data="plan_mode_manual"),
        ])
    else:
        keyboard.append([InlineKeyboardButton(t("buttons.manual", locale), callback_data="plan_mode_manual")])

    keyboard.append([InlineKeyboardButton(t("buttons.cancel", locale), callback_data="plan_cancel")])
    return InlineKeyboardMarkup(keyboard)


def get_plan_confirm_keyboard(locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for weekly plan confirmation."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [InlineKeyboardButton(t("buttons.schedule_all", locale), callback_data="plan_confirm")],
        [InlineKeyboardButton(t("buttons.cancel_all", locale), callback_data="plan_cancel_all")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_post_preview_keyboard(post_id: int, is_thread: bool = False, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Create keyboard for post preview actions.
    
    Args:
        post_id: Post ID
        is_thread: Whether the post is a thread
        
    Returns:
        Inline keyboard markup
    """
    locale = locale or DEFAULT_LOCALE
    label = t("buttons.publish_thread", locale) if is_thread else t("buttons.publish", locale)
    
    keyboard = [
        [
            InlineKeyboardButton(label, callback_data=f"publish_{post_id}"),
            InlineKeyboardButton(t("buttons.schedule", locale), callback_data=f"schedule_{post_id}"),
        ],
        [
            InlineKeyboardButton(t("buttons.edit", locale), callback_data=f"edit_{post_id}"),
            InlineKeyboardButton(t("buttons.delete", locale), callback_data=f"delete_{post_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_schedule_keyboard(post_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for scheduling options."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [
            InlineKeyboardButton(t("buttons.in_1h", locale), callback_data=f"quick_schedule_1h_{post_id}"),
            InlineKeyboardButton(t("buttons.in_3h", locale), callback_data=f"quick_schedule_3h_{post_id}"),
        ],
        [
            InlineKeyboardButton(t("buttons.tomorrow_9am", locale), callback_data=f"quick_schedule_tomorrow_{post_id}"),
            InlineKeyboardButton(t("buttons.custom", locale), callback_data=f"custom_schedule_{post_id}"),
        ],
        [InlineKeyboardButton(t("buttons.back", locale), callback_data=f"preview_{post_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_scheduled_posts_keyboard(scheduled_posts: List[tuple], page: int = 0, per_page: int = 5, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Create keyboard for scheduled posts list with pagination.
    
    Args:
        scheduled_posts: List of (post_id, preview, scheduled_for) tuples
        page: Current page number
        per_page: Items per page
        
    Returns:
        Inline keyboard markup
    """
    locale = locale or DEFAULT_LOCALE
    keyboard = []

    keyboard.append([InlineKeyboardButton(t("buttons.calendar", locale), callback_data="calendar_week_0")])
    
    # Calculate pagination
    start = page * per_page
    end = start + per_page
    page_posts = scheduled_posts[start:end]
    
    # Add post buttons
    for post_id, preview, _ in page_posts:
        keyboard.append([
            InlineKeyboardButton(f"📝 {preview}", callback_data=f"view_scheduled_{post_id}")
        ])
    
    # Add pagination buttons if needed
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(t("buttons.previous", locale), callback_data=f"scheduled_page_{page-1}"))
    if end < len(scheduled_posts):
        nav_buttons.append(InlineKeyboardButton(t("buttons.next", locale), callback_data=f"scheduled_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add back button
    keyboard.append([InlineKeyboardButton(t("buttons.back_menu", locale), callback_data="menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_weekly_calendar_keyboard(week_offset: int = 0, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for weekly calendar navigation."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [
            InlineKeyboardButton(t("buttons.previous", locale), callback_data=f"calendar_week_{week_offset - 1}"),
            InlineKeyboardButton(t("buttons.next", locale), callback_data=f"calendar_week_{week_offset + 1}"),
        ],
        [InlineKeyboardButton(t("buttons.scheduled", locale), callback_data="scheduled")],
        [InlineKeyboardButton(t("buttons.back_menu", locale), callback_data="menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_drafts_keyboard(drafts: List[tuple], page: int = 0, per_page: int = 5, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for drafts list with pagination."""
    locale = locale or DEFAULT_LOCALE
    keyboard = []

    start = page * per_page
    end = start + per_page
    page_drafts = drafts[start:end]

    for post_id, preview, _ in page_drafts:
        keyboard.append([
            InlineKeyboardButton(
                t("labels.post_preview", locale, preview=preview),
                callback_data=f"preview_{post_id}"
            )
        ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(t("buttons.previous", locale), callback_data=f"drafts_page_{page-1}"))
    if end < len(drafts):
        nav_buttons.append(InlineKeyboardButton(t("buttons.next", locale), callback_data=f"drafts_page_{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton(t("buttons.back_menu", locale), callback_data="menu")])

    return InlineKeyboardMarkup(keyboard)


def get_scheduled_post_actions_keyboard(post_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for scheduled post actions."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [
            InlineKeyboardButton(t("buttons.view", locale), callback_data=f"preview_{post_id}"),
            InlineKeyboardButton(t("buttons.reschedule", locale), callback_data=f"reschedule_{post_id}"),
        ],
        [
            InlineKeyboardButton(t("buttons.delete", locale), callback_data=f"confirm_delete_scheduled_{post_id}"),
        ],
        [InlineKeyboardButton(t("buttons.back", locale), callback_data="scheduled")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_delete_keyboard(post_id: int, is_scheduled: bool = False, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for delete confirmation."""
    locale = locale or DEFAULT_LOCALE
    callback_prefix = "scheduled" if is_scheduled else "post"
    keyboard = [
        [
            InlineKeyboardButton(t("buttons.delete_confirm", locale), callback_data=f"confirm_delete_{callback_prefix}_{post_id}"),
            InlineKeyboardButton(t("buttons.cancel", locale), callback_data=f"cancel_delete_{post_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_error_keyboard(show_retry: bool = False, show_settings: bool = False, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for error messages."""
    locale = locale or DEFAULT_LOCALE
    keyboard = []
    
    if show_retry:
        keyboard.append([InlineKeyboardButton(t("buttons.retry", locale), callback_data="retry_last_action")])
    
    if show_settings:
        keyboard.append([InlineKeyboardButton(t("buttons.settings", locale), callback_data="settings")])
    
    keyboard.append([InlineKeyboardButton(t("buttons.back_menu", locale), callback_data="menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_topics_menu_keyboard(user_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for topics management menu."""
    locale = locale or DEFAULT_LOCALE
    from bot.services.topic_service import TopicService, MAX_TOPICS_PER_USER
    
    has_max = TopicService.has_reached_max_topics(user_id)
    topic_count = TopicService.get_topic_count(user_id)
    
    keyboard = []
    
    # Add topic button (disabled if max reached)
    if has_max:
        keyboard.append([InlineKeyboardButton(t("buttons.add_topic_max", locale, max=MAX_TOPICS_PER_USER), callback_data="topics_add_disabled")])
    else:
        keyboard.append([InlineKeyboardButton(t("buttons.add_topic", locale), callback_data="topics_add")])
    
    # List topics button
    if topic_count > 0:
        keyboard.append([InlineKeyboardButton(t("buttons.list_topics", locale, count=topic_count), callback_data="topics_list")])
        keyboard.append([InlineKeyboardButton(t("buttons.delete_topic", locale), callback_data="topics_delete")])
        keyboard.append([InlineKeyboardButton(t("buttons.delete_all", locale), callback_data="topics_delete_all")])
    else:
        keyboard.append([InlineKeyboardButton(t("buttons.list_topics", locale, count=0), callback_data="topics_list_empty")])
    
    keyboard.append([InlineKeyboardButton(t("buttons.back_menu", locale), callback_data="menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_topics_list_keyboard(user_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard showing list of topics."""
    locale = locale or DEFAULT_LOCALE
    from bot.services.topic_service import TopicService
    
    topics = TopicService.get_user_topics(user_id)
    keyboard = []
    
    # Display topics as buttons (read-only)
    for topic in topics:
        keyboard.append([InlineKeyboardButton(f"🎯 {topic.name}", callback_data=f"topics_view_{topic.id}")])
    
    keyboard.append([InlineKeyboardButton(t("buttons.back", locale), callback_data="topics_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_topics_delete_keyboard(user_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for deleting topics."""
    locale = locale or DEFAULT_LOCALE
    from bot.services.topic_service import TopicService
    
    topics = TopicService.get_user_topics(user_id)
    keyboard = []
    
    # Display topics as delete buttons
    for topic in topics:
        keyboard.append([InlineKeyboardButton(f"🗑️ {topic.name}", callback_data=f"topics_delete_confirm_{topic.id}")])
    
    keyboard.append([InlineKeyboardButton(t("buttons.back", locale), callback_data="topics_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_topic_delete_confirm_keyboard(topic_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for topic deletion confirmation."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [
            InlineKeyboardButton(t("buttons.delete_confirm", locale), callback_data=f"topics_delete_execute_{topic_id}"),
            InlineKeyboardButton(t("buttons.cancel", locale), callback_data="topics_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_topics_delete_all_confirm_keyboard(locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard for delete all topics confirmation."""
    locale = locale or DEFAULT_LOCALE
    keyboard = [
        [
            InlineKeyboardButton(t("buttons.delete_all_confirm", locale), callback_data="topics_delete_all_execute"),
            InlineKeyboardButton(t("buttons.cancel", locale), callback_data="topics_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_ai_with_topics_keyboard(user_id: int, locale: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard with topic presets for AI post generation."""
    locale = locale or DEFAULT_LOCALE
    from bot.services.topic_service import TopicService
    
    topics = TopicService.get_user_topics(user_id)
    keyboard = []
    
    # Display topics in rows of 2
    row = []
    for topic in topics:
        row.append(InlineKeyboardButton(f"🎯 {topic.name}", callback_data=f"ai_topic_{topic.id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:  # Add remaining topics
        keyboard.append(row)
    
    # Always add custom option
    keyboard.append([InlineKeyboardButton(t("buttons.custom_prompt", locale), callback_data="ai_custom")])
    keyboard.append([InlineKeyboardButton(t("buttons.back", locale), callback_data="new_post")])
    
    return InlineKeyboardMarkup(keyboard)

