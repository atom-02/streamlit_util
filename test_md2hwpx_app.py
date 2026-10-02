import html
import io
import re
import unittest
import zipfile
import xml.etree.ElementTree as ET

import md2hwpx_app


class LatexToHwpTests(unittest.TestCase):
    def test_displaystyle_is_consumed_as_layout_only(self):
        converted = md2hwpx_app.latex_to_hwp(
            r"\displaystyle\lim_{n\to\infty}\frac1n"
            r"\sum_{k=1}^{n}\sqrt{4+\frac{5k}{n}}"
        )

        self.assertNotIn("displaystyle", converted)
        self.assertEqual(
            converted,
            "lim _{n -> inf} {1} over {n} sum _{k=1}^{n}"
            " sqrt {4+ {5k} over {n}}",
        )

    def test_generated_hwpx_does_not_leak_displaystyle(self):
        source = (
            r"24. $\displaystyle\lim_{n\to\infty}\frac1n"
            r"\sum_{k=1}^{n}\sqrt{4+\frac{5k}{n}}$의 값은?"
            "\n\n"
            r"25. $\displaystyle\sum_{n=1}^{\infty}a_n$의 값은?"
        )
        data, _, _ = md2hwpx_app.convert_md_to_hwpx_bytes(source)

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            section = html.unescape(
                archive.read("Contents/section0.xml").decode("utf-8")
            )

        scripts = re.findall(r"<hp:script>(.*?)</hp:script>", section)
        self.assertTrue(scripts)
        self.assertTrue(all("displaystyle" not in script for script in scripts))
        self.assertTrue(any(script.startswith("lim _{n -> inf}") for script in scripts))
        self.assertIn("sum _{n=1}^{inf}a_{n}", scripts)

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
            "eqalign{a&=b # c&=d}",
        )

    def test_symbols_fonts_and_accents(self):
        converted = md2hwpx_app.latex_to_hwp(
            r"\emptyset,\forall x,\mathcal{F},\dots,\acute{x}"
        )
        for expected in ("EMPTYSET", "FORALL", "ℱ", "ldots", "acute {x}"):
            self.assertIn(expected, converted)

    def test_keywords_verified_in_hancom(self):
        # 한글에서 직접 렌더링해 확인한 대응. 이름을 그대로 넘기면 글자로 찍히던 명령들이다.
        cases = {
            r"\overline{AB} \perp \overrightarrow{CD}": "bar {AB} BOT vec {CD}",
            r"x \in \mathbb{R}": "x in ℝ",
            r"A \setminus B": "A - B",
            r"p \Rightarrow q \iff r": "p RARROW q ~ LRARROW ~ r",
            r"\langle a, b \rangle": "LEFT < a, b RIGHT >",
            r"\left\langle a \right\rangle": "LEFT < a RIGHT >",
            r"\lfloor x \rfloor": "LFLOOR x RFLOOR",
            r"a \not\in A": "a notin A",
            r"A \not\subset B": "A not subset B",
            r"\begin{Vmatrix}a&b\\c&d\end{Vmatrix}": "LEFT DLINE matrix{a&b # c&d} RIGHT DLINE",
            r"\begin{array}{cc}a&b\\c&d\end{array}": "matrix{a&b # c&d}",
            r"\boxed{x}": "box {x}",
        }
        for latex, expected in cases.items():
            with self.subTest(latex=latex):
                self.assertEqual(md2hwpx_app.latex_to_hwp(latex), expected)

    def test_spacing_commands_become_hancom_spaces(self):
        self.assertEqual(md2hwpx_app.latex_to_hwp(r"\int_0^1 x \, dx"), "int _{0}^{1} x ` dx")
        self.assertEqual(md2hwpx_app.latex_to_hwp(r"a \quad b \; c \! d"), "a ~~ b ~ c d")

    def test_roman_text_does_not_leak(self):
        # rm 은 닫는 중괄호 뒤까지 번지므로 it 로 닫아야 뒤따르는 변수가 기울임으로 남는다.
        self.assertEqual(md2hwpx_app.latex_to_hwp(r"\mathrm{P}(A \mid B)"), "{rm P it} (A ~ vert ~ B)")
        self.assertEqual(md2hwpx_app.latex_to_hwp(r"v = 3 \text{ m/s}"), 'v = 3 ~ {rm "m/s" it}')
        self.assertEqual(md2hwpx_app.latex_to_hwp(r"\mathbf{x}+y"), "{bold x} +y")

    def test_braces_and_stacked_relations(self):
        self.assertEqual(md2hwpx_app.latex_to_hwp(r"\underbrace{1+1}_{n}"), "UNDERBRACE {n} {1+1}")
        self.assertEqual(md2hwpx_app.latex_to_hwp(r"\overbrace{1+1}^{n}"), "OVERBRACE {1+1} {n}")
        self.assertEqual(md2hwpx_app.latex_to_hwp(r"A \xrightarrow{f} B"), "A REL rarrow {f} {} B")
        self.assertEqual(md2hwpx_app.latex_to_hwp(r"\sum_{\substack{i<n \\ j<m}} a"),
                         "sum _{pile{i<n # j<m}} a")

    def test_equation_box_matches_hancom_measurements(self):
        # 한글이 같은 스크립트에 대해 직접 저장한 (가로, 세로, 기준선 %) 값
        measured = {
            "x": (600, 975, 86), "{1} over {2}": (1025, 2250, 66), "sqrt {2}": (1745, 1123, 88),
            "pmatrix{1 & 0 # 0 & 1}": (2000, 2100, 67), "sum _{k=1}^{n} a_{k}": (2530, 2700, 63),
            "eqalign{a &= b + c # d &= e}": (3765, 2100, 41),
        }
        for script, (width, height, base_line) in measured.items():
            with self.subTest(script=script):
                estimate = md2hwpx_app.estimate_equation_box(script)
                self.assertAlmostEqual(estimate[0] / width, 1, delta=0.05)
                self.assertAlmostEqual(estimate[1] / height, 1, delta=0.05)
                self.assertAlmostEqual(estimate[2], base_line, delta=2)

    def test_implies_uses_hancom_right_arrow_keyword(self):
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"P\implies Q"),
            "P ~ RARROW ~ Q",
        )
        self.assertEqual(
            md2hwpx_app.latex_to_hwp(r"P\\implies Q"),
            "P ~ RARROW ~ Q",
        )

        data, _, _ = md2hwpx_app.convert_md_to_hwpx_bytes(
            r"$P\implies Q$"
        )
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            section = html.unescape(
                archive.read("Contents/section0.xml").decode("utf-8")
            )
        scripts = re.findall(r"<hp:script>(.*?)</hp:script>", section)
        self.assertEqual(scripts, ["P ~ RARROW ~ Q"])


class MarkdownParsingTests(unittest.TestCase):
    def test_choice_only_paragraph_does_not_create_blank_paragraph(self):
        blocks = md2hwpx_app.parse_markdown(
            "23. 문제의 값은? **[2점]**\n\n"
            "① $1$    ② $2$    ③ $3$    ④ $4$    ⑤ $5$"
        )
        transformed = md2hwpx_app.transform_blocks(
            blocks, split_choices=True, gap=True
        )

        self.assertEqual([block[0] for block in transformed], ["p", "p"])
        self.assertTrue(all(block[1] for block in transformed))
        self.assertEqual(
            md2hwpx_app._runs_leading_text(transformed[1][1]), "①"
        )
        self.assertFalse(any(block[0] == "p" and not block[1] for block in transformed))

    def test_question_and_choices_are_adjacent_in_generated_hwpx(self):
        source = (
            r"24. $\displaystyle\lim_{n\to\infty}\frac1n"
            r"\sum_{k=1}^{n}\sqrt{4+\frac{5k}{n}}$의 값은? **[3점]**"
            "\n\n"
            r"① $\frac{32}{15}$    ② $\frac{34}{15}$    ③ $\frac{36}{15}$"
            r"    ④ $\frac{38}{15}$    ⑤ $\frac{40}{15}$"
        )
        data, _, _ = md2hwpx_app.convert_md_to_hwpx_bytes(source)

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            root = ET.fromstring(archive.read("Contents/section0.xml"))
        ns = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}
        paragraphs = root.findall("hp:p", ns)[1:]

        self.assertEqual(len(paragraphs), 2)
        first_text = "".join(node.text or "" for node in paragraphs[0].findall(".//hp:t", ns))
        second_text = "".join(node.text or "" for node in paragraphs[1].findall(".//hp:t", ns))
        self.assertTrue(first_text.startswith("24."))
        self.assertTrue(second_text.startswith("①"))

    def test_two_blank_lines_are_inserted_between_question_groups(self):
        blocks = md2hwpx_app.parse_markdown(
            "1. 첫 번째 문제\n\n"
            "① 1  ② 2  ③ 3  ④ 4  ⑤ 5\n\n"
            "2. 두 번째 문제"
        )

        transformed = md2hwpx_app.transform_blocks(
            blocks, split_choices=True, gap=True
        )

        self.assertEqual(len(transformed), 5)
        self.assertEqual(
            transformed[2:4],
            [("p", [("t", "")]), ("p", [("t", "")])],
        )
        self.assertTrue(md2hwpx_app._is_question(transformed[4][1]))

    def _gaps(self, source):
        blocks, steps = md2hwpx_app._parse_markdown(source)
        transformed = md2hwpx_app.transform_blocks(blocks, split_choices=True, gap=True, steps=steps)
        return sum(1 for block in transformed if block == ("p", [("t", "")]))

    def test_solution_steps_are_not_spaced_like_questions(self):
        # 풀이 표시 문단 아래의 번호 줄은 풀이 단계다. 빈 줄로 떨어져 있어도 문항 간격을 넣지 않는다.
        self.assertEqual(self._gaps(
            "**27.** 문제의 값은?\n\n**간단 풀이:**\n1. 미분한다.\n2. 대입한다.\n\n3. 정리한다."), 0)
        # 풀이 제목 아래: 하위 제목(### 1단계)을 지나도 풀이 구간이 이어진다.
        self.assertEqual(self._gaps(
            "1. 문제\n\n# 문제 풀이\n\n### 1단계\n\n1. 첫 단계\n\n### 2단계\n\n2. 둘째 단계"), 0)
        # 표시가 없어도 빈 줄 없이 이어진 번호 줄은 번호 목록으로 본다.
        self.assertEqual(self._gaps("1. 문제\n\n설명\n1. 가\n2. 나\n3. 다"), 0)

    def test_questions_after_a_solution_section_are_spaced_again(self):
        source = ("1. 첫 문제\n\n**풀이:**\n1. 단계\n\n---\n\n2. 둘째 문제\n\n"
                  "# 해설\n\n1. 해설 단계\n\n# 다음 문제\n\n3. 셋째 문제")
        self.assertEqual(self._gaps(source), 2 * md2hwpx_app.QUESTION_GAP_LINES)
        self.assertEqual(self._gaps("**문제:**\n1. 문제 가\n\n2. 문제 나"), md2hwpx_app.QUESTION_GAP_LINES)

    def test_output_template_options_preserve_page_and_column_setup(self):
        expected_layouts = {
            "A4": ("59528", "1", False),
            "A4_2단": ("59528", "2", True),
            "B4_2단": ("72852", "2", True),
        }

        for template, (width, columns, has_divider) in expected_layouts.items():
            with self.subTest(template=template):
                data, _, _ = md2hwpx_app.convert_md_to_hwpx_bytes(
                    "1. 문제", template=template
                )
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    section = archive.read("Contents/section0.xml").decode("utf-8")

                self.assertIn(f'<hp:pagePr landscape="WIDELY" width="{width}"', section)
                self.assertIn(f'colCount="{columns}"', section)
                self.assertEqual('<hp:colLine type="SOLID"' in section, has_divider)

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

    def test_particles_attach_to_equations_but_words_keep_space(self):
        texts = lambda source: [value for kind, value in md2hwpx_app.parse_inline(source)
                                if kind != "eq"]
        self.assertEqual(texts("$x$ 의 값은 $y$ 그리고 $z$ 일 때 $w$ 이상"),
                         ["의 값은 ", " 그리고 ", "일 때 ", " 이상"])
        self.assertEqual(texts("$a$ and $b$, 또는 $c$ 이다."), [" and ", ", 또는 ", "이다."])

    def test_table_separator_and_bars_inside_math(self):
        rows = md2hwpx_app.parse_table(["| 식 | 값 |", "|:-:|--:|", "| $|x|$ | 2 |"])
        self.assertEqual(rows, [["식", "값"], ["$|x|$", "2"]])

    def test_code_fence_lines_are_plain_text(self):
        blocks = md2hwpx_app.parse_markdown("```\ntotal += k * k  # $x$\n```\n본문")
        self.assertEqual(blocks, [("p", [("t", "total += k * k  # $x$")]), ("p", [("t", "본문")])])

    def test_table_and_picture_fit_the_column_of_each_template(self):
        # 2단 양식에서 표·그림이 단 밖으로 넘치지 않고, 작은 그림은 억지로 늘리지 않는다.
        png = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
               + (4000).to_bytes(4, "big") + (100).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
        small = png.replace((4000).to_bytes(4, "big"), (200).to_bytes(4, "big"), 1)
        source = "| a | b |\n|---|---|\n| 1 | 2 |\n\n![큰](big.png)\n\n![작은](small.png)"
        for template, column in {"A4": 42520, "A4_2단": 24379, "B4_2단": 29623}.items():
            with self.subTest(template=template):
                data, _, _ = md2hwpx_app.convert_md_to_hwpx_bytes(
                    source, images={"big.png": png, "small.png": small}, template=template)
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    section = archive.read("Contents/section0.xml").decode("utf-8")
                widths = [int(w) for w in re.findall(r'<hp:sz width="(\d+)"', section)]
                self.assertEqual(len(widths), 3)
                self.assertLessEqual(max(widths), column)
                self.assertGreaterEqual(widths[0], column - 2)
                self.assertEqual(widths[2], 15000)      # 200px * 75
        self.assertEqual(md2hwpx_app._column_width, md2hwpx_app.A4_TEXT_WIDTH)

    def test_display_equation_is_centered(self):
        data, _, _ = md2hwpx_app.convert_md_to_hwpx_bytes("본문\n\n$$E=mc^2$$")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            section = archive.read("Contents/section0.xml").decode("utf-8")
            header = archive.read("Contents/header.xml").decode("utf-8")
        para = re.search(r'<hp:p id="\d+" paraPrIDRef="(\d+)"[^>]*><hp:run charPrIDRef="0"><hp:equation',
                         section).group(1)
        centered = re.search(rf'<hh:paraPr id="{para}".*?</hh:paraPr>', header, re.S).group(0)
        self.assertIn('<hh:align horizontal="CENTER"', centered)
        self.assertEqual(len(re.findall(r"<hh:paraPr id=", header)),
                         int(re.search(r'<hh:paraProperties itemCnt="(\d+)"', header).group(1)))
        self.assertEqual(md2hwpx_app._center_para, "0")

    def test_consecutive_exam_lines_remain_separate_paragraphs(self):
        blocks = md2hwpx_app.parse_markdown(
            "**문제**\n"
            "함수 $f(x)$에 대하여\n"
            "$P\\implies Q$일 때 값을 구하여라."
        )

        self.assertEqual([block[0] for block in blocks], ["p", "p", "p"])
        self.assertEqual(blocks[0][1], [("b", "문제")])
        self.assertIn(("eq", "f(x)"), blocks[1][1])
        self.assertIn(("eq", r"P\implies Q"), blocks[2][1])


if __name__ == "__main__":
    unittest.main()
