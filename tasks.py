from invoke import Collection, task, run
from garcon.benchsite import genbenchsite
from garcon.changelog import genchangelog
from garcon.documentation import gendocs
from garcon.messages import genmessages
from garcon.pypi import makerelease


ns = Collection()
ns.add_task(genbenchsite, name='benchsite')
ns.add_task(genchangelog, name='changelog')
ns.add_task(gendocs, name='docs')
ns.add_task(genmessages, name='messages')
ns.add_task(makerelease, name='release')

