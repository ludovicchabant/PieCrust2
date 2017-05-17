import os.path
import logging
import datetime
import yaml
from collections import OrderedDict
from piecrust import CONFIG_PATH
from piecrust.configuration import (
    ConfigurationLoader, ConfigurationDumper, merge_dicts)
from piecrust.importing.base import Importer, create_page, download_asset


logger = logging.getLogger(__name__)


class WordpressImporterBase(Importer):
    def setupParser(self, parser, app):
        parser.add_argument(
            '--pages-source',
            default="pages",
            help="The source to store pages in.")
        parser.add_argument(
            '--posts-source',
            default="posts",
            help="The source to store posts in.")
        parser.add_argument(
            '--default-post-layout',
            help="The default layout to use for posts.")
        parser.add_argument(
            '--default-post-category',
            help="The default category to use for posts.")
        parser.add_argument(
            '--default-page-layout',
            help="The default layout to use for pages.")
        parser.add_argument(
            '--default-page-category',
            help="The default category to use for pages.")

    def importWebsite(self, app, args):
        impl = self._getImplementation(app, args)
        return impl.importWebsite()

    def _getImplementation(self, app, args):
        raise NotImplementedError()


class _ImporterBase(object):
    def __init__(self, app, args):
        self.app = app
        self._cat_map = {}
        self._author_map = {}
        self._pages_source = app.getSource(args.pages_source)
        self._posts_source = app.getSource(args.posts_source)

    def importWebsite(self):
        ctx = self._open()

        # Site configuration.
        logger.info("Generating site configuration...")
        site_config = self._getSiteConfig(ctx)
        site_config.setdefault('site', {})
        site_config['site'].update({
            'post_url': '%year%/%month%/%slug%',
            'category_url': 'category/%category%'})

        site_config_path = os.path.join(self.app.root_dir, CONFIG_PATH)
        with open(site_config_path, 'r') as fp:
            cfg_data = yaml.load(fp, Loader=ConfigurationLoader)

        cfg_data = cfg_data or {}
        merge_dicts(cfg_data, site_config)

        with open(site_config_path, 'w') as fp:
            yaml.dump(cfg_data, fp, default_flow_style=False,
                      allow_unicode=True,
                      Dumper=ConfigurationDumper)

        # Content
        for p in self._getPosts(ctx):
            if p['type'] == 'attachment':
                self._createAsset(p)
            else:
                self._createPost(p)

        self._close(ctx)

    def _open(self):
        raise NotImplementedError()

    def _close(self, ctx):
        pass

    def _getSiteConfig(self, ctx):
        raise NotImplementedError()

    def _getPosts(self, ctx):
        raise NotImplementedError()

    def _createAsset(self, asset_info):
        download_asset(self.app, asset_info['url'])

    def _createPost(self, post_info):
        post_dt = post_info['datetime']
        finder = {
            'year': post_dt.year,
            'month': post_dt.month,
            'day': post_dt.day,
            'slug': post_info['slug']}
        if post_info['type'] == 'post':
            source = self._posts_source
        elif post_info['type'] == 'page':
            source = self._pages_source
        else:
            raise Exception("Unknown post type: %s" % post_info['type'])
        factory = source.findPageFactory(finder, MODE_CREATING)

        metadata = post_info['metadata'].copy()
        for name in ['title', 'author', 'status', 'post_id', 'post_guid',
                     'description', 'categories']:
            val = post_info.get(name)
            if val is not None:
                metadata[name] = val

        content = post_info['content']
        excerpt = post_info['excerpt']
        text = content
        if excerpt is not None and excerpt.strip() != '':
            text = "%s\n\n---excerpt---\n\n%s" % (content, excerpt)

        status = metadata.get('status')
        if status == 'publish':
            path = factory.path
            create_page(self.app, path, metadata, text)
        elif status == 'draft':
            filename = '-'.join(metadata['title'].split(' ')) + '.html'
            path = os.path.join(self.app.root_dir, 'drafts', filename)
            create_page(self.app, path, metadata, text)
        else:
            logger.warning("Ignoring post with status: %s" % status)


class _XmlImporter(_ImporterBase):
    ns_wp = {'wp': 'http://wordpress.org/export/1.2/'}
    ns_dc = {'dc': "http://purl.org/dc/elements/1.1/"}
    ns_excerpt = {'excerpt': "http://wordpress.org/export/1.2/excerpt/"}
    ns_content = {'content': "http://purl.org/rss/1.0/modules/content/"}

    def __init__(self, app, args):
        super(_XmlImporter, self).__init__(app, args)
        self.path = args.xml_path

    def _open(self):
        if not os.path.exists(self.path):
            raise Exception("No such file: %s" % self.path)

        try:
            import xml.etree.ElementTree as ET
        except ImportError:
            logger.error("You don't seem to have any support for ElementTree "
                         "XML parsing.")
            return 1

        with open(self.path, 'r', encoding='utf8') as fp:
            xml = fp.read()
        xml = xml.replace(chr(0x1e), '')
        xml = xml.replace(chr(0x10), '')
        tree = ET.fromstring(xml)
        channel = tree.find('channel')

        return channel

    def _getSiteConfig(self, channel):
        # Get basic site information
        title = find_text(channel, 'title')
        description = find_text(channel, 'description')
        site_config = OrderedDict({
            'site': {
                'title': title,
                'description': description}
        })

        # Get authors' names.
        authors = {}
        for a in channel.findall('wp:author', self.ns_wp):
            login = find_text(a, 'wp:author_login', self.ns_wp)
            authors[login] = {
                'email': find_text(a, 'wp:author_email', self.ns_wp),
                'display_name': find_text(a, 'wp:author_display_name',
                                          self.ns_wp),
                'first_name': find_text(a, 'wp:author_first_name',
                                        self.ns_wp),
                'last_name': find_text(a, 'wp:author_last_name',
                                       self.ns_wp),
                'author_id': find_text(a, 'wp:author_id',
                                       self.ns_wp)}
        site_config['site']['authors'] = authors

        return site_config

    def _getPosts(self, channel):
        for i in channel.findall('item'):
            post_type = find_text(i, 'wp:post_type', self.ns_wp)
            if post_type == 'attachment':
                yield self._getAssetInfo(i)
            else:
                yield self._getPostInfo(i)

    def _getAssetInfo(self, node):
        url = find_text(node, 'wp:attachment_url', self.ns_wp)
        return {'type': 'attachment', 'url': url}

    def _getPostInfo(self, node):
        post_date_str = find_text(node, 'wp:post_date', self.ns_wp)
        post_date = datetime.datetime.strptime(post_date_str,
                                               '%Y-%m-%d %H:%M:%S')
        post_name = find_text(node, 'wp:post_name', self.ns_wp)
        post_type = find_text(node, 'wp:post_type', self.ns_wp)
        post_info = {
            'type': post_type,
            'slug': post_name,
            'datetime': post_date}

        title = find_text(node, 'title')
        creator = find_text(node, 'dc:creator', self.ns_dc)
        status = find_text(node, 'wp:status', self.ns_wp)
        post_id = find_text(node, 'wp:post_id', self.ns_wp)
        guid = find_text(node, 'guid')
        description = find_text(node, 'description')
        # TODO: menu order, parent, password, sticky
        post_info.update({
            'title': title,
            'author': creator,
            'status': status,
            'post_id': post_id,
            'post_guid': guid,
            'description': description})

        categories = []
        for c in node.findall('category'):
            nicename = str(c.attrib.get('nicename'))
            categories.append(nicename)
        post_info['categories'] = categories

        metadata = {}
        for m in node.findall('wp:postmeta', self.ns_wp):
            key = find_text(m, 'wp:meta_key', self.ns_wp)
            metadata[key] = find_text(m, 'wp:meta_value', self.ns_wp)
        post_info['metadata'] = metadata

        content = find_text(node, 'content:encoded', self.ns_content)
        excerpt = find_text(node, 'excerpt:encoded', self.ns_excerpt)
        post_info.update({
            'content': content,
            'excerpt': excerpt})

        return post_info


class WordpressXmlImporter(WordpressImporterBase):
    name = 'wordpress-xml'
    description = "Imports a Wordpress blog from an exported XML archive."

    def setupParser(self, parser, app):
        super(WordpressXmlImporter, self).setupParser(parser, app)
        parser.add_argument(
                'xml_path',
                help="The path to the exported XML archive file.")

    def _getImplementation(self, app, args):
        return _XmlImporter(app, args)


def find_text(parent, child_name, namespaces=None):
    return str(parent.find(child_name, namespaces).text)

