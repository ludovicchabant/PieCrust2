import re
import os
import os.path
import json
import uuid
import logging
import datetime
import yaml
from werkzeug.utils import secure_filename
from flask import g, url_for, request, abort, jsonify, Response
from flask_indieauth import requires_indieauth
from ..blueprint import foodtruck_bp
from piecrust import CACHE_DIR
from piecrust.configuration import merge_dicts
from piecrust.page import Page


logger = logging.getLogger(__name__)

re_unsafe_asset_char = re.compile('[^a-zA-Z0-9_]')


def _patch_flask_indieauth():
    import flask_indieauth

    def _patched_get_access_token_from_json_request(request):
        try:
            jsondata = json.loads(request.get_data(as_text=True))
            return jsondata['access_token']
        except ValueError:
            return None

    _orig_check_auth = flask_indieauth.check_auth

    def _patched_check_auth(access_token):
        user_agent = request.headers.get('User-Agent') or ''
        if user_agent.startswith('Micro.blog/'):
            return None
        return _orig_check_auth(access_token)

    flask_indieauth.get_access_token_from_json_request = \
        _patched_get_access_token_from_json_request
    flask_indieauth.check_auth = _patched_check_auth
    logger.info("Patched Flask-IndieAuth.")


_patch_flask_indieauth()


_enable_debug_auth = False


def _debug_auth():
    if _enable_debug_auth:
        logger.warning("Headers: %s" % request.headers)
        logger.warning("Args: %s" % request.args)
        logger.warning("Form: %s" % request.form)
        logger.warning("Data: %s" % request.get_data(True))


@foodtruck_bp.route('/micropub', methods=['POST'])
@requires_indieauth
def post_micropub():
    _debug_auth()

    post_type = request.form.get('h')

    if post_type == 'entry':
        source_name, content_item = _create_hentry()
        _run_publisher()
        return _get_location_response(source_name, content_item)

    logger.debug("Unknown or unsupported update type.")
    logger.debug(request.form)
    abort(400)


@foodtruck_bp.route('/micropub/media', methods=['POST'])
@requires_indieauth
def post_micropub_media():
    _debug_auth()
    photo = request.files.get('file')
    if not photo:
        logger.error("Micropub media request without a file part.")
        abort(400)
        return

    fn = secure_filename(photo.filename)
    fn = re_unsafe_asset_char.sub('_', fn)
    fn = '%s_%s' % (str(uuid.uuid1()), fn)

    photo_cache_dir = os.path.join(
        g.site.root_dir,
        CACHE_DIR, g.site.piecrust_factory.cache_key,
        'uploads')
    try:
        os.makedirs(photo_cache_dir, mode=0o775, exist_ok=True)
    except OSError:
        pass

    photo_path = os.path.join(photo_cache_dir, fn)
    logger.info("Uploading file to: %s" % photo_path)
    photo.save(photo_path)

    r = Response()
    r.status_code = 201
    r.headers.add('Location', fn)
    return r


@foodtruck_bp.route('/micropub', methods=['GET'])
def get_micropub():
    data = {}
    if request.args.get('q') == 'config':
        endpoint_url = (request.host_url.rstrip('/') +
                        url_for('.post_micropub_media'))
        data.update({
           "media-endpoint": endpoint_url
        })

        pcapp = g.site.piecrust_app
        syn_data = pcapp.config.get('micropub/syndicate_to')
        if syn_data:
            data['syndicate-to'] = syn_data

    return jsonify(**data)


def _run_publisher():
    pcapp = g.site.piecrust_app
    target = pcapp.config.get('micropub/publish_target')
    if target:
        logger.debug("Running pushing target '%s'." % target)
        g.site.publish(target)


def _get_location_response(source_name, content_item):
    from piecrust.app import PieCrust
    pcapp = PieCrust(g.site.root_dir)
    source = pcapp.getSource(source_name)

    page = Page(source, content_item)
    uri = page.getUri()

    logger.debug("Redirecting to: %s" % uri)
    r = Response()
    r.status_code = 201
    r.headers.add('Location', uri)
    return r


def _create_hentry():
    f = request.form

    summary = f.get('summary')
    categories = f.getlist('category[]')
    location = f.get('location')
    reply_to = f.get('in-reply-to')
    status = f.get('post-status')
    # pubdate = f.get('published', 'now')

    # Figure out the title of the post.
    name = f.get('name')
    if not name:
        name = f.get('name[]')

    # Figure out the contents of the post.
    post_format = None
    content = f.get('content')
    if not content:
        content = f.get('content[]')
    if not content:
        content = f.get('content[html]')
        post_format = 'none'

    if not content:
        logger.error("No content specified!")
        logger.error(dict(request.form))
        abort(400)

    # TODO: setting to conserve Windows-type line endings?
    content = content.replace('\r\n', '\n')
    if summary:
        summary = summary.replace('\r\n', '\n')

    # Figure out the slug of the post.
    now = datetime.datetime.now()
    slug = f.get('slug')
    if not slug:
        slug = f.get('mp-slug')
    if not slug:
        slug = '%02d%02d%02d' % (now.hour, now.minute, now.second)

    # Get the media to attach to the post.
    photo_urls = None
    if 'photo' in f:
        photo_urls = [f['photo']]
    elif 'photo[]' in f:
        photo_urls = f.getlist('photo[]')

    photos = None
    if 'photo' in request.files:
        photos = [request.files['photo']]
    elif 'photo[]' in request.files:
        photos = request.files.getlist('photo[]')

    # Create the post in the correct content source.
    pcapp = g.site.piecrust_app
    source_name = pcapp.config.get('micropub/source', 'posts')
    source = pcapp.getSource(source_name)

    metadata = {
        'date': now,
        'slug': slug
    }
    logger.debug("Creating item with metadata: %s" % metadata)
    content_item = source.createContent(metadata)
    if content_item is None:
        logger.error("Can't create item for: %s" % metadata)
        abort(500)

    # TODO: add proper APIs for creating related assets.
    photo_names = []
    if photo_urls or photos:
        photo_dir, _ = os.path.splitext(content_item.spec)
        photo_dir += '-assets'
        try:
            os.makedirs(photo_dir, mode=0o775, exist_ok=True)
        except OSError:
            pass

    # Photo URLs come from files uploaded via the media endpoint...
    # They're waiting for us in the upload cache folder, so let's
    # move them to the post's assets folder.
    if photo_urls:
        photo_cache_dir = os.path.join(
            g.site.root_dir,
            CACHE_DIR, g.site.piecrust_factory.cache_key,
            'uploads')

        for p_url in photo_urls:
            _, __, p_url = p_url.rpartition('/')
            p_path = os.path.join(photo_cache_dir, p_url)
            p_uuid, p_fn = p_url.split('_', 1)
            p_asset = os.path.join(photo_dir, p_fn)
            logger.info("Moving upload '%s' to '%s'." % (p_path, p_asset))
            os.rename(p_path, p_asset)

            p_fn_no_ext, _ = os.path.splitext(p_fn)
            photo_names.append(p_fn_no_ext)

    # There could also be some files uploaded along with the post
    # so upload them right now.
    if photos:
        for photo in photos:
            if not photo or not photo.filename:
                logger.warning("Got empty photo in request files... skipping.")
                continue

            fn = secure_filename(photo.filename)
            fn = re_unsafe_asset_char.sub('_', fn)
            photo_path = os.path.join(photo_dir, fn)
            logger.info("Uploading file to: %s" % photo_path)
            photo.save(photo_path)

            fn_no_ext, _ = os.path.splitext(fn)
            photo_names.append(fn_no_ext)

    # Build the config.
    post_config = {}
    if name:
        post_config['title'] = name
    if categories:
        post_config['tags'] = categories
    if location:
        post_config['location'] = location
    if reply_to:
        post_config['reply_to'] = reply_to
    if status:
        post_config['status'] = status
    if post_format:
        post_config['format'] = post_format
    post_config['time'] = '%02d:%02d:%02d' % (now.hour, now.minute, now.second)

    # If there's no title, this is a "microblogging" post.
    if not name:
        micro_config = pcapp.config.get('micropub/microblogging')
        if micro_config:
            merge_dicts(post_config, micro_config)

    logger.debug("Writing to item: %s" % content_item.spec)
    with source.openItem(content_item, mode='w') as fp:
        fp.write('---\n')
        yaml.dump(post_config, fp,
                  default_flow_style=False,
                  allow_unicode=True)
        fp.write('---\n')

        if summary:
            fp.write(summary)
            fp.write('\n')
            fp.write('<!--break-->\n\n')
        fp.write(content)

        if photo_names:
            fp.write('\n\n')
            for pn in photo_names:
                fp.write('<img src="{{assets.%s}}" alt="%s"/>\n\n' %
                         (pn, pn))

        if os.supports_fd:
            import stat
            try:
                os.chmod(fp.fileno(),
                         stat.S_IRUSR|stat.S_IWUSR|stat.S_IRGRP|stat.S_IWGRP)
            except OSError:
                pass

    return source_name, content_item

