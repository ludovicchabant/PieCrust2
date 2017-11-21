import os
import os.path
import re
import time
import codecs
import argparse
import subprocess


hg_log_template = ("{if(tags, '>>{tags};{date|shortdate}\n')}"
                   "{desc|firstline}\n\n")

re_tag = re.compile('^\d+\.\d+\.\d+([ab]\d+)?(rc\d+)?$')
re_change = re.compile('^(\w+):')
re_clean_code_span = re.compile('([^\s])``([^\s]+)')

category_commands = [
        'chef', 'bake', 'find', 'help', 'import', 'init', 'paths', 'plugin',
        'plugins', 'prepare', 'purge', 'root', 'routes', 'serve',
        'showconfig', 'showrecord', 'sources', 'theme', 'themes', 'admin',
        'publish']
category_core = [
        'internal', 'templating', 'formatting', 'performance',
        'data', 'config', 'rendering', 'render', 'debug', 'reporting',
        'linker', 'pagination', 'routing', 'caching', 'cli']
category_bugfixes = [
        'bug']
category_project = ['build', 'cm', 'docs', 'tests', 'setup']
categories = [
        ('commands', category_commands),
        ('core', category_core),
        ('bugfixes', category_bugfixes),
        ('project', category_project),
        ('miscellaneous', None)]
category_names = list(map(lambda i: i[0], categories))

re_add_tag_changeset = re.compile('^Added tag [^\s]+ for changeset [\w\d]+$')
re_merge_pr_changeset = re.compile('^Merge pull request')
re_merge_changes_changeset = re.compile('^Merge(d?) changes')
message_blacklist = [
    re_add_tag_changeset,
    re_merge_pr_changeset,
    re_merge_changes_changeset]


def generate(out_file, last=None):
    print("Generating %s" % out_file)

    if not os.path.exists('.hg'):
        raise Exception("You must run this script from the root of a "
                        "Mercurial clone of the PieCrust repository.")
    hglog = subprocess.check_output([
        'hg', 'log',
        '--rev', 'reverse(::.)',
        '--template', hg_log_template])
    hglog = codecs.decode(hglog, encoding='utf-8', errors='replace')

    _, out_ext = os.path.splitext(out_file)
    templates = _get_templates(out_ext)

    with open(out_file, 'w', encoding='utf8', newline='') as fp:
        fp.write(templates['header'])

        skip = False
        in_desc = False
        current_version = 0
        current_version_info = None
        current_changes = None

        if last:
            current_version = 1
            cur_date = time.strftime('%Y-%m-%d')
            current_version_info = last, cur_date
            current_changes = {}

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
                                current_changes, fp, out_ext)

                    current_version += 1
                    current_version_info = tags, tag_date
                    current_changes = {}
                    in_desc = True
                else:
                    skip = True
                continue

            if skip or current_version == 0:
                continue

            for blre in message_blacklist:
                if blre.match(line):
                    skip = True
                    break

            if skip:
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
                    current_changes, fp, out_ext)


def _write_version_changes(templates, version, version_info, changes, fp, ext):
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
                'num': str(version),
                'sub_num': str(i),
                'category': cat_name.title()}
        tpl = _multi_replace(templates['category_title'], tokens)
        fp.write(tpl)

        msgs = list(sorted(msgs))
        for msg in msgs:
            if ext == '.rst':
                msg = msg.replace('`', '``').rstrip('\n')
                msg = re_clean_code_span.sub(r'\1`` \2', msg)
            fp.write('* ' + msg + '\n')


def _multi_replace(s, tokens):
    for token in tokens:
        s = s.replace('%%%s%%' % token, tokens[token])
    return s


def _get_templates(extension):
    tpl_dir = os.path.join(os.path.dirname(__file__), 'changelog')
    tpls = {}
    for name in os.listdir(tpl_dir):
        if name.endswith(extension):
            tpl = _get_template(os.path.join(tpl_dir, name))
            name_no_ext, _ = os.path.splitext(name)
            tpls[name_no_ext] = tpl
    return tpls


def _get_template(filename):
    with open(filename, 'r', encoding='utf8', newline='') as fp:
        return fp.read()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate CHANGELOG file.')
    parser.add_argument(
            'out_file',
            nargs='?',
            default='CHANGELOG.rst',
            help='The output file.')
    parser.add_argument(
            '--last',
            help="The version for the last few untagged changes.")
    args = parser.parse_args()

    generate(args.out_file, last=args.last)
else:
    from invoke import task

    @task
    def genchangelog(out_file='CHANGELOG.rst', last=None):
        generate(out_file, last)

