import io
import os
import zipfile
import streamlit as st
from pypdf import PdfReader, PdfWriter

st.set_page_config(page_title="PDF 쪽 추출 · 병합기", page_icon="📄")


def parse_pages(text, max_page):
    """'1, 3, 9-12' -> [1, 3, 9, 10, 11, 12] (중복 제거, 정렬)"""
    pages = set()
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            if a > b:
                a, b = b, a
            pages.update(range(a, b + 1))
        else:
            pages.add(int(part))
    valid = sorted(p for p in pages if 1 <= p <= max_page)
    if not valid:
        raise ValueError("유효한 쪽 번호가 없습니다.")
    return valid


def extract_to_bytes(file, page_text):
    reader = PdfReader(file)
    pages = parse_pages(page_text, len(reader.pages))
    writer = PdfWriter()
    for p in pages:
        writer.add_page(reader.pages[p - 1])
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.getvalue(), len(pages)


def merge_to_bytes(files, page_text=None, add_bookmarks=True):
    writer = PdfWriter()
    total = 0
    for f in files:
        f.seek(0)
        reader = PdfReader(f)
        start = total
        if page_text:
            targets = parse_pages(page_text, len(reader.pages))
            for p in targets:
                writer.add_page(reader.pages[p - 1])
            total += len(targets)
        else:
            for page in reader.pages:
                writer.add_page(page)
            total += len(reader.pages)
        if add_bookmarks and total > start:
            writer.add_outline_item(os.path.splitext(f.name)[0], start)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.getvalue(), total


st.title("📄 PDF 쪽 추출 · 병합기")
st.caption("수능·모의고사 PDF에서 원하는 쪽만 뽑거나, 여러 파일을 한 권으로 묶습니다.")

uploaded = st.file_uploader(
    "PDF 파일 선택 (여러 개 가능)", type="pdf", accept_multiple_files=True
)

if uploaded:
    st.success(f"{len(uploaded)}개 업로드됨")

    # 병합 순서 조정
    order = st.multiselect(
        "처리 순서 (드래그로 순서 변경, 빼면 제외됩니다)",
        options=[f.name for f in uploaded],
        default=[f.name for f in uploaded],
    )
    by_name = {f.name: f for f in uploaded}
    files = [by_name[n] for n in order]
else:
    files = []

col1, col2 = st.columns([3, 2])
with col1:
    page_text = st.text_input("쪽 번호", value="9-12", help="예: 9-12 / 1, 3, 5 / 1, 9-12, 20")
with col2:
    suffix = st.text_input("파일명 접미사", value="_미적분")

tab1, tab2 = st.tabs(["쪽 추출", "하나로 합치기"])

with tab1:
    st.write("각 파일에서 지정한 쪽만 뽑아 **파일별로 따로** 저장합니다.")
    if st.button("추출 실행", type="primary", use_container_width=True, disabled=not files):
        results, errors = [], []
        for f in files:
            try:
                f.seek(0)
                data, n = extract_to_bytes(f, page_text)
                base = os.path.splitext(f.name)[0]
                results.append((f"{base}{suffix or '_추출'}.pdf", data, n))
            except Exception as e:
                errors.append(f"{f.name}: {e}")

        for name, data, n in results:
            st.download_button(
                f"⬇ {name} ({n}쪽)", data, file_name=name,
                mime="application/pdf", key=f"dl_{name}",
            )

        if len(results) > 1:
            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
                for name, data, _ in results:
                    z.writestr(name, data)
            st.download_button(
                "📦 전체 ZIP으로 받기", zbuf.getvalue(),
                file_name="추출결과.zip", mime="application/zip",
                type="primary", use_container_width=True,
            )

        for e in errors:
            st.error(e)

with tab2:
    st.write("선택한 파일을 **위 순서대로** 이어 붙여 한 개의 PDF로 만듭니다.")
    only_selected = st.checkbox(
        "합칠 때 각 파일에서 지정한 쪽만 가져오기 (해제하면 전체 쪽)", value=True
    )
    add_bm = st.checkbox("파일명으로 북마크(목차) 넣기", value=True)
    out_name = st.text_input("저장할 파일명", value="합본.pdf")

    if st.button("하나로 합치기", type="primary", use_container_width=True,
                 disabled=len(files) < 2):
        try:
            data, total = merge_to_bytes(
                files, page_text if only_selected else None, add_bm
            )
            st.success(f"{len(files)}개 파일, 총 {total}쪽")
            st.download_button(
                f"⬇ {out_name} 다운로드", data,
                file_name=out_name if out_name.endswith(".pdf") else out_name + ".pdf",
                mime="application/pdf", type="primary", use_container_width=True,
            )
        except Exception as e:
            st.error(f"병합 실패: {e}")

    if len(files) < 2:
        st.info("2개 이상 업로드하면 활성화됩니다.")
