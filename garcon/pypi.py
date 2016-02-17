from invoke import task, run


@task
def makerelease(version, notag=False, noupload=False):
    if not version:
        raise Exception("You must specify a version!")

    # FoodTruck assets.
    print("Update node modules")
    run("npm install")
    print("Install Bower components")
    run("bower install")
    print("Generating FoodTruck assets")
    run("gulp")

    # CHANGELOG.rst
    run("invoke changelog --last %s" % version)

    # Tag in Mercurial, which will then be used for PyPi version.
    if not notag:
        run("hg tag %s" % version)

    # PyPi upload.
    if not noupload:
        run("python setup.py sdist upload")

