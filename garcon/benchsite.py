import io
import os
import os.path
import string
import random
import datetime
import argparse


def generateWord(min_len=1, max_len=10):
    length = random.randint(min_len, max_len)
    word = ''.join(random.choice(string.ascii_letters) for _ in range(length))
    return word


def generateSentence(words):
    return ' '.join([generateWord() for i in range(words)])


def generateDate():
    year = random.choice(range(1995, 2015))
    month = random.choice(range(1, 13))
    day = random.choice(range(1, 29))
    hours = random.choice(range(0, 24))
    minutes = random.choice(range(0, 60))
    seconds = random.choice(range(0, 60))
    return datetime.datetime(
            year, month, day, hours, minutes, seconds)


def generateTitleAndSlug():
    title = generateSentence(8)
    slug = title.replace(' ', '-').lower()
    slug = ''.join(c for c in slug if c.isalnum() or c == '-')
    return title, slug


class BenchmarkSiteGenerator(object):
    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.all_tags = []

    def generatePost(self):
        post_info = {}
        title, slug = generateTitleAndSlug()
        post_info.update({
            'title': title,
            'slug': slug})
        post_info['description'] = generateSentence(20)
        post_info['tags'] = random.choice(self.all_tags)
        post_info['datetime'] = generateDate()

        buf = io.StringIO()
        with buf:
            para_count = random.randint(5, 10)
            for i in range(para_count):
                buf.write(generateSentence(random.randint(50, 100)))
                buf.write('\n\n')
            post_info['text'] = buf.getvalue()

        self.writePost(post_info)

    def initialize(self):
        pass

    def writePost(self, post_info):
        raise NotImplementedError()


class PieCrustBechmarkSiteGenerator(BenchmarkSiteGenerator):
    def initialize(self):
        posts_dir = os.path.join(self.out_dir, 'posts')
        if not os.path.isdir(posts_dir):
            os.makedirs(posts_dir)

        config_path = os.path.join(self.out_dir, 'config.yml')
        if not os.path.exists(config_path):
            with open(config_path, 'w') as fp:
                fp.write('\n')

    def writePost(self, post_info):
        out_dir = os.path.join(self.out_dir, 'posts')
        slug = post_info['slug']
        dtstr = post_info['datetime'].strftime('%Y-%m-%d')
        with open('%s/%s_%s.md' % (out_dir, dtstr, slug), 'w',
                  encoding='utf8') as f:
            f.write('---\n')
            f.write('title: %s\n' % post_info['title'])
            f.write('description: %s\n' % post_info['description'])
            f.write('tags: [%s]\n' % post_info['tags'])
            f.write('---\n')

            para_count = random.randint(5, 10)
            for i in range(para_count):
                f.write(generateSentence(random.randint(50, 100)))
                f.write('\n\n')


class OctopressBenchmarkSiteGenerator(BenchmarkSiteGenerator):
    def initialize(self):
        posts_dir = os.path.join(self.out_dir, 'source', '_posts')
        if not os.path.isdir(posts_dir):
            os.makedirs(posts_dir)

    def writePost(self, post_info):
        out_dir = os.path.join(self.out_dir, 'source', '_posts')
        slug = post_info['slug']
        dtstr = post_info['datetime'].strftime('%Y-%m-%d')
        with open('%s/%s-%s.markdown' % (out_dir, dtstr, slug), 'w',
                  encoding='utf8') as f:
            f.write('---\n')
            f.write('layout: post\n')
            f.write('title: %s\n' % post_info['title'])
            f.write('date: %s 12:00\n' % dtstr)
            f.write('comments: false\n')
            f.write('categories: [%s]\n' % post_info['tags'])
            f.write('---\n')

            para_count = random.randint(5, 10)
            for i in range(para_count):
                f.write(generateSentence(random.randint(50, 100)))
                f.write('\n\n')


class MiddlemanBenchmarkSiteGenerator(BenchmarkSiteGenerator):
    def initialize(self):
        posts_dir = os.path.join(self.out_dir, 'source')
        if not os.path.isdir(posts_dir):
            os.makedirs(posts_dir)

    def writePost(self, post_info):
        out_dir = os.path.join(self.out_dir, 'source')
        slug = post_info['slug']
        dtstr = post_info['datetime'].strftime('%Y-%m-%d')
        with open('%s/%s-%s.html.markdown' % (out_dir, dtstr, slug), 'w',
                  encoding='utf8') as f:
            f.write('---\n')
            f.write('title: %s\n' % post_info['title'])
            f.write('date: %s\n' % post_info['datetime'].strftime('%Y/%m/%d'))
            f.write('tags: %s\n' % post_info['tags'])
            f.write('---\n')

            para_count = random.randint(5, 10)
            for i in range(para_count):
                f.write(generateSentence(random.randint(50, 100)))
                f.write('\n\n')


class HugoBenchmarkSiteGenerator(BenchmarkSiteGenerator):
    def initialize(self):
        posts_dir = os.path.join(self.out_dir, 'content', 'post')
        if not os.path.isdir(posts_dir):
            os.makedirs(posts_dir)

    def writePost(self, post_info):
        out_dir = os.path.join(self.out_dir, 'content', 'post')
        dtstr = post_info['datetime'].strftime('%Y-%m-%d_%H-%M-%S')
        post_path = os.path.join(out_dir, '%s.md' % dtstr)
        with open(post_path, 'w', encoding='utf8') as f:
            f.write('+++\n')
            f.write('title = "%s"\n' % post_info['title'])
            f.write('description = "%s"\n' % post_info['description'])
            f.write('categories = [\n  "%s"\n]\n' % post_info['tags'])
            f.write('date = "%s"\n' % post_info['datetime'].strftime(
                    "%Y-%m-%d %H:%M:%S-00:00"))
            f.write('slug ="%s"\n' % post_info['slug'])
            f.write('+++\n')
            f.write(post_info['text'])


generators = {
        'piecrust': PieCrustBechmarkSiteGenerator,
        'octopress': OctopressBenchmarkSiteGenerator,
        'middleman': MiddlemanBenchmarkSiteGenerator,
        'hugo': HugoBenchmarkSiteGenerator
        }


def main():
    parser = argparse.ArgumentParser(
            prog='generate_benchsite',
            description=("Generates a benchmark website with placeholder "
                         "content suitable for testing."))
    parser.add_argument(
            'engine',
            help="The engine to generate the site for.",
            choices=list(generators.keys()))
    parser.add_argument(
            'out_dir',
            help="The target directory for the website.")
    parser.add_argument(
            '-c', '--post-count',
            help="The number of posts to create.",
            type=int,
            default=100)
    parser.add_argument(
            '--tag-count',
            help="The number of tags to use.",
            type=int,
            default=30)

    result = parser.parse_args()
    generate(result.engine, result.out_dir,
             post_count=result.post_count,
             tag_count=result.tag_count)


def generate(engine, out_dir, post_count=100, tag_count=10):
    print("Generating %d posts in %s..." % (post_count, out_dir))

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    gen = generators[engine](out_dir)
    gen.all_tags = [generateWord(3, 12) for _ in range(tag_count)]
    gen.initialize()

    for i in range(post_count):
        gen.generatePost()


if __name__ == '__main__':
    main()
else:
    from invoke import task

    @task
    def genbenchsite(ctx, engine, out_dir, post_count=100, tag_count=10):
        generate(engine, out_dir,
                 post_count=post_count,
                 tag_count=tag_count)

