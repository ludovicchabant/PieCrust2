import logging


logger = logging.getLogger(__name__)


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


class IsDefinedFilterClause(IFilterClause):
    def __init__(self, name):
        self.name = name

    def pageMatches(self, fil, page):
        return self.name in page.config


class IsNotEmptyFilterClause(IFilterClause):
    def __init__(self, name):
        self.name = name

    def pageMatches(self, fil, page):
        return bool(page.config.get(self.name))


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
        actual_value = page.config.get(self.name)
        if actual_value is None or not isinstance(actual_value, list):
            return False

        if self.coercer:
            actual_value = list(map(self.coercer, actual_value))

        return self.value in actual_value


class IsFilterClause(SettingFilterClause):
    def pageMatches(self, fil, page):
        actual_value = page.config.get(self.name)
        if self.coercer:
            actual_value = self.coercer(actual_value)
        return actual_value == self.value


unary_ops = {'not': NotClause}
binary_ops = {
    'and': AndBooleanClause,
    'or': OrBooleanClause}
misc_ops = {
    'defined': IsDefinedFilterClause,
    'not_empty': IsNotEmptyFilterClause}


class PaginationFilter(object):
    def __init__(self):
        self.root_clause = None

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
            clause_class = unary_ops.get(key)
            if clause_class:
                if isinstance(val, list):
                    if len(val) != 1:
                        raise Exception(
                            "Unary filter '%s' must have exactly one child "
                            "clause." % key)
                    val = val[0]
                subcl = clause_class()
                parent_clause.addClause(subcl)
                self._addClausesFromConfigRecursive(val, subcl)
                continue

            clause_class = binary_ops.get(key)
            if clause_class:
                if not isinstance(val, list) or len(val) == 0:
                    raise Exception(
                        "Binary filter clause '%s' doesn't have an array "
                        "of child clauses." % key)
                subcl = clause_class()
                parent_clause.addClause(subcl)
                for c in val:
                    self._addClausesFromConfigRecursive(c, subcl)
                continue

            clause_class = misc_ops.get(key)
            if clause_class:
                if isinstance(val, list):
                    wrappercl = AndBooleanClause()
                    for c in val:
                        wrappercl.addClause(clause_class(c))
                    parent_clause.addClause(wrappercl)
                else:
                    parent_clause.addClause(clause_class(val))
                continue

            if key[:4] == 'has_':
                setting_name = key[4:]
                if isinstance(val, list):
                    wrappercl = AndBooleanClause()
                    for c in val:
                        wrappercl.addClause(HasFilterClause(setting_name, c))
                    parent_clause.addClause(wrappercl)
                else:
                    parent_clause.addClause(HasFilterClause(setting_name, val))
                continue

            if key[:3] == 'is_':
                setting_name = key[3:]
                parent_clause.addClause(IsFilterClause(setting_name, val))
                continue

            raise Exception("Unknown filter clause: %s" % key)
