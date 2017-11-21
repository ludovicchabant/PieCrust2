import re
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

    # See if any asset was modified and needs to be submitted.
    r = run('hg status', hide=True)
    if re.match(r'^[R\!] ', r.stdout):
        raise Exception("FoodTruck assets are missing or were removed!")

    commit_assets = False
    if re.match(r'^[MA] ', r.stdout):
        commit_assets = True

    # CHANGELOG.rst and documentation changelog page.
    run("invoke changelog --last %s" % version)
    run("invoke changelog --last %s -o docs/pages/support/changelog.md" %
            version)

    if not local_only:
        if commit_assets:
            res = run('hg status piecrust/admin/static')
            if not res:
                return
            if res.stdout.strip() != '':
                run('hg commit piecrust/admin/static '
                    '-m "admin: Regenerate FoodTruck assets."')

        # Submit the CHANGELOG.
        run('hg commit CHANGELOG.rst docs/pages/support/changelog.md '
            '-m "cm: Regenerate the CHANGELOG."')

        # Tag in Mercurial, which will then be used for PyPi version.
        run("hg tag %s" % version)

        # PyPi upload.
        run("python setup.py version")
        run("python setup.py sdist upload")
    else:
        if commit_assets:
            print("Would submit FoodTruck assets...")
        print("Would submit changelog files...")
        print("Would tag repo with %s..." % version)
        print("Would upload to PyPi...")

