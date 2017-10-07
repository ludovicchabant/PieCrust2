import re
import os
import os.path
import logging
import datetime
import yaml
from werkzeug.utils import secure_filename
from flask import g, request, abort, Response
from flask_indieauth import requires_indieauth
from ..blueprint import foodtruck_bp
from piecrust.configuration import merge_dicts
from piecrust.page import Page


logger = logging.getLogger(__name__)

re_unsafe_asset_char = re.compile('[^a-zA-Z0-9_]')


@foodtruck_bp.route('/micropub', methods=['POST'])
@requires_indieauth
def micropub():
    post_type = request.form.get('h')

    if post_type == 'entry':
        uri = _create_hentry()
        _run_publisher()
        return _get_location_response(uri)

    logger.debug("Unknown or unsupported update type.")
    logger.debug(request.form)
    abort(400)


def _run_publisher():
    pcapp = g.site.piecrust_app
    target = pcapp.config.get('micropub/publish_target')
    if target:
        logger.debug("Running pushing target '%s'." % target)
        g.site.publish(target)


def _get_location_response(uri):
    logger.debug("Redirecting to: %s" % uri)
    r = Response()
    r.status_code = 201
    r.headers.add('Location', uri)
    return r


def _create_hentry():
    f = request.form
    pcapp = g.site.piecrust_app

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
    photo_names = None
    if photos:
        photo_dir, _ = os.path.splitext(content_item.spec)
        photo_dir += '-assets'
        if not os.path.exists(photo_dir):
            os.makedirs(photo_dir)

        photo_names = []
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

        if photo_urls:
            fp.write('\n\n')
            for pu in photo_urls:
                fp.write('<img src="{{assets.%s}}" alt=""/>\n\n' % pu)

        if photo_names:
            fp.write('\n\n')
            for pn in photo_names:
                fp.write('<img src="{{assets.%s}}" alt="%s"/>\n\n' %
                         (pn, pn))

    page = Page(source, content_item)
    uri = page.getUri()
    return uri

