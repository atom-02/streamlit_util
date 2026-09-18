"""제목 + 링크 주소 + QR코드 안내문 생성기 (PDF / 한글 HWPX).

streamlit_app.py 에서 render() 를 호출해 사용합니다.
QR코드는 페이지 가로 중앙에 크게, 제목은 크게, 링크 주소는 제목 바로
아래에 부제목처럼 작고 가깝게 배치하며(왼쪽 정렬), 내용 블록이 몇 줄이든
위·아래 여백이 자동으로 균형 있게 맞춰진다.
"""
import io
import os
import re

import qrcode
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import md2hwpx_app as hwpx


# ===========================================================================
#  한글 폰트 등록 (Streamlit Community Cloud 배포 시 packages.txt 의
#  fonts-nanum 패키지로 아래 경로에 폰트가 설치된다)
# ===========================================================================
KOREAN_FONT_CANDIDATES = [
    ("KRFont", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf", None),
    ("KRFont-Bold", "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", None),
    ("KRFont", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 1),  # KR = index 1
    ("KRFont-Bold", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1),
    ("KRFont", "C:/Windows/Fonts/malgun.ttf", None),          # Windows에서 로컬 실행 시
    ("KRFont-Bold", "C:/Windows/Fonts/malgunbd.ttf", None),
    ("KRFont", "/System/Library/Fonts/Supplemental/AppleGothic.ttf", None),  # macOS
    ("KRFont-Bold", "/System/Library/Fonts/Supplemental/AppleGothic.ttf", None),
]


def register_korean_fonts():
    """사용 가능한 한글 폰트를 찾아 reportlab에 등록한다."""
    registered = {"regular": None, "bold": None}
    for name, path, index in KOREAN_FONT_CANDIDATES:
        slot = "regular" if name == "KRFont" else "bold"
        if registered[slot] is not None:
            continue
        if name not in pdfmetrics.getRegisteredFontNames():
            if not os.path.exists(path):
                continue
            try:
                if index is None:
                    pdfmetrics.registerFont(TTFont(name, path))
                else:
                    pdfmetrics.registerFont(TTFont(name, path, subfontIndex=index))
            except Exception:
                continue
        registered[slot] = name

    if registered["regular"] is None:
        registered["regular"] = "Helvetica"
    if registered["bold"] is None:
        registered["bold"] = "Helvetica-Bold"
    return registered


FONTS = register_korean_fonts()


# ===========================================================================
#  공용 로직
# ===========================================================================
def normalize_url(url: str) -> str:
    url = url.strip()
    if url and not re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", url):
        url = "https://" + url
    return url


def make_qr_image(url: str, box_size: int = 10, border: int = 2) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(normalize_url(url))
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def safe_filename(title: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", (title or "").strip() or "qr_code")


def _wrap_text_by_width(c, text, font_name, font_size, max_width):
    """긴 텍스트를 지정된 너비에 맞춰 여러 줄로 나눈다."""
    lines = []
    current = ""
    for ch in text:
        trial = current + ch
        if c.stringWidth(trial, font_name, font_size) > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


# ===========================================================================
#  PDF 생성
# ===========================================================================
def create_qr_pdf_bytes(title: str, url: str) -> bytes:
    """제목 / 링크 주소 / QR코드가 담긴 1페이지 PDF를 만들어 bytes로 반환한다."""
    title = (title or "").strip() or "QR 코드"
    url = (url or "").strip()
    if not url:
        raise ValueError("링크 주소가 비어 있습니다.")
    url = normalize_url(url)

    page_w, page_h = A4
    left_margin = 37 * mm
    min_margin = 20 * mm

    title_font_size = 40
    title_line_height = title_font_size * 1.15
    url_font_size = 18
    gap_title_to_url = 8 * mm
    url_line_height = 10 * mm
    gap_url_to_qr = 18 * mm

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    max_text_width = page_w - 2 * left_margin

    c.setFont(FONTS["bold"], title_font_size)
    title_lines = _wrap_text_by_width(c, title, FONTS["bold"], title_font_size, max_text_width)
    c.setFont(FONTS["regular"], url_font_size)
    url_lines = _wrap_text_by_width(c, url, FONTS["regular"], url_font_size, max_text_width)

    text_height = (
        len(title_lines) * title_line_height
        + gap_title_to_url
        + len(url_lines) * url_line_height
    )

    desired_qr_size = 150 * mm
    available_for_qr = page_h - 2 * min_margin - text_height - gap_url_to_qr
    qr_size = min(desired_qr_size, page_w - 20 * mm, available_for_qr)
    qr_size = max(qr_size, 40 * mm)

    total_block_height = text_height + gap_url_to_qr + qr_size
    top_margin = max(min_margin, (page_h - total_block_height) / 2)

    y = page_h - top_margin

    c.setFont(FONTS["bold"], title_font_size)
    for line in title_lines:
        c.drawString(left_margin, y, line)
        y -= title_line_height

    # 링크 주소를 제목 바로 아래에 부제목처럼 작게, 간격을 좁혀서 배치
    y -= gap_title_to_url
    c.setFont(FONTS["regular"], url_font_size)
    for line in url_lines:
        c.drawString(left_margin, y, line)
        y -= url_line_height

    y -= gap_url_to_qr
    qr_img = make_qr_image(url)
    qr_x = (page_w - qr_size) / 2
    img_buf = io.BytesIO()
    qr_img.save(img_buf, format="PNG")
    img_buf.seek(0)
    from reportlab.lib.utils import ImageReader
    y -= qr_size
    c.drawImage(ImageReader(img_buf), qr_x, y, width=qr_size, height=qr_size)
    c.save()

    return buf.getvalue()


# ===========================================================================
#  한글(.hwpx) 생성
# ===========================================================================
PT = 7200 / 72  # HWPUNIT per point (HWPUNIT = 1/7200 inch)

# md2hwpx_app 의 내장 템플릿에 이 도구용 글자/문단 모양을 덧붙일 때 쓰는 id
_CP_TITLE, _CP_URL = 10, 11          # patch_header 가 7~9 를 쓰므로 그 다음부터
_PP_TITLE, _PP_URL, _PP_QR = 20, 21, 22  # 템플릿 paraPr 는 0~19


def _make_parapr(pp0, pid, align, line_pct, next_pt, snap=False):
    """템플릿의 paraPr id=0 을 복제해 정렬 / 줄간격(%) / 문단 아래 간격(pt)만 바꾼 paraPr XML."""
    s = re.sub(r'id="0"', f'id="{pid}"', pp0, count=1)
    s = s.replace('snapToGrid="1"', f'snapToGrid="{1 if snap else 0}"', 1)
    s = re.sub(r'<hh:align horizontal="[A-Z]+"', f'<hh:align horizontal="{align}"', s, count=1)
    s = re.sub(r'<hh:lineSpacing type="PERCENT" value="\d+"',
               f'<hh:lineSpacing type="PERCENT" value="{line_pct}"', s)          # switch 의 case/default 둘 다
    s = re.sub(r'<hc:next value="0"', f'<hc:next value="{round(next_pt * PT)}"', s)
    return s


def _qr_header_patch(title_pt, url_pt, gap_title_to_url_pt, gap_url_to_qr_pt):
    def patch(header):
        cp0 = re.search(r'<hh:charPr id="0".*?</hh:charPr>', header, re.S).group(0)
        cps = (hwpx.make_charpr(cp0, _CP_TITLE, round(title_pt * 100), True) + "\n      "
               + hwpx.make_charpr(cp0, _CP_URL, round(url_pt * 100), False) + "\n      ")
        header = header.replace('</hh:charProperties>', cps + '</hh:charProperties>', 1)
        header = re.sub(r'(<hh:charProperties itemCnt=")(\d+)(")',
                        lambda mm: f'{mm.group(1)}{int(mm.group(2)) + 2}{mm.group(3)}', header, count=1)

        pp0 = re.search(r'<hh:paraPr id="0".*?</hh:paraPr>', header, re.S).group(0)
        pps = (_make_parapr(pp0, _PP_TITLE, "LEFT", 115, gap_title_to_url_pt) + "\n      "
               + _make_parapr(pp0, _PP_URL, "LEFT", 140, gap_url_to_qr_pt) + "\n      "
               + _make_parapr(pp0, _PP_QR, "CENTER", 100, 0) + "\n      ")
        header = header.replace('</hh:paraProperties>', pps + '</hh:paraProperties>', 1)
        header = re.sub(r'(<hh:paraProperties itemCnt=")(\d+)(")',
                        lambda mm: f'{mm.group(1)}{int(mm.group(2)) + 3}{mm.group(3)}', header, count=1)
        return header
    return patch


def _qr_section_patch(page_w_pt, page_h_pt, left_pt, top_pt, bottom_pt):
    def patch(sec):
        sec = re.sub(r'<hp:pagePr [^>]*>',
                     f'<hp:pagePr landscape="WIDELY" width="{round(page_w_pt * PT)}" '
                     f'height="{round(page_h_pt * PT)}" gutterType="LEFT_ONLY">', sec, count=1)
        sec = re.sub(r'<hp:margin [^>]*/>',
                     f'<hp:margin header="0" footer="0" gutter="0" left="{round(left_pt * PT)}" '
                     f'right="{round(left_pt * PT)}" top="{round(top_pt * PT)}" bottom="{round(bottom_pt * PT)}"/>',
                     sec, count=1)
        return sec
    return patch


def create_qr_hwpx_bytes(title: str, url: str) -> bytes:
    """제목 / 링크 주소 / QR코드가 담긴 1페이지 한글(HWPX) 문서를 만들어 bytes로 반환한다.

    여백·글자 크기·QR 크기·위쪽 여백(세로 가운데 배치) 계산을 PDF 버전
    (create_qr_pdf_bytes)과 동일한 수치로 맞춰 두 출력물이 같은 모양으로 보이도록 한다.
    제목과 링크는 편집 가능한 글자로, QR코드는 그림 개체로 들어간다.
    (한글 문서 안의 링크는 일반 글자이며 클릭 링크는 아니다.)
    """
    title = (title or "").strip() or "QR 코드"
    url = (url or "").strip()
    if not url:
        raise ValueError("링크 주소가 비어 있습니다.")
    url = normalize_url(url)

    # ---- PDF 버전과 동일한 레이아웃 상수 / 계산 (단위: pt) ----
    page_w, page_h = A4
    left_margin = 37 * mm
    min_margin = 20 * mm

    title_font_size = 40
    title_line_height = title_font_size * 1.15
    url_font_size = 18
    gap_title_to_url = 8 * mm
    url_line_height = 10 * mm
    gap_url_to_qr = 18 * mm

    max_text_width = page_w - 2 * left_margin
    mc = canvas.Canvas(io.BytesIO(), pagesize=A4)  # 줄 수 추정용(출력되지 않음)
    title_lines = _wrap_text_by_width(mc, title, FONTS["bold"], title_font_size, max_text_width)
    url_lines = _wrap_text_by_width(mc, url, FONTS["regular"], url_font_size, max_text_width)

    text_height = (
        len(title_lines) * title_line_height
        + gap_title_to_url
        + len(url_lines) * url_line_height
    )
    desired_qr_size = 150 * mm
    available_for_qr = page_h - 2 * min_margin - text_height - gap_url_to_qr
    qr_size = min(desired_qr_size, page_w - 20 * mm, available_for_qr)
    qr_size = max(qr_size, 40 * mm)

    total_block_height = text_height + gap_url_to_qr + qr_size
    top_margin = max(min_margin, (page_h - total_block_height) / 2)

    # ---- 문서 생성 ----
    hwpx.reset_images()
    img_buf = io.BytesIO()
    make_qr_image(url).save(img_buf, format="PNG")
    qr_mm = qr_size / mm
    body = (
        hwpx.paragraph([hwpx.text_run(title, str(_CP_TITLE))], para_pr=str(_PP_TITLE))
        + hwpx.paragraph([hwpx.text_run(url, str(_CP_URL))], para_pr=str(_PP_URL))
        + hwpx.paragraph([hwpx.picture_xml(img_buf.getvalue(), "qr.png", width_mm=qr_mm, max_width_mm=qr_mm)],
                         para_pr=str(_PP_QR))
    )
    return hwpx.package_hwpx(
        body,
        section_patch=_qr_section_patch(page_w, page_h, left_margin, top_margin, min_margin),
        header_patch=_qr_header_patch(title_font_size, url_font_size, gap_title_to_url, gap_url_to_qr),
    )


# ===========================================================================
#  Streamlit UI  (streamlit_app.py 에서 render() 호출)
# ===========================================================================
def render():
    import streamlit as st

    st.subheader("🔗 QR코드 안내문 생성기")
    st.caption("제목과 링크 주소를 입력하면, QR코드가 담긴 안내문을 PDF 또는 한글(HWPX) 파일로 만들어 드립니다.")

    title = st.text_input(
        "제목", value="", placeholder="예: 미적분 패들렛 QR코드", key="qr_title",
    )
    url = st.text_input(
        "링크 주소 (URL)", value="", placeholder="예: https://padlet.com/...", key="qr_url",
    )

    if not url.strip():
        st.info("링크 주소를 입력하면 QR 코드 미리보기와 다운로드 버튼이 나타납니다.")
        return

    norm_url = normalize_url(url)

    col_preview, col_info = st.columns([1, 2])
    with col_preview:
        try:
            preview_img = make_qr_image(norm_url, box_size=6)
            st.image(preview_img, caption="QR 코드 미리보기", width=180)
        except Exception as e:
            st.error(f"QR 코드를 만드는 중 오류가 발생했습니다.\n{e}")
            return
    with col_info:
        st.write(f"**제목**  \n{title.strip() or 'QR 코드'}")
        st.write(f"**링크 주소**  \n{norm_url}")

    base_name = safe_filename(title)

    dl_pdf, dl_hwpx = st.columns(2)
    with dl_pdf:
        try:
            pdf_bytes = create_qr_pdf_bytes(title, url)
            st.download_button(
                "⬇ PDF 다운로드", pdf_bytes, file_name=f"{base_name}.pdf",
                mime="application/pdf", type="primary",
                use_container_width=True, key="qr_pdf_dl",
            )
        except Exception as e:
            st.error(f"PDF 생성 실패: {e}")
    with dl_hwpx:
        try:
            hwpx_bytes = create_qr_hwpx_bytes(title, url)
            st.download_button(
                "⬇ 한글(HWPX) 다운로드", hwpx_bytes, file_name=f"{base_name}.hwpx",
                mime="application/octet-stream",
                type="primary", use_container_width=True, key="qr_hwpx_dl",
            )
        except Exception as e:
            st.error(f"한글 문서 생성 실패: {e}")


if __name__ == "__main__":
    print("이 파일은 모듈입니다. 다음처럼 실행하세요:\n"
          "    pip install -r requirements.txt\n"
          "    streamlit run streamlit_app.py")
