import os
import tempfile
import unittest


database_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
database_file.close()
media_directory = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = database_file.name
os.environ["MEDIA_PATH"] = media_directory.name
os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["TELEGRAM_USER_ID"] = "1"


class PostServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from bot.database import PostStatus
        from bot.database.database import engine, init_db
        from bot.services.post_service import PostService

        cls.engine = engine
        cls.post_status = PostStatus
        cls.post_service = PostService
        init_db()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        os.unlink(database_file.name)
        media_directory.cleanup()

    def test_successful_retry_clears_previous_error(self):
        post = self.post_service.create_post("Retry this post")
        self.assertIsNotNone(post)

        failed = self.post_service.update_post_status(
            post.id,
            self.post_status.FAILED,
            error_message="Temporary outage",
        )
        published = self.post_service.update_post_status(
            post.id,
            self.post_status.PUBLISHED,
            twitter_id="12345",
        )
        updated = self.post_service.get_post(post.id)

        self.assertTrue(failed)
        self.assertTrue(published)
        self.assertEqual(updated.status, self.post_status.PUBLISHED)
        self.assertEqual(updated.twitter_id, "12345")
        self.assertIsNone(updated.error_message)


if __name__ == "__main__":
    unittest.main()
