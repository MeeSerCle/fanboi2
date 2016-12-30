import json
import unittest
from pyramid import testing
from fanboi2.tests import ModelMixin, RegistryMixin, TaskMixin, DummyAsyncResult


class TestJSONRenderer(RegistryMixin, unittest.TestCase):

    def _getTargetFunction(self):
        from fanboi2.serializers import initialize_renderer
        return initialize_renderer()

    def _makeOne(self, object, request=None):
        if request is None:  # pragma: no cover
            request = testing.DummyRequest()
        renderer = self._getTargetFunction()(None)
        return json.loads(renderer(object, {'request': request}))

    def test_datetime(self):
        from datetime import datetime, timezone
        request = self._makeRequest()
        registry = self._makeRegistry(settings={'app.timezone': 'Asia/Bangkok'})
        self._makeConfig(request, registry)
        date = datetime(2013, 1, 2, 0, 4, 1, 0, timezone.utc)
        self.assertEqual(
            self._makeOne(date, request=request),
            '2013-01-02T07:04:01+07:00')

    def test_error_serializer(self):
        from fanboi2.errors import BaseError
        error = BaseError()
        request = self._makeRequest()
        response = self._makeOne(error, request=request)
        self.assertEqual(response['type'], 'error')
        self.assertEqual(response['status'], error.name)
        self.assertEqual(response['message'], error.message(request))


class TestJSONRendererWithModel(ModelMixin, RegistryMixin, unittest.TestCase):

    def _getTargetFunction(self):
        from fanboi2.serializers import initialize_renderer
        return initialize_renderer()

    def _makeOne(self, object, request=None):
        if request is None:  # pragma: no cover
            request = testing.DummyRequest()
        renderer = self._getTargetFunction()(None)
        return json.loads(renderer(object, {'request': request}))

    def test_query(self):
        from fanboi2.models import DBSession
        from fanboi2.models import Board
        board1 = self._makeBoard(title='Foobar', slug='bar')
        board2 = self._makeBoard(title='Foobaz', slug='baz')
        request = self._makeRequest()
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_board', '/board/{board}/')
        response = self._makeOne(
            DBSession.query(Board).order_by(Board.title),
            request=request)
        self.assertIsInstance(response, list)
        self.assertEqual(response[0]['title'], board1.title)
        self.assertEqual(response[1]['title'], board2.title)

    def test_board(self):
        board = self._makeBoard(title='Foobar', slug='foo', status='open')
        request = self._makeRequest()
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_board', '/board/{board}/')
        response = self._makeOne(board, request=request)
        self.assertEqual(response['type'], 'board')
        self.assertEqual(response['title'], 'Foobar')
        self.assertEqual(response['slug'], 'foo')
        self.assertEqual(response['status'], 'open')
        self.assertEqual(response['path'], '/board/foo/')
        self.assertIn('agreements', response)
        self.assertIn('description', response)
        self.assertIn('id', response)
        self.assertIn('settings', response)
        self.assertNotIn('topics', response)

    def test_board_with_topics(self):
        board = self._makeBoard(title='Foobar', slug='foo')
        topic = self._makeTopic(board=board, title='Heavenly Moon')
        request = self._makeRequest(params={'topics': True})
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_board', '/board/{board}/')
        config.add_route('api_topic', '/board/{topic}/')
        response = self._makeOne(board, request=request)
        self.assertIn('topics', response)

    def test_board_with_topics_board(self):
        board = self._makeBoard(title='Foobar', slug='foo')
        topic = self._makeTopic(board=board, title='Heavenly Moon')
        request = self._makeRequest(params={'topics': True, 'board': True})
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_board', '/board/{board}/')
        config.add_route('api_topic', '/board/{topic}/')
        response = self._makeOne(board, request=request)
        self.assertNotIn('topics', response)

    def test_topic(self):
        board = self._makeBoard(title='Foobar', slug='foo')
        topic = self._makeTopic(board=board, title='Heavenly Moon')
        request = self._makeRequest()
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_topic', '/topic/{topic}/')
        response = self._makeOne(topic, request=request)
        self.assertEqual(response['type'], 'topic')
        self.assertEqual(response['title'], 'Heavenly Moon')
        self.assertEqual(response['board_id'], board.id)
        self.assertEqual(response['path'], '/topic/%s/' % topic.id)
        self.assertIn('bumped_at', response)
        self.assertIn('created_at', response)
        self.assertIn('post_count', response)
        self.assertIn('posted_at', response)
        self.assertIn('status', response)
        self.assertNotIn('posts', response)

    def test_topic_with_board(self):
        board = self._makeBoard(title='Foobar', slug='foo')
        topic = self._makeTopic(board=board, title='Heavenly Moon')
        request = self._makeRequest(params={'board': True})
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_topic', '/topic/{topic}/')
        config.add_route('api_board', '/board/{board}/')
        response = self._makeOne(topic, request=request)
        self.assertEqual(response['board_id'], board.id)
        self.assertIn('board', response)

    def test_topic_with_board_topics(self):
        board = self._makeBoard(title='Foobar', slug='foo')
        topic = self._makeTopic(board=board, title='Heavenly Moon')
        request = self._makeRequest(params={'board': True, 'topics': True})
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_topic', '/topic/{topic}/')
        config.add_route('api_board', '/board/{board}/')
        response = self._makeOne(topic, request=request)
        self.assertIn('board', response)
        self.assertNotIn('topics', response['board'])

    def test_topic_with_posts(self):
        board = self._makeBoard(title='Foobar', slug='foo')
        topic = self._makeTopic(board=board, title='Heavenly Moon')
        request = self._makeRequest(params={'posts': True})
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_topic', '/topic/{topic}/')
        response = self._makeOne(topic, request=request)
        self.assertEqual(response['title'], 'Heavenly Moon')
        self.assertEqual(response['board_id'], board.id)
        self.assertIn('posts', response)

    def test_topic_with_posts_topic(self):
        board = self._makeBoard(title='Foobar', slug='foo')
        topic = self._makeTopic(board=board, title='Heavenly Moon')
        request = self._makeRequest(params={'posts': True, 'topic': True})
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_topic', '/topic/{topic}/')
        response = self._makeOne(topic, request=request)
        self.assertEqual(response['title'], 'Heavenly Moon')
        self.assertEqual(response['board_id'], board.id)
        self.assertNotIn('posts', response)

    def test_post(self):
        board = self._makeBoard(title='Foobar', slug='foo')
        topic = self._makeTopic(board=board, title='Baz')
        post = self._makePost(topic=topic, body='Hello, world!')
        request = self._makeRequest()
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_topic_posts_scoped', '/topic/{topic}/{query}/')
        response = self._makeOne(post, request=request)
        self.assertEqual(response['type'], 'post')
        self.assertEqual(response['body'], 'Hello, world!')
        self.assertEqual(response['body_formatted'], '<p>Hello, world!</p>')
        self.assertEqual(response['topic_id'], topic.id)
        self.assertEqual(
            response['path'],
            '/topic/%s/%s/' % (topic.id, post.number))
        self.assertIn('bumped', response)
        self.assertIn('created_at', response)
        self.assertIn('ident', response)
        self.assertIn('name', response)
        self.assertIn('number', response)
        self.assertNotIn('ip_address', response)

    def test_post_with_topic(self):
        board = self._makeBoard(title='Foobar', slug='foo')
        topic = self._makeTopic(board=board, title='Baz')
        post = self._makePost(topic=topic, body='Hello, world!')
        request = self._makeRequest(params={'topic': True})
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_topic', '/topic/{topic}/')
        config.add_route('api_topic_posts_scoped', '/topic/{topic}/{query}/')
        response = self._makeOne(post, request=request)
        self.assertIn('topic', response)

    def test_post_with_topic_board(self):
        board = self._makeBoard(title='Foobar', slug='foo')
        topic = self._makeTopic(board=board, title='Baz')
        post = self._makePost(topic=topic, body='Hello, world!')
        request = self._makeRequest(params={'topic': True, 'board': True})
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_board', '/board/{board}/')
        config.add_route('api_topic', '/topic/{topic}/')
        config.add_route('api_topic_posts_scoped', '/topic/{topic}/{query}/')
        response = self._makeOne(post, request=request)
        self.assertIn('topic', response)
        self.assertIn('board', response['topic'])

    def test_post_with_topic_posts(self):
        board = self._makeBoard(title='Foobar', slug='foo')
        topic = self._makeTopic(board=board, title='Baz')
        post = self._makePost(topic=topic, body='Hello, world!')
        request = self._makeRequest(params={'topic': True, 'posts': True})
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_topic', '/topic/{topic}/')
        config.add_route('api_topic_posts_scoped', '/topic/{topic}/{query}/')
        response = self._makeOne(post, request=request)
        self.assertIn('topic', response)
        self.assertNotIn('posts', response['topic'])

    def test_page(self):
        page = self._makePage(title='Test', body='**Test**', slug='test')
        request = self._makeRequest()
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_page', '/page/{page}')
        response = self._makeOne(page, request=request)
        self.assertEqual(response['type'], 'page')
        self.assertEqual(response['body'], '**Test**')
        self.assertEqual(
            response['body_formatted'],
            '<p><strong>Test</strong></p>\n')
        self.assertEqual(response['formatter'], 'markdown')
        self.assertEqual(response['slug'], 'test')
        self.assertEqual(response['title'], 'Test')
        self.assertEqual(response['path'], '/page/test')
        self.assertIn('updated_at', response)


class TestJSONRendererWithTask(
        TaskMixin,
        ModelMixin,
        RegistryMixin,
        unittest.TestCase):

    def _getTargetFunction(self):
        from fanboi2.serializers import initialize_renderer
        return initialize_renderer()

    def _makeOne(self, object, request=None):
        if request is None:  # pragma: no cover
            request = testing.DummyRequest()
        renderer = self._getTargetFunction()(None)
        return json.loads(renderer(object, {'request': request}))

    def test_result_proxy(self):
        from fanboi2.tasks import ResultProxy
        request = self._makeRequest()
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_task', '/task/{task}/')
        result_proxy = ResultProxy(DummyAsyncResult('demo', 'pending'))
        response = self._makeOne(result_proxy, request=request)
        self.assertEqual(response['type'], 'task')
        self.assertEqual(response['status'], 'pending')
        self.assertEqual(response['id'], 'demo')
        self.assertEqual(response['path'], '/task/demo/')
        self.assertNotIn('data', response)

    def test_result_proxy_success(self):
        from fanboi2.tasks import ResultProxy
        board = self._makeBoard(title='Foobar', slug='foo')
        request = self._makeRequest()
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_task', '/task/{task}/')
        config.add_route('api_board', '/board/{board}/')
        result = ['board', board.id]
        result_proxy = ResultProxy(DummyAsyncResult('demo', 'success', result))
        response = self._makeOne(result_proxy, request=request)
        self.assertEqual(response['type'], 'task')
        self.assertEqual(response['status'], 'success')
        self.assertEqual(response['id'], 'demo')
        self.assertEqual(response['path'], '/task/demo/')
        self.assertIn('data', response)

    def test_async_result(self):
        from fanboi2.tasks import celery
        request = self._makeRequest()
        config = self._makeConfig(request, self._makeRegistry())
        config.add_route('api_task', '/task/{task}/')
        async_result = celery.AsyncResult('demo')
        response = self._makeOne(async_result, request=request)
        self.assertEqual(response['type'], 'task')
        self.assertEqual(response['status'], 'queued')
        self.assertEqual(response['id'], 'demo')
        self.assertEqual(response['path'], '/task/demo/')
