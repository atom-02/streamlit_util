"""수능·모의평가 수학 PDF -> 문항별 이미지 캡처 -> 2단 HWPX.

streamlit_app.py 에서 render() 를 호출해 사용합니다.
문항 번호("1. ", "23. " ...)를 PDF 텍스트 레이어의 위치로 찾아 같은 단(column) 안에서 다음 문항
직전까지를 잘라내고, 그 그림들을 2단 HWPX(용지 B4/A4)에 차례로 넣습니다. 글자·수식은 편집할 수
없는 대신 원본 모양이 그대로 유지됩니다. 모든 처리는 메모리에서만 하고 디스크에 쓰지 않습니다.
HWPX 생성은 md2hwpx_app 의 그림 삽입/패키징 코드를 재사용합니다.
"""
import io
import os
import re
import zipfile

import pymupdf
from PIL import Image

import md2hwpx_app as m

MM = 7200 / 25.4  # HWPUNIT per mm
PAPERS = {"B4 (수능 시험지 규격)": (257, 364), "A4": (210, 297)}
MARGIN_LR_MM, MARGIN_TB_MM, HEADER_FOOTER_MM = 15, 15, 8
COL_COUNT, COL_GAP_MM = 2, 6

# --- 자르기 설정: 평가원 수학 영역(A3 2단) 기준을 쪽 크기 비율로 표현 ---------------
CROP_DPI = 300
Q_TOP_MARGIN_PT = 12          # 문항 번호 블록 위로 이만큼 더 포함 (윗첨자 보호)
CONTENT_BOTTOM_FRAC = 0.905   # 이 아래는 쪽번호/저작권
COL_X_FRAC = {"L": (0.093, 0.490), "R": (0.511, 0.917)}  # 가운데 세로 구분선을 피한 각 단의 x 범위
PAD_PT = 5
GAP_CUT_PT = 50               # 이만큼 이상 비어 있는 세로 공백이 나오면 그 앞에서 자름 ("확인 사항" 상자 제외)

Q_RE = re.compile(r"^\s*(\d{1,2})\.\s")


# ===========================================================================
# 1. PDF에서 문항 찾기 / 자르기
# ===========================================================================
def find_questions(doc):
    """[(page_idx, col, qnum, y0), ...] 문서 순서(쪽 -> 왼단 -> 오른단 -> 위에서 아래)."""
    out = []
    for pi, page in enumerate(doc):
        W = page.rect.width
        hits = []
        for b in page.get_text("blocks"):
            mm = Q_RE.match(b[4])
            if mm:
                col = "L" if b[0] < W / 2 else "R"
                hits.append((col, b[1], int(mm.group(1))))
        hits.sort()
        out.extend((pi, col, q, y0) for col, y0, q in hits)
    return out


def header_rule_y(page):
    """제목 아래 가로 괘선의 y (pt). 없으면 0."""
    ys = [0.0]
    for d in page.get_drawings():
        r = d.get("rect")
        if r is not None and r.width > page.rect.width * 0.45 and r.height < 3 and r.y0 < page.rect.height * 0.25:
            ys.append(r.y1)
    return max(ys)


def crop_question(page, col, y_top, y_bottom):
    """한 문항 영역을 잘라 PNG bytes 로. 내용이 없으면 None."""
    W = page.rect.width
    x0, x1 = (W * f for f in COL_X_FRAC[col])
    clip = pymupdf.Rect(x0, max(y_top, 0), x1, y_bottom)
    pix = page.get_pixmap(dpi=CROP_DPI, clip=clip, colorspace=pymupdf.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    bw = img.point(lambda v: 255 if v < 200 else 0)
    bbox = bw.getbbox()
    if bbox is None:
        return None
    px_per_pt = CROP_DPI / 72
    pad = int(PAD_PT * px_per_pt)
    _, t, _, b = bbox

    row_has_ink = bw.crop((0, t, img.width, b)).getprojection()[1]
    gap_px = int(GAP_CUT_PT * px_per_pt)
    run = 0
    for i, ink in enumerate(row_has_ink):
        run = 0 if ink else run + 1
        if run >= gap_px:
            b = t + i - run + 1
            break

    t, b = max(t - pad, 0), min(b + pad, img.height)
    # 가로는 단 전체 폭을 유지(문항마다 배율이 달라지지 않도록), 세로만 잘라냄
    out = io.BytesIO()
    img.crop((0, t, img.width, b)).save(out, format="PNG", optimize=True)
    return out.getvalue()


TITLE_PAGE_RULE_FRAC = 0.16   # 괘선이 이보다 아래면 큰 제목("수학 영역(확률과 통계)")이 있는 구간 첫 쪽


def capture_questions(pdf_bytes):
    """PDF bytes -> [(qnum, png_bytes, is_section_start), ...]
    구간(선택과목) 시작 = 큰 제목이 있는 쪽의 첫 문항, 또는 문항 번호가 앞보다 작아진 곳."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    qs = find_questions(doc)
    result = []
    rule_y = {}
    prev_q = None
    for i, (pi, col, q, y0) in enumerate(qs):
        page = doc[pi]
        if pi not in rule_y:
            rule_y[pi] = header_rule_y(page)
        y_next = page.rect.height * CONTENT_BOTTOM_FRAC
        for pj, cj, qj, yj in qs[i + 1:]:
            if pj != pi:
                break
            if cj == col:
                y_next = yj - Q_TOP_MARGIN_PT
                break
        y_top = max(y0 - Q_TOP_MARGIN_PT, rule_y[pi] + 2)
        png = crop_question(page, col, y_top, y_next)
        if png is None:
            continue
        first_on_page = (i == 0 or qs[i - 1][0] != pi)
        title_page = rule_y[pi] > page.rect.height * TITLE_PAGE_RULE_FRAC
        section_start = (prev_q is None) or (first_on_page and title_page) or (q < prev_q)
        result.append((q, png, section_start))
        prev_q = q
    return result


# ===========================================================================
# 2. 문서 구성 (제목 배치) + HWPX 조립
# ===========================================================================
def plan_document(questions, section_names, add_type_headings, short_answer_from):
    """[(kind, value)] : ("h1", 제목) / ("h2", 소제목) / ("img", (파일명, png))"""
    items = []
    sec_idx = -1
    prev_q = None
    for n, (q, png, section_start) in enumerate(questions, 1):
        if section_start:
            sec_idx += 1
            name = section_names[sec_idx] if sec_idx < len(section_names) else f"선택과목 {sec_idx}"
            items.append(("h1", f"수학 영역 ({name})"))
            if add_type_headings:
                items.append(("h2", "5지선다형"))
        if add_type_headings and q == short_answer_from[min(sec_idx, 1)] and prev_q is not None and prev_q < q:
            items.append(("h2", "단답형"))
        items.append(("img", (f"q{n:02d}_{q}.png", png)))
        prev_q = q
    return items


def _patch_section(sec, page_mm, divider):
    """구역 설정(첫 문단)의 용지·여백·단 설정을 덮어쓴다. 첫 문단에만 있으므로 count=1 로 충분."""
    w, h = page_mm
    sec = re.sub(r'<hp:pagePr [^>]*>',
                 f'<hp:pagePr landscape="WIDELY" width="{round(w*MM)}" height="{round(h*MM)}" gutterType="LEFT_ONLY">',
                 sec, count=1)
    sec = re.sub(r'<hp:margin [^>]*/>',
                 f'<hp:margin header="{round(HEADER_FOOTER_MM*MM)}" footer="{round(HEADER_FOOTER_MM*MM)}" gutter="0" '
                 f'left="{round(MARGIN_LR_MM*MM)}" right="{round(MARGIN_LR_MM*MM)}" '
                 f'top="{round(MARGIN_TB_MM*MM)}" bottom="{round(MARGIN_TB_MM*MM)}"/>',
                 sec, count=1)
    col_line = '<hp:colLine type="SOLID" width="0.12 mm" color="#000000"/>' if divider else ""
    sec = re.sub(r'<hp:colPr [^>]*/>',
                 f'<hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="{COL_COUNT}" sameSz="1" '
                 f'sameGap="{round(COL_GAP_MM*MM)}">{col_line}</hp:colPr>',
                 sec, count=1)
    return sec


def build_hwpx(items, paper_label, gap_lines, divider):
    """items(plan_document 결과) -> HWPX bytes."""
    page_mm = PAPERS[paper_label]
    col_w = (page_mm[0] - 2 * MARGIN_LR_MM - COL_GAP_MM * (COL_COUNT - 1)) / COL_COUNT
    img_w = col_w - 1

    m.reset_images()
    body = []
    first_h1 = True
    for kind, val in items:
        if kind == "h1":
            p = m.paragraph([m.text_run(val, "5")])
            if not first_h1:
                p = p.replace('pageBreak="0"', 'pageBreak="1"', 1)  # 선택과목마다 새 쪽
            first_h1 = False
            body.append(p)
        elif kind == "h2":
            body.append(m.paragraph([m.text_run(val, "8")]))
        else:
            name, png = val
            body.append(m.paragraph([m.picture_xml(png, name, max_width_mm=img_w)]))
            body.extend(m.paragraph([m.text_run("")]) for _ in range(gap_lines))

    return m.package_hwpx("".join(body), section_patch=lambda sec: _patch_section(sec, page_mm, divider))


def crops_zip(items):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for kind, val in items:
            if kind == "img":
                z.writestr(val[0], val[1])
    return out.getvalue()


# ===========================================================================
#  Streamlit UI
# ===========================================================================
def render():
    import streamlit as st

    st.subheader("📷 시험지 문항 캡처 → HWPX (2단)")
    st.caption("수능·모의평가 **수학 영역** PDF의 문항을 하나씩 그림으로 잘라내어, 원본처럼 2단으로 배치한 "
               "한글 문서를 만듭니다. 글자·수식 편집은 되지 않지만 원본 모양이 그대로 유지됩니다.")

    up = st.file_uploader("시험지 PDF", type=["pdf"], key="cap_pdf")

    with st.expander("옵션", expanded=True):
        c1, c2 = st.columns(2)
        paper = c1.radio("용지", list(PAPERS), index=0, key="cap_paper",
                         help="원본 시험지가 A3 2단이라 B4는 약 91%, A4는 약 75% 크기로 들어갑니다.")
        gap = c2.number_input("문항 사이 빈 줄 수", min_value=0, max_value=10, value=3, key="cap_gap")
        divider = c2.checkbox("단 사이 구분선", value=True, key="cap_divider")
        headings = st.checkbox("5지선다형 / 단답형 제목 넣기 (공통 16번, 선택 29번부터 단답형)",
                               value=True, key="cap_headings")
        names_txt = st.text_input("구간 이름 (쉼표로 구분, 공통과목 + 선택과목 순서)",
                                  value="공통과목, 확률과 통계, 미적분, 기하", key="cap_names")

    if st.button("변환하기", type="primary", disabled=(up is None), use_container_width=True, key="cap_convert"):
        section_names = [s.strip() for s in names_txt.split(",") if s.strip()]
        try:
            with st.spinner("문항을 잘라내는 중..."):
                questions = capture_questions(up.getvalue())
            if not questions:
                st.error("문항 번호(예: `1. `, `23. `)를 찾지 못했습니다. 평가원 수학 영역 형식의 PDF인지 확인해 주세요.")
                return
            items = plan_document(questions, section_names, headings, short_answer_from=(16, 29))
            with st.spinner("HWPX를 만드는 중..."):
                hwpx = build_hwpx(items, paper, int(gap), divider)
            zipped = crops_zip(items)
        except Exception as e:
            st.error(f"변환 중 오류가 발생했습니다: {e}")
            st.exception(e)
            return

        n_sec = sum(1 for k, _ in items if k == "h1")
        stem = os.path.splitext(up.name)[0]
        st.success(f"변환 완료!  (문항 {len(questions)}개, 구간 {n_sec}개)")
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ HWPX 다운로드", data=hwpx, file_name=f"{stem}_문항캡처_2단.hwpx",
                           mime="application/octet-stream", use_container_width=True, key="cap_dl_hwpx")
        d2.download_button("⬇️ 문항 PNG 묶음 (ZIP)", data=zipped, file_name=f"{stem}_문항.zip",
                           mime="application/zip", use_container_width=True, key="cap_dl_zip")

        with st.expander("잘라낸 문항 미리보기 (앞 4개)"):
            cols = st.columns(2)
            for i, (q, png, _) in enumerate(questions[:4]):
                cols[i % 2].image(png, caption=f"{q}번", use_container_width=True)

    with st.expander("지원 범위 / 참고"):
        st.markdown(
            "- **대상**: 평가원 형식의 수학 영역 PDF (A3 2단, `번호.` 로 시작하는 문항, 공통 1~22 + 선택 23~30). "
            "다른 과목·출판사 형식은 문항 인식이 안 될 수 있습니다.\n"
            "- 큰 제목이 있는 쪽(각 선택과목 첫 쪽)의 첫 문항, 또는 문항 번호가 다시 작아지는 곳을 새 구간으로 보고, "
            "구간마다 새 쪽에서 시작합니다.\n"
            "- 제목 밑 괘선, 쪽번호, \"확인 사항\" 안내 상자는 자동으로 제외합니다.\n"
            "- 문항은 그림으로 들어가므로 글자·수식 편집은 되지 않습니다. 편집이 필요하면 "
            "**Markdown → HWPX** 탭을 이용하세요.")
