"""
Scheduler Service
APScheduler integration for scheduling posts.
"""

from datetime import datetime
from typing import Optional, Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.base import JobLookupError
from bot.config import logger
import pytz


class SchedulerService:
    """Service for scheduling posts using APScheduler"""
    
    def __init__(self):
        """Initialize scheduler"""
        self.scheduler = AsyncIOScheduler(timezone=pytz.UTC)
        self.scheduler.start()
        logger.info("Scheduler service initialized")
    
    def schedule_post(
        self,
        post_id: int,
        scheduled_time: datetime,
        callback: Callable,
        *args,
        job_id: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Schedule a post for publishing.
        
        Args:
            post_id: ID of the post to schedule
            scheduled_time: When to publish the post
            callback: Function to call when time arrives
            *args: Arguments for callback
            **kwargs: Keyword arguments for callback
            
        Returns:
            Job ID if scheduled successfully, None otherwise
        """
        try:
            # Create unique job ID if not provided
            if not job_id:
                job_id = f"post_{post_id}_{int(scheduled_time.timestamp())}"
            
            # Ensure scheduled_time is timezone-aware (UTC)
            if scheduled_time.tzinfo is None:
                scheduled_time = pytz.UTC.localize(scheduled_time)
            else:
                scheduled_time = scheduled_time.astimezone(pytz.UTC)
            
            # Schedule the job
            job = self.scheduler.add_job(
                callback,
                trigger=DateTrigger(run_date=scheduled_time),
                args=args,
                kwargs=kwargs,
                id=job_id,
                replace_existing=True,
            )
            
            logger.info(f"Scheduled post {post_id} for {scheduled_time} (Job ID: {job_id})")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to schedule post {post_id}: {e}")
            return None
    
    def cancel_post(self, job_id: str) -> bool:
        """
        Cancel a scheduled post.
        
        Args:
            job_id: ID of the job to cancel
            
        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Cancelled scheduled post (Job ID: {job_id})")
            return True
            
        except JobLookupError:
            logger.warning(f"Job not found: {job_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False
    
    def reschedule_post(
        self,
        job_id: str,
        new_time: datetime
    ) -> bool:
        """
        Reschedule an existing post.
        
        Args:
            job_id: ID of the job to reschedule
            new_time: New scheduled time
            
        Returns:
            True if rescheduled successfully, False otherwise
        """
        try:
            # Ensure new_time is timezone-aware (UTC)
            if new_time.tzinfo is None:
                new_time = pytz.UTC.localize(new_time)
            else:
                new_time = new_time.astimezone(pytz.UTC)
            
            self.scheduler.reschedule_job(
                job_id,
                trigger=DateTrigger(run_date=new_time)
            )
            logger.info(f"Rescheduled job {job_id} to {new_time}")
            return True
            
        except JobLookupError:
            logger.warning(f"Job not found: {job_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to reschedule job {job_id}: {e}")
            return False
    
    def get_scheduled_jobs(self) -> list:
        """
        Get all scheduled jobs.
        
        Returns:
            List of scheduled jobs
        """
        return self.scheduler.get_jobs()
    
    def get_job(self, job_id: str):
        """
        Get a specific job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job object or None if not found
        """
        try:
            return self.scheduler.get_job(job_id)
        except JobLookupError:
            return None
    
    def shutdown(self):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down")
