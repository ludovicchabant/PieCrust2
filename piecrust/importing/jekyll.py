import os
import os.path
import re
import shutil
import yaml
import logging
from piecrust.configuration import parse_config_header
from piecrust.importing.base import FileWalkingImporter
from piecrust.uriutil import multi_replace


logger = logging.getLogger(__name__)


class JekyllImporter(FileWalkingImporter):
    name = 'jekyll'
    description = "Imports content from a Jekyll or Octopress blog."

    def setupParser(self, parser, app):
        super(JekyllImporter, self).setupParser(parser, app)
        parser.add_argument('root_dir',
                help="The root directory of the Jekyll or Octopress website.")

    def importWebsite(self, app, args):
        logger.debug("Importing Jekyll site from: %s" % args.root_dir)
        self._startWalk(args.root_dir, args.exclude, app)
        logger.info("The Jekyll website was successfully imported.")

    def _importFile(self, full_fn, rel_fn, app):
        logger.debug("- %s" % rel_fn)
        if rel_fn == '_config.yml':
            self.convertConfig(app, full_fn)
        elif rel_fn.startswith('_layouts'):
            self.convertLayout(app, full_fn, rel_fn[len('_layouts/'):])
        elif rel_fn.startswith('_includes'):
            self.convertInclude(app, full_fn, rel_fn[len('_includes/'):])
        elif rel_fn.startswith('_posts'):
            self.convertPost(app, full_fn, rel_fn[len('_posts/'):])
        else:
            with open(full_fn, 'rb') as fp:
                firstline = fp.read(3)
            if firstline == '---':
                self.convertPage(app, full_fn, rel_fn)
            else:
                self.convertStatic(app, full_fn, rel_fn)

    def convertConfig(self, app, src_path):
        logger.debug("  Converting configuration file.")
        with open(src_path, 'r', encoding='utf8') as fp:
            config = yaml.load(fp)

        if 'site' not in config:
            config['site'] = {}
        config['site']['related_posts'] = []
        config['site']['posts_fs'] = 'flat'
        config['site']['templates_dirs'] = ['includes', 'layouts']
        config['site']['tag_url'] = 'tags/%tag%'
        if 'permalink' in config:
            permalink = config['permalink']
            if permalink == 'date':
                permalink = '/:categories/:year/:month/:day/:title.html'
            elif permalink == 'pretty':
                permalink = '/:categories/:year/:month/:day/:title/'
            elif permalink == 'none':
                permalink = '/:categories/:title.html'

            # TODO: handle `:categories` token.
            post_url = multi_replace(
                    permalink,
                    {':year': '%year%', ':month': '%month%', ':day': '%day%',
                        ':title': '%slug%', ':categories': ''})
            post_url = post_url.replace('//', '/').strip('/')
            config['site']['post_url'] = post_url
        if 'exclude' in config:
            if 'baker' not in config:
                config['baker'] = {}
            config['baker']['ignore'] = list(map(
                    lambda i: '^/_%s/' % re.escape(i)))
        if 'jinja' not in config:
            config['jinja'] = {}
        config['jinja']['auto_escape'] = False
        if 'markdown' in config:
            if not isinstance(config['markdown'], dict):
                logger.warning("Discarding markdown setting: %s" %
                        config['markdown'])
                del config['markdown']

        with open(os.path.join(app.root_dir, 'config.yml'), 'w') as fp:
            yaml.dump(config, stream=fp)

    def convertPage(self, app, path, rel_path):
        logger.debug("  Converting page: %s" % rel_path)
        is_index = False
        is_static = False
        _, ext = os.path.splitext(rel_path)
        if re.search(r'^index\.(html?|textile|markdown)$', rel_path):
            out_path = os.path.join(app.root_dir, 'pages', '_index' + ext)
            is_index = True
        else:
            out_path = os.path.join(app.root_dir, 'pages', rel_path)

        if ext not in ['htm', 'html', 'textile', 'markdown']:
            # There could be static files (SCSS or Less files) that look like
            # pages because they have a YAML front matter.
            is_static = True
            out_path = os.path.join(app.root_dir, 'assets', rel_path)

        if is_static:
            logger.debug("  Actually a static file... forwarding converstion.")
            self.convertStatic(app, path, rel_path, True)
            return

        self._doConvertPage(app, path, out_path)
        if is_index:
            shutil.copy2(out_path, os.path.join(app.root_dir, 'pages', '_tag.%s' % ext))

    def convertPost(self, app, path, rel_path):
        logger.debug("  Converting post: %s" % rel_path)
        out_path = re.sub(
                r'(\d{4}\-\d{2}\-\d{2})\-(.*)$',
                r'\1_\2',
                rel_path)
        out_path = os.path.join(app.root_dir, 'posts', out_path)
        self._doConvertPage(app, path, out_path)

    def convertLayout(self, app, path, rel_path):
        logger.debug("  Converting layout: %s" % rel_path)
        out_path = os.path.join(app.root_dir, 'layouts', rel_path)
        self._doConvertPage(app, path, out_path, True)

    def convertInclude(self, app, path, rel_path):
        logger.debug("  Converting include: %s" % rel_path)
        out_path = os.path.join(app.root_dir, 'includes', rel_path)
        self._doConvertPage(app, path, out_path, True)

    def convertStatic(self, app, path, rel_path, strip_header=False):
        logger.debug("  Converting static: %s" % rel_path)
        out_path = os.path.join(app.root_dir, 'assets', rel_path)
        logger.debug("  %s -> %s" % (path, out_path))
        os.makedirs(os.path.dirname(out_path), 0o755, True)

        if strip_header:
            with open(path, 'r', encoding='utf8') as fp:
                content = fp.write()
            config, offset = parse_config_header(content)
            content = content[offset:]
            with open(out_path, 'w', encoding='utf8') as fp:
                fp.write(content)
            return

        shutil.copy2(path, out_path)

    def _doConvertPage(self, app, path, out_path, is_template=False):
        logger.debug("  %s -> %s" % (path, out_path))
        os.makedirs(os.path.dirname(out_path), 0o755, True)

        with open(path, 'r', encoding='utf8') as fp:
            contents = fp.read()

        config, offset = parse_config_header(contents)
        text = contents[offset:]
        text_before = text

        wrap_content_tag = True

        if is_template:
            if 'layout' in config:
                # Liquid doesn't support template inheritance but
                # Jinja does.
                text = ("{%% extends '%s.html' %%}\n\n"
                        "{%% block jekyllcontent %%}\n"
                        "%s\n"
                        "{%% endblock %%}\n" % (config['layout'], text))
                wrap_content_tag = False
        else:
            if 'layout' in config:
                if config['layout'] == 'nil':
                    config['layout'] = 'none'

        # Convert the template stuff we can:
        # - content tag may have to be wrapped in a `jekyllcontent`
        #   because Jekyll uses implicit layout inheritance
        #   placements.
        if wrap_content_tag:
            text = re.sub(
                    r'{{\s*content\s*}}',
                    r'{% block jekyllcontent %}{{ content }}{% endblock %}',
                    text)
        # - list of posts
        text = re.sub(
            '(?<=\{%|\{\{)([^\}]*)site.posts',
            '\\1blog.posts',
            text);
        text = re.sub(
            '(?<=\{%|\{\{)([^\}]*)paginator.posts',
            '\\1pagination.posts',
            text);
        # - list of categories or tags
        text = re.sub(
            '(?<=\{%|\{\{)([^\}]*)site.categories',
            '\\1blog.categories',
            text);
        text = re.sub(
            '(?<=\{%|\{\{)([^\}]*)site.tags',
            '\\1blog.tags',
            text);
        # - list of related posts
        text = re.sub(
            '(?<=\{%|\{\{)(?<!%\})site.related_posts',
            '\\1pagination.related_posts',
            text);
        # - enumeration limits
        text = re.sub(
            '{%\s*for\s+([^}]+)\s+limit\:\s*(\d+)',
            '{% for \\1[:\\2]',
            text);
        text = re.sub(
            '{%\s*for\s+([^}]+)\s+offset\:\s*(\d+)',
            '{% for \\1[\\2:]',
            text);
        # - code highlighting
        text = re.sub(
            '{%\s*highlight\s+([\w\d]+)\s*%}',
            '{% geshi \'\\1\' %}',
            text);
        text = re.sub(
            '{%\s*endhighlight\s*%}',
            '{% endgeshi %}',
            text);
        # - unless tag
        text = re.sub(
            '{%\s*unless\s+([^}]+)\s*%}',
            '{% if not \\1 %}',
            text);
        text = re.sub(
            '{%\s*endunless\s*%}',
            '{% endif %}',
            text);
        # - variable assignment
        text = re.sub(
            '\{%\s*assign\s+',
            '{% set ',
            text);
        # - include tag
        text = re.sub(
            '\{%\s*include\s+([\w\d\.\-_]+)\s*%}',
            '{% include "\\1" %}',
            text);
        # - truncate filter
        text = re.sub(
            '\|\s*truncate\:\s*(\d+)',
            '|truncate(\\1)',
            text);
        # - date filter
        text = re.sub(
            '\|\s*date\:\s*"([^"]+)"',
            '|date("\\1")',
            text);
        # - some filters we don't need
        text = re.sub(
            '\|\s*date_to_string',
            '',
            text);

        if text != text_before:
            # We changed the text, so create a backup.
            shutil.copy2(path, '%s.orig' % out_path)

        with open(out_path, 'w', encoding='utf8') as fp:
            if not is_template:
                fp.write("---\n")
                fp.write(yaml.dump(config))
                fp.write("---\n")
            fp.write(text)

