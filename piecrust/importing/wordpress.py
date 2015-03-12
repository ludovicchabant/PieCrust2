import os.path
import logging
import datetime
import yaml
from urllib.parse import urlparse
from piecrust import CONFIG_PATH
from piecrust.importing.base import Importer, create_page, download_asset
from piecrust.sources.base import MODE_CREATING


logger = logging.getLogger(__name__)


class WordpressImporter(Importer):
    name = 'wordpress'
    description = "Imports a Wordpress blog."

    def setupParser(self, parser, app):
        parser.add_argument(
                '--posts_fs',
                default="hierarchy",
                choices=['flat', 'shallow', 'hierarchy'],
                help="The blog file-system type to use.")
        parser.add_argument(
                '--prefix',
                default="wp_",
                help="The SQL table prefix. Defaults to `wp_`.")
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
        parser.add_argument(
                'xml_or_db_url',
                help=("The exported XML archive of the Wordpress site, or "
                      "the URL of the SQL database.\n"
                      "\n"
                      "If an SQL database URL, it should be of the "
                      "form:  type://user:password@server/database\n"
                      "\n"
                      "For example:\n"
                      "mysql://user:password@example.org/my_database"))

    def importWebsite(self, app, args):
        parsed_url = urlparse(args.xml_or_db_url)
        if not parsed_url.scheme:
            impl = _XmlImporter(app, args)
        else:
            impl = _SqlImporter(app, args)
        return impl.importWebsite()


class _XmlImporter(object):
    ns_wp = {'wp': 'http://wordpress.org/export/1.2/'}
    ns_dc = {'dc': "http://purl.org/dc/elements/1.1/"}
    ns_excerpt = {'excerpt': "http://wordpress.org/export/1.2/excerpt/"}
    ns_content = {'content': "http://purl.org/rss/1.0/modules/content/"}

    def __init__(self, app, args):
        self.app = app
        self.path = args.xml_or_db_url
        self.posts_fs = args.posts_fs
        self._cat_map = {}
        self._author_map = {}

        for cls in self.app.plugin_loader.getSources():
            if cls.SOURCE_NAME == ('posts/%s' % self.posts_fs):
                src_config = {
                        'type': 'posts/%s' % self.posts_fs,
                        'fs_endpoint': 'posts',
                        'data_type': 'blog'}
                self.posts_source = cls(app, 'posts', src_config)
                break
        else:
            raise Exception("No such posts file-system: " % self.posts_fs)

    def importWebsite(self):
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

        # Get basic site information
        title = find_text(channel, 'title')
        description = find_text(channel, 'description')
        site_config = {
                'site': {
                    'title': title,
                    'description': description,
                    'posts_fs': self.posts_fs}
                }
        logger.info("Importing '%s'" % title)

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

        # Other stuff.
        site_config['site'].update({
                'post_url': '%year%/%month%/%slug%',
                'category_url': 'category/%category%'})

        logger.info("Generating site configuration...")
        site_config_path = os.path.join(self.app.root_dir, CONFIG_PATH)
        with open(site_config_path, 'w') as fp:
            yaml.safe_dump(site_config, fp, default_flow_style=False,
                           allow_unicode=True)

        # Content.
        for i in channel.findall('item'):
            post_type = find_text(i, 'wp:post_type', self.ns_wp)
            if post_type == 'attachment':
                self._createAsset(i)
            elif post_type == 'post':
                self._createPost(i)

        self._cat_map = None
        self._author_map = None

    def _createAsset(self, node):
        url = find_text(node, 'wp:attachment_url', self.ns_wp)
        download_asset(self.app, url)

    def _getPageMetadata(self, node):
        title = find_text(node, 'title')
        creator = find_text(node, 'dc:creator', self.ns_dc)
        status = find_text(node, 'wp:status', self.ns_wp)
        post_id = find_text(node, 'wp:post_id', self.ns_wp)
        guid = find_text(node, 'guid')
        description = find_text(node, 'description')
        # TODO: menu order, parent, password, sticky

        categories = []
        for c in node.findall('category'):
            nicename = str(c.attrib.get('nicename'))
            categories.append(nicename)

        metadata = {
                'title': title,
                'author': creator,
                'status': status,
                'post_id': post_id,
                'post_guid': guid,
                'description': description,
                'categories': categories}

        for m in node.findall('wp:postmeta', self.ns_wp):
            key = find_text(m, 'wp:meta_key', self.ns_wp)
            metadata[key] = find_text(m, 'wp:meta_value', self.ns_wp)

        return metadata

    def _getPageContents(self, node):
        content = find_text(node, 'content:encoded', self.ns_content)
        excerpt = find_text(node, 'excerpt:encoded', self.ns_excerpt)
        if not excerpt.strip():
            return content
        return "%s\n\n---excerpt---\n\n%s" % (content, excerpt)

    def _getPageInfo(self, node):
        url = find_text(node, 'link')
        post_date_str = find_text(node, 'wp:post_date', self.ns_wp)
        post_date = datetime.datetime.strptime(post_date_str,
                                               '%Y-%m-%d %H:%M:%S')
        post_name = find_text(node, 'wp:post_name', self.ns_wp)
        return {
                'url': url,
                'slug': post_name,
                'datetime': post_date}

    def _createPage(self, node):
        info = self._getPageInfo(node)
        rel_path = os.path.join('pages', info['slug'])
        metadata = self._getPageMetadata(node)
        contents = self._getPageContents(node)
        create_page(self.app, rel_path, metadata, contents)

    def _createPost(self, node):
        info = self._getPageInfo(node)
        post_dt = info['datetime']
        finder = {
                'year': post_dt.year,
                'month': post_dt.month,
                'day': post_dt.day,
                'slug': info['slug']}
        rel_path, fac_metadata = self.posts_source.findPagePath(
                finder, MODE_CREATING)
        rel_path = os.path.join('posts', rel_path)
        metadata = self._getPageMetadata(node)
        contents = self._getPageContents(node)
        create_page(self.app, rel_path, metadata, contents)


class _SqlImporter(object):
    def __init__(self, app, args):
        self.app = app
        self.db_url = args.xml_or_db_url
        self.prefix = args.prefix

    def importWebsite(self):
        raise NotImplementedError()


def find_text(parent, child_name, namespaces=None):
    return str(parent.find(child_name, namespaces).text)

