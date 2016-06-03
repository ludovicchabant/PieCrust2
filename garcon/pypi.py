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

    # CHANGELOG.rst and documentation changelog page.
    run("invoke changelog --last %s" % version)
    run("invoke changelog --last %s -o docs/pages/support/changelog.md" %
            version)

    if not local_only:
        # Submit the CHANGELOG.
        run('hg commit CHANGELOG.rst docs/pages/support/changelog.md '
            '-m "cm: Regenerate the CHANGELOG."')

        # Tag in Mercurial, which will then be used for PyPi version.
        run("hg tag %s" % version)

        # PyPi upload.
        run("python setup.py version")
        run("python setup.py sdist upload")
    else:
        print("Would submit changelog files...")
        print("Would tag repo with %s..." % version)
        print("Would upload to PyPi...")

