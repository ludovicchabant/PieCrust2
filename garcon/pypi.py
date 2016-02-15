from invoke import task, run


@task
def makerelease(version, notag=False, noupload=False):
    if not version:
        raise Exception("You must specify a version!")

    # FoodTruck assets.
    run("gulp")

    # CHANGELOG.rst
    run("invoke changelog --last %s" % version)

    # Tag in Mercurial, which will then be used for PyPi version.
    if not notag:
        run("hg tag %s" % version)

    # PyPi upload.
    if not noupload:
        run("python setup.py sdist upload")

