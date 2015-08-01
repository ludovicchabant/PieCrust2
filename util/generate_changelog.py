import os
import os.path
import re
import sys
import subprocess


hg_log_template = ("{if(tags, '>>{tags};{date|shortdate}\n')}"
                   "{desc|firstline}\n\n")

re_add_tag_changeset = re.compile('^Added tag [^\s]+ for changeset [\w\d]+$')
re_merge_pr_changeset = re.compile('^Merge pull request')
re_tag = re.compile('^\d+\.\d+\.\d+([ab]\d+)?(rc\d+)?$')
re_change = re.compile('^(\w+):')
re_clean_code_span = re.compile('([^\s])``([^\s]+)')

category_commands = [
        'chef', 'bake', 'find', 'help', 'import', 'init', 'paths', 'plugin',
        'plugins', 'prepare', 'purge', 'root', 'routes', 'serve',
        'showconfig', 'showrecord', 'sources', 'theme', 'themes']
category_core = [
        'internal', 'bug', 'templating', 'formatting', 'performance',
        'data', 'config', 'rendering', 'render', 'debug', 'reporting',
        'linker', 'pagination', 'routing', 'caching']
category_project = ['build', 'cm', 'docs', 'tests', 'setup']
categories = [
        ('commands', category_commands),
        ('core', category_core),
        ('project', category_project),
        ('miscellaneous', None)]
category_names = list(map(lambda i: i[0], categories))


def generate():
    out_file = 'CHANGELOG.rst'
    if len(sys.argv) > 1:
        out_file = sys.argv[1]

    print("Generating %s" % out_file)

    if not os.path.exists('.hg'):
        raise Exception("You must run this script from the root of a "
                        "Mercurial clone of the PieCrust repository.")
    hglog = subprocess.check_output([
        'hg', 'log',
        '--rev', 'reverse(::master)',
        '--template', hg_log_template])
    hglog = hglog.decode('utf8')

    templates = _get_templates()

    with open(out_file, 'w') as fp:
        fp.write(templates['header'])

        skip = False
        in_desc = False
        current_version = 0
        current_version_info = None
        current_changes = None
        for line in hglog.splitlines():
            if line == '':
                skip = False
                in_desc = False
                continue

            if not in_desc and line.startswith('>>'):
                tags, tag_date = line[2:].split(';')
                if re_tag.match(tags):
                    if current_version > 0:
                        _write_version_changes(
                                templates,
                                current_version, current_version_info,
                                current_changes, fp)

                    current_version += 1
                    current_version_info = tags, tag_date
                    current_changes = {}
                    in_desc = True
                else:
                    skip = True
                continue

            if skip or current_version == 0:
                continue

            if re_add_tag_changeset.match(line):
                continue
            if re_merge_pr_changeset.match(line):
                continue

            m = re_change.match(line)
            if m:
                ch_type = m.group(1)
                for cat_name, ch_types in categories:
                    if ch_types is None or ch_type in ch_types:
                        msgs = current_changes.setdefault(cat_name, [])
                        msgs.append(line)
                        break
                else:
                    assert False, ("Change '%s' should have gone in the "
                                   "misc. bucket." % line)
            else:
                msgs = current_changes.setdefault('miscellaneous', [])
                msgs.append(line)

        if current_version > 0:
            _write_version_changes(
                    templates,
                    current_version, current_version_info,
                    current_changes, fp)


def _write_version_changes(templates, version, version_info, changes, fp):
    tokens = {
            'num': str(version),
            'version': version_info[0],
            'date': version_info[1]}
    tpl = _multi_replace(templates['version_title'], tokens)
    fp.write(tpl)

    for i, cat_name in enumerate(category_names):
        msgs = changes.get(cat_name)
        if not msgs:
            continue

        tokens = {
                'sub_num': str(i),
                'category': cat_name.title()}
        tpl = _multi_replace(templates['category_title'], tokens)
        fp.write(tpl)

        for msg in msgs:
            msg = msg.replace('`', '``').rstrip('\n')
            msg = re_clean_code_span.sub(r'\1`` \2', msg)
            fp.write('* ' + msg + '\n')


def _multi_replace(s, tokens):
    for token in tokens:
        s = s.replace('%%%s%%' % token, tokens[token])
    return s


def _get_templates():
    tpl_dir = os.path.join(os.path.dirname(__file__), 'changelog')
    tpls = {}
    for name in os.listdir(tpl_dir):
        tpl = _get_template(os.path.join(tpl_dir, name))
        name_no_ext, _ = os.path.splitext(name)
        tpls[name_no_ext] = tpl
    return tpls


def _get_template(filename):
    with open(filename, 'r', encoding='utf8') as fp:
        return fp.read()


if __name__ == '__main__':
    generate()

