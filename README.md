# 문서 유틸리티 (Streamlit)

두 가지 문서 도구를 한 화면에 모은 웹앱입니다. 상단 탭으로 전환합니다.

## 도구

### 📄 Markdown → HWPX 변환기
LaTeX 수식이 포함된 마크다운(.md)을 한글(HWPX) 문서로 변환합니다.
수식은 편집 가능한 한글 수식 개체로 삽입되며, 변환 로직은 파이썬 표준
라이브러리만 사용합니다(기본 HWPX 템플릿은 앱에 내장).

- 수식: 인라인 `$...$`, 디스플레이 `$$...$$`
- 서식: 제목(`#`~`######`), **굵게**, 가로줄(`---`), 표(`|...|`)

### 📑 PDF 쪽 추출 · 병합기
수능·모의고사 PDF에서 원하는 쪽만 뽑거나, 여러 파일을 한 권으로 묶습니다.

- **쪽 추출** — 각 PDF에서 지정한 쪽만 뽑아 파일별로 저장 (여러 개면 ZIP 일괄 다운로드)
- **하나로 합치기** — 지정한 순서대로 병합, 파일명 기준 북마크(목차) 자동 생성
- 쪽 지정: `9-12`(범위), `1, 3, 5`(낱장), `1, 9-12, 20`(혼합)

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

브라우저가 자동으로 열립니다(기본 http://localhost:8501).

## Streamlit Community Cloud 배포 (무료)

1. 저장소 전체를 GitHub에 올립니다.
2. https://share.streamlit.io 에 GitHub 계정으로 로그인합니다.
3. **Create app → Deploy a public app from GitHub** 를 선택합니다.
4. 저장소(Repository), 브랜치(Branch), 메인 파일 경로(`streamlit_app.py`)를 지정합니다.
5. **Deploy** 를 누르면 공개 URL이 생성됩니다.

## 파일 구조

```
streamlit_app.py    메인 진입점 (탭으로 두 도구 전환)
md2hwpx_app.py      Markdown → HWPX 변환 로직 + UI (render())
pdf_tool.py         PDF 추출·병합 로직 + UI (render())
requirements.txt    streamlit, pypdf
```

두 모듈 모두 `render()` 함수만 노출하며, `st.set_page_config()`는
`streamlit_app.py`에서 한 번만 호출합니다.

## 참고

- HWPX 출력은 한글 2014 이상에서 열립니다.
- 수식 상자 크기가 처음에 어색하면, 한글에서 그 수식을 더블클릭해 수식 편집기를
  한 번 열었다 닫으면 정확히 다시 계산됩니다.
- 업로드한 파일은 서버에 저장되지 않고 세션 메모리에서만 처리됩니다.
