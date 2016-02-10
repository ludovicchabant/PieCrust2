
#########
CHANGELOG
#########

This is the changelog for PieCrust_.

.. _PieCrust: http://bolt80.com/piecrust/



==================================
1. PieCrust 2.0.0b4 (2016-02-09)
==================================


1.0 Commands
----------------------

* chef: Fix the ``--config-set`` option.
* chef: Add ``--pid-file`` option.
* bake: Add new performance timers.
* bake: Add support for a "known" page setting that excludes it from the bake.
* bake: Add option to bake assets for FoodTruck. This is likely temporary.
* sources: Add method to get a page factory from a path.
* sources: Add code to support "interactive" metadata acquisition.
* serve: Make it possible to preview pages with a custom root URL.
* serve: Fix corner cases where the pipeline doesn't run correctly.
* showconfig: Don't crash when the whole config should be shown.
* bake: Don't re-setup logging for workers unless we're sure we need it.
* serve: Fix error reporting when the background pipeline fails.
* chef: Add ``--debug-only`` option to only show debug logging for a given logger.
* routes: Add better support for taxonomy slugification.
* serve: Improve reloading and shutdown of the preview server.
* serve: Don't crash when looking at the debug info in a stand-alone window.
* serve: Improve debug information in the preview server.
* serve: Refactor the server to make pieces usable by the debugging middleware.
* serve: Fix timing information in the debug window.
* serve: Extract some of the server's functionality into WSGI middlewares.
* serve: Rewrite of the Server-Sent Event code for build notifications.
* serve: Werkzeug docs say you need to pass a flag with ``wrap_file`` .
* bake: Add a flag to know which record entries got collapsed from last run.
* bake: Set the flags, don't combine.

1.1 Core
----------------------

* debug: Fix debug window CSS.
* debug: Don't show parentheses on redirected properties.
* debug: Fix how the linker shows children/siblings/etc. in the debug window.
* internal: Some fixes to the new app configuration.
* internal: Refactor the app configuration class.
* internal: Rename ``raw_content`` to ``segments`` since it's what it is.
* bug: Fix a crash when some errors occur during page rendering.
* data: Fix a crash bug when no parent page is set on an iterator.
* bug: Correctly handle root URLs with special characters.
* debug: Fix a crash when rendering debug info for some pages.

1.2 Project
----------------------

* docs: Make FoodTruck screenshots the proper size.
* cm: Add script to generate documentation.
* docs: Add documentation about FoodTruck.
* docs: Add raw files for FoodTruck screenshots.
* docs: Add documentation about the ``publish`` command.
* cm: Add some pretty little icons in the README.
* tests: Add unicode tests for case-sensitive file-systems.
* cm: Merge the 2 foodtruck folders, cleanup.
* cm: Fix Gulp config.
* docs: Fix broken link.
* cm: Put Bower/Gulp/etc. stuff all at the root.
* cm: Add requirements for FoodTruck.
* cm: Ignore more stuff for CtrlP or Gutentags.
* tests: Fix (hopefully) time-sensitive tests.
* cm: CHANGELOG generator can handle future versions.
* docs: Remove LessCSS dependencies in the tutorial, fix typos.
* tests: Fix broken unit test.
* tests: Fix another broken test.
* docs: Add reference entry about the ``site/slugify_mode`` setting.
* tests: Fix broken test.
* tests: Print more information when a bake test fails to find an output file.

1.3 Miscellaneous
----------------------

* admin: Make the publish UI handle new kinds of target configurations.
* admin: Fix crashes when creating a new page.
* admin: Fix responsive layout.
* admin: Use ``HGPLAIN`` for the Mercurial VCS provider.
* publish: Add option to change the source for the ``rsync`` publisher.
* publish: Change the ``shell`` config setting name for the command to run.
* publish: Add the ``rsync`` publisher.
* publish: Polish/refactor the publishing workflows.
* admin: Make the sidebar togglable for smaller screens.
* admin: Change the default admin server port to 8090, add ``--port`` option.
* admin: Improve publish logs showing as alerts in the admin panel.
* publish: Make the ``shell`` log update faster by flushing the pipe.
* publish: Add publish command.
* admin: Use the app directory, not the cwd, in case of ``--root`` .
* admin: Configuration changes.
* admin: Fix "Publish started" message showing up multiple times.
* admin: Show the install page if no secret key is available.
* admin: Prompt the user for a commit message when committing a page.
* admin: Fix creating pages.
* admin: Better UI for publishing websites.
* admin: Better error reporting, general clean-up.
* admin: Fix constructor for Mercurial SCM.
* admin: Set the ``DEBUG`` flag before the app runs so we can read it during setup.
* admin: Ability to configure SCM stuff per site.
* admin: Better production config for FoodTruck, provide proper first site.
* admin: Make sure we have a valid default site to start with.
* admin: Dashboard UI cleaning, re-use utility function for page summaries.
* admin: Add summary of page in source listing.
* admin: New ``admin`` command to manage FoodTruck-related things.
* admin: Add "FoodTruck" admin panel from the side experiment project.
* cli: More proper argument parsing for the main/root arguments.
* cli: Add ``--no-color`` option.

==================================
2. PieCrust 2.0.0b3 (2015-08-01)
==================================


1.0 Commands
----------------------

* import: Correctly convert unicode characters in site configuration.
* import: Fix the PieCrust 1 importer.
* import: Add some debug logging.

1.1 Core
----------------------

* internal: Fix a severe bug with the file-system wrappers on OSX.
* templating: Make more date functions accept 'now' as an input.

1.2 Project
----------------------

* cm: Update changelog.
* cm: Changelog generator script.
* cm: Add a Gutentags config file for ``ctags`` generation.
* tests: Check accented characters work in configurations.
* cm: Ignore Rope cache.

==================================
3. PieCrust 2.0.0b2 (2015-07-29)
==================================


1.0 Commands
----------------------

* prepare: More help about scaffolding.

1.1 Core
----------------------

* bug: Fix crash running ``chef help scaffolding`` outside of a website.

==================================
4. PieCrust 2.0.0b1 (2015-07-29)
==================================


1.0 Commands
----------------------

* prepare: Fix the RSS template.
* serve: Improve Jinja rendering error reporting.
* serve: Don't show the same error message twice.
* serve: Say what page a rendering error happened in.
* serve: Improve error reporting when pages are not found.
* bake: Add a processor to generate a Pygments style CSS file.
* bake: Fix logging configuration for multi-processing on Windows.
* themes: Improve CLI, add ``deactivate`` command.
* themes: Don't fixup template directories, it's actually better as-is.
* serve: Try to serve taxonomy pages after all normal pages have failed.
* serve: Fix a crash when matching taxonomy URLs with incorrect URLs.
* bake: Fix random crash with the Sass processor.
* themes: Add a ``link`` sub-command to install a theme via a symbolic link.
* themes: Add config paths to the cache key.
* themes: Proper template path fixup for the theme configuration.
* bake: Set the worker ID in the configuration. It's useful.
* themes: Fix crash when invoking command with no sub-command.

1.1 Core
----------------------

* templating: Add ``now`` global to Jinja, improve date error message.
* bug: Of course I broke something. Some exceptions need to pass through Jinja.
* bug: Fix file-system wrappers for non-Mac systems.
* bug: Forgot to add a new file like a big n00b.
* config: Make sure ``site/auto_formats`` has at least ``html`` .
* internal: Return ``None`` instead of raising an exception when finding pages.
* internal: Improve handling of taxonomy term slugification.
* formatting: Add support for Markdown extension configs.
* templating: ``highlight_css`` can be passed the name of a Pygments style.
* bug: Fix a crash with the ``ordered`` page source when sorting pages.
* internal: Fix some edge-cases for splitting sub-URIs.
* internal: Fix timing info.
* templating: Make Jinja support arbitrary extension, show warning for old stuff.
* internal: Correctly split sub URIs. Add unit tests.

1.2 Project
----------------------

* tests: Help the Yaml loader figure out the encoding on Windows.
* cm: Re-fix Mac file-system wrappers.
* cm: Add ``unidecode`` to requirements.
* tests: Fix processing test after adding ``PygmentsStyleProcessor`` .
* docs: Use fenced code block syntax.
* docs: Add some syntax highlighting to tutorial pages.
* docs: Make code prettier :)
* docs: Always use Pygments styles. Use the new CSS generation processor.
* docs: Configure fenced code blocks in Markdown with Pygments highlighting.
* docs: Add some API documentation.
* docs: Start a proper "code/API" section.
* cm: Error in ``.hgignore`` . Weird.
* docs: No need to specify the layout here.
* docs: Make the "deploying" page consistent with "publishing".
* docs: More generic information about baking and publishing.
* tests: Fix the Mustache tests on Windows.
* tests: Fix ``find`` tests on Windows.
* tests: Fix processing tests on Windows.
* tests: Normalize test paths using the correct method.
* cm: Fix benchmark website generation on Windows.
* cm: Ignore ``.egg-info`` stuff.

1.3 Miscellaneous
----------------------

* bake/serve: Improve support for unicode, add slugification options.
* cosmetic: Remove debug print here too.
* cosmetic: Remove debug printing.
* sass: Overwrite the old map file with the new one always.
* less: Fix issues with the map file on Windows.
* jinja: Support ``.j2`` file extensions.

==================================
5. PieCrust 2.0.0a13 (2015-07-14)
==================================


1.0 Commands
----------------------

* bake: Fix a bug with copying assets when ``pretty_urls`` are disabled.

1.1 Core
----------------------

* bug: Fix copying of page assets during the bake.
* bug: Correctly setup the environment/app for bake workers.

==================================
6. PieCrust 2.0.0a12 (2015-07-14)
==================================


1.0 Commands
----------------------

* bake: Pass the config variants and values from the CLI to the baker.
* bake: Add CLI argument to specify job batch size.
* bake: Use batched jobs in the worker pool.
* bake: Correctly use the ``num_worers`` setting.
* bake: Abort "render first" jobs if we start using other pages.
* bake: Don't pass the previous record entries to the workers.
* bake: Optimize the bake by not using custom classes for passing info.
* serve: Use Werkzeug's HTTP exceptions correctly.
* serve: Fix bug with creating routing metadata from the URL.
* bake: Commonize worker pool code between html and asset baking.
* bake: Tweaks to the ``sitemap`` processor. Add tests.
* bake: Pass the sub-cache directory to the bake workers.
* bake: Improve performance timers reports.
* serve: Fix crash on start.
* bake: Improve bake record information.
* bake: Make pipeline processing multi-process.
* bake: Enable multiprocess baking.

1.1 Core
----------------------

* bug: Fix CLI crash caused by configuration variants.
* internal: Handle data serialization more under the hood.
* internal: Add support for fake pickling of date/time structures.
* internal: Just use the plain old standard function.
* rendering: Truly skip formatters that are not enabled.
* templating: Let Jinja2 cache the parsed template for page contents.
* internal: Add a ``fastpickle`` module to help with multiprocess serialization.
* bug: Fix infinite loop in Jinja2 rendering.
* performance: Only use Jinja2 for rendering text if necessary.
* performance: Use the fast YAML loader if available.
* performance: Add profiling to the asset pipeline workers.
* internal: Remove unnecessary import.
* performance: Refactor how data is managed to reduce copying.
* bug: Fix routing bug introduced by 21e26ed867b6.
* bug: Fix a crash when errors occur while processing an asset.
* reporting: Print errors that occured during pipeline processing.
* templating: Add modification time of the page to the template data.
* reporting: Better error messages for incorrect property access on data.
* internal: Floats are also allowed in configurations, duh.
* internal: Create full route metadata in one place.
* templating: Workaround for a bug with Pystache.
* templating: Fix Pystache template engine.
* performance: Compute default layout extensions only once.
* performance: Quick and dirty profiling support for bake workers.
* internal: Fix caches being orphaned from their directory.
* render: Lazily import Textile package.
* internal: Remove unnecessary code.
* internal: Optimize page data building.
* internal: Optimize page segments rendering.
* internal: Add utility function for incrementing performance timers.
* internal: Move ``MemCache`` to the ``cache`` module, remove threading locks.
* internal: Register performance timers for plugin components.
* internal: Allow re-registering performance timers.
* debug: Fix serving of resources now that the module moved to a sub-folder.
* debug: Better debug info output for iterators, providers, and linkers.
* debug: Add support for more attributes for the debug info.
* debug: Log error when an exception gets raised during debug info building.
* linker: Add ability to return the parent and ancestors of a page.

1.2 Project
----------------------

* cm: Fix wrong directory for utilities.
* cm: Add script to generate benchmark websites.
* cm: Use Travis CI's new infrastructure.
* tests: Fix Jinja2 test.
* cm: Move build directory to util to avoid conflicts with pip.
* tests: Fix crash in processing tests.
* tests: Add pipeline processing tests.
* docs: Add the ``--pre`` flag to ``pip install`` while PieCrust is in beta.

1.3 Miscellaneous
----------------------

* Fixed 'bootom' to 'bottom'
* markdown: Cache the formatter once.

==================================
7. PieCrust 2.0.0a11 (2015-05-18)
==================================


1.0 Commands
----------------------

* bake: Return all errors from a bake record entry when asked for it.
* serve: Fix bug where ``?!debug`` doesn't get appending correctly.
* serve: Remove development assert.

1.1 Core
----------------------

* linker: Fix linker returning the wrong value for ``is_dir`` in some situations.
* linker: Fix error when trying to list non-existing children.
* pagination: Fix regression bug with previous/next posts.
* data: Fix regression bug with accessing page metadata that doesn't exist.

1.2 Project
----------------------

* tests: More accurate marker position for diff'ing strings.
* tests: Fail bake tests with a proper error message when bake fails.
* tests: Move all bakes/cli/servings tests files to have a YAML extension.
* tests: Also mock ``open`` in Jinja to be able to use templates in bake tests.
* tests: Add support for testing the Chef server.

1.3 Miscellaneous
----------------------

* jinja: Look for ``html`` extension first instead of last.

==================================
8. PieCrust 2.0.0a10 (2015-05-15)
==================================


1.2 Project
----------------------

* setup: Add ``requirements.txt`` to ``MANIFEST.in`` so it can be used by the setup.

==================================
9. PieCrust 2.0.0a9 (2015-05-11)
==================================


1.0 Commands
----------------------

* serve: Add a generic WSGI app factory.
* serve: Compatibility with ``mod_wsgi`` .
* serve: Add a WSGI utility module for easily getting a default app.
* serve: Add ability to suppress the debug info window programmatically.
* serve: Split the server code in a couple modules inside a ``serving`` package.

1.1 Core
----------------------

* internal: Make it possible to pass ``argv`` to the main Chef function.
* data: Fix problems with using non-existing metadata on a linked page.
* routing: Fix bugs with matching URLs with correct route but missing metadata.

1.2 Project
----------------------

* tests: Add a Chef test for the ``find`` command.
* tests: Add support for "Chef tests", which are direct CLI tests.
* docs: Add lame bit of documentation on publishing your website.
* docs: Add documentation for deploying as a dynamic CMS.
* tests: Fix serving unit-tests.
* setup: Keep the requirements in sync between ``setuptools`` and ``pip`` .

==================================
10. PieCrust 2.0.0a8 (2015-05-03)
==================================


1.0 Commands
----------------------

* theme: Fix link to PieCrust documentation.
* serve: Giant refactor to change how we handle data when serving pages.
* sources: Default source lists pages in order.
* serve: Refactoring and fixes to be able to serve taxonomy pages.
* sources: Fix how the ``autoconfig`` source iterates over its structure.
* bake: Fix crash when handling bake errors.

1.1 Core
----------------------

* caching: Use separate caches for config variants and other contexts.
* linker: Don't put linker stuff in the config.
* config: Add method to deep-copy a config and validate its contents.
* internal: Return the first route for a source if no metadata match is needed.

1.2 Project
----------------------

* tests: Changes to output report and hack for comparing outputs.

1.3 Miscellaneous
----------------------

* Update development ``requirements.txt`` , add code coverage tools.
* Update ``requirements.txt`` .

==================================
11. PieCrust 2.0.0a7 (2015-04-20)
==================================


1.0 Commands
----------------------

* import: Use the proper baker setting in the Jekyll importer.
* serve: Don't access the current render pass info after rendering is done.
* chef: Fix pre-parsing.
* chef: Add a ``--config-set`` option to set ad-hoc site configuration settings.
* find: Don't change the pattern when there's none.
* bake: Improve render context and bake record, fix incremental bake bugs.
* bake: Several bug taxonomy-related fixes for incorrect incremental bakes.
* bake: Use a rotating bake record.
* showrecord: Add ability to filter on the output path.
* serve: Fix crash on URI parsing.

1.1 Core
----------------------

* data: Also expose XML date formatting as ``xmldate`` in Jinja.
* pagination: Make pagination use routes to generate proper URLs.
* internal: Remove unused code.
* config: Add ``default_page_layout`` and ``default_post_layout`` settings.
* internal: Template functions could potentially be called outside of a render.
* internal: Fix stupid routing bug.
* internal: Use hashes for cache paths.
* internal: Try handling URLs in a consistent way.

1.2 Project
----------------------

* docs: Add documentation for importing content from other engines.
* build: Put dev-only lib requirements into a ``dev-requirements.txt`` file.
* docs: Add "active page" style for the navigation menu.
* tests: Improve bake tests output, add support for partial output checks.
* tests: Add more utility functions to the mock file-system.
* docs: Add new site configuration settings to the reference documentation.
* tests: Support for YAML-based baking tests. Convert old code-based ones.
* tests: Remove debug output.
* tests: Add ``os.rename`` to the mocked functions.
* tests: Fix test.
* tests: Raise an exception instead of crashing rudely.

1.3 Miscellaneous
----------------------

* cleancss: Fix stupid bug.

==================================
12. PieCrust 2.0.0a6 (2015-03-30)
==================================


1.0 Commands
----------------------

* import: Wordpress importer puts drafts in a ``draft`` folder. Ignore other statuses.
* plugins: Remove unused API endpoints.
* plugins: Fix crash for sites that don't specify a ``site/plugins`` setting.
* plugins: Change how plugins are loaded. Add a ``plugins`` command.
* import: Show help if no sub-command was specified.
* plugins: First pass for a working plugin loader functionality.
* import: Make the Wordpress importer extendable, rename it to ``wordpressxml`` .
* import: Add an XML-based Wordpress importer.
* sources: Make sure page sources have some basic config info they need.
* import: Put importer metadata on the class, and allow return values.
* import: Upgrade more settings for the PieCrust 1 importer.
* serve: Don't crash when a post URL doesn't match our expectations.
* serve: Correctly show timing info even when not in debug mode.
* theme: Fix the default theme's templates after changes in Jinja's wrapper.
* themes: Add the ``chef themes`` command
* sources: Generate proper slugs in the ``autoconfig`` and ``ordered`` sources.
* bake: Don't store internal config values in the bake record.
* sources: Use ``posts_*`` and ``items_*`` settings more appropriately.
* serve: Use Etags and 304 responses for assets.
* sources: The ordered source returns names without prefixes in ``listPath`` .
* sources: Fix a bug where the ``posts`` source wasn't correctly parsing URLs.
* sources: Refactor ``autoconfig`` source, add ``OrderedPageSource`` .
* bake: Don't include the site root when building output paths.
* serve: Fix a bug where empty route metadata is not the same as invalid route.
* serve: Print nested exception messages in the dev server.
* serve: Keep the ``?!debug`` when generating URLs if it is enabled.
* serve: Fix exiting the server with ``CTRL+C`` when the SSE response is running.
* serve: Don't expose the debug info right away when running with ``--debug`` .
* bake: Fix processing record bugs and error logging for external processes.
* bake: Change arguments to selectively bake to make them symmetrical.
* serve: Add server sent events for showing pipeline errors in the debug window.
* showrecord: Show the overall status (success/failed) of the bake.
* bake: Better error handling for site baking.
* bake: Better error handling for the processing pipeline.
* serve: Don't have 2 processing loops running when using ``--use-reloader`` .
* theme: Updated "quickstart" text shown for new websites.
* serve: Run the asset pipeline asynchronously.
* bake: Changes in how assets directories are configured.
* serve: Correctly pass on the HTTP status code when an error occurs.
* bake: Remove ``--portable`` option until it's (maybe) implemented.
* showrecord: Also show the pipeline record.
* showrecord: Show relative paths.
* serve: Make the server find assets generated by external tools.
* prepare: Add user-defined scaffolding templates.
* sources: Pass any current mode to ``_populateMetadata`` when finding pages.

1.1 Core
----------------------

* data: Better error message for old date formats, add ``emaildate`` filter.
* pagination: Add support for ``site/default_pagination_source`` .
* config: Assign correct data endpoint for blogs to be v1-compatible.
* internal: Add utility function to get a page from a source.
* internal: Be more forgiving about building ``Taxonomy`` objects. Add ``setting_name`` .
* config: Make sure ``site/plugins`` is transformed into a list.
* internal: Remove mentions of plugins directories and sources.
* config: Make YAML consider ``omap`` structures as normal maps.
* data: Fix incorrect next/previous page URLs in pagination data.
* data: Temporary hack for asset URLs.
* data: Don't nest filters in the paginator -- nest clauses instead.
* data: Correctly build pagination filters when we know items are pages.
* internal: Re-use the cached resource directory.
* routing: Better generate URLs according to the site configuration.
* data: Add a top level wrapper for ``Linker`` .
* internal: Code reorganization to put less stuff in ``sources.base`` .
* internal: Fix bug with the default source when listing ``/`` path.
* data: ``Linker`` refactor.
* internal: Add support for "wildcard" loader in ``LazyPageConfigData`` .
* internal: Removing some dependency of filters and iterators on pages.
* internal: Make the simple page source use ``slug`` everywhere.
* data: Fix typos and stupid errors.
* data: Make the ``Linekr`` use the new ``getSettingAccessor`` API.
* data: Add ability for ``IPaginationSource`` s to specify how to get settings.
* data: Only expose the ``family`` linker.
* internal: Bump the processing record version.
* internal: Remove the (unused) ``new_only`` flag for pipeline processing.
* data: Improve the Linker and RecursiveLinker features. Add tests.
* internal: A bit of input validation for source APIs.
* internal: Add ability to get a default value if a config value doesn't exist.
* render: Add support for a Mustache template engine.
* render: Don't always use a ``.html`` extension for layouts.
* render: When a template engine can't be found, show the correct name in the error.

1.2 Project
----------------------

* docs: Quick support info page.
* tests: Add utility function to create multiple mock pages in one go.
* tests: Add a blog data provider test.
* tests: Bad me, the tests were broken. Now they're fixed.
* docs: Add documentation on making a plugin.
* docs: Add documentation on the asset pipeline.
* docs: Fix link, add another link.
* docs: A whole bunch of drafts for content model and reference pages.
* docs: Fix missing link.
* docs: Documentation for iterators and filtering.
* docs: Add the ability to use Pygments highlighting.
* docs: Pagination and assets' documentation.
* tests: Fixes for running on Windows.
* docs: Still more documentation.
* docs: Properly escape examples with Jinja markup.
* docs: Last part of the tutorial.
* docs: More tutorial text.
* docs: Tutorial part 2.
* docs: Tweak CSS for boxed text.
* docs: Change docs' templates after changes in Jinja's wrapper.
* docs: Add information about the asset pipeline.
* docs: Add a page explaining how PieCrust works at a high level.
* docs: Still adding more pages.
* tests: Fix linker tests.
* docs: Website configuration reference.
* docs: Add website configuration page.
* docs: More on creating websites.
* docs: Documentation on website structure.
* docs: Add some general information on ``chef`` .
* docs: Tutorial part 1.
* docs: Fix URLs to the docs source.
* docs: Add embryo of a documentation website.
* tests: Fix tests for base sources.
* tests: Remove debug output.
* tests: Add tests for Jinja template engine.
* build: Add ``pystache`` to ``requirements.txt`` .
* tests: Patch ``os.path.exists`` and improve patching for ``open`` .
* tests: Add help functions to get and render a simple page.

1.3 Miscellaneous
----------------------

* bake/serve: Fix how taxonomy index pages are setup and rendered.
* dataprovider: Use the setting name for a taxonomy to match page config values.
* cleancss: Add option to specify an output extension, like ``.min.css`` .
* jinja: Add a global function to render Pygments' CSS styles.
* jinja: Fix Twig compatibility for block trimming.
* sitemap: Fix broken API call.
* jinja: Provide a more "standard" Jinja configuration by default.
* logging: If an error doesn't have a message, print its type.
* Use the site root for docs assets.
* Temporary root URL for publishing.
* Add bower configuration file.
* Merge docs.
* cosmetic: PEP8 compliance.
* bake/serve: Make previewed and baked URLs consistent.
* oops: Remove debug print.
* Merge code changes.
* less: Generate a proper, available URL for the LESS CSS map file.
* sitemap: Fixed typo bug.
* cosmetic: Fix PEP8 spacing.
* processing: Use the correct full path for mounts.
* processing: Don't fail if an asset we want to remove has already been removed.
* processing: Add ``concat`` , ``uglifyjs`` and ``cleancss`` processors.
* processing: More powerful syntax to specify pipeline processors.
* markdown: Let the user specify extensions in one line.
* processing: Add ability to specify processors per mount.
* builtin: Remove ``plugins`` command, it's not ready yet.
* processing: Add Compass and Sass processors.
* cosmetic: Fix some PEP8 issues.
* cosmetic: Fix some PEP8 issues.
* processing: Add more information to the pipeline record.

==================================
13. PieCrust 2.0.0a5 (2015-01-03)
==================================


1.0 Commands
----------------------

* routes: When matching URIs, return metadata directly instead of the match object.
* serve: Always force render the page being previewed.
* routes: Actually match metadata when finding routes, fix problems with paths.
* sources: Add an ``IListableSource`` interface for sources that can be listed.
* sources: Make the ``SimplePageSource`` more extensible, fix bugs in ``prose`` source.
* serve: Add option to use the debugger without ``--debug`` .
* routes: Show regex patterns for routes.
* chef: Work around a bug in MacOSX where the default locale doesn't work.
* bake: Don't crash stupidly when there was no previous version.
* prepare: Show a more friendly user message when no arguments are given.
* find: Fix the ``find`` command, add more options.
* sources: Add ``chef sources`` command to list page sources.
* paths: properly format lists of paths.

1.1 Core
----------------------

* linker: Actually implement the ``Linker`` class, and use it in the page data.

1.2 Project
----------------------

* setup: Make version generation compatible with PEP440.
* build: Add Travis-CI config file.
* tests: Add unit tests for routing classes.
* tests: Fix serving test.

1.3 Miscellaneous
----------------------

* cosmetic: pep8 compliance.
* Moved all installation instructions to a new ``INSTALL`` file.
* Add support for KeyboardInterrupt in bake process.
* Fix some indentation and line lengths.
* First draft of the ``prose`` page source.
* Simplify ``AutoConfigSource`` by inheriting from ``SimplePageSource`` .
* Properly use, or not, the debugging when using the chef server.
* Match routes completely, not partially.
* Make a nice error message when a layout hasn't been found.
* Better combine user sources/routes with the default ones.
* Forgot this wasn't C++.
* Split baking code in smaller files.
* Add ``ctrlpignore`` file.
* Add ``autoconfig`` page source.
* Pass date information to routing when building URLs.
* Don't fail if trying to clean up a file that has already been deleted.
* Fix unit tests.
* Fix a bug with page references in cases of failure. Add unit tests.
* Use ordered dictionaries to preserve priorities between auto-formats.
* Better date/time handling for pages:
* Switch the PieCrust server to debug mode with ``?!debug`` in the URL.
* Display page tags with default theme.
* Fix outdate information and bug in default theme's main page.
* Make configuration class more like ``dict`` , add support for merging ``dicts`` .
* Fixed outdate information in error messages' footer.
* Oops.
* Don't use Werkzeug's reloader in non-debug mode unless we ask for it.
* More installation information in the README file.
* Optimize server for files that already exist.
* Don't colour debug output.
* Ignore messages' counter.
* Handle the case where the debug server needs to serve an asset created after it was started.
* Add ability for the processing pipeline to only process new assets.
* Fix error reporting and counting of lines.
* Fix how we pass the out directory to the baking modules.
* Check we don't give null values to the processing pipeline.
* Update system messages.
* Add Textile formatter.
* Upgrade system messages to the new folder structure.
* Fix generation of system messages.
* Fix stupid bug.
* Better error management and removal support in baking/processing.
* Slightly more robust dependency handling for the LESS processor.
* Don't stupidly crash in the RequireJS processor.
* Changes to the asset processing pipeline:
* Cosmetic fix.
* Fix search for root folder. Must have been drunk when I wrote this originally.
* When possible, try and batch-load pages so we only lock once.
* Re-enable proper caching of rendered segments in server.
* Use cache paths that are easier to debug than hashes.
* Quick fix for making the server correctly update referenced pages.
* Prepare the server to support background asset pipelines.
* Fix post sources datetimes by adding missing metadata when in "find" mode.
* Properly add the config time to a page's datetime.
* Better support for times in YAML interop.
* Don't look for tests inside the ``build`` directory.
* Property clean all caches when force baking, except the ``app`` cache.
* Fix a bug with the posts source incorrectly escaping regex characters.
* Better ``prepare`` command, with templates and help topics.
* Changes to ``help`` command and extendable commands:
* Exit with the proper code.
* Add ``--log-debug`` option.
* Improvements and fixes to incremental baking.
* Fixed a bug with the ``shallow`` source. Add unit tests.
* Unused import.
* Use the ``OrderedDict`` correctly when fresh-loading the app config.
* More options for the ``showrecord`` command.
* Improvements to incremental baking and cache invalidating.
* PyYAML supports sexagesimal notation, so handle that for page times.
* Fixes to the ``cache`` Jinja tag.
* Remove unneeded trace.
* Merge changes.
* Allow adding to the default content model instead of replacing it.
* Ability to output debug logging to ``stdout`` when running unit-tests.
* Add a ``BakeScheduler`` to handle build dependencies. Add unit-tests.
* Don't complain about missing ``pages`` or ``posts`` directories by default.
* Support for installing from Git.
* Propertly create ``OrderedDict`` s when loading YAML.
* Better date creation for blog post scaffolding.
* Use ``SafeLoader`` instead of ``BaseLoader`` for Yaml parsing.
* Fix ``setuptools`` install.
* Ignore ``setuptools`` build directory.
* Always use version generated by ``setup.py`` . Better version generation.
* I don't care what the YAML spec says, ordered maps are the only sane way.
* Add ``compressinja`` to install/env requirements.
* Jinja templating now has ``spaceless`` , ``|keys`` and ``|values`` .
* PieCrust 1 import: clean empty directories and convert some config values.
* In-place upgrade for PieCrust 1 sites.
* Simple importer for PieCrust 1 websites.
* Print the help by default when running ``chef`` with no command.
* Add ``import`` command, Jekyll importer.
* Better handling of Jinja configuration.
* More robust Markdown configuration handling.
* Add ``help`` function, cleanup argument handling.
* Make template directories properly absolute.
* Processors can match on other things than just the extension.
* Use properly formatted date components for the blog sources.
* Setup the server better.
* Don't use file-system caching for rendered segments yet.
* Use the item name for the ``prepare`` command.
* Properly override pages between realms.
* Fix cache validation issue with rendered segments, limit disk access.
* Give the proper URL to ``Paginator`` in the ``paginate`` filter.
* Cache rendered segments to disk.
* Apparently Jinja doesn't understand ``None`` the way I thought.
* Don't recursively clean the cache.
* Correctly set the ``debug`` flag on the app.
* Proper debug logging.
* Fix a crash when checking for timestamps on template files.
* Error out if ``date`` filter is used with PHP date formats.
* Fix stupid debug logging bug.
* Better error reporting and cache validation.
* Fix running ``chef`` outside of a website. Slightly better error reporting.
* Don't look at theme sources in ``chef prepare`` .
* New site layout support.
* More unit tests, fix a bug with the skip patterns.
* Add ``sitemap`` processor.
* Get the un-paginated URL of a page early and pass that around.
* Fix problems with asset URLs.
* Make sure ``.html`` is part of auto-formats.
* Fix stupid bug in default source, add some unit tests.
* More unit tests for output bake paths.
* The ``date`` filter now supports passing ``"now"`` as in Twig.
* Various fixes for the default page source:
* Use the same defaults as in PieCrust 1.
* Copy page assets to bake output, use correct slashes when serving assets.
* Mock ``os.path.isfile`` , and fix a few other test utilities.
* Don't try to get the name of a source that doesn't have one.
* Correctly match skip patterns.
* Fix for pages listing pages from other sources.
* Add support for Markdown extensions.
* Add the ``paginate`` filter to Jinja, activate ``auto_reload`` .
* Slightly better exception throwing in the processing pipeline.
* The LESS compiler must be launched in a shell on Windows.
* Correctly set the current page on a pagination slicer.
* Fix how the ``Paginator`` gets the numer of items per page.
* Properly escape HTML characters in the debug info, add more options.
* Make the ``Assetor`` iterate over paths.
* Define page slugs properly, avoid recursions with debug data.
* Fixes for Windows, make ``findPagePath`` return a ref path.
* Fix some bugs with iterators, add some unit tests.
* Add packaging and related files.
* Update the ``requirements`` file.
* More PieCrust 3 fixes, and a couple of miscellaneous bug fixes.
* More Python 3 fixes, modularization, and new unit tests.
* Upgrade to Python 3.
* Added requirements file for ``pip`` .
* Gigantic change to basically make PieCrust 2 vaguely functional.
* Added unit tests (using ``py.test`` ) for ``Configuration`` .
* Re-arranged modules to reduce dependencies to builtin stuff.
* Initial commit.
