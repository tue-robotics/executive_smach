import ast
import astor
from copy import deepcopy
from smach.state_checks import add_spaces, del_spaces, num_spaces, unindent_block, StateCodeTransformer,\
    StateCodeReverseTransformer
from smach.state import State
import unittest


class TestAddSpaces(unittest.TestCase):

    def test_single_line(self):
        """
        Test the addition of 4 leading spaces to a single line string
        """
        s1 = "line1"
        s2 = add_spaces(s1, 4)
        self.assertEqual("    " + s1, s2)

    def test_single_line_add_zero(self):
        """
        Test the addition of zero leading spaces to a single line string
        """
        s1 = "line1"
        s2 = add_spaces(s1, 0)
        self.assertEqual(s1, s2)

    def test_multi_line(self):
        """
        Test the addition of 4 leading spaces to a multi line string
        """
        strings = ["line1", "line2", "line3"]
        s1 = "\n".join(strings)
        s2 = add_spaces(s1, 4)
        for string1, string2 in zip(strings, s2.splitlines(False)):
            self.assertEqual("    " + string1, string2)

    def test_multi_line_add_zero(self):
        """
        Test the addition of zero leading spaces to a multi line string
        """
        strings = ["line1", "line2", "line3"]
        s1 = "\n".join(strings)
        s2 = add_spaces(s1, 0)
        for string1, string2 in zip(strings, s2.splitlines(False)):
            self.assertEqual(repr(string1), repr(string2))


class TestDelSpaces(unittest.TestCase):

    def test_del_spaces(self):
        """
        Test the removal of leading spaces of a string with 4 leading spaces, it should raise a ValueError, when
        more paces are being removed than are available.
        """
        s1 = "    four_spaces"
        s2 = del_spaces(s1, 0)
        self.assertEqual(s1, s2)
        s3 = del_spaces(s1, 1)
        self.assertEqual(s1[1:], s3)
        s4 = del_spaces(s1, 2)
        self.assertEqual(s1[2:], s4)
        s5 = del_spaces(s1, 3)
        self.assertEqual(s1[3:], s5)
        s6 = del_spaces(s1, 4)
        self.assertEqual(s1[4:], s6)
        with self.assertRaises(ValueError) as cm:
            del_spaces(s1, 5)
        self.assertEqual(cm.exception.message, "removing more spaces than there are!")

    def test_del_spaces_single_tab(self):
        """
        Test the removal of leading spaces of a string with a only a tab. As this line only contains whitespace, it
        should be ignored
        """
        s1 = "\t"
        s2 = del_spaces(s1, 0)
        self.assertEqual(s1, s2)
        s3 = del_spaces(s1, 1)
        self.assertEqual(s3, s1)
        s4 = del_spaces(s1, 2)
        self.assertEqual(s4, s1)

    def test_del_spaces_multi_tab(self):
        """
        Test the removal of leading spaces of a string with a two tabs. As this line only contains whitespace, it
        should be ignored
        """
        s1 = "\t\t"
        s2 = del_spaces(s1, 0)
        self.assertEqual(s1, s2)
        s3 = del_spaces(s1, 1)
        self.assertEqual(s3, s1)
        s4 = del_spaces(s1, 2)
        self.assertEqual(s4, s1)

    def test_del_spaces_multi_tab_and_text(self):
        """
        Test the removal of leading spaces of a string with a two tabs and text. Tabs aren't counted as spaces, so
        a ValueError sho
        """
        s1 = "\t\ttwo_tabs"
        with self.assertRaises(ValueError) as cm:
            s2 = del_spaces(s1, 0)
        self.assertEqual(cm.exception.message, r"No tabs allowed in lines with not only whitespace: '\t\ttwo_tabs'")


class TestNumSpaces(unittest.TestCase):

    def test_num_spaces(self):
        """
        Test the counting of leading spaces, tabs should be counted as one
        """
        strings = ["l1", " l2", "  l3", "\n", "\t", "    "]
        s1 = "\n".join(strings)
        spaces = num_spaces(s1)
        self.assertEqual(spaces, [0, 1, 2, 0, 0, 1, 4])


class TestUnindentBlock(unittest.TestCase):

    def test_unindent_block_zero(self):
        """
        Test the removal of an indent, which should be detected as a zero space indent
        """
        strings = ["zero", "one", "  two", "\n", "", "    four"]
        s1 = "\n".join(strings)
        s2 = unindent_block(s1)
        for string1, string2 in zip(["zero", "one", "  two", "", "", "", "    four"], s2.splitlines(False)):
            self.assertEqual(string1, string2)

    def test_unindent_block_two(self):
        """
        Test the removal of an indent, which should be detected as a two space indent
        """
        strings = ["  two", "", "\n", "    four"]
        s1 = "\n".join(strings)
        s2 = unindent_block(s1)
        for string1, string2 in zip(["two", "", "", "", "  four"], s2.splitlines(False)):
            self.assertEqual(string1, string2)

    def test_unindent_block_raise(self):
        """
        Test the removal of an indent which contains tabs, which aren't accepted. So a ValueError should be raised
        """
        strings = ["  two", "\ttab", "\t", "    four"]
        s1 = "\n".join(strings)
        with self.assertRaises(ValueError):
            s2 = unindent_block(s1)


class TestStateCodeTransformer(unittest.TestCase):

    def test_state_code_transformer(self):
        """
        Test the conversion of code from a member function/variable of a State to code which can be evaluated in the
        StateAttributeAnalyser, so an object with the State as member '_state'.
        In short, replace 'self' by 'self._state'
        """
        strings = ["self.list1 = []", "list2 = []"]
        s1 = "\n".join(strings)
        tree1 = ast.parse(s1)
        tree2 = StateCodeTransformer().visit(deepcopy(tree1))
        s2 = astor.to_source(tree2)
        for string1, string2 in zip(["self._state.list1 = []", "list2 = []"], s2.splitlines(False)):
            self.assertEqual(string1, string2)


class TestStateCodeReverseTransformer(unittest.TestCase):

    def test_state_code_reverse_transformer(self):
        """
        Test the conversion of code as part of the StateAttributeAnalyser back to code from a State.
        In short, replace 'self._state' by 'self'
        """
        strings = ["self._state.list1 = []", "list2 = []", "self.list3 = []"]
        s1 = "\n".join(strings)
        tree1 = ast.parse(s1)
        tree2 = StateCodeReverseTransformer().visit(deepcopy(tree1))
        s2 = astor.to_source(tree2)
        for string1, string2 in zip(["self.list1 = []", "list2 = []", "self.list3 = []"], s2.splitlines(False)):
            self.assertEqual(string1, string2)


class TestStateAttributeAnalyser(unittest.TestCase):

    def test_state_attribute_analyser(self):
        """
        Test the code in the execute. As all member variables are defined in the constructor and the member function
        does exist, no Exceptions should be raised.
        """
        class TestState1(State):
            def __init__(self):
                super(TestState1, self).__init__(outcomes=["done"])
                self.string1 = "1"

            def execute(self, ud=None):
                self.get_string1()
                self.string1 = ""

            def get_string1(self):
                return self.string1

        state = TestState1()
        state.check_member_variables()

    def test_state_attribute_analyser_raise_attribute(self):
        """
        Test the code in the execute. As a new member variables is defined in the execute an Exception should be raised.
        """
        class TestState2(State):
            def __init__(self):
                super(TestState2, self).__init__(outcomes=["done"])
                self.string1 = "1"

            def execute(self, ud=None):
                self.get_string1()
                self.list1 = []
                self.string1 = ""

            def get_string1(self):
                return self.string1

        state = TestState2()
        with self.assertRaises(AssertionError):
            state.check_member_variables()

    def test_state_attribute_analyser_raise_callable(self):
        """
        Test the code in the execute. As the member function is not defined, it isn't callable an Exception should be
        raised.
        """
        class TestState3(State):
            def __init__(self):
                super(TestState3, self).__init__(outcomes=["done"])
                self.string1 = "1"
                self.get_string1 = ""

            def execute(self, ud=None):
                self.get_string1()
                self.string1 = ""

        state = TestState3()
        with self.assertRaises(AssertionError):
            state.check_member_variables()


if __name__ == "__main__":
    unittest.main(verbosity=2)
