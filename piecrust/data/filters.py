import logging


logger = logging.getLogger(__name__)


def page_value_accessor(page, name):
    return page.config.get(name)


class PaginationFilter(object):
    def __init__(self, value_accessor=None):
        self.root_clause = None
        self.value_accessor = value_accessor or self._default_value_accessor

    @property
    def is_empty(self):
        return self.root_clause is None

    def addClause(self, clause):
        self._ensureRootClause()
        self.root_clause.addClause(clause)

    def addClausesFromConfig(self, config):
        self._ensureRootClause()
        self._addClausesFromConfigRecursive(config, self.root_clause)

    def pageMatches(self, page):
        if self.root_clause is None:
            return True
        return self.root_clause.pageMatches(self, page)

    def _ensureRootClause(self):
        if self.root_clause is None:
            self.root_clause = AndBooleanClause()

    def _addClausesFromConfigRecursive(self, config, parent_clause):
        for key, val in config.items():
            if key == 'and':
                if not isinstance(val, list) or len(val) == 0:
                    raise Exception("The given boolean 'AND' filter clause "
                                    "doesn't have an array of child clauses.")
                subcl = AndBooleanClause()
                parent_clause.addClause(subcl)
                for c in val:
                    self._addClausesFromConfigRecursive(c, subcl)

            elif key == 'or':
                if not isinstance(val, list) or len(val) == 0:
                    raise Exception("The given boolean 'OR' filter clause "
                                    "doesn't have an array of child clauses.")
                subcl = OrBooleanClause()
                parent_clause.addClause(subcl)
                for c in val:
                    self._addClausesFromConfigRecursive(c, subcl)

            elif key == 'not':
                if isinstance(val, list):
                    if len(val) != 1:
                        raise Exception("'NOT' filter clauses must have "
                                        "exactly one child clause.")
                    val = val[0]
                subcl = NotClause()
                parent_clause.addClause(subcl)
                self._addClausesFromConfigRecursive(val, subcl)

            elif key[:4] == 'has_':
                setting_name = key[4:]
                if isinstance(val, list):
                    wrappercl = AndBooleanClause()
                    for c in val:
                        wrappercl.addClause(HasFilterClause(setting_name, c))
                    parent_clause.addClause(wrappercl)
                else:
                    parent_clause.addClause(HasFilterClause(setting_name, val))

            elif key[:3] == 'is_':
                setting_name = key[3:]
                parent_clause.addClause(IsFilterClause(setting_name, val))

            else:
                raise Exception("Unknown filter clause: %s" % key)

    @staticmethod
    def _default_value_accessor(item, name):
        try:
            return getattr(item, name)
        except AttributeError:
            return None


class IFilterClause(object):
    def addClause(self, clause):
        raise NotImplementedError()

    def pageMatches(self, fil, page):
        raise NotImplementedError()


class NotClause(IFilterClause):
    def __init__(self):
        self.child = None

    def addClause(self, clause):
        if self.child is not None:
            raise Exception("'NOT' filtering clauses can only have one "
                            "child clause.")
        self.child = clause

    def pageMatches(self, fil, page):
        if self.child is None:
            raise Exception("'NOT' filtering clauses must have one child "
                            "clause.")
        return not self.child.pageMatches(fil, page)


class BooleanClause(IFilterClause):
    def __init__(self):
        self.clauses = []

    def addClause(self, clause):
        self.clauses.append(clause)


class AndBooleanClause(BooleanClause):
    def pageMatches(self, fil, page):
        for c in self.clauses:
            if not c.pageMatches(fil, page):
                return False
        return True


class OrBooleanClause(BooleanClause):
    def pageMatches(self, fil, page):
        for c in self.clauses:
            if c.pageMatches(fil, page):
                return True
        return False


class SettingFilterClause(IFilterClause):
    def __init__(self, name, value, coercer=None):
        self.name = name
        self.value = value
        self.coercer = coercer

    def addClause(self, clause):
        raise Exception("Setting filter clauses can't have child clauses. "
                        "Use a boolean filter clause instead.")


class HasFilterClause(SettingFilterClause):
    def pageMatches(self, fil, page):
        actual_value = fil.value_accessor(page, self.name)
        if actual_value is None or not isinstance(actual_value, list):
            return False

        if self.coercer:
            actual_value = list(map(self.coercer, actual_value))

        return self.value in actual_value


class IsFilterClause(SettingFilterClause):
    def pageMatches(self, fil, page):
        actual_value = fil.value_accessor(page, self.name)
        if self.coercer:
            actual_value = self.coercer(actual_value)
        return actual_value == self.value

