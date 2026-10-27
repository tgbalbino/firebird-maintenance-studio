import unittest
from decimal import Decimal

from firebird_studio.grid_edit import (
    RowChange,
    SimpleSelect,
    build_update,
    coerce_like,
    editable_key,
    parse_simple_select,
    sql_literal,
)


class ParseSimpleSelectTests(unittest.TestCase):
    def test_star_select(self):
        self.assertEqual(parse_simple_select("select * from tblcliente"), SimpleSelect("TBLCLIENTE", None))

    def test_columns_where_and_semicolon(self):
        parsed = parse_simple_select("SELECT codigo, nome FROM CLIENTE WHERE codigo > 3 ORDER BY nome;")
        self.assertEqual(parsed, SimpleSelect("CLIENTE", ("CODIGO", "NOME")))

    def test_first_and_quoted_table(self):
        parsed = parse_simple_select('select first 10 t.codigo from "Cliente Especial" where 1=1')
        self.assertEqual(parsed, SimpleSelect("Cliente Especial", ("CODIGO",)))

    def test_comments_are_ignored(self):
        self.assertIsNotNone(parse_simple_select("-- nota\nselect * from a /* x */"))

    def test_rejects_non_simple_statements(self):
        rejected = (
            "select * from a join b on a.id = b.id",
            "select * from a, b",
            "select count(*) from a",
            "select codigo as c from a",
            "select upper(nome) from a",
            "select distinct nome from a",
            "select nome from a group by nome",
            "select * from a union select * from b",
            "select * from a where id in (select id from b)",
            "select * from a; delete from a",
            "update a set x = 1",
            "select 1 from rdb$database where 'a;b' = 'a;b'",
        )
        for sql in rejected:
            with self.subTest(sql=sql):
                self.assertIsNone(parse_simple_select(sql))

    def test_semicolon_inside_string_literal_is_allowed(self):
        self.assertIsNotNone(parse_simple_select("select * from a where nome = 'x;y'"))


class LiteralTests(unittest.TestCase):
    def test_typed_literals(self):
        self.assertEqual(sql_literal("12", 3), "12")
        self.assertEqual(sql_literal("1.5", Decimal("2.0")), "1.5")
        self.assertEqual(sql_literal("abc", "x"), "'abc'")
        self.assertEqual(sql_literal("O'Brien", "x"), "'O''Brien'")
        self.assertEqual(sql_literal("", 3), "NULL")
        self.assertEqual(sql_literal("", ""), "''")
        self.assertEqual(sql_literal("true", True), "TRUE")

    def test_non_numeric_text_for_number_column_is_quoted_not_injected(self):
        self.assertEqual(sql_literal("1; drop table a", 3), "'1; drop table a'")


class BuildUpdateTests(unittest.TestCase):
    columns = ["CODIGO", "NOME", "LIMITE"]

    def test_update_uses_original_key_and_only_changed_columns(self):
        change = RowChange((1, "Ana", Decimal("10.5")), ("2", "Ana", "20"))
        sql = build_update("CLIENTE", self.columns, ["CODIGO"], change)
        self.assertEqual(sql, 'UPDATE "CLIENTE" SET "CODIGO" = 2, "LIMITE" = 20 WHERE "CODIGO" = 1')

    def test_unchanged_row_gives_nothing(self):
        self.assertIsNone(build_update("CLIENTE", self.columns, ["CODIGO"], RowChange((1, "Ana", None), ("1", "Ana", ""))))

    def test_composite_key_and_null_key_value(self):
        change = RowChange((1, None, 5), ("1", "novo", "5"))
        sql = build_update("T", ["A", "B", "C"], ["a", "B"], change)
        self.assertEqual(sql, 'UPDATE "T" SET "B" = \'novo\' WHERE "A" = 1 AND "B" IS NULL')

    def test_clearing_a_value_sets_null(self):
        change = RowChange((1, "Ana", 3), ("1", "", "3"))
        self.assertEqual(build_update("T", ["ID", "NOME", "X"], ["ID"], change), 'UPDATE "T" SET "NOME" = NULL WHERE "ID" = 1')


class EditableKeyTests(unittest.TestCase):
    def test_requires_select_and_full_key_in_result(self):
        select = SimpleSelect("T", None)
        self.assertEqual(editable_key(select, ["id", "nome"], ("ID",)), ["ID"])
        self.assertIsNone(editable_key(select, ["nome"], ("ID",)))
        self.assertIsNone(editable_key(select, ["id"], ()))
        self.assertIsNone(editable_key(None, ["id"], ("ID",)))


class CoerceTests(unittest.TestCase):
    def test_follows_original_type(self):
        self.assertEqual(coerce_like(1, "7"), 7)
        self.assertEqual(coerce_like(Decimal("1.0"), "2.5"), Decimal("2.5"))
        self.assertEqual(coerce_like(1.5, "2"), 2.0)
        self.assertEqual(coerce_like("a", "b"), "b")
        self.assertIsNone(coerce_like(1, " "))
        self.assertEqual(coerce_like(1, "abc"), "abc")


if __name__ == "__main__":
    unittest.main()
