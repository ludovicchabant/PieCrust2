from piecrust.commands.base import HelpCommand
from piecrust.commands.builtin.baking import (
        BakeCommand, ShowRecordCommand)
from piecrust.commands.builtin.info import (
        RootCommand, ShowConfigCommand,
        FindCommand, ShowSourcesCommand, ShowRoutesCommand, ShowPathsCommand)
from piecrust.commands.builtin.plugins import PluginsCommand
from piecrust.commands.builtin.scaffolding import (
        PrepareCommand,
        DefaultPrepareTemplatesCommandExtension,
        UserDefinedPrepareTemplatesCommandExtension,
        DefaultPrepareTemplatesHelpTopic)
from piecrust.commands.builtin.serving import (ServeCommand)
from piecrust.commands.builtin.themes import (ThemesCommand)
from piecrust.commands.builtin.util import (
        InitCommand, PurgeCommand, ImportCommand)
from piecrust.data.provider import (IteratorDataProvider, BlogDataProvider)
from piecrust.formatting.markdownformatter import MarkdownFormatter
from piecrust.formatting.textileformatter import TextileFormatter
from piecrust.formatting.smartypantsformatter import SmartyPantsFormatter
from piecrust.importing.jekyll import JekyllImporter
from piecrust.importing.piecrust import PieCrust1Importer
from piecrust.importing.wordpress import WordpressXmlImporter
from piecrust.plugins.base import PieCrustPlugin
from piecrust.processing.base import CopyFileProcessor
from piecrust.processing.compass import CompassProcessor
from piecrust.processing.compressors import (
        CleanCssProcessor, UglifyJSProcessor)
from piecrust.processing.less import LessProcessor
from piecrust.processing.requirejs import RequireJSProcessor
from piecrust.processing.sass import SassProcessor
from piecrust.processing.sitemap import SitemapProcessor
from piecrust.processing.util import ConcatProcessor
from piecrust.sources.default import DefaultPageSource
from piecrust.sources.posts import (
        FlatPostsSource, ShallowPostsSource, HierarchyPostsSource)
from piecrust.sources.autoconfig import (
        AutoConfigSource, OrderedPageSource)
from piecrust.sources.prose import ProseSource
from piecrust.templating.jinjaengine import JinjaTemplateEngine
from piecrust.templating.pystacheengine import PystacheTemplateEngine


class BuiltInPlugin(PieCrustPlugin):
    name = '__builtin__'

    def getCommands(self):
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
                ServeCommand()]

    def getCommandExtensions(self):
        return [
                DefaultPrepareTemplatesCommandExtension(),
                UserDefinedPrepareTemplatesCommandExtension(),
                DefaultPrepareTemplatesHelpTopic()]

    def getSources(self):
        return [
                DefaultPageSource,
                FlatPostsSource,
                ShallowPostsSource,
                HierarchyPostsSource,
                AutoConfigSource,
                OrderedPageSource,
                ProseSource]

    def getDataProviders(self):
        return [
                IteratorDataProvider,
                BlogDataProvider]

    def getTemplateEngines(self):
        return [
                JinjaTemplateEngine(),
                PystacheTemplateEngine()]

    def getFormatters(self):
        return [
                MarkdownFormatter(),
                SmartyPantsFormatter(),
                TextileFormatter()]

    def getProcessors(self):
        return [
                CopyFileProcessor(),
                ConcatProcessor(),
                CompassProcessor(),
                LessProcessor(),
                SassProcessor(),
                RequireJSProcessor(),
                SitemapProcessor(),
                CleanCssProcessor(),
                UglifyJSProcessor()]

    def getImporters(self):
        return [
                PieCrust1Importer(),
                JekyllImporter(),
                WordpressXmlImporter()]

