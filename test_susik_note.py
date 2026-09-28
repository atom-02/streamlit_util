import unittest

import md2hwpx_app
import susik_note


class SusikNotePdfTests(unittest.TestCase):
    def test_sample_note_produces_a_valid_pdf(self):
        data = susik_note.build_pdf_bytes(susik_note.SAMPLE_NOTE)
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 1000)

    def test_empty_note_still_produces_a_pdf(self):
        data = susik_note.build_pdf_bytes("")
        self.assertTrue(data.startswith(b"%PDF"))

    def test_table_with_inline_math_does_not_raise(self):
        md = "| 판별식 $D=b^2-4ac$ | 실근의 개수 |\n| --- | --- |\n| $D>0$ | 서로 다른 두 실근 |\n"
        data = susik_note.build_pdf_bytes(md)
        self.assertTrue(data.startswith(b"%PDF"))

    def test_broken_latex_falls_back_to_visible_text_instead_of_raising(self):
        markup = susik_note._latex_to_img_tag(r"\notarealcommand{", display=False,
                                              tmpdir=".", counter=iter([0]))
        # 렌더링 실패 시에도 예외 없이 원문을 담은 태그를 돌려줘야 한다.
        self.assertIn("$", markup)

    def test_sample_note_also_converts_to_hwpx(self):
        # 수식노트와 Markdown → HWPX 변환기가 같은 파서를 공유하는지 확인.
        data, n_blocks, n_eq = md2hwpx_app.convert_md_to_hwpx_bytes(susik_note.SAMPLE_NOTE)
        self.assertTrue(data.startswith(b"PK"))  # HWPX는 zip 컨테이너
        self.assertGreater(n_blocks, 0)
        self.assertGreater(n_eq, 0)


if __name__ == "__main__":
    unittest.main()
