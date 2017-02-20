
#########
CHANGELOG
#########

This is the changelog for PieCrust_.

.. _PieCrust: http://bolt80.com/piecrust/



==================================
1. PieCrust 2.0.0 (2017-02-19)
==================================


1.0 Commands
----------------------

* admin: Add ability to upload page assets.
* admin: Add quick links in sidebar to create new posts/pages.
* admin: Bigger text for the site summary.
* admin: Don't have the static folder for the app collide with the blueprint's.
* admin: Fix crash when running ``admin run`` outside of a website.
* bake: Don’t swallow generic errors during baking
* bake: Show bake stats in descending order of time.
* showrecord: Add ``show-manifest`` argument.

1.1 Core
----------------------

* config: Cleanup config loading code. Add support for a ``local.yml`` config.
* data: Allow page generators to have an associated data provider
* internal: Don't check for a page repository, there's always one.
* internal: Import things in the builtin plugin only when needed.
* internal: Keep things out of the ``PieCrust`` class, and other clean-ups.
* internal: Make ``posts`` sources cache their list of pages.
* internal: PEP8 fixup for admin panel code.
* rendering: Separate performance timers for renering segments and layouts.
* templating: Put the routing functions in the data, not the template engine.

1.2 Bugfixes
----------------------

* bug: Fix crashes for commands run outside of a website.

1.3 Project
----------------------

* cm: Add setup.cfg file for flake8.
* cm: Allow generating documentation from inside the virtualenv.
* cm: Fix ``gulpfile`` for FoodTruck.
* docs: Add missing quote in example
* docs: Add space before link
* docs: Correct typos
* docs: Fix line-end / new-line issues
* docs: Invalid yaml in example
* docs: Repair some broken links
* tests: Fix for time comparisons.

1.4 Miscellaneous
----------------------

* Allow PageSource to provide a custom assetor
* Allow an individual page to override pretty_urls in it config
* Allow page source to post-process page config at the end of page loading
* Assetor is now responsible for copying assets, to allow customization
* Don’t swallow generic errors during baking
* Fixed call to Assetor.copyAssets
* Land assets in the correct directory for pages with no pretty_urls override
* Refactored Assetor into Assetor and AssetorBase
* Removed pointless page argument from copyAssets
* Renamed buildPageAssetor to buildAssetor
* Use assetor provided by page source when paginating
* assets: Fix crash when a page doesn't have assets.

==================================
2. PieCrust 2.0.0rc2 (2016-09-07)
==================================


2.0 Commands
----------------------

* admin: Correctly flush loggers before exiting.
* admin: Don't crash when the site isn't in a source control repository.
* admin: Fix API changes, don't crash the dashboard on non-binary WIP files.
* admin: Fix crash when running the ``admin`` command.
* admin: Fix various crashes caused by incorrect Blueprint setup.
* admin: Fixes for the Git support.
* admin: Make the whole FoodTruck site into a blueprint.
* bake: Add the list of deleted files to the bake/processing records.
* bake: Fix how slugified taxonomy terms are handled.
* bake: Print slightly better debug information.
* chef: Don't crash when running ``chef`` outside of a website.
* chef: Make all the commands descriptions fit in one line.
* plugins: Abort the command if there's no site.
* plugins: Don't crash when running the ``chef plugins`` command outside a site.
* prepare: Add ablity to run an editor program after creating the page file.
* prepare: Use the same convention as other commands with sub-commands.
* publish: Add SFTP publisher.
* publish: Add support for ``--preview`` for the SFTP publisher.
* publish: Fix crash.
* publish: Fix stupid typo.
* publish: Make publisher more powerful and better exposed on the command line.
* showrecord: Fix some crashes and incorrect information.
* themes: No parameters shoudl make the help text show up.

2.1 Core
----------------------

* config: Fix how we parse the root URL to allow for absolute and user URLs.
* data: Fix debug information for the blog data provider.
* internal: Add missing timer scope.
* internal: Add missing timer scope.
* internal: Don't strip the trailing slash when we get the root URL exactly.
* internal: Move admin panel code into the piecrust package.
* routing: Add some backwards compatibility support for parameter types.
* routing: Don't mistakenly raise errors about incorrect variadic parameters.
* routing: Simplify how route functions are declared and handled.
* routing: Simplify how routes are defined.

2.2 Bugfixes
----------------------

* bug: Fix possible crash with overlapping pages.

2.3 Project
----------------------

* cm: Add a "Bugfixes" section to the CHANGELOG and order things alphabetically.
* cm: Declare PieCrust as a Python 3 only package.
* cm: Regenerate the CHANGELOG.
* docs: Add documentation about the SFTP publisher.
* docs: Fix outdated routing in the configuration file.
* docs: Tutorial chapter about adding pages.
* docs: Update documentation on routing.
* tests: Add more ``showconfig`` tests.
* tests: Add tests for publishers.
* tests: Fix crash when reporting 404 errors during server tests.
* tests: Fix some CLI tests.
* tests: Make it possible to run FoodTruck tests.
* tests: Try and finally fix the time-based tests.

==================================
3. PieCrust 2.0.0rc1 (2016-06-09)
==================================


3.0 Commands
----------------------

* admin: Add support for Git source-control.
* admin: Add support for ``.well-known`` folder.
* admin: Fix OS-specific new line problems when editing pages.
* admin: Fix crash when previewing a website.
* admin: Fix crash when running FoodTruck as a standalone web app.
* admin: Run the asset pipeline before showing the admin panel.
* admin: Show a more classic blog post listing in FoodTruck.
* admin: run an asset processing loop in the background.
* bake: Add blog archives generator.
* bake: Add stat about aborted jobs
* bake: Add the timestamp of the page to each record entry.
* bake: Change ``show-timers`` to ``show-stats`` , add stats.
* bake: Don't clean the ``baker`` cache on a force bake.
* bake: Fix a crash when a rendering error occurs.
* bake: Fix some bugs with taxonomy combinations.
* bake: Fix some crashes with new blog archive/taxonomy for incremental bakes.
* bake: Re-enable faster serialization between processes.
* bake: Replace hard-coded taxonomy support with "generator" system.
* bake: Show more stats.
* bake: Some more optimizations.
* bake: Use standard pickle and queue for now to fix some small issues.
* bake: Use threads to read/write from/to the main arbitrator process.
* chef: Fix ``--debug-only`` argument.
* init: Use a better config template when creating websites.
* purge: Delete the whole cache directory, not just the current sub-cache.
* routes: Show the route template function.
* serve: Fix some crashes introduced by recent refactor.
* serve: Fix some problems with trailing slashes.
* showrecord: Don't print the record when you just want the stats.
* themes: Add support for a ``--theme`` argument to ``chef`` .
* themes: Add support for loading from a library of themes.
* themes: Expand ``~`` paths, fix error message.
* themes: Simplify ``themes`` command.

3.1 Core
----------------------

* data: Make the blog provider give usable data to the year archive routes.
* data: Support both objects and dictionaries in ``MergedMapping`` .
* debug: Pass the exceptions untouched when debugging.
* debug: Show more stuff pertaining to data providers in the debug window.
* formatting: Add a ``hoedown`` formatter.
* formatting: Don't import ``hoedown`` until we need it.
* internal: Bump cache version.
* internal: Don't run regexes for the 99% case of pages with no segments.
* internal: Fix a bug with registering taxonomy terms that are not strings.
* internal: Fix compatibility with older Python 3.x.
* internal: Fix incorrect check for cache times.
* internal: Fix some bugs with the ``fastpickle`` module.
* internal: Get rid of the whole "sub cache" business.
* internal: Improve how theme configuration is validated and merged.
* internal: More work/fixes on how default/theme/user configs are merged.
* internal: Move some basic FoodTruck SCM code to the base.
* internal: Prevent crash because of missing logger.
* internal: Refactor config loading some more.
* internal: Remove exception logging that shouldn't happen. Better message.
* internal: Remove threading stuff we don't need anymore.
* internal: Remove unused code.
* internal: Remove unused import.
* internal: Remove unused piece of code.
* internal: Update the cache version to force re-gen the configuration settings.
* render: Change how we store render passes info.
* rendering: Use ``fastpickle`` serialization before JSON.
* routing: Cleanup URL routing and improve page matching.
* routing: Correctly call the underlying route template function from a merged one.
* routing: Fix problems with route functions.
* templating: Make blog archives generator expose more templating data.
* templating: Make the 'categories' taxonomy use a 'pccaturl' function again.
* templating: Use HTTPS URLs for a couple things.

3.2 Bugfixes
----------------------

* bug: Also look for format changes when determining if a page needs parsing.

3.3 Project
----------------------

* cm: Add AppVeyor support.
* cm: Add generation of Mardown changelog suitable for the online documentation.
* cm: Add generation of online changelog to the release task.
* cm: Also test Python 3.5 with Travis.
* cm: Don't always generation the version when running ``setuptools`` .
* cm: Don't raise an exception when no version file exists.
* cm: Fix ``setup.py`` script.
* cm: Fix a packaging bug, update package metadata.
* cm: Ignore ``py.test`` cache.
* cm: Ignore bdist output directory.
* cm: Improve documentation generation script.
* cm: It's fun to send typos to Travis-CI.
* cm: Make Travis-CI test packaging.
* cm: Regenerate the CHANGELOG.
* docs: Add changelog page.
* docs: Add information on more global ``chef`` options.
* docs: Use HTTPS version of Google Fonts.
* docs: Use new config variants format.
* docs: Very basic theme documentation.
* docs: Write about generators and data providers, update all related topics.
* tests: Add ability to run tests with a theme site.
* tests: Add another app config test.
* tests: Add more tests for merged mappings.
* tests: Add some tests for blog archives and multi-blog features.
* tests: Fix logic for making time-based tests not fail randomly.
* tests: Improve failure reporting.
* tests: the ``PageBaker`` now needs to be shutdown.

3.4 Miscellaneous
----------------------

* Fix 404 broken link
* jinja: Add ``md5`` filter.

==================================
4. PieCrust 2.0.0b5 (2016-02-16)
==================================


4.0 Commands
----------------------

* admin: Don't require ``bcrypt`` for running FoodTruck with ``chef`` .
* admin: Remove settings view.

4.1 Core
----------------------

* internal: Remove SyntaxWarning from MacOS wrappers.

4.3 Project
----------------------

* cm: Exclude the correct directories from vim-gutentags.
* cm: Fix CHANGELOG newlines on Windows.
* cm: Fix categorization of CHANGELOG entries for new commands.
* cm: Fixes and tweaks to the documentation generation task.
* cm: Get a new version of pytest-cov to avoid a random multiprocessing bug.
* cm: Ignore more things for pytest.
* cm: Move all scripts into a ``garcon`` package with ``invoke`` support.
* cm: Regenerate the CHANGELOG.
* cm: Regenerate the CHANGELOG.
* cm: Tweaks to the release script.
* cm: Update node module versions.
* cm: Update npm modules and bower packages before making a release.
* cm: Update the node modules before building the documentation.

==================================
5. PieCrust 2.0.0b4 (2016-02-09)
==================================


5.0 Commands
----------------------

* admin: Ability to configure SCM stuff per site.
* admin: Add "FoodTruck" admin panel from the side experiment project.
* admin: Add summary of page in source listing.
* admin: Better UI for publishing websites.
* admin: Better error reporting, general clean-up.
* admin: Better production config for FoodTruck, provide proper first site.
* admin: Change the default admin server port to 8090, add ``--port`` option.
* admin: Configuration changes.
* admin: Dashboard UI cleaning, re-use utility function for page summaries.
* admin: Fix "Publish started" message showing up multiple times.
* admin: Fix constructor for Mercurial SCM.
* admin: Fix crashes when creating a new page.
* admin: Fix creating pages.
* admin: Fix responsive layout.
* admin: Improve publish logs showing as alerts in the admin panel.
* admin: Make sure we have a valid default site to start with.
* admin: Make the publish UI handle new kinds of target configurations.
* admin: Make the sidebar togglable for smaller screens.
* admin: New ``admin`` command to manage FoodTruck-related things.
* admin: Prompt the user for a commit message when committing a page.
* admin: Set the ``DEBUG`` flag before the app runs so we can read it during setup.
* admin: Show the install page if no secret key is available.
* admin: Use ``HGPLAIN`` for the Mercurial VCS provider.
* admin: Use the app directory, not the cwd, in case of ``--root`` .
* bake: Add a flag to know which record entries got collapsed from last run.
* bake: Add new performance timers.
* bake: Add option to bake assets for FoodTruck. This is likely temporary.
* bake: Add support for a "known" page setting that excludes it from the bake.
* bake: Don't re-setup logging for workers unless we're sure we need it.
* bake: Set the flags, don't combine.
* chef: Add ``--debug-only`` option to only show debug logging for a given logger.
* chef: Add ``--pid-file`` option.
* chef: Fix the ``--config-set`` option.
* publish: Add option to change the source for the ``rsync`` publisher.
* publish: Add publish command.
* publish: Add the ``rsync`` publisher.
* publish: Change the ``shell`` config setting name for the command to run.
* publish: Make the ``shell`` log update faster by flushing the pipe.
* publish: Polish/refactor the publishing workflows.
* routes: Add better support for taxonomy slugification.
* serve: Don't crash when looking at the debug info in a stand-alone window.
* serve: Extract some of the server's functionality into WSGI middlewares.
* serve: Fix corner cases where the pipeline doesn't run correctly.
* serve: Fix error reporting when the background pipeline fails.
* serve: Fix timing information in the debug window.
* serve: Improve debug information in the preview server.
* serve: Improve reloading and shutdown of the preview server.
* serve: Make it possible to preview pages with a custom root URL.
* serve: Refactor the server to make pieces usable by the debugging middleware.
* serve: Rewrite of the Server-Sent Event code for build notifications.
* serve: Werkzeug docs say you need to pass a flag with ``wrap_file`` .
* showconfig: Don't crash when the whole config should be shown.
* sources: Add code to support "interactive" metadata acquisition.
* sources: Add method to get a page factory from a path.

5.1 Core
----------------------

* cli: Add ``--no-color`` option.
* cli: More proper argument parsing for the main/root arguments.
* data: Fix a crash bug when no parent page is set on an iterator.
* debug: Don't show parentheses on redirected properties.
* debug: Fix a crash when rendering debug info for some pages.
* debug: Fix debug window CSS.
* debug: Fix how the linker shows children/siblings/etc. in the debug window.
* internal: Refactor the app configuration class.
* internal: Rename ``raw_content`` to ``segments`` since it's what it is.
* internal: Some fixes to the new app configuration.

5.2 Bugfixes
----------------------

* bug: Correctly handle root URLs with special characters.
* bug: Fix a crash when some errors occur during page rendering.

5.3 Project
----------------------

* cm: Add requirements for FoodTruck.
* cm: Add script to generate documentation.
* cm: Add some pretty little icons in the README.
* cm: CHANGELOG generator can handle future versions.
* cm: Fix Gulp config.
* cm: Ignore more stuff for CtrlP or Gutentags.
* cm: Merge the 2 foodtruck folders, cleanup.
* cm: Put Bower/Gulp/etc. stuff all at the root.
* docs: Add documentation about FoodTruck.
* docs: Add documentation about the ``publish`` command.
* docs: Add raw files for FoodTruck screenshots.
* docs: Add reference entry about the ``site/slugify_mode`` setting.
* docs: Fix broken link.
* docs: Make FoodTruck screenshots the proper size.
* docs: Remove LessCSS dependencies in the tutorial, fix typos.
* tests: Add unicode tests for case-sensitive file-systems.
* tests: Fix (hopefully) time-sensitive tests.
* tests: Fix another broken test.
* tests: Fix broken test.
* tests: Fix broken unit test.
* tests: Print more information when a bake test fails to find an output file.

==================================
6. PieCrust 2.0.0b3 (2015-08-01)
==================================


6.0 Commands
----------------------

* import: Add some debug logging.
* import: Correctly convert unicode characters in site configuration.
* import: Fix the PieCrust 1 importer.

6.1 Core
----------------------

* internal: Fix a severe bug with the file-system wrappers on OSX.
* templating: Make more date functions accept 'now' as an input.

6.3 Project
----------------------

* cm: Add a Gutentags config file for ``ctags`` generation.
* cm: Changelog generator script.
* cm: Ignore Rope cache.
* cm: Update changelog.
* tests: Check accented characters work in configurations.

==================================
7. PieCrust 2.0.0b2 (2015-07-29)
==================================


7.0 Commands
----------------------

* prepare: More help about scaffolding.

7.2 Bugfixes
----------------------

* bug: Fix crash running ``chef help scaffolding`` outside of a website.

==================================
8. PieCrust 2.0.0b1 (2015-07-29)
==================================


8.0 Commands
----------------------

* bake: Add a processor to generate a Pygments style CSS file.
* bake: Fix logging configuration for multi-processing on Windows.
* bake: Fix random crash with the Sass processor.
* bake: Set the worker ID in the configuration. It's useful.
* prepare: Fix the RSS template.
* serve: Don't show the same error message twice.
* serve: Fix a crash when matching taxonomy URLs with incorrect URLs.
* serve: Improve Jinja rendering error reporting.
* serve: Improve error reporting when pages are not found.
* serve: Say what page a rendering error happened in.
* serve: Try to serve taxonomy pages after all normal pages have failed.
* themes: Add a ``link`` sub-command to install a theme via a symbolic link.
* themes: Add config paths to the cache key.
* themes: Don't fixup template directories, it's actually better as-is.
* themes: Fix crash when invoking command with no sub-command.
* themes: Improve CLI, add ``deactivate`` command.
* themes: Proper template path fixup for the theme configuration.

8.1 Core
----------------------

* config: Make sure ``site/auto_formats`` has at least ``html`` .
* formatting: Add support for Markdown extension configs.
* internal: Correctly split sub URIs. Add unit tests.
* internal: Fix some edge-cases for splitting sub-URIs.
* internal: Fix timing info.
* internal: Improve handling of taxonomy term slugification.
* internal: Return ``None`` instead of raising an exception when finding pages.
* templating: Add ``now`` global to Jinja, improve date error message.
* templating: Make Jinja support arbitrary extension, show warning for old stuff.
* templating: ``highlight_css`` can be passed the name of a Pygments style.

8.2 Bugfixes
----------------------

* bug: Fix a crash with the ``ordered`` page source when sorting pages.
* bug: Fix file-system wrappers for non-Mac systems.
* bug: Forgot to add a new file like a big n00b.
* bug: Of course I broke something. Some exceptions need to pass through Jinja.

8.3 Project
----------------------

* cm: Add ``unidecode`` to requirements.
* cm: Error in ``.hgignore`` . Weird.
* cm: Fix benchmark website generation on Windows.
* cm: Ignore ``.egg-info`` stuff.
* cm: Re-fix Mac file-system wrappers.
* docs: Add some API documentation.
* docs: Add some syntax highlighting to tutorial pages.
* docs: Always use Pygments styles. Use the new CSS generation processor.
* docs: Configure fenced code blocks in Markdown with Pygments highlighting.
* docs: Make code prettier :)
* docs: Make the "deploying" page consistent with "publishing".
* docs: More generic information about baking and publishing.
* docs: No need to specify the layout here.
* docs: Start a proper "code/API" section.
* docs: Use fenced code block syntax.
* tests: Fix ``find`` tests on Windows.
* tests: Fix processing test after adding ``PygmentsStyleProcessor`` .
* tests: Fix processing tests on Windows.
* tests: Fix the Mustache tests on Windows.
* tests: Help the Yaml loader figure out the encoding on Windows.
* tests: Normalize test paths using the correct method.

8.4 Miscellaneous
----------------------

* bake/serve: Improve support for unicode, add slugification options.
* cosmetic: Remove debug print here too.
* cosmetic: Remove debug printing.
* jinja: Support ``.j2`` file extensions.
* less: Fix issues with the map file on Windows.
* sass: Overwrite the old map file with the new one always.

==================================
9. PieCrust 2.0.0a13 (2015-07-14)
==================================


9.0 Commands
----------------------

* bake: Fix a bug with copying assets when ``pretty_urls`` are disabled.

9.2 Bugfixes
----------------------

* bug: Correctly setup the environment/app for bake workers.
* bug: Fix copying of page assets during the bake.

==================================
10. PieCrust 2.0.0a12 (2015-07-14)
==================================


10.0 Commands
----------------------

* bake: Abort "render first" jobs if we start using other pages.
* bake: Add CLI argument to specify job batch size.
* bake: Commonize worker pool code between html and asset baking.
* bake: Correctly use the ``num_worers`` setting.
* bake: Don't pass the previous record entries to the workers.
* bake: Enable multiprocess baking.
* bake: Improve bake record information.
* bake: Improve performance timers reports.
* bake: Make pipeline processing multi-process.
* bake: Optimize the bake by not using custom classes for passing info.
* bake: Pass the config variants and values from the CLI to the baker.
* bake: Pass the sub-cache directory to the bake workers.
* bake: Tweaks to the ``sitemap`` processor. Add tests.
* bake: Use batched jobs in the worker pool.
* serve: Fix bug with creating routing metadata from the URL.
* serve: Fix crash on start.
* serve: Use Werkzeug's HTTP exceptions correctly.

10.1 Core
----------------------

* debug: Add support for more attributes for the debug info.
* debug: Better debug info output for iterators, providers, and linkers.
* debug: Fix serving of resources now that the module moved to a sub-folder.
* debug: Log error when an exception gets raised during debug info building.
* internal: Add a ``fastpickle`` module to help with multiprocess serialization.
* internal: Add support for fake pickling of date/time structures.
* internal: Add utility function for incrementing performance timers.
* internal: Allow re-registering performance timers.
* internal: Create full route metadata in one place.
* internal: Fix caches being orphaned from their directory.
* internal: Floats are also allowed in configurations, duh.
* internal: Handle data serialization more under the hood.
* internal: Just use the plain old standard function.
* internal: Move ``MemCache`` to the ``cache`` module, remove threading locks.
* internal: Optimize page data building.
* internal: Optimize page segments rendering.
* internal: Register performance timers for plugin components.
* internal: Remove unnecessary code.
* internal: Remove unnecessary import.
* linker: Add ability to return the parent and ancestors of a page.
* performance: Add profiling to the asset pipeline workers.
* performance: Compute default layout extensions only once.
* performance: Only use Jinja2 for rendering text if necessary.
* performance: Quick and dirty profiling support for bake workers.
* performance: Refactor how data is managed to reduce copying.
* performance: Use the fast YAML loader if available.
* render: Lazily import Textile package.
* rendering: Truly skip formatters that are not enabled.
* reporting: Better error messages for incorrect property access on data.
* reporting: Print errors that occured during pipeline processing.
* templating: Add modification time of the page to the template data.
* templating: Fix Pystache template engine.
* templating: Let Jinja2 cache the parsed template for page contents.
* templating: Workaround for a bug with Pystache.

10.2 Bugfixes
----------------------

* bug: Fix CLI crash caused by configuration variants.
* bug: Fix a crash when errors occur while processing an asset.
* bug: Fix infinite loop in Jinja2 rendering.
* bug: Fix routing bug introduced by 21e26ed867b6.

10.3 Project
----------------------

* cm: Add script to generate benchmark websites.
* cm: Fix wrong directory for utilities.
* cm: Move build directory to util to avoid conflicts with pip.
* cm: Use Travis CI's new infrastructure.
* docs: Add the ``--pre`` flag to ``pip install`` while PieCrust is in beta.
* tests: Add pipeline processing tests.
* tests: Fix Jinja2 test.
* tests: Fix crash in processing tests.

10.4 Miscellaneous
----------------------

* Fixed 'bootom' to 'bottom'
* markdown: Cache the formatter once.

==================================
11. PieCrust 2.0.0a11 (2015-05-18)
==================================


11.0 Commands
----------------------

* bake: Return all errors from a bake record entry when asked for it.
* serve: Fix bug where ``?!debug`` doesn't get appending correctly.
* serve: Remove development assert.

11.1 Core
----------------------

* data: Fix regression bug with accessing page metadata that doesn't exist.
* linker: Fix error when trying to list non-existing children.
* linker: Fix linker returning the wrong value for ``is_dir`` in some situations.
* pagination: Fix regression bug with previous/next posts.

11.3 Project
----------------------

* tests: Add support for testing the Chef server.
* tests: Also mock ``open`` in Jinja to be able to use templates in bake tests.
* tests: Fail bake tests with a proper error message when bake fails.
* tests: More accurate marker position for diff'ing strings.
* tests: Move all bakes/cli/servings tests files to have a YAML extension.

11.4 Miscellaneous
----------------------

* jinja: Look for ``html`` extension first instead of last.

==================================
12. PieCrust 2.0.0a10 (2015-05-15)
==================================


12.3 Project
----------------------

* setup: Add ``requirements.txt`` to ``MANIFEST.in`` so it can be used by the setup.

==================================
13. PieCrust 2.0.0a9 (2015-05-11)
==================================


13.0 Commands
----------------------

* serve: Add a WSGI utility module for easily getting a default app.
* serve: Add a generic WSGI app factory.
* serve: Add ability to suppress the debug info window programmatically.
* serve: Compatibility with ``mod_wsgi`` .
* serve: Split the server code in a couple modules inside a ``serving`` package.

13.1 Core
----------------------

* data: Fix problems with using non-existing metadata on a linked page.
* internal: Make it possible to pass ``argv`` to the main Chef function.
* routing: Fix bugs with matching URLs with correct route but missing metadata.

13.3 Project
----------------------

* docs: Add documentation for deploying as a dynamic CMS.
* docs: Add lame bit of documentation on publishing your website.
* setup: Keep the requirements in sync between ``setuptools`` and ``pip`` .
* tests: Add a Chef test for the ``find`` command.
* tests: Add support for "Chef tests", which are direct CLI tests.
* tests: Fix serving unit-tests.

==================================
14. PieCrust 2.0.0a8 (2015-05-03)
==================================


14.0 Commands
----------------------

* bake: Fix crash when handling bake errors.
* serve: Giant refactor to change how we handle data when serving pages.
* serve: Refactoring and fixes to be able to serve taxonomy pages.
* sources: Default source lists pages in order.
* sources: Fix how the ``autoconfig`` source iterates over its structure.
* theme: Fix link to PieCrust documentation.

14.1 Core
----------------------

* caching: Use separate caches for config variants and other contexts.
* config: Add method to deep-copy a config and validate its contents.
* internal: Return the first route for a source if no metadata match is needed.
* linker: Don't put linker stuff in the config.

14.3 Project
----------------------

* tests: Changes to output report and hack for comparing outputs.

14.4 Miscellaneous
----------------------

* Update ``requirements.txt`` .
* Update development ``requirements.txt`` , add code coverage tools.

==================================
15. PieCrust 2.0.0a7 (2015-04-20)
==================================


15.0 Commands
----------------------

* bake: Improve render context and bake record, fix incremental bake bugs.
* bake: Several bug taxonomy-related fixes for incorrect incremental bakes.
* bake: Use a rotating bake record.
* chef: Add a ``--config-set`` option to set ad-hoc site configuration settings.
* chef: Fix pre-parsing.
* find: Don't change the pattern when there's none.
* import: Use the proper baker setting in the Jekyll importer.
* serve: Don't access the current render pass info after rendering is done.
* serve: Fix crash on URI parsing.
* showrecord: Add ability to filter on the output path.

15.1 Core
----------------------

* config: Add ``default_page_layout`` and ``default_post_layout`` settings.
* data: Also expose XML date formatting as ``xmldate`` in Jinja.
* internal: Fix stupid routing bug.
* internal: Remove unused code.
* internal: Template functions could potentially be called outside of a render.
* internal: Try handling URLs in a consistent way.
* internal: Use hashes for cache paths.
* pagination: Make pagination use routes to generate proper URLs.

15.3 Project
----------------------

* build: Put dev-only lib requirements into a ``dev-requirements.txt`` file.
* docs: Add "active page" style for the navigation menu.
* docs: Add documentation for importing content from other engines.
* docs: Add new site configuration settings to the reference documentation.
* tests: Add ``os.rename`` to the mocked functions.
* tests: Add more utility functions to the mock file-system.
* tests: Fix test.
* tests: Improve bake tests output, add support for partial output checks.
* tests: Raise an exception instead of crashing rudely.
* tests: Remove debug output.
* tests: Support for YAML-based baking tests. Convert old code-based ones.

15.4 Miscellaneous
----------------------

* cleancss: Fix stupid bug.

==================================
16. PieCrust 2.0.0a6 (2015-03-30)
==================================


16.0 Commands
----------------------

* bake: Better error handling for site baking.
* bake: Better error handling for the processing pipeline.
* bake: Change arguments to selectively bake to make them symmetrical.
* bake: Changes in how assets directories are configured.
* bake: Don't include the site root when building output paths.
* bake: Don't store internal config values in the bake record.
* bake: Fix processing record bugs and error logging for external processes.
* bake: Remove ``--portable`` option until it's (maybe) implemented.
* import: Add an XML-based Wordpress importer.
* import: Make the Wordpress importer extendable, rename it to ``wordpressxml`` .
* import: Put importer metadata on the class, and allow return values.
* import: Show help if no sub-command was specified.
* import: Upgrade more settings for the PieCrust 1 importer.
* import: Wordpress importer puts drafts in a ``draft`` folder. Ignore other statuses.
* plugins: Change how plugins are loaded. Add a ``plugins`` command.
* plugins: First pass for a working plugin loader functionality.
* plugins: Fix crash for sites that don't specify a ``site/plugins`` setting.
* plugins: Remove unused API endpoints.
* prepare: Add user-defined scaffolding templates.
* serve: Add server sent events for showing pipeline errors in the debug window.
* serve: Correctly pass on the HTTP status code when an error occurs.
* serve: Correctly show timing info even when not in debug mode.
* serve: Don't crash when a post URL doesn't match our expectations.
* serve: Don't expose the debug info right away when running with ``--debug`` .
* serve: Don't have 2 processing loops running when using ``--use-reloader`` .
* serve: Fix a bug where empty route metadata is not the same as invalid route.
* serve: Fix exiting the server with ``CTRL+C`` when the SSE response is running.
* serve: Keep the ``?!debug`` when generating URLs if it is enabled.
* serve: Make the server find assets generated by external tools.
* serve: Print nested exception messages in the dev server.
* serve: Run the asset pipeline asynchronously.
* serve: Use Etags and 304 responses for assets.
* showrecord: Also show the pipeline record.
* showrecord: Show relative paths.
* showrecord: Show the overall status (success/failed) of the bake.
* sources: Fix a bug where the ``posts`` source wasn't correctly parsing URLs.
* sources: Generate proper slugs in the ``autoconfig`` and ``ordered`` sources.
* sources: Make sure page sources have some basic config info they need.
* sources: Pass any current mode to ``_populateMetadata`` when finding pages.
* sources: Refactor ``autoconfig`` source, add ``OrderedPageSource`` .
* sources: The ordered source returns names without prefixes in ``listPath`` .
* sources: Use ``posts_*`` and ``items_*`` settings more appropriately.
* theme: Fix the default theme's templates after changes in Jinja's wrapper.
* theme: Updated "quickstart" text shown for new websites.
* themes: Add the ``chef themes`` command

16.1 Core
----------------------

* config: Assign correct data endpoint for blogs to be v1-compatible.
* config: Make YAML consider ``omap`` structures as normal maps.
* config: Make sure ``site/plugins`` is transformed into a list.
* data: Add a top level wrapper for ``Linker`` .
* data: Add ability for ``IPaginationSource`` s to specify how to get settings.
* data: Better error message for old date formats, add ``emaildate`` filter.
* data: Correctly build pagination filters when we know items are pages.
* data: Don't nest filters in the paginator -- nest clauses instead.
* data: Fix incorrect next/previous page URLs in pagination data.
* data: Fix typos and stupid errors.
* data: Improve the Linker and RecursiveLinker features. Add tests.
* data: Make the ``Linekr`` use the new ``getSettingAccessor`` API.
* data: Only expose the ``family`` linker.
* data: Temporary hack for asset URLs.
* data: ``Linker`` refactor.
* internal: A bit of input validation for source APIs.
* internal: Add ability to get a default value if a config value doesn't exist.
* internal: Add support for "wildcard" loader in ``LazyPageConfigData`` .
* internal: Add utility function to get a page from a source.
* internal: Be more forgiving about building ``Taxonomy`` objects. Add ``setting_name`` .
* internal: Bump the processing record version.
* internal: Code reorganization to put less stuff in ``sources.base`` .
* internal: Fix bug with the default source when listing ``/`` path.
* internal: Make the simple page source use ``slug`` everywhere.
* internal: Re-use the cached resource directory.
* internal: Remove mentions of plugins directories and sources.
* internal: Remove the (unused) ``new_only`` flag for pipeline processing.
* internal: Removing some dependency of filters and iterators on pages.
* pagination: Add support for ``site/default_pagination_source`` .
* render: Add support for a Mustache template engine.
* render: Don't always use a ``.html`` extension for layouts.
* render: When a template engine can't be found, show the correct name in the error.
* routing: Better generate URLs according to the site configuration.

16.3 Project
----------------------

* build: Add ``pystache`` to ``requirements.txt`` .
* docs: A whole bunch of drafts for content model and reference pages.
* docs: Add a page explaining how PieCrust works at a high level.
* docs: Add documentation on making a plugin.
* docs: Add documentation on the asset pipeline.
* docs: Add embryo of a documentation website.
* docs: Add information about the asset pipeline.
* docs: Add some general information on ``chef`` .
* docs: Add the ability to use Pygments highlighting.
* docs: Add website configuration page.
* docs: Change docs' templates after changes in Jinja's wrapper.
* docs: Documentation for iterators and filtering.
* docs: Documentation on website structure.
* docs: Fix URLs to the docs source.
* docs: Fix link, add another link.
* docs: Fix missing link.
* docs: Last part of the tutorial.
* docs: More on creating websites.
* docs: More tutorial text.
* docs: Pagination and assets' documentation.
* docs: Properly escape examples with Jinja markup.
* docs: Quick support info page.
* docs: Still adding more pages.
* docs: Still more documentation.
* docs: Tutorial part 1.
* docs: Tutorial part 2.
* docs: Tweak CSS for boxed text.
* docs: Website configuration reference.
* tests: Add a blog data provider test.
* tests: Add help functions to get and render a simple page.
* tests: Add tests for Jinja template engine.
* tests: Add utility function to create multiple mock pages in one go.
* tests: Bad me, the tests were broken. Now they're fixed.
* tests: Fix linker tests.
* tests: Fix tests for base sources.
* tests: Fixes for running on Windows.
* tests: Patch ``os.path.exists`` and improve patching for ``open`` .
* tests: Remove debug output.

16.4 Miscellaneous
----------------------

* Add bower configuration file.
* Merge code changes.
* Merge docs.
* Temporary root URL for publishing.
* Use the site root for docs assets.
* bake/serve: Fix how taxonomy index pages are setup and rendered.
* bake/serve: Make previewed and baked URLs consistent.
* builtin: Remove ``plugins`` command, it's not ready yet.
* cleancss: Add option to specify an output extension, like ``.min.css`` .
* cosmetic: Fix PEP8 spacing.
* cosmetic: Fix some PEP8 issues.
* cosmetic: Fix some PEP8 issues.
* cosmetic: PEP8 compliance.
* dataprovider: Use the setting name for a taxonomy to match page config values.
* jinja: Add a global function to render Pygments' CSS styles.
* jinja: Fix Twig compatibility for block trimming.
* jinja: Provide a more "standard" Jinja configuration by default.
* less: Generate a proper, available URL for the LESS CSS map file.
* logging: If an error doesn't have a message, print its type.
* markdown: Let the user specify extensions in one line.
* oops: Remove debug print.
* processing: Add Compass and Sass processors.
* processing: Add ``concat`` , ``uglifyjs`` and ``cleancss`` processors.
* processing: Add ability to specify processors per mount.
* processing: Add more information to the pipeline record.
* processing: Don't fail if an asset we want to remove has already been removed.
* processing: More powerful syntax to specify pipeline processors.
* processing: Use the correct full path for mounts.
* sitemap: Fix broken API call.
* sitemap: Fixed typo bug.

==================================
17. PieCrust 2.0.0a5 (2015-01-03)
==================================


17.0 Commands
----------------------

* bake: Don't crash stupidly when there was no previous version.
* chef: Work around a bug in MacOSX where the default locale doesn't work.
* find: Fix the ``find`` command, add more options.
* paths: properly format lists of paths.
* prepare: Show a more friendly user message when no arguments are given.
* routes: Actually match metadata when finding routes, fix problems with paths.
* routes: Show regex patterns for routes.
* routes: When matching URIs, return metadata directly instead of the match object.
* serve: Add option to use the debugger without ``--debug`` .
* serve: Always force render the page being previewed.
* sources: Add ``chef sources`` command to list page sources.
* sources: Add an ``IListableSource`` interface for sources that can be listed.
* sources: Make the ``SimplePageSource`` more extensible, fix bugs in ``prose`` source.

17.1 Core
----------------------

* linker: Actually implement the ``Linker`` class, and use it in the page data.

17.3 Project
----------------------

* build: Add Travis-CI config file.
* setup: Make version generation compatible with PEP440.
* tests: Add unit tests for routing classes.
* tests: Fix serving test.

17.4 Miscellaneous
----------------------

* Ability to output debug logging to ``stdout`` when running unit-tests.
* Add Textile formatter.
* Add ``--log-debug`` option.
* Add ``autoconfig`` page source.
* Add ``compressinja`` to install/env requirements.
* Add ``ctrlpignore`` file.
* Add ``help`` function, cleanup argument handling.
* Add ``import`` command, Jekyll importer.
* Add ``sitemap`` processor.
* Add a ``BakeScheduler`` to handle build dependencies. Add unit-tests.
* Add ability for the processing pipeline to only process new assets.
* Add packaging and related files.
* Add support for KeyboardInterrupt in bake process.
* Add support for Markdown extensions.
* Add the ``paginate`` filter to Jinja, activate ``auto_reload`` .
* Added requirements file for ``pip`` .
* Added unit tests (using ``py.test`` ) for ``Configuration`` .
* Allow adding to the default content model instead of replacing it.
* Always use version generated by ``setup.py`` . Better version generation.
* Apparently Jinja doesn't understand ``None`` the way I thought.
* Better ``prepare`` command, with templates and help topics.
* Better combine user sources/routes with the default ones.
* Better date creation for blog post scaffolding.
* Better date/time handling for pages:
* Better error management and removal support in baking/processing.
* Better error reporting and cache validation.
* Better handling of Jinja configuration.
* Better support for times in YAML interop.
* Cache rendered segments to disk.
* Changes to ``help`` command and extendable commands:
* Changes to the asset processing pipeline:
* Check we don't give null values to the processing pipeline.
* Copy page assets to bake output, use correct slashes when serving assets.
* Correctly match skip patterns.
* Correctly set the ``debug`` flag on the app.
* Correctly set the current page on a pagination slicer.
* Cosmetic fix.
* Define page slugs properly, avoid recursions with debug data.
* Display page tags with default theme.
* Don't colour debug output.
* Don't complain about missing ``pages`` or ``posts`` directories by default.
* Don't fail if trying to clean up a file that has already been deleted.
* Don't look at theme sources in ``chef prepare`` .
* Don't look for tests inside the ``build`` directory.
* Don't recursively clean the cache.
* Don't stupidly crash in the RequireJS processor.
* Don't try to get the name of a source that doesn't have one.
* Don't use Werkzeug's reloader in non-debug mode unless we ask for it.
* Don't use file-system caching for rendered segments yet.
* Error out if ``date`` filter is used with PHP date formats.
* Exit with the proper code.
* First draft of the ``prose`` page source.
* Fix ``setuptools`` install.
* Fix a bug with page references in cases of failure. Add unit tests.
* Fix a bug with the posts source incorrectly escaping regex characters.
* Fix a crash when checking for timestamps on template files.
* Fix cache validation issue with rendered segments, limit disk access.
* Fix error reporting and counting of lines.
* Fix for pages listing pages from other sources.
* Fix generation of system messages.
* Fix how the ``Paginator`` gets the numer of items per page.
* Fix how we pass the out directory to the baking modules.
* Fix outdate information and bug in default theme's main page.
* Fix post sources datetimes by adding missing metadata when in "find" mode.
* Fix problems with asset URLs.
* Fix running ``chef`` outside of a website. Slightly better error reporting.
* Fix search for root folder. Must have been drunk when I wrote this originally.
* Fix some bugs with iterators, add some unit tests.
* Fix some indentation and line lengths.
* Fix stupid bug in default source, add some unit tests.
* Fix stupid bug.
* Fix stupid debug logging bug.
* Fix unit tests.
* Fixed a bug with the ``shallow`` source. Add unit tests.
* Fixed outdate information in error messages' footer.
* Fixes for Windows, make ``findPagePath`` return a ref path.
* Fixes to the ``cache`` Jinja tag.
* Forgot this wasn't C++.
* Get the un-paginated URL of a page early and pass that around.
* Gigantic change to basically make PieCrust 2 vaguely functional.
* Give the proper URL to ``Paginator`` in the ``paginate`` filter.
* Handle the case where the debug server needs to serve an asset created after it was started.
* I don't care what the YAML spec says, ordered maps are the only sane way.
* Ignore ``setuptools`` build directory.
* Ignore messages' counter.
* Improvements and fixes to incremental baking.
* Improvements to incremental baking and cache invalidating.
* In-place upgrade for PieCrust 1 sites.
* Initial commit.
* Jinja templating now has ``spaceless`` , ``|keys`` and ``|values`` .
* Make a nice error message when a layout hasn't been found.
* Make configuration class more like ``dict`` , add support for merging ``dicts`` .
* Make sure ``.html`` is part of auto-formats.
* Make template directories properly absolute.
* Make the ``Assetor`` iterate over paths.
* Match routes completely, not partially.
* Mock ``os.path.isfile`` , and fix a few other test utilities.
* More PieCrust 3 fixes, and a couple of miscellaneous bug fixes.
* More Python 3 fixes, modularization, and new unit tests.
* More installation information in the README file.
* More options for the ``showrecord`` command.
* More robust Markdown configuration handling.
* More unit tests for output bake paths.
* More unit tests, fix a bug with the skip patterns.
* Moved all installation instructions to a new ``INSTALL`` file.
* New site layout support.
* Oops.
* Optimize server for files that already exist.
* Pass date information to routing when building URLs.
* PieCrust 1 import: clean empty directories and convert some config values.
* Prepare the server to support background asset pipelines.
* Print the help by default when running ``chef`` with no command.
* Processors can match on other things than just the extension.
* Proper debug logging.
* Properly add the config time to a page's datetime.
* Properly escape HTML characters in the debug info, add more options.
* Properly override pages between realms.
* Properly use, or not, the debugging when using the chef server.
* Propertly create ``OrderedDict`` s when loading YAML.
* Property clean all caches when force baking, except the ``app`` cache.
* PyYAML supports sexagesimal notation, so handle that for page times.
* Quick fix for making the server correctly update referenced pages.
* Re-arranged modules to reduce dependencies to builtin stuff.
* Re-enable proper caching of rendered segments in server.
* Remove unneeded trace.
* Setup the server better.
* Simple importer for PieCrust 1 websites.
* Simplify ``AutoConfigSource`` by inheriting from ``SimplePageSource`` .
* Slightly better exception throwing in the processing pipeline.
* Slightly more robust dependency handling for the LESS processor.
* Split baking code in smaller files.
* Support for installing from Git.
* Switch the PieCrust server to debug mode with ``?!debug`` in the URL.
* The LESS compiler must be launched in a shell on Windows.
* The ``date`` filter now supports passing ``"now"`` as in Twig.
* Unused import.
* Update system messages.
* Update the ``requirements`` file.
* Upgrade system messages to the new folder structure.
* Upgrade to Python 3.
* Use ``SafeLoader`` instead of ``BaseLoader`` for Yaml parsing.
* Use cache paths that are easier to debug than hashes.
* Use ordered dictionaries to preserve priorities between auto-formats.
* Use properly formatted date components for the blog sources.
* Use the ``OrderedDict`` correctly when fresh-loading the app config.
* Use the item name for the ``prepare`` command.
* Use the same defaults as in PieCrust 1.
* Various fixes for the default page source:
* When possible, try and batch-load pages so we only lock once.
* cosmetic: pep8 compliance.
