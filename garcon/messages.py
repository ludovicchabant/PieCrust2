import os
from invoke import task, run


@task
def genmessages(ctx):
    root_dir = 'garcon/messages'
    out_dir = 'piecrust/resources/messages'
    run('python chef.py --root %s bake -o %s' % (root_dir, out_dir))
    os.unlink('piecrust/resources/messages/index.html')

