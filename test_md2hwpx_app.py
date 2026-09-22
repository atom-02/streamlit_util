import html
import io
import re
import unittest
import zipfile

import md2hwpx_app


class LatexToHwpTests(unittest.TestCase):
    def test_literal_set_braces_are_visible(self):
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"A=\{1,2,3\}"),
            "A= LEFT { 1,~2,~3 RIGHT }",
        )

    def test_left_right_set_braces_are_visible(self):
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"B=\left\{x\mid x>0\right\}"),
            "B= LEFT { x ~ vert ~ x>0 RIGHT }",
        )

    def test_nested_set_braces(self):
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"P=\{\{1\},\{2\}\}"),
            "P= LEFT { LEFT { 1 RIGHT } ,~ LEFT { 2 RIGHT } RIGHT }",
        )

    def test_commas_outside_sets_are_unchanged(self):
        self.assertEqual(md2hwpx_app.latex_to_hwp(r"P=(1,2)"), "P=(1,2)")

    def test_grouping_braces_still_group_fraction(self):
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"\frac{1}{2}"),
            "{1} over {2}",
        )

    def test_generated_hwpx_contains_visible_set_script(self):
        data, _, _ = md2hwpx_app.convert_md_to_hwpx_bytes(
            r"집합 $A=\{1,2,3\}$에서 $n(A)=3$이다."
        )
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.namelist()[0], "mimetype")
            section = html.unescape(
                archive.read("Contents/section0.xml").decode("utf-8")
            )
        scripts = re.findall(r"<hp:script>(.*?)</hp:script>", section)
        self.assertIn("A= LEFT { 1,~2,~3 RIGHT }", scripts)

    def test_nth_root_uses_hancom_of_syntax(self):
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"\sqrt[3]{x}"),
            "root {3} of {x}",
        )

    def test_matrix_wrappers_are_preserved(self):
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"\begin{pmatrix}a&b\\c&d\end{pmatrix}"),
            "pmatrix{a&b # c&d}",
        )
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"\begin{bmatrix}a&b\\c&d\end{bmatrix}"),
            "bmatrix{a&b # c&d}",
        )
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"\begin{vmatrix}a&b\\c&d\end{vmatrix}"),
            "dmatrix{a&b # c&d}",
        )

    def test_scalable_delimiters_and_aligned(self):
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"\left(\sum_{k=1}^{n}k\right)"),
            "LEFT ( sum _{k=1}^{n}k RIGHT )",
        )
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"\begin{aligned}a&=b\\c&=d\end{aligned}"),
            "eqalign{a=b # c=d}",
        )

    def test_symbols_fonts_and_accents(self):
        converted = md2hwpx_app.latex_to_hwp(
            r"\emptyset,\forall x,\mathcal{F},\dots,\acute{x}"
        )
        for expected in ("EMPTYSET", "FORALL", "it {F}", "ldots", "acute {x}"):
            self.assertIn(expected, converted)


class MarkdownParsingTests(unittest.TestCase):
    def test_ai_style_bracket_display_math(self):
        blocks = md2hwpx_app.parse_markdown(
            "무한급수\n[ \\sum\\_{n=1}^{\\infty}\\frac1{n(n+2)} ]\n의 합은?"
        )

        self.assertEqual(blocks[1], ("eq", r"\sum_{n=1}^{\infty}\frac1{n(n+2)}"))
        body = md2hwpx_app.build_body(blocks)
        self.assertIn("<hp:script>sum _{n=1}^{inf} {1} over {n(n+2)}</hp:script>", body)
        self.assertNotIn(r"\sum\_", body)

    def test_parenthesized_latex_choices_become_equations(self):
        source = r"① (\frac12)　② (\frac23)　③ (\frac34)　④ (\frac56)　⑤ (1)"
        runs = md2hwpx_app.parse_inline(source)

        self.assertEqual([value for kind, value in runs if kind == "eq"],
                         [r"\frac12", r"\frac23", r"\frac34", r"\frac56"])
        self.assertIn(("t", "　⑤ (1)"), runs)
        body = md2hwpx_app.build_body([("p", runs)])
        self.assertEqual(body.count("<hp:equation"), 4)
        self.assertNotIn(r"(\frac", body)

    def test_bold_text_can_contain_inline_math(self):
        source = "**원래의 함수 $f(x)$ 곡선 위에도 있는**"

        self.assertEqual(
            md2hwpx_app.parse_inline(source),
            [("b", "원래의 함수 "), ("eq", "f(x)"), ("b", " 곡선 위에도 있는")],
        )

        body = md2hwpx_app.build_body(md2hwpx_app.parse_markdown(source))
        self.assertIn('<hp:run charPrIDRef="9"><hp:t>원래의 함수 </hp:t></hp:run>', body)
        self.assertIn("<hp:script>f(x)</hp:script>", body)
        self.assertIn('<hp:run charPrIDRef="9"><hp:t> 곡선 위에도 있는</hp:t></hp:run>', body)
        self.assertNotIn("$f(x)$", body)

    def test_heading_inline_math_becomes_equation(self):
        blocks = md2hwpx_app.parse_markdown(
            r"### 1. 가로선 $y=t$ 와의 만남"
        )
        body = md2hwpx_app.build_body(blocks)

        self.assertIn('<hp:run charPrIDRef="7"><hp:t>1. 가로선 </hp:t></hp:run>', body)
        self.assertIn("<hp:script>y=t</hp:script>", body)
        self.assertNotIn("$y=t$", body)

    def test_heading_parenthesized_math_becomes_equation(self):
        blocks = md2hwpx_app.parse_markdown(
            r"## 역함수 관계 \(f(g(t))=t\)"
        )
        body = md2hwpx_app.build_body(blocks)

        self.assertIn('<hp:run charPrIDRef="8"><hp:t>역함수 관계 </hp:t></hp:run>', body)
        self.assertIn("<hp:script>f(g(t))=t</hp:script>", body)
        self.assertNotIn(r"\(f(g(t))=t\)", body)

    def test_code_spans_protect_literal_math_delimiters(self):
        self.assertEqual(
            md2hwpx_app.parse_inline("기호 `$`와 `$$`, 수식 $x+1$, **굵게**"),
            [("t", "기호 "), ("t", "$"), ("t", "와 "), ("t", "$$"),
             ("t", ", 수식 "), ("eq", "x+1"), ("t", ", "), ("b", "굵게")],
        )

    def test_list_items_remain_separate_paragraphs(self):
        blocks = md2hwpx_app.parse_markdown("- 첫째\n- 둘째\n\n일반 문단")
        self.assertEqual([block[0] for block in blocks], ["p", "p", "p"])
        self.assertEqual(blocks[0][1], [("t", "- 첫째")])
        self.assertEqual(blocks[1][1], [("t", "- 둘째")])


if __name__ == "__main__":
    unittest.main()
