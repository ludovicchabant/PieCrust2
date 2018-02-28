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

    flask_indieauth.get_access_token_from_json_request = \
        _patched_get_access_token_from_json_request
    logger.info("Patched Flask-IndieAuth.")


_patch_flask_indieauth()


_enable_debug_req = False


def _debug_req():
    if _enable_debug_req:
        logger.warning("Headers: %s" % request.headers)
        logger.warning("Args: %s" % request.args)
        logger.warning("Form: %s" % request.form)
        logger.warning("Data: %s" % request.get_data(True))
        try:
            logger.warning("JSON: %s" % request.json)
        except:  # NOQA
            pass


@foodtruck_bp.route('/micropub', methods=['POST'])
@requires_indieauth
def post_micropub():
    _debug_req()

    if 'h' in request.form:
        data = _get_mf2_from_form(request.form)
    else:
        try:
            data = json.loads(request.get_data(as_text=True))
        except Exception:
            data = None

    if data:
        entry_type = _mf2get(data, 'type')
        if entry_type == 'h-entry':
            source_name, content_item, do_publish = \
                _create_hentry(data['properties'])
            if do_publish:
                _run_publisher()
            return _get_location_response(source_name, content_item)

        else:
            logger.error("Post type '%s' is not supported." % entry_type)
    else:
        logger.error("Missing form or JSON data.")

    abort(400)


@foodtruck_bp.route('/micropub/media', methods=['POST'])
@requires_indieauth
def post_micropub_media():
    _debug_req()

    photo = request.files.get('file')
    if not photo:
        logger.error("Micropub media request without a file part.")
        abort(400)
        return

    fn = secure_filename(photo.filename)
    fn = re_unsafe_asset_char.sub('_', fn)
    fn = '%s_%s' % (uuid.uuid1().hex, fn)
    fn = fn.rstrip('_')

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


re_array_prop = re.compile(r'\[(?P<name>\w*)\]$')


def _get_mf2_from_form(f):
    post_type = 'h-' + f.get('h', '')

    properties = {}
    for key, vals in f.lists():
        m = re_array_prop.search(key)
        if not m:
            properties[key] = vals
            continue

        key_name_only = key[:m.start()]
        inner_name = m.group('name')
        if not inner_name:
            properties[key_name_only] = vals
            continue

        properties[key_name_only] = [{inner_name: vals[0]}]

    return {
        'type': [post_type],
        'properties': properties}


def _mf2get(data, key):
    val = data.get(key)
    if val is not None:
        return val[0]
    return None


def _create_hentry(data):
    name = _mf2get(data, 'name')
    summary = _mf2get(data, 'summary')
    location = _mf2get(data, 'location')
    reply_to = _mf2get(data, 'in-reply-to')
    status = _mf2get(data, 'post-status')
    # pubdate = _mf2get(data, 'published') or 'now'

    categories = data.get('category')

    # Get the content.
    post_format = None
    content = _mf2get(data, 'content')
    if isinstance(content, dict):
        content = content.get('html')
        post_format = 'none'
    if not content:
        logger.error("No content specified!")
        logger.error(data)
        abort(400)

    # Clean-up stuff.
    # TODO: setting to conserve Windows-type line endings?
    content = content.replace('\r\n', '\n')
    if summary:
        summary = summary.replace('\r\n', '\n')

    # Get the slug.
    slug = _mf2get(data, 'slug') or _mf2get(data, 'mp-slug')
    now = datetime.datetime.now()
    if not slug:
        slug = '%02d%02d%02d' % (now.hour, now.minute, now.second)

    # Create the post in the correct content source.
    # Note that this won't actually write anything to disk yet, we're
    # just creating it in memory.
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

    paths_to_commit = []

    # Get the media to attach to the post.
    photos = None
    if 'photo' in request.files:
        photos = [request.files['photo']]
    elif 'photo[]' in request.files:
        photos = request.files.getlist('photo[]')
    photo_urls = data.get('photo')

    # Create the assets folder if we have anything to put there.
    # TODO: add proper APIs for creating related assets.
    if photo_urls or photos:
        photo_dir, _ = os.path.splitext(content_item.spec)
        photo_dir += '-assets'
        try:
            os.makedirs(photo_dir, mode=0o775, exist_ok=True)
        except OSError:
            # An `OSError` can still be raised in older versions of Python
            # if the permissions don't match an existing folder.
            # Let's ignore it.
            pass

    # Photo URLs come from files uploaded via the media endpoint...
    # They're waiting for us in the upload cache folder, so let's
    # move them to the post's assets folder.
    photo_names = []
    if photo_urls:
        photo_cache_dir = os.path.join(
            g.site.root_dir,
            CACHE_DIR, g.site.piecrust_factory.cache_key,
            'uploads')

        p_thumb_size = pcapp.config.get('micropub/resize_photos', 800)

        for p_url in photo_urls:
            _, __, p_fn = p_url.rpartition('/')
            p_cache_path = os.path.join(photo_cache_dir, p_fn)
            p_asset_path = os.path.join(photo_dir, p_fn)
            logger.info("Moving upload '%s' to '%s'." %
                        (p_cache_path, p_asset_path))
            try:
                os.rename(p_cache_path, p_asset_path)
                paths_to_commit.append(p_asset_path)
            except OSError:
                logger.error("Can't move '%s' to '%s'." %
                             (p_cache_path, p_asset_path))
                raise

            p_fn_no_ext, _ = os.path.splitext(p_fn)
            if p_thumb_size > 0:
                from PIL import Image
                im = Image.open(p_asset_path)
                im.thumbnail((p_thumb_size, p_thumb_size))
                p_thumb_path = os.path.join(photo_dir,
                                            '%s_thumb.jpg' % p_fn_no_ext)
                im.save(p_thumb_path)
                paths_to_commit.append(p_thumb_path)

                p_thumb_no_ext = '%s_thumb' % p_fn_no_ext
                photo_names.append((p_thumb_no_ext, p_fn_no_ext))
            else:
                photo_names.append((p_fn_no_ext, None))

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
            paths_to_commit.append(photo_path)

            # TODO: generate thumbnail.

            fn_no_ext, _ = os.path.splitext(fn)
            photo_names.append((fn_no_ext, None))

    # Build the config.
    do_publish = True
    post_config = {}
    if name:
        post_config['title'] = name
    if categories:
        post_config['tags'] = categories
    if location:
        post_config['location'] = location
    if reply_to:
        post_config['reply_to'] = reply_to
    if status and status != 'published':
        post_config['draft'] = True
        do_publish = False
    if post_format:
        post_config['format'] = post_format
    post_config['time'] = '%02d:%02d:%02d' % (now.hour, now.minute, now.second)

    # If there's no title, this is a "microblogging" post.
    if not name:
        micro_config = pcapp.config.get('micropub/microblogging')
        if micro_config:
            merge_dicts(post_config, micro_config)

    logger.debug("Writing to item: %s" % content_item.spec)
    paths_to_commit.append(content_item.spec)
    with source.openItem(content_item, mode='w', encoding='utf8') as fp:
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
            for pthumb, pfull in photo_names:
                if pfull:
                    fp.write('<a href="{{assets["%s"]}}">'
                             '<img src="{{assets["%s"]}}" alt="%s"/>'
                             '</a>\n\n' %
                             (pfull, pthumb, pthumb))
                else:
                    fp.write('<img src="{{assets["%s"]}}" alt="%s"/>\n\n' %
                             (pthumb, pthumb))

        if os.supports_fd:
            import stat
            try:
                os.chmod(
                    fp.fileno(),
                    stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP)
            except OSError:
                pass

    autocommit = pcapp.config.get('micropub/autocommit', False)
    if autocommit:
        scm = g.site.scm
        if scm:
            commit_msg = None
            if isinstance(autocommit, dict):
                commit_msg = autocommit.get('message')
            if not commit_msg:
                post_title = post_config.get('title')
                if post_title:
                    commit_msg = "New post: %s" % post_title
                else:
                    commit_msg = "New post"
            logger.debug("Commit files: %s" % paths_to_commit)
            scm.commit(paths_to_commit, commit_msg)

    return source_name, content_item, do_publish

