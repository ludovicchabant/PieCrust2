import os
import os.path
from invoke import task, run


@task
def gendocs(tmp_dir=None, out_dir=None, root_url=None):
    if not tmp_dir:
        tmp_dir = '_docs-counter'

    if not os.path.isdir('venv'):
        raise Exception(
                "You need a virtual environment in the PieCrust repo.")
    pyexe = os.path.join('venv', 'bin', 'python')

    print("Update node modules")
    run("npm install")

    print("Update Bower packages")
    run("bower update")

    print("Generate PieCrust version")
    run(pyexe + ' setup.py version')
    from piecrust.__version__ import APP_VERSION
    version = APP_VERSION

    print("Baking documentation for version: %s" % version)
    if root_url:
        print("Using root URL: %s" % root_url)
    args = [
            pyexe, 'chef.py',
            '--root', 'docs',
            '--config', 'dist']
    if root_url:
        args += ['--config-set', 'site/root', root_url]
    args += [
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

