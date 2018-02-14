import os
import os.path
import re
from invoke import task, run


pyver_re = re.compile('^Python (?P<maj>\d)\.(?P<min>\d)\.(?P<pat>\d)$')


@task(help={
    'tmp_dir': "The directory in which to bake the docs temporarily.",
    'out_dir': "If the bake is successful, the directory in which to deploy "
               "the files at the end.",
    'root_url': "Set the docs site root URL to this if needed.",
    'venv_dir': "The directory of the virtual environment to use to run "
                "PieCrust. If none, will create a new one under `venv`."
})
def gendocs(ctx, tmp_dir=None, out_dir=None, root_url=None, venv_dir=None):
    base_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..'))
    os.chdir(base_dir)

    if not tmp_dir:
        tmp_dir = os.path.join(base_dir, '_docs-counter')

    if not venv_dir:
        venv_dir = os.path.join(base_dir, 'venv')

    if not os.path.isdir(venv_dir):
        print("Creating virtual environment in: %s" % venv_dir)
        run('virtualenv -p python3 "%s"' % venv_dir)

    pyexe = os.path.join(venv_dir, 'bin', 'python')
    pyver_out = run('%s --version' % pyexe, hide=True)
    if pyver_out.failed or not pyver_out.stdout.startswith('Python 3.'):
        raise Exception("Can't run Python3 from: %s" % pyexe)
    print("Using: %s" % pyver_out.stdout.strip())

    pipexe = os.path.join(venv_dir, 'bin', 'pip')
    pipver_out = run('%s --version' % pipexe, hide=True)
    if pipver_out.failed or '(python 3.' not in pipver_out.stdout:
        raise Exception("Can't run pip3 from: %s" % pipexe)
    print("Using: %s" % pipver_out.stdout.strip())

    npmver_out = run('npm --version', hide=True)
    print("Using: npm %s" % npmver_out.stdout.strip())

    print("Updating virtual environment.")
    run("%s install pip -U" % pipexe)
    run("%s install -r requirements.txt" % pipexe)

    print("Update node modules")
    run("npm install")

    this_pwd = os.path.dirname(os.path.dirname(__file__))
    node_bin = os.path.join(this_pwd, 'node_modules', '.bin')
    print("Adding '%s' to the PATH" % node_bin)
    os.environ['PATH'] = (node_bin + os.pathsep + os.environ['PATH'])

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

