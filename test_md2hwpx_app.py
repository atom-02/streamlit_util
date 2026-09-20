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


if __name__ == "__main__":
    unittest.main()
