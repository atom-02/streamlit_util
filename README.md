# Markdown → HWPX 변환기 (Streamlit)

LaTeX 수식이 포함된 마크다운(.md)을 한글(HWPX) 문서로 변환하는 웹앱입니다.
수식은 편집 가능한 한글 수식 개체로 삽입됩니다. 외부 의존성은 `streamlit` 하나뿐이며,
HWPX 변환은 파이썬 표준 라이브러리만 사용합니다(기본 HWPX 템플릿은 앱에 내장).

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

브라우저가 자동으로 열립니다(기본 http://localhost:8501).

## Streamlit Community Cloud 배포 (무료)

1. 이 두 파일(`streamlit_app.py`, `requirements.txt`)을 GitHub 저장소에 올립니다.
2. https://share.streamlit.io 에 GitHub 계정으로 로그인합니다.
3. **Create app → Deploy a public app from GitHub** 를 선택합니다.
4. 저장소(Repository), 브랜치(Branch), 메인 파일 경로(`streamlit_app.py`)를 지정합니다.
5. **Deploy** 를 누르면 공개 URL이 생성됩니다.

## 사용법

- **파일 업로드** 탭에서 `.md` 파일을 올리거나, **직접 붙여넣기** 탭에 마크다운을 붙여넣습니다.
- 출력 파일 이름을 정한 뒤 **변환하기** → **HWPX 다운로드**.

## 참고

- 출력은 HWPX 형식이며 한글 2014 이상에서 열립니다.
- 수식 상자 크기가 처음에 어색하면, 한글에서 그 수식을 더블클릭해 수식 편집기를
  한 번 열었다 닫으면 정확히 다시 계산됩니다.
