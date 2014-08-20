from piecrust.commands.builtin.baking import (BakeCommand, ShowRecordCommand)
from piecrust.commands.builtin.info import (RootCommand, ShowConfigCommand,
        FindCommand, ShowRoutesCommand, ShowPathsCommand)
from piecrust.commands.builtin.serving import (ServeCommand)
from piecrust.commands.builtin.util import (InitCommand, PurgeCommand,
        PrepareCommand)
from piecrust.data.provider import (IteratorDataProvider, BlogDataProvider)
from piecrust.formatting.markdownformatter import MarkdownFormatter
from piecrust.plugins.base import PieCrustPlugin
from piecrust.processing.base import CopyFileProcessor
from piecrust.processing.less import LessProcessor
from piecrust.processing.sitemap import SitemapProcessor
from piecrust.sources.base import DefaultPageSource
from piecrust.sources.posts import (FlatPostsSource, ShallowPostsSource,
        HierarchyPostsSource)
from piecrust.templating.jinjaengine import JinjaTemplateEngine


class BuiltInPlugin(PieCrustPlugin):
    def __init__(self):
        super(BuiltInPlugin, self).__init__()
        self.name = '__builtin__'

    def getCommands(self):
        return [
                InitCommand(),
                RootCommand(),
                PurgeCommand(),
                ShowConfigCommand(),
                FindCommand(),
                PrepareCommand(),
                ShowRoutesCommand(),
                ShowPathsCommand(),
                BakeCommand(),
                ShowRecordCommand(),
                ServeCommand()]

    def getCommandExtensions(self):
        return []

    def getSources(self):
        return [
                DefaultPageSource,
                FlatPostsSource,
                ShallowPostsSource,
                HierarchyPostsSource]

    def getDataProviders(self):
        return [
                IteratorDataProvider,
                BlogDataProvider]

    def getTemplateEngines(self):
        return [
                JinjaTemplateEngine()]

    def getFormatters(self):
        return [
                MarkdownFormatter()]

    def getProcessors(self):
        return [
                CopyFileProcessor(),
                LessProcessor(),
                SitemapProcessor()]

