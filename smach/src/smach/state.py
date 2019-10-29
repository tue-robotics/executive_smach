
import threading
import traceback

import ast
import astor
from copy import deepcopy
import inspect
import smach

__all__ = ['State','CBState']


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


class State(object):
    """Base class for SMACH states.

    A SMACH state interacts with SMACH containers in two ways. The first is its
    outcome identifier, and the second is the set of userdata variables which
    it reads from and writes to at runtime. Both of these interactions are
    declared before the state goes active (when its C{execute()} method is
    called) and are checked during construction.
    """
    _member_variables_checked = False

    @property
    def member_variables_checked(self):
        return self._member_variables_checked

    def check_member_variables(self):
        filename = inspect.getsourcefile(self.execute)
        execute_code, line_offset = inspect.getsourcelines(self.execute)
        execute_contents_only = "\n".join(map(str.rstrip, execute_code[1:]))

        tree = ast.parse(unindent_block(execute_contents_only))
        tree = StateCodeTransformer().visit(tree)
        analyser = StateAttributeAnalyser(self, filename, line_offset)
        analyser.visit(tree)
        analyser.compile()

        self._member_variables_checked = True

    def __init__(self, outcomes=[], input_keys=[], output_keys=[], io_keys=[]):
        """State constructor
        @type outcomes: list of str
        @param outcomes: Custom outcomes for this state.

        @type input_keys: list of str
        @param input_keys: The userdata keys from which this state might read
        at runtime.

        @type output_keys: list of str
        @param output_keys: The userdata keys to which this state might write
        at runtime.

        @type io_keys: list of str
        @param io_keys: The userdata keys to which this state might write or
        from which it might read at runtime.
        """
        # Store outcomes
        self._outcomes = set(outcomes)

        # Store userdata interface description
        self._input_keys = set(input_keys + io_keys)
        self._output_keys = set(output_keys + io_keys)

        # Declare preempt flag
        self._preempt_requested = False
        self._shutdown_requested = False
        smach.handle_shutdown(self.request_shutdown)

    ### Meat
    def execute(self, ud):
        """Called when executing a state.
        In the base class this raises a NotImplementedError.

        @type ud: L{UserData} structure
        @param ud: Userdata for the scope in which this state is executing
        """
        raise NotImplementedError()

    ### SMACH Interface API
    def register_outcomes(self, new_outcomes):
        """Add outcomes to the outcome set."""
        self._outcomes = self._outcomes.union(new_outcomes)

    def get_registered_outcomes(self):
        """Get a list of registered outcomes.
        @rtype: tuple of str
        @return: Tuple of registered outcome strings.
        """
        return tuple(self._outcomes)

    ### Userdata API
    def register_io_keys(self, keys):
        """Add keys to the set of keys from which this state may read and write.
        @type keys: list of str
        @param keys: List of keys which may be read from and written to when this
        state is active.
        """
        self._input_keys = self._input_keys.union(keys)
        self._output_keys = self._output_keys.union(keys)

    def register_input_keys(self, keys):
        """Add keys to the set of keys from which this state may read.
        @type keys: list of str
        @param keys: List of keys which may be read from when this state is
        active.
        """
        self._input_keys = self._input_keys.union(keys)

    def get_registered_input_keys(self):
        """Get a tuple of registered input keys."""
        return tuple(self._input_keys)

    def register_output_keys(self, keys):
        """Add keys to the set of keys to which this state may write.
        @type keys: list of str
        @param keys: List of keys which may be written to when this state is
        active.
        """
        self._output_keys = self._output_keys.union(keys)

    def get_registered_output_keys(self):
        """Get a tuple of registered output keys."""
        return tuple(self._output_keys)

    ### Preemption interface
    def request_preempt(self):
        """Sets preempt_requested to True"""
        self._preempt_requested = True

    def service_preempt(self):
        """Sets preempt_requested to False"""
        self._preempt_requested = False

    def recall_preempt(self):
        """Sets preempt_requested to False"""
        self._preempt_requested = False

    def preempt_requested(self):
        """True if a preempt has been requested."""
        return self._preempt_requested

    def request_shutdown(self):
        """Sets action on shutdown to request_preempt"""
        self._shutdown_requested = True
        self.request_preempt()

class CBState(State):
    def __init__(self, cb, cb_args=[], cb_kwargs={}, outcomes=[], input_keys=[], output_keys=[], io_keys=[]):
        """Create s state from a single function.

        @type outcomes: list of str
        @param outcomes: Custom outcomes for this state.

        @type input_keys: list of str
        @param input_keys: The userdata keys from which this state might read
        at runtime. 

        @type output_keys: list of str
        @param output_keys: The userdata keys to which this state might write
        at runtime.

        @type io_keys: list of str
        @param io_keys: The userdata keys to which this state might write or
        from which it might read at runtime.
        """
        State.__init__(self, outcomes, input_keys, output_keys, io_keys)
        self._cb = cb
        self._cb_args = cb_args
        self._cb_kwargs = cb_kwargs

        if smach.util.has_smach_interface(cb):
            self._cb_input_keys = cb.get_registered_input_keys()
            self._cb_output_keys = cb.get_registered_output_keys()
            self._cb_outcomes = cb.get_registered_outcomes()

            self.register_input_keys(self._cb_input_keys)
            self.register_output_keys(self._cb_output_keys)
            self.register_outcomes(self._cb_outcomes)

    def execute(self, ud):
        return self._cb(ud, *self._cb_args, **self._cb_kwargs)
