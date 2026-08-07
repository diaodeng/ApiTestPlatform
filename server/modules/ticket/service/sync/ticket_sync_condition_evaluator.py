"""
工单群推送条件表达式引擎。

支持的语法:
- 字段引用: status, internal_priority, module_id 等 Ticket 模型字段名
- 比较运算: ==, !=, >, <, >=, <=
- 成员运算: in, not in
- 空值判断: is None, is not None
- 逻辑运算: and, or, not
- 函数: has(field) — 字段有值（非 None 且非空字符串）
- 字面量: 字符串(单/双引号)、数字、None、True/False
- 列表: [值1, 值2, ...]

示例:
  status in ['2. 1.5线处理', '3. 待产研处理'] and has(module_id)
  internal_priority in ['P0', 'P1'] and severity == 'S1'
  has(module_id) and has(merchant_name) and status not in ['5. 已关闭']
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# ============================================================
# Token 定义
# ============================================================

class TokenType:
    FIELD = "FIELD"
    STRING = "STRING"
    NUMBER = "NUMBER"
    NONE = "NONE"
    TRUE = "TRUE"
    FALSE = "FALSE"
    LPAREN = "LPAREN"  # (
    RPAREN = "RPAREN"  # )
    LBRACKET = "LBRACKET"  # [
    RBRACKET = "RBRACKET"  # ]
    COMMA = "COMMA"
    EQ = "EQ"  # ==
    NE = "NE"  # !=
    GE = "GE"  # >=
    LE = "LE"  # <=
    GT = "GT"  # >
    LT = "LT"  # <
    IN = "IN"
    NOT_IN = "NOT_IN"
    IS_NONE = "IS_NONE"
    IS_NOT_NONE = "IS_NOT_NONE"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    HAS = "HAS"  # has(field) 函数
    EOF = "EOF"


@dataclass
class Token:
    type: str
    value: Any = None
    pos: int = 0


# ============================================================
# 词法分析器
# ============================================================

class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def _peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else "\0"

    def _advance(self) -> str:
        ch = self._peek()
        self.pos += 1
        return ch

    def _skip_whitespace(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def _read_string(self, quote: str) -> Token:
        """读取引号内的字符串，支持转义"""
        start = self.pos
        result = []
        while self.pos < len(self.text):
            ch = self._advance()
            if ch == "\\":
                result.append(self._advance())
            elif ch == quote:
                return Token(TokenType.STRING, "".join(result), start)
            else:
                result.append(ch)
        raise SyntaxError(f"未闭合的字符串，起始位置 {start}")

    def _read_number(self, first: str) -> Token:
        start = self.pos - 1
        num_str = first
        while self.pos < len(self.text) and self.text[self.pos].isdigit():
            num_str += self._advance()
        if self._peek() == ".":
            num_str += self._advance()
            while self.pos < len(self.text) and self.text[self.pos].isdigit():
                num_str += self._advance()
        return Token(TokenType.NUMBER, float(num_str) if "." in num_str else int(num_str), start)

    def _read_identifier(self, first: str) -> Token:
        start = self.pos - 1
        ident = first
        while self.pos < len(self.text) and (self.text[self.pos].isalnum() or self.text[self.pos] == "_"):
            ident += self._advance()

        lower = ident.lower()
        if lower == "none":
            return Token(TokenType.NONE, None, start)
        if lower == "true":
            return Token(TokenType.TRUE, True, start)
        if lower == "false":
            return Token(TokenType.FALSE, False, start)
        if lower == "and":
            return Token(TokenType.AND, "and", start)
        if lower == "or":
            return Token(TokenType.OR, "or", start)
        if lower == "not":
            # 判断是 "not" 还是 "not in"
            saved_pos = self.pos
            self._skip_whitespace()
            if self.pos + 1 < len(self.text) and self.text[self.pos : self.pos + 2].lower() == "in":
                self.pos += 2
                return Token(TokenType.NOT_IN, "not in", start)
            self.pos = saved_pos
            return Token(TokenType.NOT, "not", start)
        if lower == "in":
            return Token(TokenType.IN, "in", start)
        if lower == "is":
            saved_pos = self.pos
            self._skip_whitespace()
            if self.pos < len(self.text) and self.text[self.pos : self.pos + 3].lower() == "not":
                self.pos += 3
                self._skip_whitespace()
                if self.pos < len(self.text) and self.text[self.pos : self.pos + 4].lower() == "none":
                    self.pos += 4
                    return Token(TokenType.IS_NOT_NONE, "is not None", start)
            else:
                if self.pos < len(self.text) and self.text[self.pos : self.pos + 4].lower() == "none":
                    self.pos += 4
                    return Token(TokenType.IS_NONE, "is None", start)
            self.pos = saved_pos
        if lower == "has":
            return Token(TokenType.HAS, "has", start)

        return Token(TokenType.FIELD, ident, start)

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.pos < len(self.text):
            self._skip_whitespace()
            if self.pos >= len(self.text):
                break

            ch = self._peek()
            if ch in ("'", '"'):
                self._advance()
                tokens.append(self._read_string(ch))
            elif ch.isdigit():
                self._advance()
                tokens.append(self._read_number(ch))
            elif ch.isalpha() or ch == "_":
                self._advance()
                tokens.append(self._read_identifier(ch))
            elif ch == "(":
                tokens.append(Token(TokenType.LPAREN, "(", self.pos))
                self._advance()
            elif ch == ")":
                tokens.append(Token(TokenType.RPAREN, ")", self.pos))
                self._advance()
            elif ch == "[":
                tokens.append(Token(TokenType.LBRACKET, "[", self.pos))
                self._advance()
            elif ch == "]":
                tokens.append(Token(TokenType.RBRACKET, "]", self.pos))
                self._advance()
            elif ch == ",":
                tokens.append(Token(TokenType.COMMA, ",", self.pos))
                self._advance()
            elif ch == "=":
                self._advance()
                if self._peek() == "=":
                    self._advance()
                    tokens.append(Token(TokenType.EQ, "==", self.pos - 2))
                else:
                    raise SyntaxError(f"意外的字符 '='，位置 {self.pos - 1}，你是想写 '==' 吗？")
            elif ch == "!":
                self._advance()
                if self._peek() == "=":
                    self._advance()
                    tokens.append(Token(TokenType.NE, "!=", self.pos - 2))
                else:
                    raise SyntaxError(f"意外的字符 '!'，位置 {self.pos - 1}，你是想写 '!=' 吗？")
            elif ch == ">":
                self._advance()
                if self._peek() == "=":
                    self._advance()
                    tokens.append(Token(TokenType.GE, ">=", self.pos - 2))
                else:
                    tokens.append(Token(TokenType.GT, ">", self.pos - 1))
            elif ch == "<":
                self._advance()
                if self._peek() == "=":
                    self._advance()
                    tokens.append(Token(TokenType.LE, "<=", self.pos - 2))
                else:
                    tokens.append(Token(TokenType.LT, "<", self.pos - 1))
            else:
                raise SyntaxError(f"意外的字符 '{ch}'，位置 {self.pos}")
        tokens.append(Token(TokenType.EOF))
        return tokens


# ============================================================
# AST 节点定义
# ============================================================

class ASTNode:
    """基类"""
    pass


@dataclass
class FieldNode(ASTNode):
    name: str


@dataclass
class LiteralNode(ASTNode):
    value: Any


@dataclass
class ListNode(ASTNode):
    items: list[ASTNode]


@dataclass
class BinaryOpNode(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode


@dataclass
class UnaryOpNode(ASTNode):
    op: str
    operand: ASTNode


@dataclass
class FunctionCallNode(ASTNode):
    name: str
    args: list[ASTNode]


# ============================================================
# 语法分析器 (Pratt Parser)
# ============================================================

class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _expect(self, token_type: str) -> Token:
        token = self._peek()
        if token.type != token_type:
            raise SyntaxError(f"期望 {token_type}，但找到 {token.type}({token.value})")
        return self._advance()

    def parse(self) -> ASTNode:
        node = self._parse_or()
        if self._peek().type != TokenType.EOF:
            token = self._peek()
            raise SyntaxError(f"意外的 token: {token.type}({token.value})")
        return node

    def _parse_or(self) -> ASTNode:
        left = self._parse_and()
        while self._peek().type == TokenType.OR:
            self._advance()
            right = self._parse_and()
            left = BinaryOpNode(op="or", left=left, right=right)
        return left

    def _parse_and(self) -> ASTNode:
        left = self._parse_not()
        while self._peek().type == TokenType.AND:
            self._advance()
            right = self._parse_not()
            left = BinaryOpNode(op="and", left=left, right=right)
        return left

    def _parse_not(self) -> ASTNode:
        if self._peek().type == TokenType.NOT:
            self._advance()
            operand = self._parse_comparison()
            return UnaryOpNode(op="not", operand=operand)
        return self._parse_comparison()

    def _parse_comparison(self) -> ASTNode:
        left = self._parse_primary()
        token = self._peek()
        if token.type in (
            TokenType.EQ, TokenType.NE, TokenType.GT, TokenType.LT,
            TokenType.GE, TokenType.LE, TokenType.IN, TokenType.NOT_IN,
            TokenType.IS_NONE, TokenType.IS_NOT_NONE,
        ):
            self._advance()
            if token.type in (TokenType.IS_NONE, TokenType.IS_NOT_NONE):
                right = LiteralNode(None)
            else:
                right = self._parse_primary()
            left = BinaryOpNode(op=token.type.lower().replace("_", " "), left=left, right=right)
        return left

    def _parse_primary(self) -> ASTNode:
        token = self._peek()

        if token.type == TokenType.FIELD:
            self._advance()
            return FieldNode(name=token.value)

        if token.type == TokenType.HAS:
            self._advance()
            self._expect(TokenType.LPAREN)
            arg = FieldNode(name=self._expect(TokenType.FIELD).value)
            self._expect(TokenType.RPAREN)
            return FunctionCallNode(name="has", args=[arg])

        if token.type == TokenType.STRING:
            self._advance()
            return LiteralNode(value=token.value)

        if token.type == TokenType.NUMBER:
            self._advance()
            return LiteralNode(value=token.value)

        if token.type == TokenType.NONE:
            self._advance()
            return LiteralNode(value=None)

        if token.type == TokenType.TRUE:
            self._advance()
            return LiteralNode(value=True)

        if token.type == TokenType.FALSE:
            self._advance()
            return LiteralNode(value=False)

        if token.type == TokenType.LPAREN:
            self._advance()
            node = self._parse_or()
            self._expect(TokenType.RPAREN)
            return node

        if token.type == TokenType.LBRACKET:
            return self._parse_list()

        raise SyntaxError(f"意外的 token: {token.type}({token.value})，位置 {token.pos}")

    def _parse_list(self) -> ListNode:
        self._expect(TokenType.LBRACKET)
        items: list[ASTNode] = []
        if self._peek().type != TokenType.RBRACKET:
            items.append(self._parse_primary())
            while self._peek().type == TokenType.COMMA:
                self._advance()
                items.append(self._parse_primary())
        self._expect(TokenType.RBRACKET)
        return ListNode(items=items)


# ============================================================
# 表达式求值器
# ============================================================

class Evaluator:
    def __init__(self, field_values: dict[str, Any]):
        self.fields = field_values

    def evaluate(self, node: ASTNode) -> bool:
        if isinstance(node, LiteralNode):
            return node.value
        if isinstance(node, FieldNode):
            return self.fields.get(node.name)
        if isinstance(node, ListNode):
            return [self.evaluate(item) for item in node.items]
        if isinstance(node, FunctionCallNode):
            return self._eval_function(node)
        if isinstance(node, BinaryOpNode):
            return self._eval_binary(node)
        if isinstance(node, UnaryOpNode):
            return self._eval_unary(node)
        raise ValueError(f"未知节点类型: {type(node).__name__}")

    def _eval_function(self, node: FunctionCallNode) -> bool:
        if node.name == "has":
            arg = node.args[0]
            if not isinstance(arg, FieldNode):
                raise SyntaxError("has() 函数的参数必须是字段名")
            value = self.fields.get(arg.name)
            if value is None:
                return False
            if isinstance(value, str) and value.strip() == "":
                return False
            return True
        raise SyntaxError(f"未知函数: {node.name}")

    def _eval_binary(self, node: BinaryOpNode) -> bool:
        left = self.evaluate(node.left)
        # 短路求值
        if node.op == "and":
            if not left:
                return False
            return bool(self.evaluate(node.right))
        if node.op == "or":
            if left:
                return True
            return bool(self.evaluate(node.right))

        right = self.evaluate(node.right)

        if node.op == "eq":
            return left == right
        if node.op == "ne":
            return left != right
        if node.op == "gt":
            return self._safe_compare(left, right, lambda a, b: a > b)
        if node.op == "lt":
            return self._safe_compare(left, right, lambda a, b: a < b)
        if node.op == "ge":
            return self._safe_compare(left, right, lambda a, b: a >= b)
        if node.op == "le":
            return self._safe_compare(left, right, lambda a, b: a <= b)
        if node.op == "in":
            if right is None:
                return False
            return left in right
        if node.op == "not in":
            if right is None:
                return True
            return left not in right
        if node.op == "is none":
            return left is None
        if node.op == "is not none":
            return left is not None

        raise SyntaxError(f"未知运算符: {node.op}")

    def _eval_unary(self, node: UnaryOpNode) -> bool:
        if node.op == "not":
            return not bool(self.evaluate(node.operand))
        raise SyntaxError(f"未知一元运算符: {node.op}")

    @staticmethod
    def _safe_compare(a: Any, b: Any, op: Callable[[Any, Any], bool]) -> bool:
        """安全比较，类型不兼容时返回 False"""
        try:
            return op(a, b)
        except TypeError:
            return False


# ============================================================
# 公共接口
# ============================================================

def evaluate_ticket_condition(condition: str, ticket_fields: dict[str, Any]) -> bool:
    """
    对一条工单执行条件表达式求值。

    :param condition: 条件表达式字符串，如 "status in ['3. 待产研处理'] and has(module_id)"
    :param ticket_fields: 工单字段名→值的字典
    :return: 是否满足条件
    :raises SyntaxError: 表达式语法错误
    :raises ValueError: 求值过程错误
    """
    if not condition or not condition.strip():
        return True  # 空条件视为不限制

    lexer = Lexer(condition.strip())
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    evaluator = Evaluator(ticket_fields)
    return bool(evaluator.evaluate(ast))
