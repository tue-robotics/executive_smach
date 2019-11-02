import ast
import astor
from copy import deepcopy
import inspect


# Whitespace functions
def add_spaces(s, num_add):
    # type: (str, int) -> str
    """
    Add leading spaces to (multi-line) string

    :param s: string
    :param num_add: number of spaces to add
    :return: string with added spaces
    """
    white = " "*num_add
    return white + white.join(s.splitlines(True))


def del_spaces(s, num_del):
    # type: (str, int) -> str
    """
    Delete 'num_del' leading spaces from (multi-line) string
    Empty lines are ignore
    If a line contains less leading spaces than to be removed a ValueError is raised

    :param s: string to strip from leading spaces
    :param num_del: number of spaces to delete
    :return: string stripped from leading spaces
    """
    def aux(line, num_del=num_del, white=" "*num_del):
        # type: (str, int, str) -> [str]
        if line.strip() and line[:num_del] != white:
            raise ValueError("removing more spaces than there are!")
        return line[num_del:] if line.strip() else line
    return ''.join(map(aux, s.splitlines(True)))


def num_spaces(s):
    # type: (str) -> [int]
    """
    Get the number of leading spaces per line of a (multi-line) string

    :param s: string
    :return: number of leading spaces per line
    """
    return [len(line)-len(line.lstrip()) for line in s.splitlines(False)]


def unindent_block(s):
    # type: (str) -> str
    """
    Remove the maximum number of leading spaces of a (multi-line) string, so that the line with the least number of
    leading spaces, is stripped from all leading spaces. No tabs allowed

    :param s: string
    :return: stripped string
    """
    if "\t" in s:
        raise ValueError("No tabs allowed: {}".format(repr(s)))
    return del_spaces(s, min(num_spaces("\n".join([l for l in s.splitlines() if l]))))


class StateCodeTransformer(ast.NodeTransformer):
    """
    Convert code of a state to be part of the StateAttributeAnalyser by replacing "self" by "self._state"
    """
    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def visit_Name(self, node):
        # type: (ast.AST) -> ast.AST
        if node.id == "self":
            return ast.copy_location(ast.Attribute(attr="_state", value=node, ctx=ast.Load()), node)
        else:
            return self.generic_visit(node)


class StateCodeReverseTransformer(ast.NodeTransformer):
    """
    Convert code of the StateAttributeAnalyser back to original state code by replacing "self._state" by "self"
    """
    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def visit_Attribute(self, node):
        # type: (ast.AST) -> ast.AST
        if node.attr == "_state" and isinstance(node.value, ast.Name) and node.value.id == "self":
            return node.value
        else:
            return self.generic_visit(node)


class StateAttributeAnalyser(ast.NodeVisitor):
    """
    Analyse members and functions of state variables
    """
    def __init__(self, state):
        """
        Constructor

        :param state: state to be analysed
        """
        self._state = state
        self._lines = []

        self._recent_lineno = None
        self._recent_col_offset = None

        filename = inspect.getsourcefile(self._state.execute)
        execute_code, line_offset = inspect.getsourcelines(self._state.execute)

        self._filename = filename
        self._line_offset = line_offset

        execute_contents_only = "\n".join(map(str.rstrip, execute_code[1:]))
        tree = ast.parse(unindent_block(execute_contents_only.expandtabs(4)))
        self._tree = StateCodeTransformer().visit(tree)

    def analyse(self):
        """
        Analyse the code of self._tree if is compatible with the current self._state and its functions and members.
        """
        self.visit(self._tree)
        self._compile()

    def _compile(self):
        exceptions = []
        for line in self._lines:
            obj = compile(ast.fix_missing_locations(ast.Module(body=[line["expr"]])), filename=self._filename,
                          mode="exec")
            try:
                exec obj
            except Exception as e:
                exceptions.append(e)

        if exceptions:
            msg = "\nIncorrect call(s):"
            msg += "\n".join(map(str, exceptions))
            raise AssertionError(msg)

    def reset(self):
        """
        Clear stored expressions to be evaluated.
        :return:
        """
        self._lines = []

    def _add_expr(self, expr):
        # type: (ast.stmt) -> None
        """
        Add expr to be evaluated at the end. Include line number and column offset for possible logging.

        :param expr: (ast.expr) expression
        """
        self._lines.append({"expr": expr, "lineno": self._recent_lineno,
                            "col_offset": self._recent_col_offset})

    def _file_line_error(self):
        # type: () -> str
        """
        Generate a message with the filename and current line.

        :return: message
        """
        return '\n  File "{0}", line {1}\n\t'.format(self._filename, self._recent_lineno)

    @staticmethod
    def _ast_unparse(node):
        # type: (ast.AST) -> str
        """
        Convert ast code back to plain code

        :param node: (ast.AST)
        :return: (str) plain code
        """
        return astor.to_source(StateCodeReverseTransformer().visit(deepcopy(node))).strip()

    def _visit_item(self, node):
        # type: (ast.AST) -> bool
        if isinstance(node, ast.AST):
            old_lineno = self._recent_lineno
            old_col_offset = self._recent_col_offset
            if isinstance(node, ast.stmt):
                self._recent_lineno = node.lineno + self._line_offset
                self._recent_col_offset = node.col_offset
            output = self.visit(node)
            self._recent_lineno = old_lineno
            self._recent_col_offset = old_col_offset
            return output

    def generic_visit(self, node):
        # type: (ast.AST) -> bool
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                outputs = []
                for item in value:
                    outputs.append(self._visit_item(item))
                return any(outputs)
            # else
            return self._visit_item(value)

    # noinspection PyPep8Naming
    def visit_Attribute(self, node):
        # type: (ast.Attribute) -> bool
        expr = ast.Assert(test=ast.Call(func=ast.Name(id='hasattr', ctx=ast.Load()),
                                        args=[node.value, ast.Str(s=node.attr)], keywords=[],
                                        starargs=None, kwargs=None),
                          msg=ast.Str(s="{}'{}' has no attribute '{}'".format(
                              self._file_line_error(),
                              self._ast_unparse(node.value),
                              node.attr)))

        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                outputs = []
                for item in value:
                    outputs.append(self._visit_item(item))
                output = any(outputs)
                if output:
                    self._add_expr(expr)
                return output
            # else
            output = self._visit_item(value)
            if output:
                self._add_expr(expr)
            return output

    # noinspection PyPep8Naming
    def visit_Call(self, node):
        # type: (ast.Call) -> bool
        expr = ast.Assert(test=ast.Compare(left=ast.Call(func=ast.Name(id="callable", ctx=ast.Load()),
                                                         args=[node.func], keywords=[]),
                                           ops=[ast.Eq()], comparators=[ast.Name(id="True", ctx=ast.Load())]),
                          msg=ast.Str(s="{}'{}' object is not callable".format(
                              self._file_line_error(),
                              self._ast_unparse(node))))

        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                outputs = []
                for item in value:
                    outputs.append(self._visit_item(item))
                output = any(outputs)
                if output:
                    self._add_expr(expr)
                return output
            # else
            output = self._visit_item(value)
            if output:
                self._add_expr(expr)
            return output

    # noinspection PyPep8Naming
    @staticmethod
    def visit_Name(node):
        # type: (ast.Name) -> bool
        return node.id == "self"
