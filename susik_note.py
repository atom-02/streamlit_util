"""수식노트 — 수식이 포함된 마크다운을 편집·미리보기하고
Markdown / PDF / 한글(HWPX) 파일로 내보내는 도구.

streamlit_app.py 에서 render() 를 호출해 사용합니다.

마크다운/수식 파싱은 md2hwpx_app 의 파서(parse_markdown, parse_inline)를 그대로
재사용합니다 (인라인 `$...$`/`\\(...\\)`, 디스플레이 `$$...$$`/`\\[...\\]` 모두 인식).
PDF는 reportlab(Platypus)로 문단을 흘려 쓰고, 수식은 matplotlib의 mathtext로
그린 PNG를 문단 안에 인라인 이미지로 끼워 넣습니다. 한글(HWPX) 내보내기는
md2hwpx_app.convert_md_to_hwpx_bytes 를 그대로 호출합니다(변환 로직 중복 없음).
"""
import io
import itertools
import os
import re
import tempfile
from xml.sax.saxutils import escape as xml_escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import md2hwpx_app as hwpx
from qr_tool import FONTS  # qr_tool이 이미 등록해 둔 한글 폰트 이름(regular/bold) 재사용

SAMPLE_NOTE = """# 이차방정식의 해 (예시)

아래 내용은 예시입니다. 자유롭게 지우고 원하는 내용을 작성하세요.

이차방정식 $ax^2 + bx + c = 0$ ($a \\neq 0$) 의 해는 근의 공식으로 구할 수 있다.

$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$

## 예제

다음 방정식을 풀어라.

$$x^2 - 5x + 6 = 0$$

**풀이**

좌변을 인수분해하면

$$x^2 - 5x + 6 = (x-2)(x-3) = 0$$

따라서 $x = 2$ 또는 $x = 3$ 이다.

| 판별식 $D=b^2-4ac$ | 실근의 개수 |
| --- | --- |
| $D>0$ | 서로 다른 두 실근 |
| $D=0$ | 중근 (한 실근) |
| $D<0$ | 실근 없음 |
"""


# ===========================================================================
#  PDF: 수식 -> 이미지 (matplotlib mathtext)
# ===========================================================================
def _latex_to_img_tag(latex: str, display: bool, tmpdir: str, counter) -> str:
    """matplotlib mathtext로 수식을 PNG로 그려 reportlab Paragraph의 <img> 태그로 반환.

    <img>는 원본 PNG 픽셀 수가 아니라 지정한 width/height(pt)로 배치되므로,
    렌더링에 쓴 폰트 크기가 실제로 측정하는 물리적 크기(pt)를 명시해야
    본문 글자와 비례가 맞는다."""
    fontsize = 15 if display else 11
    try:
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.patch.set_alpha(0)
        t = fig.text(0, 0, f"${latex}$", fontsize=fontsize, color="#1a1a2e")
        fig.canvas.draw()
        bbox = t.get_window_extent()
        width = max(bbox.width, 1) / fig.dpi
        height = max(bbox.height, 1) / fig.dpi
        fig.set_size_inches(width, height)
        pad = 0.025
        idx = next(counter)
        path = os.path.join(tmpdir, f"eq_{idx}.png")
        fig.savefig(path, format="png", dpi=220, transparent=True, bbox_inches="tight", pad_inches=pad)
        plt.close(fig)
        w_pt = (width + 2 * pad) * 72
        h_pt = (height + 2 * pad) * 72
        return f'<img src="{path}" width="{w_pt:.1f}" height="{h_pt:.1f}" valign="middle"/>'
    except Exception:
        plt.close("all")
        raw = f"$${latex}$$" if display else f"${latex}$"
        return f'<font color="#b3261e">{xml_escape(raw)}</font>'


def _runs_markup(runs, tmpdir, counter) -> str:
    parts = []
    for kind, val in runs:
        if kind == "eq":
            parts.append(_latex_to_img_tag(val, False, tmpdir, counter))
        elif kind == "b":
            parts.append(f"<b>{xml_escape(val)}</b>")
        else:
            parts.append(xml_escape(val))
    return "".join(parts) or " "


def build_pdf_bytes(md_text: str) -> bytes:
    """마크다운(+수식) -> PDF bytes. md2hwpx_app.parse_markdown 으로 구조를 얻고,
    reportlab Platypus로 흘려 쓴다 (자동 줄바꿈·페이지 나눔)."""
    blocks = hwpx.parse_markdown(md_text)

    body_style = ParagraphStyle(
        "susik_body", fontName=FONTS["regular"], fontSize=10.5, leading=16,
        spaceAfter=8, alignment=TA_LEFT,
    )
    h_styles = {
        1: ParagraphStyle("susik_h1", fontName=FONTS["bold"], fontSize=17, leading=22,
                          spaceBefore=4, spaceAfter=10),
        2: ParagraphStyle("susik_h2", fontName=FONTS["bold"], fontSize=13.5, leading=18,
                          spaceBefore=10, spaceAfter=6),
        3: ParagraphStyle("susik_h3", fontName=FONTS["bold"], fontSize=11.5, leading=16,
                          spaceBefore=8, spaceAfter=6),
    }
    eq_style = ParagraphStyle(
        "susik_eq", fontName=FONTS["regular"], fontSize=11, leading=26,
        spaceBefore=6, spaceAfter=10, alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle("susik_cell", fontName=FONTS["regular"], fontSize=9.5, leading=13)
    cell_head_style = ParagraphStyle("susik_cell_h", fontName=FONTS["bold"], fontSize=9.5, leading=13)

    story = []
    with tempfile.TemporaryDirectory(prefix="susiknote_pdf_") as tmpdir:
        counter = itertools.count()
        for b in blocks:
            kind = b[0]
            if kind == "h":
                level, text = b[1], b[2]
                runs = hwpx.parse_inline(text)
                style = h_styles.get(level, h_styles[3])
                story.append(Paragraph(_runs_markup(runs, tmpdir, counter), style))
                if level == 1:
                    story.append(HRFlowable(width="100%", thickness=0.6,
                                            color=colors.HexColor("#dde1da"), spaceAfter=10))
            elif kind == "hr":
                story.append(HRFlowable(width="100%", thickness=0.5,
                                        color=colors.HexColor("#dde1da"), spaceBefore=6, spaceAfter=10))
            elif kind == "eq":
                story.append(Paragraph(_latex_to_img_tag(b[1], True, tmpdir, counter), eq_style))
            elif kind == "table":
                rows = b[1]
                data = []
                for r_idx, row in enumerate(rows):
                    style = cell_head_style if r_idx == 0 else cell_style
                    data.append([
                        Paragraph(_runs_markup(hwpx.parse_inline(c), tmpdir, counter), style)
                        for c in row
                    ])
                tbl = Table(data, hAlign="LEFT")
                tbl.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef0ec")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 10))
            elif kind == "p":
                story.append(Paragraph(_runs_markup(b[1], tmpdir, counter), body_style))
            elif kind == "img":
                alt = b[1] or b[2]
                story.append(Paragraph(f"[이미지: {xml_escape(alt)}]", body_style))

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
            title="수식노트",
        )
        doc.build(story or [Paragraph(" ", body_style)])
        return buf.getvalue()


# ===========================================================================
#  Streamlit UI  (streamlit_app.py 에서 render() 호출)
# ===========================================================================
def render():
    import streamlit as st

    st.subheader("🧮 수식노트")
    st.caption(
        "수식이 포함된 마크다운을 편집하고 실시간으로 미리 보며, "
        "Markdown · PDF · 한글(HWPX) 파일로 내보냅니다."
    )

    if "susik_text" not in st.session_state:
        st.session_state["susik_text"] = SAMPLE_NOTE
    if "susik_name" not in st.session_state:
        st.session_state["susik_name"] = "이차방정식-예제"
    if "susik_confirm_new" not in st.session_state:
        st.session_state["susik_confirm_new"] = False

    def handle_upload():
        f = st.session_state.get("susik_upload")
        if f is None:
            return
        text = f.getvalue().decode("utf-8", errors="replace")
        st.session_state["susik_text"] = text
        base = re.sub(r"\.(md|markdown|txt)$", "", f.name, flags=re.I)
        if base:
            st.session_state["susik_name"] = base

    def ask_new():
        st.session_state["susik_confirm_new"] = True

    def cancel_new():
        st.session_state["susik_confirm_new"] = False

    def confirm_new():
        st.session_state["susik_text"] = ""
        st.session_state["susik_name"] = "새-노트"
        st.session_state["susik_confirm_new"] = False

    top = st.columns([2, 1, 1])
    with top[0]:
        st.text_input("파일 이름", key="susik_name", label_visibility="collapsed",
                      placeholder="파일 이름")
    with top[1]:
        # st.file_uploader는 좁은 컬럼에서도 버튼 + 안내문(용량 제한 등)이 함께
        # 렌더링되어 최소 2줄을 차지한다. 툴바를 한 줄로 유지하기 위해 실제
        # 업로더는 popover 안에 넣고, 겉으로는 다른 버튼과 높이가 같은 단일 버튼만 노출한다.
        with st.popover("📂 열기", use_container_width=True):
            st.file_uploader("파일 열기", type=["md", "markdown", "txt"], key="susik_upload",
                             on_change=handle_upload, label_visibility="collapsed")
    with top[2]:
        st.button("새 노트", on_click=ask_new, use_container_width=True, key="susik_new_btn")

    if st.session_state["susik_confirm_new"]:
        c1, c2, c3 = st.columns([4, 1, 1])
        with c1:
            st.warning("지금 내용을 지우고 새 노트를 시작할까요? 저장하지 않은 내용은 사라집니다.")
        with c2:
            st.button("지우기", on_click=confirm_new, use_container_width=True, key="susik_new_yes")
        with c3:
            st.button("취소", on_click=cancel_new, use_container_width=True, key="susik_new_no")

    left, right = st.columns(2)
    with left:
        st.caption(f"MARKDOWN · {len(st.session_state['susik_text'])}자")
        st.text_area("마크다운 원문", key="susik_text", height=420, label_visibility="collapsed")
    with right:
        st.caption("미리보기")
        with st.container(border=True, height=420):
            st.markdown(st.session_state["susik_text"])

    base_name = (st.session_state["susik_name"] or "note").strip() or "note"

    dl1, dl2, dl3 = st.columns(3)
    with dl1:
        st.download_button(
            "Markdown 저장", data=st.session_state["susik_text"].encode("utf-8"),
            file_name=f"{base_name}.md", mime="text/markdown",
            use_container_width=True, key="susik_dl_md",
        )
    with dl2:
        if st.button("PDF로 내보내기", use_container_width=True, key="susik_pdf_btn"):
            with st.spinner("PDF 생성 중…"):
                try:
                    st.session_state["susik_pdf_bytes"] = build_pdf_bytes(st.session_state["susik_text"])
                    st.session_state["susik_pdf_error"] = None
                except Exception as e:  # noqa: BLE001
                    st.session_state["susik_pdf_bytes"] = None
                    st.session_state["susik_pdf_error"] = str(e)
    with dl3:
        if st.button("한글(HWPX)로 내보내기", use_container_width=True, key="susik_hwpx_btn"):
            try:
                data, _nb, _ne = hwpx.convert_md_to_hwpx_bytes(st.session_state["susik_text"])
                st.session_state["susik_hwpx_bytes"] = data
                st.session_state["susik_hwpx_error"] = None
            except Exception as e:  # noqa: BLE001
                st.session_state["susik_hwpx_bytes"] = None
                st.session_state["susik_hwpx_error"] = str(e)

    if st.session_state.get("susik_pdf_bytes"):
        st.download_button(
            "⬇ 생성된 PDF 다운로드", data=st.session_state["susik_pdf_bytes"],
            file_name=f"{base_name}.pdf", mime="application/pdf", key="susik_pdf_dl",
        )
    if st.session_state.get("susik_pdf_error"):
        st.error(f"PDF 생성 실패: {st.session_state['susik_pdf_error']}")

    if st.session_state.get("susik_hwpx_bytes"):
        st.download_button(
            "⬇ 생성된 한글(HWPX) 다운로드", data=st.session_state["susik_hwpx_bytes"],
            file_name=f"{base_name}.hwpx", mime="application/octet-stream", key="susik_hwpx_dl",
        )
    if st.session_state.get("susik_hwpx_error"):
        st.error(f"한글 문서 생성 실패: {st.session_state['susik_hwpx_error']}")

    st.caption(
        "인라인 수식은 `$…$` 또는 `\\(...\\)`, 블록 수식은 `$$…$$` 또는 `\\[...\\]` 로 씁니다. "
        "PDF는 matplotlib으로 수식을 그려 넣으므로 일부 고급 LaTeX 문법(`\\begin{align}` 등)은 "
        "지원하지 않을 수 있습니다 — 그런 경우 한글(HWPX) 내보내기를 사용하면 "
        "Markdown → HWPX 변환기와 같은 수식 변환기를 거쳐 더 넓은 범위를 지원합니다."
    )


if __name__ == "__main__":
    print("이 파일은 모듈입니다. 다음처럼 실행하세요:\n"
          "    pip install -r requirements.txt\n"
          "    streamlit run streamlit_app.py")
