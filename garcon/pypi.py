from invoke import task, run


@task
def makerelease(version, local_only=False):
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

    if not local_only:
        # Submit the CHANGELOG.
        run('hg commit CHANGELOG.rst -m "cm: Regenerate the CHANGELOG."')

        # Tag in Mercurial, which will then be used for PyPi version.
        run("hg tag %s" % version)

        # PyPi upload.
        run("python setup.py sdist upload")

