
"""Generate pytest tests for simple Python functions without executing source code."""

import ast
import itertools
import operator
import re

_UNSUPPORTED = object()

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

_COMPARE_OPERATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda left, right: left in right,
    ast.NotIn: lambda left, right: left not in right,
}

_SAFE_FUNCTIONS = {
    "abs": abs,
    "len": len,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "sorted": sorted,
    "all": all,
    "any": any,
}


def _safe_eval(node, environment):
    """Evaluate only explicitly supported AST expressions."""
    try:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            return environment.get(node.id, _UNSUPPORTED)

        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = [_safe_eval(item, environment) for item in node.elts]
            if any(value is _UNSUPPORTED for value in values):
                return _UNSUPPORTED

            if isinstance(node, ast.List):
                return values
            if isinstance(node, ast.Tuple):
                return tuple(values)
            return set(values)

        if isinstance(node, ast.Dict):
            keys = [_safe_eval(key, environment) for key in node.keys]
            values = [_safe_eval(value, environment) for value in node.values]

            if any(value is _UNSUPPORTED for value in keys + values):
                return _UNSUPPORTED

            return dict(zip(keys, values))

        if isinstance(node, ast.BinOp):
            left = _safe_eval(node.left, environment)
            right = _safe_eval(node.right, environment)

            if left is _UNSUPPORTED or right is _UNSUPPORTED:
                return _UNSUPPORTED

            operation = _BINARY_OPERATORS.get(type(node.op))

            # Limit exponentiation to avoid unexpectedly expensive calculations.
            if isinstance(node.op, ast.Pow):
                if (
                    not isinstance(right, (int, float))
                    or abs(right) > 10
                ):
                    return _UNSUPPORTED
                return left**right

            if operation is None:
                return _UNSUPPORTED

            return operation(left, right)

        if isinstance(node, ast.UnaryOp):
            value = _safe_eval(node.operand, environment)

            if value is _UNSUPPORTED:
                return _UNSUPPORTED

            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.Not):
                return not value

            return _UNSUPPORTED

        if isinstance(node, ast.Compare):
            left = _safe_eval(node.left, environment)

            if left is _UNSUPPORTED:
                return _UNSUPPORTED

            for operation_node, comparator in zip(
                node.ops, node.comparators
            ):
                right = _safe_eval(comparator, environment)
                operation = _COMPARE_OPERATORS.get(type(operation_node))

                if right is _UNSUPPORTED or operation is None:
                    return _UNSUPPORTED

                if not operation(left, right):
                    return False

                left = right

            return True

        if isinstance(node, ast.BoolOp):
            values = [_safe_eval(item, environment) for item in node.values]

            if any(value is _UNSUPPORTED for value in values):
                return _UNSUPPORTED

            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)

            return _UNSUPPORTED

        if isinstance(node, ast.IfExp):
            condition = _safe_eval(node.test, environment)

            if condition is _UNSUPPORTED:
                return _UNSUPPORTED

            branch = node.body if condition else node.orelse
            return _safe_eval(branch, environment)

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                return _UNSUPPORTED

            function = _SAFE_FUNCTIONS.get(node.func.id)

            if function is None or node.keywords:
                return _UNSUPPORTED

            arguments = [
                _safe_eval(argument, environment)
                for argument in node.args
            ]

            if any(value is _UNSUPPORTED for value in arguments):
                return _UNSUPPORTED

            return function(*arguments)

        if isinstance(node, ast.Subscript):
            value = _safe_eval(node.value, environment)
            index = _safe_eval(node.slice, environment)

            if value is _UNSUPPORTED or index is _UNSUPPORTED:
                return _UNSUPPORTED

            return value[index]

        return _UNSUPPORTED

    except (ArithmeticError, TypeError, ValueError, KeyError, IndexError):
        return _UNSUPPORTED


def _candidate_values(parameter_name):
    """Choose a small set of example inputs based on a parameter name."""
    name = parameter_name.lower()

    if any(word in name for word in ("text", "name", "word", "message", "title")):
        return ["hello", "", "Python"]

    if any(word in name for word in ("list", "arr", "items", "numbers", "values", "nums")):
        return [[1, 2, 3], [], [0, -1, 2]]

    if any(word in name for word in ("flag", "enabled", "active")):
        return [True, False]

    return [1, 2, 0, -1]


def _format_call(function_name, arguments):
    """Format a function call using Python literal representations."""
    rendered_arguments = ", ".join(repr(value) for value in arguments)
    return f"{function_name}({rendered_arguments})"


def generate_tests(
    source_code,
    module_name="your_module",
    max_cases_per_function=6,
):
    """
    Generate pytest tests for simple functions with one direct return.

    Returns a dictionary containing test_code, generated_count, functions,
    and warnings. Replace 'your_module' with the module containing the code.
    """
    if not re.fullmatch(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*", module_name):
        raise ValueError(
            "module_name must be a valid Python module path, "
            "such as 'calculator' or 'src.calculator'."
        )

    if max_cases_per_function < 1:
        raise ValueError("max_cases_per_function must be at least 1.")

    try:
        tree = ast.parse(source_code)
    except SyntaxError as error:
        return {
            "test_code": "",
            "generated_count": 0,
            "functions": [],
            "warnings": [
                f"Cannot generate tests because of a syntax error: {error.msg}"
            ],
        }

    generated_tests = []
    generated_functions = []
    warnings = []

    for function_node in tree.body:
        if not isinstance(function_node, (ast.FunctionDef,)):
            continue

        if function_node.name.startswith("_"):
            continue

        if function_node.decorator_list:
            warnings.append(
                f"Skipped '{function_node.name}': decorated functions "
                "are not supported by this first version."
            )
            continue

        if function_node.args.vararg or function_node.args.kwarg:
            warnings.append(
                f"Skipped '{function_node.name}': *args and **kwargs "
                "are not supported."
            )
            continue

        if function_node.args.kwonlyargs:
            warnings.append(
                f"Skipped '{function_node.name}': keyword-only arguments "
                "are not supported."
            )
            continue

        if function_node.args.posonlyargs:
            warnings.append(
                f"Skipped '{function_node.name}': positional-only "
                "arguments are not supported."
            )
            continue

        # Only support one direct return statement.
        # Nested returns and multi-statement control flow are not inferred.
        direct_returns = [
            statement
            for statement in function_node.body
            if isinstance(statement, ast.Return)
        ]

        if len(direct_returns) != 1 or direct_returns[0].value is None:
            warnings.append(
                f"Skipped '{function_node.name}': expected exactly one "
                "direct return expression."
            )
            continue

        return_expression = direct_returns[0].value
        parameters = [
            argument.arg for argument in function_node.args.args
        ]

        # Functions with no parameters can still be tested.
        candidate_sets = [
            _candidate_values(parameter) for parameter in parameters
        ]

        if candidate_sets:
            combinations = itertools.product(*candidate_sets)
        else:
            combinations = [()]

        function_tests = []

        for arguments in combinations:
            if len(function_tests) >= max_cases_per_function:
                break

            environment = dict(zip(parameters, arguments))
            expected = _safe_eval(return_expression, environment)

            if expected is _UNSUPPORTED:
                continue

            # Keep generated output to simple Python literal values.
            if not isinstance(expected, (type(None), bool, int, float, str, list, tuple, dict)):
                continue

            call = _format_call(function_node.name, arguments)
            test_name = (
                f"test_{function_node.name}_case_{len(function_tests) + 1}"
            )

            function_tests.append(
                f"def {test_name}():\n"
                f"    assert {call} == {expected!r}"
            )

        if function_tests:
            generated_tests.extend(function_tests)
            generated_functions.append(function_node.name)
        else:
            warnings.append(
                f"Skipped '{function_node.name}': no expected results could "
                "be safely calculated for the supported sample inputs."
            )

    if generated_tests:
        imports = (
            f"from {module_name} import "
            + ", ".join(generated_functions)
        )
        test_code = (
            '"""Generated tests. Review these before relying on them."""\n\n'
            f"{imports}\n\n\n"
            + "\n\n\n".join(generated_tests)
            + "\n"
        )
    else:
        test_code = (
            "# No tests were generated. See the warnings returned by "
            "generate_tests().\n"
        )

    return {
        "test_code": test_code,
        "generated_count": len(generated_tests),
        "functions": generated_functions,
        "warnings": warnings,
    }
