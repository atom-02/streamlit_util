"""문서 유틸리티 - Markdown→HWPX 변환기 + PDF 쪽 추출·병합기"""
import streamlit as st

st.set_page_config(page_title="문서 유틸리티", page_icon="🧰", layout="centered")

from md2hwpx_app import render as render_md2hwpx
from pdf_tool import render as render_pdf_tool

st.title("🧰 문서 유틸리티")

tab_md, tab_pdf = st.tabs(["📄 Markdown → HWPX", "📑 PDF 쪽 추출 · 병합"])

with tab_md:
    render_md2hwpx()

with tab_pdf:
    render_pdf_tool()

st.divider()
st.caption("업로드한 파일은 서버에 저장되지 않고 세션 메모리에서만 처리됩니다.")
