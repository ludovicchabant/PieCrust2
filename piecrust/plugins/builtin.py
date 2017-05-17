from piecrust.plugins.base import PieCrustPlugin


class BuiltInPlugin(PieCrustPlugin):
    name = '__builtin__'

    def getCommands(self):
        from piecrust.commands.base import HelpCommand
        from piecrust.commands.builtin.admin import AdministrationPanelCommand
        from piecrust.commands.builtin.baking import (
            BakeCommand, ShowRecordCommand)
        from piecrust.commands.builtin.info import (
            RootCommand, ShowConfigCommand,
            FindCommand, ShowSourcesCommand, ShowRoutesCommand,
            ShowPathsCommand)
        from piecrust.commands.builtin.plugins import PluginsCommand
        from piecrust.commands.builtin.publishing import PublishCommand
        from piecrust.commands.builtin.scaffolding import PrepareCommand
        from piecrust.commands.builtin.serving import (ServeCommand)
        from piecrust.commands.builtin.themes import (ThemesCommand)
        from piecrust.commands.builtin.util import (
            InitCommand, PurgeCommand, ImportCommand)

        return [
            InitCommand(),
            ImportCommand(),
            HelpCommand(),
            RootCommand(),
            PurgeCommand(),
            ShowConfigCommand(),
            FindCommand(),
            PrepareCommand(),
            ShowSourcesCommand(),
            ShowRoutesCommand(),
            ShowPathsCommand(),
            ThemesCommand(),
            PluginsCommand(),
            BakeCommand(),
            ShowRecordCommand(),
            ServeCommand(),
            AdministrationPanelCommand(),
            PublishCommand()]

    def getCommandExtensions(self):
        from piecrust.commands.builtin.scaffolding import (
            DefaultPrepareTemplatesCommandExtension,
            UserDefinedPrepareTemplatesCommandExtension,
            DefaultPrepareTemplatesHelpTopic)

        return [
            DefaultPrepareTemplatesCommandExtension(),
            UserDefinedPrepareTemplatesCommandExtension(),
            DefaultPrepareTemplatesHelpTopic()]

    def getSources(self):
        from piecrust.sources.autoconfig import (
            AutoConfigContentSource, OrderedContentSource)
        from piecrust.sources.blogarchives import BlogArchivesSource
        from piecrust.sources.default import DefaultContentSource
        from piecrust.sources.fs import FSContentSource
        from piecrust.sources.posts import (
            FlatPostsSource, ShallowPostsSource, HierarchyPostsSource)
        from piecrust.sources.prose import ProseSource
        from piecrust.sources.taxonomy import TaxonomySource

        return [
            AutoConfigContentSource,
            BlogArchivesSource,
            DefaultContentSource,
            FSContentSource,
            FlatPostsSource,
            HierarchyPostsSource,
            OrderedContentSource,
            ProseSource,
            ShallowPostsSource,
            TaxonomySource]

    def getPipelines(self):
        from piecrust.pipelines.page import PagePipeline
        from piecrust.pipelines.asset import AssetPipeline

        return [
            PagePipeline,
            AssetPipeline]

    def getDataProviders(self):
        from piecrust.data.provider import (
            IteratorDataProvider, BlogDataProvider)

        return [
            IteratorDataProvider,
            BlogDataProvider]

    def getTemplateEngines(self):
        from piecrust.templating.jinjaengine import JinjaTemplateEngine
        from piecrust.templating.pystacheengine import PystacheTemplateEngine

        return [
            JinjaTemplateEngine(),
            PystacheTemplateEngine()]

    def getFormatters(self):
        from piecrust.formatting.hoedownformatter import HoedownFormatter
        from piecrust.formatting.markdownformatter import MarkdownFormatter
        from piecrust.formatting.textileformatter import TextileFormatter
        from piecrust.formatting.smartypantsformatter import (
            SmartyPantsFormatter)

        return [
            HoedownFormatter(),
            MarkdownFormatter(),
            SmartyPantsFormatter(),
            TextileFormatter()]

    def getProcessors(self):
        from piecrust.processing.compass import CompassProcessor
        from piecrust.processing.compressors import (
            CleanCssProcessor, UglifyJSProcessor)
        from piecrust.processing.copy import CopyFileProcessor
        from piecrust.processing.less import LessProcessor
        from piecrust.processing.pygments_style import PygmentsStyleProcessor
        from piecrust.processing.requirejs import RequireJSProcessor
        from piecrust.processing.sass import SassProcessor
        from piecrust.processing.sitemap import SitemapProcessor
        from piecrust.processing.util import ConcatProcessor

        return [
            CopyFileProcessor(),
            ConcatProcessor(),
            PygmentsStyleProcessor(),
            CompassProcessor(),
            LessProcessor(),
            SassProcessor(),
            RequireJSProcessor(),
            SitemapProcessor(),
            CleanCssProcessor(),
            UglifyJSProcessor()]

    def getImporters(self):
        from piecrust.importing.jekyll import JekyllImporter
        from piecrust.importing.piecrust import PieCrust1Importer
        from piecrust.importing.wordpress import WordpressXmlImporter

        return [
            PieCrust1Importer(),
            JekyllImporter(),
            WordpressXmlImporter()]

    def getPublishers(self):
        from piecrust.publishing.sftp import SftpPublisher
        from piecrust.publishing.shell import ShellCommandPublisher
        from piecrust.publishing.rsync import RsyncPublisher

        return [
            ShellCommandPublisher,
            SftpPublisher,
            RsyncPublisher]

