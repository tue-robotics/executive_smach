import ast
import astor
from copy import deepcopy


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
    return white + white.join(s.splitlines(1))


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
        if line != "\n" and line[:num_del] != white:
            raise ValueError("removing more spaces than there are!")
        return line[num_del:] if line != "\n" else line
    return ''.join(map(aux, s.splitlines(1)))


def num_spaces(s):
    # type: (str) -> [int]
    """
    Get the number of leading spaces per line of a (multi-line) string

    :param s: string
    :return: number of leading spaces per line
    """
    return [len(line)-len(line.lstrip()) for line in s.splitlines(0)]


def unindent_block(s):
    # type: (str) -> str
    """
    Remove the maximum number of leading spaces of a (multi-line) string, so that the line with the least number of
    leading spaces, is stripped from all leading spaces

    :param s: string
    :return: stripped string
    """
    return del_spaces(s, min([x for x in num_spaces(s) if x > 0]))


class StateCodeTransformer(ast.NodeTransformer):
    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def visit_Name(self, node):
        if node.id == "self":
            return ast.copy_location(ast.Attribute(attr="_state", value=node, ctx=ast.Load()), node)
        else:
            return self.generic_visit(node)


class StateCodeReverseTransformer(ast.NodeTransformer):
    # noinspection PyPep8Naming,PyMethodMayBeStatic
    def visit_Attribute(self, node):
        if node.attr == "_state" and isinstance(node.value, ast.Name) and node.value.id == "self":
            return node.value
        else:
            return self.generic_visit(node)


class StateAttributeAnalyser(ast.NodeVisitor):
    def __init__(self, state, filename, line_offset):
        self._state = state
        self._filename = filename
        self._line_offset = line_offset
        self._lines = []

        self._recent_lineno = None
        self._recent_col_offset = None

    def compile(self):
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
        self._lines = []

    def _add_expr(self, expr):
        self._lines.append({"expr": expr, "lineno": self._recent_lineno,
                            "col_offset": self._recent_col_offset})

    def _file_line_error(self):
        return '\n  File "{0}", line {1}\n\t'.format(self._filename, self._recent_lineno, "blaat")

    @staticmethod
    def _ast_unparse(node):
        return astor.to_source(StateCodeReverseTransformer().visit(deepcopy(node))).strip()

    def _visit_item(self, node):
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
        return node.id == "self"