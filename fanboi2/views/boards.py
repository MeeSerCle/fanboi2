from pyramid.httpexceptions import HTTPNotFound, HTTPFound
from pyramid.renderers import render_to_response
from sqlalchemy.orm.exc import NoResultFound
from fanboi2.errors import RateLimitedError, ParamsInvalidError, \
    SpamRejectedError, DnsblRejectedError, StatusRejectedError, \
    BanRejectedError
from fanboi2.forms import SecurePostForm, SecureTopicForm
from fanboi2.tasks import celery
from fanboi2.views.api import boards_get, board_get, board_topics_get,\
    topic_get, topic_posts_get, topic_posts_post, board_topics_post, task_get


def root(request):
    """Display a list of all boards.

    :param request: A :class:`pyramid.request.Request` object.

    :type request: pyramid.request.Request
    :rtype: dict
    """
    boards = boards_get(request)
    return locals()


def board_show(request):
    """Display a single board with its related topics.

    :param request: A :class:`pyramid.request.Request` object.

    :type request: pyramid.request.Request
    :rtype: dict
    """
    board = board_get(request)
    topics = board_topics_get(request).limit(10)
    return locals()


def board_all(request):
    """Display a single board with a list of all its topic.

    :param request: A :class:`pyramid.request.Request` object.

    :type request: pyramid.request.Request
    :rtype: dict
    """
    board = board_get(request)
    topics = board_topics_get(request).all()
    return locals()


def board_new_get(request):
    """Display a form for creating new topic in a board. If a `task` query
    string is given, the function will try to retrieve and process that task
    in board context instead.

    :param request: A :class:`pyramid.request.Request` object.

    :type request: pyramid.request.Request
    :rtype: dict | pyramid.response.Response
    """
    board = board_get(request)

    if board.status != 'open':
        raise HTTPNotFound(request.path)

    if request.params.get('task'):
        try:
            task_result = celery.AsyncResult(request.params['task'])
            task = task_get(request, task_result)
        except SpamRejectedError as e:
            response = render_to_response('boards/error_spam.mako', locals())
            response.status = e.http_status
            return response
        except DnsblRejectedError as e:
            response = render_to_response('boards/error_dnsbl.mako', locals())
            response.status = e.http_status
            return response
        except BanRejectedError as e:
            response = render_to_response('boards/error_ban.mako', locals())
            response.status = e.http_status
            return response
        except StatusRejectedError as e:
            status = e.status
            response = render_to_response('boards/error_status.mako', locals())
            response.status = e.http_status
            return response

        if task.success():
            topic = task.object
            return HTTPFound(location=request.route_path(
                route_name='topic',
                board=board.slug,
                topic=topic.id))
        return render_to_response('boards/new_wait.mako', locals())

    form = SecureTopicForm(request=request)
    return locals()


def board_new_post(request):
    """Handle form posting for creating new topic in a board.

    :param request: A :class:`pyramid.request.Request` object.

    :type request: pyramid.request.Request
    :rtype: dict
    """
    board = board_get(request)
    form = SecureTopicForm(request.params, request=request)

    try:
        task = board_topics_post(request, board=board, form=form)
    except RateLimitedError as e:
        timeleft = e.timeleft
        response = render_to_response('boards/error_rate.mako', locals())
        response.status = e.http_status
        return response
    except ParamsInvalidError as e:
        request.response.status = e.http_status
        return locals()

    return HTTPFound(location=request.route_path(
        route_name='board_new',
        board=board.slug,
        _query={'task': task.id}))


def topic_show_get(request):
    """Display a single topic with its related posts. If a `task` query string
    is given, the function will try to retrieve and process that task in topic
    context instead.

    :param request: A :class:`pyramid.request.Request` object.

    :type request: pyramid.request.Request
    :rtype: dict | pyramid.response.Response
    """
    board = board_get(request)
    topic = topic_get(request)

    if request.params.get('task'):
        try:
            task_result = celery.AsyncResult(request.params['task'])
            task = task_get(request, task_result)
        except SpamRejectedError as e:
            response = render_to_response('topics/error_spam.mako', locals())
            response.status = e.http_status
            return response
        except BanRejectedError as e:
            response = render_to_response('topics/error_ban.mako', locals())
            response.status = e.http_status
            return response
        except StatusRejectedError as e:
            status = e.status
            response = render_to_response('topics/error_status.mako', locals())
            response.status = e.http_status
            return response

        if task.success():
            return HTTPFound(location=request.route_path(
                route_name='topic_scoped',
                board=board.slug,
                topic=topic.id,
                query='l10'))
        return render_to_response('topics/show_wait.mako', locals())

    posts = topic_posts_get(request, topic=topic)
    if not topic.board_id == board.id or not posts:
        raise HTTPNotFound(request.path)
    form = SecurePostForm(request=request)
    return locals()


def topic_show_post(request):
    """Handle form posting for replying to a topic.

    :param request: A :class:`pyramid.request.Request` object.

    :type request: pyramid.request.Request
    :rtype: dict
    """
    board = board_get(request)
    topic = topic_get(request)

    if not topic.board_id == board.id:
        raise HTTPNotFound(request.path)

    form = SecurePostForm(request.params, request=request)

    try:
        task = topic_posts_post(request, board=board, topic=topic, form=form)
    except RateLimitedError as e:
        timeleft = e.timeleft
        response = render_to_response('topics/error_rate.mako', locals())
        response.status = e.http_status
        return response
    except ParamsInvalidError as e:
        request.response.status = e.http_status
        return locals()

    return HTTPFound(location=request.route_path(
        route_name='topic',
        board=topic.board.slug,
        topic=topic.id,
        _query={'task': task.id}))


def error_not_found(exc, request):
    """Handle any exception that should cause the app to treat it as
    NotFound resources, such as :class:`pyramid.httpexceptions.HTTPNotFound`
    or :class:`sqlalchemy.orm.exc.NoResultFound`.

    :param exc: An :class:`Exception`.
    :param request: A :class:`pyramid.request.Request` object.

    :type exc: Exception
    :type request: pyramid.request.Request
    :rtype: pyramid.response.Response
    """
    response = render_to_response('not_found.mako', locals())
    response.status = '404 Not Found'
    return response


def includeme(config):  # pragma: no cover
    def _map_view(name, path, renderer, callables=None):
        config.add_route(name, path)
        if callables is not None:
            for method, callable in callables.items():
                config.add_view(
                    callable,
                    request_method=method,
                    route_name=name,
                    renderer=renderer)

    _map_view('root', '/', 'root.mako', {'GET': root})
    _map_view('board', '/{board}/', 'boards/show.mako', {'GET': board_show})
    _map_view('board_all', '/{board}/all/', 'boards/all.mako', {
        'GET': board_all})

    _map_view('board_new', '/{board}/new/', 'boards/new.mako', {
        'GET': board_new_get,
        'POST': board_new_post})

    _map_view('topic', '/{board:\w+}/{topic:\d+}/', 'topics/show.mako', {
        'GET': topic_show_get,
        'POST': topic_show_post})

    _map_view('topic_scoped',
        '/{board:\w+}/{topic:\d+}/{query}/',
        'topics/show.mako',
        {'GET': topic_show_get})

    config.add_view(error_not_found, context=NoResultFound)
    config.add_notfound_view(error_not_found, append_slash=True)
