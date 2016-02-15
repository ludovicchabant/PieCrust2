import os
import os.path
from invoke import task, run


@task
def gendocs(tmp_dir=None, out_dir=None):
    if not tmp_dir:
        tmp_dir = '_docs-counter'

    print("Updating virtual environment")
    run("pip install -r requirements.txt --upgrade")

    print("Update node modules")
    run("npm install")

    print("Update Bower packages")
    run("bower update")

    print("Generate PieCrust version")
    run('python setup.py version')
    from piecrust.__version__ import APP_VERSION
    version = APP_VERSION

    print("Baking documentation for version: %s" % version)
    args = [
            'python', 'chef.py',
            '--root', 'docs',
            '--config', 'dist',
            '--config-set', 'site/root', '/piecrust/en/%s' % version,
            'bake',
            '-o', tmp_dir
            ]
    run(' '.join(args))

    if out_dir:
        print("Synchronizing %s" % out_dir)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        tmp_dir = tmp_dir.rstrip('/') + '/'
        out_dir = out_dir.rstrip('/') + '/'
        run('rsync -av --delete %s %s' % (tmp_dir, out_dir))

