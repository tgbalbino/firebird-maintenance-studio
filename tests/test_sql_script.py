import unittest

from firebird_studio.sql_script import is_script, split_script

SUPORTE = """/* Inclui ou atualiza o usuario tecnico SUPORTE.
   A senha fica somente no formato PBKDF2; com ; e ' dentro do comentario. */
SET TERM ^;

EXECUTE BLOCK AS
DECLARE VARIABLE V_ID INTEGER;
BEGIN
  SELECT FIRST 1 IDGRUPO FROM GRUPO INTO :V_ID;
  IF (V_ID IS NULL) THEN
  BEGIN
    INSERT INTO USUARIO (A, B) VALUES (1, 'v=1$pbkdf2$a;b==');
  END
  ELSE
    UPDATE USUARIO SET A = 2;
END^

SET TERM ;^
COMMIT;

QUIT;
"""


def kinds(text):
    return [item.kind for item in split_script(text)]


class SplitScriptTests(unittest.TestCase):
    def test_supporte_script_is_one_execute_block_between_commands(self):
        items = split_script(SUPORTE)
        self.assertEqual([item.kind for item in items], ["set_term", "sql", "set_term", "commit", "quit"])
        block = items[1].text
        self.assertTrue(block.startswith("EXECUTE BLOCK AS"))
        self.assertTrue(block.rstrip().endswith("END"))
        self.assertIn("SELECT FIRST 1 IDGRUPO FROM GRUPO INTO :V_ID;", block)
        self.assertIn("'v=1$pbkdf2$a;b=='", block)

    def test_plain_statements_split_on_semicolon(self):
        items = split_script("INSERT INTO T VALUES (1);\nUPDATE T SET A = 2;\nSELECT * FROM T")
        self.assertEqual([item.text for item in items], ["INSERT INTO T VALUES (1)", "UPDATE T SET A = 2", "SELECT * FROM T"])

    def test_semicolons_inside_strings_comments_and_identifiers_do_not_split(self):
        text = "SELECT 'a;b', \"x;y\" FROM T -- fim; de linha\n;SELECT /* ; */ 2 FROM D;"
        items = split_script(text)
        self.assertEqual(len(items), 2)
        self.assertIn("'a;b'", items[0].text)
        self.assertIn('"x;y"', items[0].text)

    def test_escaped_quote_does_not_end_the_string(self):
        items = split_script("SELECT 'O''Brien; Jr' FROM D; SELECT 2 FROM D;")
        self.assertEqual(len(items), 2)
        self.assertIn("'O''Brien; Jr'", items[0].text)

    def test_set_term_changes_the_terminator_for_what_follows(self):
        text = "SET TERM !! ;\nCREATE PROCEDURE P AS BEGIN EXIT; END!!\nSET TERM ; !!\nSELECT 1 FROM D;"
        self.assertEqual(kinds(text), ["set_term", "sql", "set_term", "sql"])

    def test_commit_and_rollback_are_transaction_controls(self):
        self.assertEqual(kinds("COMMIT; COMMIT WORK; ROLLBACK; commit retain;"), ["commit", "commit", "rollback", "commit"])

    def test_quit_stops_processing_the_rest(self):
        self.assertEqual(kinds("SELECT 1 FROM D; QUIT; DROP TABLE T;"), ["sql", "quit"])

    def test_isql_only_set_commands_are_ignored_but_dsql_ones_run(self):
        self.assertEqual(kinds("SET SQL DIALECT 3; SET NAMES UTF8; SET AUTODDL OFF; SET STATS ON;"), ["ignore"] * 4)
        self.assertEqual(kinds("SET TRANSACTION READ ONLY; SET GENERATOR G TO 5; SET STATISTICS INDEX I;"), ["sql"] * 3)

    def test_comment_only_pieces_are_dropped(self):
        self.assertEqual(split_script("-- nada\n; /* tambem */ ;"), [])

    def test_last_statement_without_terminator_is_kept(self):
        self.assertEqual([item.text for item in split_script("SELECT 1 FROM D")], ["SELECT 1 FROM D"])

    def test_is_script_only_for_multiple_items_or_isql_commands(self):
        self.assertFalse(is_script("SELECT 1 FROM D"))
        self.assertFalse(is_script("SELECT 1 FROM D;"))
        self.assertFalse(is_script("-- so um comentario\nSELECT 1 FROM D"))
        self.assertTrue(is_script("SELECT 1 FROM D; SELECT 2 FROM D;"))
        self.assertTrue(is_script("COMMIT;"))
        self.assertTrue(is_script(SUPORTE))

    def test_execute_block_is_not_a_script_by_itself_without_set_term_noise(self):
        block = "EXECUTE BLOCK AS BEGIN SELECT 1 FROM D INTO :X; END"
        # Without SET TERM the first ';' ends the statement, exactly like isql.
        self.assertTrue(is_script(block))


if __name__ == "__main__":
    unittest.main()
