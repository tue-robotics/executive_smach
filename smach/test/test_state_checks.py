import ast
import astor
from copy import deepcopy
from smach.state_checks import add_spaces, del_spaces, num_spaces, unindent_block, StateCodeTransformer,\
    StateCodeReverseTransformer
from smach.state import State
import unittest


class TestAddSpaces(unittest.TestCase):

    def test_single_line(self):
        s1 = "line1"
        s2 = add_spaces(s1, 4)
        self.assertEqual("    " + s1, s2)

    def test_single_line_add_zero(self):
        s1 = "line1"
        s2 = add_spaces(s1, 0)
        self.assertEqual(s1, s2)

    def test_multi_line(self):
        strings = ["line1", "line2", "line3"]
        s1 = "\n".join(strings)
        s2 = add_spaces(s1, 4)
        for string1, string2 in zip(strings, s2.splitlines(False)):
            self.assertEqual("    " + string1, string2)

    def test_multi_line_add_zero(self):
        strings = ["line1", "line2", "line3"]
        s1 = "\n".join(strings)
        s2 = add_spaces(s1, 0)
        for string1, string2 in zip(strings, s2.splitlines(False)):
            self.assertEqual(repr(string1), repr(string2))


class TestDelSpaces(unittest.TestCase):

    def test_del_spaces(self):
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
        with self.assertRaises(ValueError):
            del_spaces(s1, 5)

    def test_del_spaces_single_tab(self):
        s1 = "\t"
        s2 = del_spaces(s1, 0)
        self.assertEqual(s1, s2)
        s3 = del_spaces(s1, 1)
        self.assertEqual(s3, s1)
        s4 = del_spaces(s1, 2)
        self.assertEqual(s4, s1)

    def test_del_spaces_multi_tab(self):
        s1 = "\t\t"
        s2 = del_spaces(s1, 0)
        self.assertEqual(s1, s2)
        s3 = del_spaces(s1, 1)
        self.assertEqual(s3, s1)
        s4 = del_spaces(s1, 2)
        self.assertEqual(s4, s1)


class TestNumSpaces(unittest.TestCase):

    def test_num_spaces(self):
        strings = ["l1", " l2", "  l3", "\n", "\t", "    "]
        s1 = "\n".join(strings)
        spaces = num_spaces(s1)
        self.assertEqual(spaces, [0, 1, 2, 0, 0, 1, 4])


class TestUnindentBlock(unittest.TestCase):

    def test_unindent_block_zero(self):
        strings = ["zero", "one", "  two", "\n", "", "    four"]
        s1 = "\n".join(strings)
        s2 = unindent_block(s1)
        for string1, string2 in zip(["zero", "one", "  two", "", "", "", "    four"], s2.splitlines(False)):
            self.assertEqual(string1, string2)

    def test_unindent_block_two(self):
        strings = ["  two", "", "\n", "    four"]
        s1 = "\n".join(strings)
        s2 = unindent_block(s1)
        for string1, string2 in zip(["two", "", "", "", "  four"], s2.splitlines(False)):
            self.assertEqual(string1, string2)


class TestStateCodeTransformer(unittest.TestCase):

    def test_state_code_transformer(self):
        strings = ["self.list1 = []", "list2 = []"]
        s1 = "\n".join(strings)
        tree1 = ast.parse(s1)
        tree2 = StateCodeTransformer().visit(deepcopy(tree1))
        s2 = astor.to_source(tree2)
        for string1, string2 in zip(["self._state.list1 = []", "list2 = []"], s2.splitlines(False)):
            self.assertEqual(string1, string2)


class TestStateCodeReverseTransformer(unittest.TestCase):

    def test_state_code_reverse_transformer(self):
        strings = ["self._state.list1 = []", "list2 = []", "self.list3 = []"]
        s1 = "\n".join(strings)
        tree1 = ast.parse(s1)
        tree2 = StateCodeReverseTransformer().visit(deepcopy(tree1))
        s2 = astor.to_source(tree2)
        for string1, string2 in zip(["self.list1 = []", "list2 = []", "self.list3 = []"], s2.splitlines(False)):
            self.assertEqual(string1, string2)


class TestStateAttributeAnalyser(unittest.TestCase):

    def test_state_attribute_analyser(self):
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
