import transaction
import unittest
import unittest.mock
from fanboi2.models import DBSession
from fanboi2.tests import ModelMixin, TaskMixin, DummyAsyncResult


class TestResultProxy(TaskMixin, ModelMixin, unittest.TestCase):

    def test_object(self):
        from fanboi2.tasks import ResultProxy
        board = self._makeBoard(title='Foobar', slug='foobar')
        response = ['board', board.id]
        proxy = ResultProxy(DummyAsyncResult('demo', 'success', response))
        self.assertEqual(proxy.object, board)

    # noinspection PyUnresolvedReferences
    def test_object_failure(self):
        from fanboi2.tasks import ResultProxy
        from fanboi2.errors import BaseError, StatusRejectedError
        response = ['failure', 'status_rejected', 'locked']
        proxy = ResultProxy(DummyAsyncResult('demo', 'success', response))
        self.assertIsInstance(proxy.object, BaseError)
        self.assertIsInstance(proxy.object, StatusRejectedError)
        self.assertEqual(proxy.object.status, 'locked')

    def test_success(self):
        from fanboi2.tasks import ResultProxy
        proxy = ResultProxy(DummyAsyncResult('demo', 'success'))
        self.assertTrue(proxy.success())

    def test_success_non_success(self):
        from fanboi2.tasks import ResultProxy
        proxy = ResultProxy(DummyAsyncResult('demo', 'pending'))
        self.assertFalse(proxy.success())

    def test_proxy(self):
        from fanboi2.tasks import ResultProxy

        class DummyDummyAsyncResult(DummyAsyncResult):
            def dummy(self):
                return "dummy"

        proxy = ResultProxy(DummyDummyAsyncResult('demo', 'success'))
        self.assertEqual(proxy.dummy(), "dummy")


class TestAddTopicTask(TaskMixin, ModelMixin, unittest.TestCase):

    def _makeOne(self, *args, **kwargs):
        from fanboi2.tasks import add_topic
        return add_topic.delay(*args, **kwargs)

    def test_add_topic(self):
        import transaction
        from fanboi2.models import Topic
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(title='Foobar', slug='foobar')
            board_id = board.id  # board is not bound outside transaction!
        result = self._makeOne(request, board_id, 'Foobar', 'Hello, world!')
        topic = DBSession.query(Topic).first()
        self.assertTrue(result.successful())
        self.assertEqual(DBSession.query(Topic).count(), 1)
        self.assertEqual(DBSession.query(Topic).get(result.get()[1]), topic)
        self.assertEqual(topic.title, 'Foobar')
        self.assertEqual(topic.posts[0].body, 'Hello, world!')
        self.assertEqual(result.result, ('topic', topic.id))

    @unittest.mock.patch('fanboi2.utils.Akismet.spam')
    def test_add_topic_spam(self, akismet):
        from fanboi2.models import Topic
        akismet.return_value = True
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(title='Foobar', slug='foobar')
            board_id = board.id  # board is not bound outside transaction!
        result = self._makeOne(request, board_id, 'Foobar', 'Hello, world!')
        self.assertTrue(result.successful())
        self.assertEqual(DBSession.query(Topic).count(), 0)
        self.assertEqual(result.result, ('failure', 'spam_rejected'))

    @unittest.mock.patch('fanboi2.utils.Dnsbl.listed')
    def test_add_topic_dnsbl(self, dnsbl):
        from fanboi2.models import Topic
        dnsbl.return_value = True
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(title='Foobar', slug='foobar')
            board_id = board.id  # board is not bound outside transaction!
        result = self._makeOne(request, board_id, 'Foobar', 'Hello, world!')
        self.assertTrue(result.successful())
        self.assertEqual(DBSession.query(Topic).count(), 0)
        self.assertEqual(result.result, ('failure', 'dnsbl_rejected'))

    def test_add_topic_board_restricted(self):
        from fanboi2.models import Topic
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(
                title='Foobar',
                slug='foobar',
                status='restricted')
            board_id = board.id  # board is not bound outside transaction!
        result = self._makeOne(request, board_id, 'Foobar', 'Hello, world!')
        self.assertTrue(result.successful())
        self.assertEqual(DBSession.query(Topic).count(), 0)
        self.assertEqual(result.result, (
            'failure',
            'status_rejected',
            'restricted'))

    def test_add_topic_board_locked(self):
        from fanboi2.models import Topic
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(
                title='Foobar',
                slug='foobar',
                status='locked')
            board_id = board.id  # board is not bound outside transaction!
        result = self._makeOne(request, board_id, 'Foobar', 'Hello, world!')
        self.assertTrue(result.successful())
        self.assertEqual(DBSession.query(Topic).count(), 0)
        self.assertEqual(result.result, (
            'failure',
            'status_rejected',
            'locked'))

    def test_add_topic_board_archived(self):
        from fanboi2.models import Topic
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(
                title='Foobar',
                slug='foobar',
                status='archived')
            board_id = board.id  # board is not bound outside transaction!
        result = self._makeOne(request, board_id, 'Foobar', 'Hello, world!')
        self.assertTrue(result.successful())
        self.assertEqual(DBSession.query(Topic).count(), 0)
        self.assertEqual(result.result, (
            'failure',
            'status_rejected',
            'archived'))


class TestAddPostTask(TaskMixin, ModelMixin, unittest.TestCase):

    def _makeOne(self, *args, **kwargs):
        from fanboi2.tasks import add_post
        return add_post.delay(*args, **kwargs)

    def test_add_post(self):
        import transaction
        from fanboi2.models import Post
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(title='Foobar', slug='foobar')
            topic = self._makeTopic(board=board, title='Hello, world!')
            topic_id = topic.id  # topic is not bound outside transaction!
        result = self._makeOne(request, topic_id, 'Hi!', True)
        post = DBSession.query(Post).first()
        self.assertTrue(result.successful())
        self.assertEqual(DBSession.query(Post).count(), 1)
        self.assertEqual(DBSession.query(Post).get(result.get()[1]), post)
        self.assertEqual(post.body, 'Hi!')
        self.assertEqual(post.bumped, True)
        self.assertEqual(result.result, ('post', post.id))

    @unittest.mock.patch('fanboi2.utils.Akismet.spam')
    def test_add_post_spam(self, akismet):
        import transaction
        from fanboi2.models import Post
        akismet.return_value = True
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(title='Foobar', slug='foobar')
            topic = self._makeTopic(board=board, title='Hello, world!')
            topic_id = topic.id  # topic is not bound outside transaction!
        result = self._makeOne(request, topic_id, 'Hi!', True)
        self.assertTrue(result.successful())
        self.assertEqual(DBSession.query(Post).count(), 0)
        self.assertEqual(result.result, ('failure', 'spam_rejected'))

    def test_add_post_locked(self):
        import transaction
        from fanboi2.models import Post
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(title='Foobar', slug='foobar')
            topic = self._makeTopic(
                board=board,
                title='Hello, world!',
                status='locked')
            topic_id = topic.id  # topic is not bound outside transaction!
        result = self._makeOne(request, topic_id, 'Hi!', True)
        self.assertTrue(result.successful())
        self.assertEqual(DBSession.query(Post).count(), 0)
        self.assertEqual(result.result, (
            'failure',
            'status_rejected',
            'locked'))

    def test_add_post_board_locked(self):
        import transaction
        from fanboi2.models import Post
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(
                title='Foobar',
                slug='foobar',
                status='locked')
            topic = self._makeTopic(
                board=board,
                title='Hello, world!')
            topic_id = topic.id  # topic is not bound outside transaction!
        result = self._makeOne(request, topic_id, 'Hi!', True)
        self.assertTrue(result.successful())
        self.assertEqual(DBSession.query(Post).count(), 0)
        self.assertEqual(result.result, (
            'failure',
            'status_rejected',
            'locked'))

    def test_add_post_board_archived(self):
        import transaction
        from fanboi2.models import Post
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(
                title='Foobar',
                slug='foobar',
                status='archived')
            topic = self._makeTopic(
                board=board,
                title='Hello, world!')
            topic_id = topic.id  # topic is not bound outside transaction!
        result = self._makeOne(request, topic_id, 'Hi!', True)
        self.assertTrue(result.successful())
        self.assertEqual(DBSession.query(Post).count(), 0)
        self.assertEqual(result.result, (
            'failure',
            'status_rejected',
            'archived'))

    def test_add_post_retry(self):
        import transaction
        from sqlalchemy.exc import IntegrityError
        request = {'remote_addr': '127.0.0.1'}
        with transaction.manager:
            board = self._makeBoard(title='Foobar', slug='foobar')
            topic = self._makeTopic(board=board, title='Hello, world!')
            topic_id = topic.id  # topic is not bound outside transaction!
        with unittest.mock.patch('fanboi2.models.DBSession.flush') as dbs:
            dbs.side_effect = IntegrityError(None, None, None)
            result = self._makeOne(request, topic_id, 'Hi!', True)
        self.assertEqual(dbs.call_count, 5)
        self.assertFalse(result.successful())
