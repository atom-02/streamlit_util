"""Markdown (+LaTeX) -> HWPX converter.

streamlit_app.py 에서 render() 를 호출해 사용합니다.
HWPX 변환은 파이썬 표준 라이브러리만 사용하며, 기본 HWPX 템플릿은
아래에 base64 로 내장되어 있습니다.

[이식 기능]
- 5지선다 보기(①~⑤)를 문항(점수) 다음 줄로 자동 분리 (SPLIT_CHOICES)
- 문항과 문항 사이에 빈 줄 자동 삽입 (GAP_BETWEEN_QUESTIONS)
"""
import base64, html, io, os, re, zipfile

# --- 이식 기능 스위치 -------------------------------------------------------
SPLIT_CHOICES = True          # ①②③④⑤ 보기를 문항 다음 줄로 내림
GAP_BETWEEN_QUESTIONS = True  # 새 문항 앞에 빈 줄 삽입

# --- embedded base HWPX template (real Hancom-saved skeleton) --------------
_BASE_ZIP_B64 = """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"""

def _extract_base(dst):
    data = base64.b64decode(_BASE_ZIP_B64)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dst)

FRAC = (r"\frac", r"\dfrac", r"\tfrac")
KEYWORDS = {
    "sum", "prod", "int", "oint", "lim", "log", "ln", "exp", "max", "min",
    "sin", "cos", "tan", "cot", "sec", "csc", "sinh", "cosh", "tanh",
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta",
    "eta", "theta", "vartheta", "iota", "kappa", "lambda", "mu", "nu",
    "xi", "pi", "varpi", "rho", "sigma", "tau", "upsilon", "phi", "varphi",
    "chi", "psi", "omega", "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi",
    "Sigma", "Upsilon", "Phi", "Psi", "Omega", "partial", "nabla",
    "cdot", "times", "div", "ast", "circ", "cdots", "ldots", "dots",
    "in", "notin", "subset", "supset", "cup", "cap", "forall", "exists",
    "sim", "approx", "equiv", "propto",
}
SYMBOL = {
    r"\pm": " +- ", r"\mp": " -+ ",
    r"\leq": " <= ", r"\le": " <= ", r"\geq": " >= ", r"\ge": " >= ",
    r"\neq": " != ", r"\ne": " != ",
    r"\ll": " << ", r"\gg": " >> ",
    r"\infty": " inf ", r"\to": " -> ", r"\rightarrow": " -> ",
    r"\gets": " <- ", r"\leftarrow": " <- ",
    r"\Rightarrow": " => ", r"\Leftarrow": " <= ",
    r"\leftrightarrow": " <-> ", r"\Leftrightarrow": " <=> ",
    r"\cdot": " cdot ", r"\times": " times ", r"\div": " div ",
}
SPACES = [r"\,", r"\;", r"\:", r"\!", r"\quad", r"\qquad", r"\ ", r"\>"]
SIZERS = r"\\(?:Biggl|Biggr|Bigg|biggl|biggr|bigg|Bigl|Bigr|Big|bigl|bigr|big|left|right)\b"


def _find_group(s, i):
    depth, j = 0, i
    while j < len(s):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def _read_arg(s, i):
    while i < len(s) and s[i] == " ":
        i += 1
    if i < len(s) and s[i] == "{":
        return _find_group(s, i)
    if i < len(s) and s[i] == "\\":
        m = re.match(r"\\[A-Za-z]+", s[i:])
        if m:
            return s[i:i + m.end()], i + m.end()
        return s[i:i + 2], i + 2
    if i < len(s):
        return s[i], i + 1
    return "", i


def _preprocess(s):
    s = s.strip()
    def repl_cases(m):
        return " cases{" + m.group(1).replace(r"\\", " # ") + "} "
    s = re.sub(r"\\begin\{cases\}(.*?)\\end\{cases\}", repl_cases, s, flags=re.S)
    def repl_matrix(m):
        return " matrix{" + m.group(2).replace(r"\\", " # ") + "} "
    s = re.sub(r"\\begin\{(p|b|v|V|)matrix\}(.*?)\\end\{\1matrix\}", repl_matrix, s, flags=re.S)
    s = re.sub(r"\\boxed\s*\{", "{", s)
    for cmd in (r"\text", r"\mathrm", r"\mathbf", r"\mathit", r"\operatorname"):
        s = re.sub(re.escape(cmd) + r"\s*\{([^{}]*)\}", r'"\1"', s)
    for sp in SPACES:
        s = s.replace(sp, " ")
    s = re.sub(SIZERS, "", s)
    s = s.replace(r"\{", "{ ").replace(r"\}", " }")
    return s


def latex_to_hwp(src):
    s = _preprocess(src)
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\[A-Za-z]+|\\.", s[i:])
            cmd = m.group(0)
            if cmd in FRAC:
                a, i = _read_arg(s, i + len(cmd))
                b, i = _read_arg(s, i)
                out.append(" {" + latex_to_hwp(a) + "} over {" + latex_to_hwp(b) + "} ")
                continue
            if cmd == r"\sqrt":
                j = i + len(cmd)
                while j < len(s) and s[j] == " ":
                    j += 1
                if j < len(s) and s[j] == "[":
                    k = s.index("]", j)
                    n = s[j + 1:k]
                    x, i = _read_arg(s, k + 1)
                    out.append(" root {" + latex_to_hwp(n) + "} {" + latex_to_hwp(x) + "} ")
                else:
                    x, i = _read_arg(s, i + len(cmd))
                    out.append(" sqrt {" + latex_to_hwp(x) + "} ")
                continue
            if cmd in (r"\vec", r"\hat", r"\bar", r"\tilde", r"\dot", r"\ddot", r"\overline"):
                a, i = _read_arg(s, i + len(cmd))
                name = {r"\overline": "bar"}.get(cmd, cmd[1:])
                out.append(" " + name + " {" + latex_to_hwp(a) + "} ")
                continue
            if cmd in SYMBOL:
                out.append(SYMBOL[cmd]); i += len(cmd); continue
            out.append(" " + cmd[1:] + " ")   # keyword or unknown: strip backslash
            i += len(cmd)
            continue
        if c in "_^":
            arg, i = _read_arg(s, i + 1)
            out.append(c + "{" + latex_to_hwp(arg) + "}")
            continue
        out.append(c)
        i += 1
    return re.sub(r"[ \t]+", " ", "".join(out)).strip()


# ===========================================================================
# 2.  Markdown parsing
# ===========================================================================
def parse_markdown(text):
    blocks, lines = [], text.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        st = line.strip()
        if not st:
            i += 1; continue
        if re.match(r"^-{3,}$", st):
            blocks.append(("hr",)); i += 1; continue
        if st.startswith("|"):
            tbl = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl.append(lines[i].strip()); i += 1
            blocks.append(("table", parse_table(tbl))); continue
        if st.startswith("$$"):
            buf = st
            while buf.count("$$") < 2 and i + 1 < len(lines):
                i += 1; buf += "\n" + lines[i].strip()
            blocks.append(("eq", buf.strip()[2:-2].strip())); i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2).strip())); i += 1; continue
        para = [line]; i += 1
        while i < len(lines):
            nx = lines[i].strip()
            if not nx or nx.startswith(("#", "$$", "|")) or re.match(r"^-{3,}$", nx):
                break
            para.append(lines[i].rstrip()); i += 1
        blocks.append(("p", parse_inline(" ".join(para))))
    return blocks


def parse_table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    return [r for r in cells if not all(re.match(r"^:?-{2,}:?$", c or "-") for c in r)]


def parse_inline(text):
    runs = []
    for idx, part in enumerate(re.split(r"(?<!\$)\$(?!\$)", text)):
        if idx % 2 == 1:
            runs.append(("eq", part.strip()))
        else:
            for j, seg in enumerate(re.split(r"\*\*", part)):
                if seg:
                    runs.append(("b", seg) if j % 2 == 1 else ("t", seg))
    return runs


# ===========================================================================
# 2.5  이식 기능: 보기(①~⑤) 줄바꿈 + 문항 간격
# ===========================================================================
_CHOICE_MARK = "①"


def _runs_leading_text(runs):
    """문단 첫 텍스트 run의 앞부분을 반환(문항 번호 판별용)."""
    for kind, val in runs:
        if kind in ("t", "b"):
            return val
        return ""   # 첫 run이 수식이면 문항 시작 아님
    return ""


def _is_question(runs):
    return bool(re.match(r"\s*\d+\.", _runs_leading_text(runs)))


def _split_choice_runs(runs):
    """runs 안에서 첫 ① 를 찾아 (문항 runs, 보기 runs)로 분리.
    ① 가 없으면 (runs, None)."""
    for idx, (kind, val) in enumerate(runs):
        if kind in ("t", "b") and _CHOICE_MARK in val:
            pos = val.index(_CHOICE_MARK)
            head, tail = val[:pos].rstrip(), val[pos:].strip()
            q = list(runs[:idx])
            if head:
                q.append((kind, head))
            c = []
            if tail:
                c.append((kind, tail))
            c.extend(runs[idx + 1:])
            return q, (c or None)
    return runs, None


def transform_blocks(blocks, split_choices=SPLIT_CHOICES, gap=GAP_BETWEEN_QUESTIONS):
    """파싱된 blocks에 보기 줄바꿈/문항 간격을 적용한 새 blocks 반환."""
    out = []
    prev_q = False
    for b in blocks:
        if b[0] != "p":
            out.append(b)
            prev_q = False
            continue
        runs = b[1]
        is_q = _is_question(runs)
        if is_q and prev_q and gap:
            out.append(("p", [("t", "")]))          # 빈 줄
        if split_choices:
            q_runs, c_runs = _split_choice_runs(runs)
            out.append(("p", q_runs))
            if c_runs is not None:
                out.append(("p", c_runs))
        else:
            out.append(("p", runs))
        prev_q = is_q
    return out


# ===========================================================================
# 3.  HWPX emission
# ===========================================================================
_eq_id, _obj_id, _pid = 1200000000, 1300000000, 100

def esc(s):
    return html.escape(s, quote=True)


def equation_xml(latex):
    global _eq_id
    _eq_id += 7
    script = latex_to_hwp(latex)
    bu = 1000
    n = max(len(re.sub(r"[{}\s]", "", script)), 2)
    h = 1.5
    if "over" in script or "cases" in script or "matrix" in script:
        h += 1.1
    if "cases" in script:
        h += latex.count(r"\\") * 0.9
    if "sqrt" in script or "root" in script:
        h += 0.4
    if any(k in script for k in ("sum", "int", "prod", "lim")):
        h += 0.7
    height = int(bu * h)
    width = min(int(bu * 0.60 * n), 42000)
    base_line = max(1, height // 54)
    return (
        f'<hp:run charPrIDRef="0"><hp:equation id="{_eq_id}" zOrder="0" '
        f'numberingType="EQUATION" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" '
        f'lock="0" dropcapstyle="None" version="Equation Version 60" '
        f'baseLine="{base_line}" textColor="#000000" baseUnit="{bu}" '
        f'lineMode="CHAR" font="HYhwpEQ">'
        f'<hp:sz width="{width}" widthRelTo="ABSOLUTE" height="{height}" heightRelTo="ABSOLUTE" protect="0"/>'
        f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" '
        f'vertOffset="0" horzOffset="0"/>'
        f'<hp:outMargin left="56" right="56" top="0" bottom="0"/>'
        f'<hp:shapeComment>{esc(latex)}</hp:shapeComment>'
        f'<hp:script>{esc(script)}</hp:script></hp:equation><hp:t/></hp:run>'
    )


def text_run(s, cp="0"):
    return f'<hp:run charPrIDRef="{cp}"><hp:t>{esc(s)}</hp:t></hp:run>'


def paragraph(inner, para_pr="0", style="0"):
    global _pid
    _pid += 1
    return (f'<hp:p id="{_pid}" paraPrIDRef="{para_pr}" styleIDRef="{style}" '
            f'pageBreak="0" columnBreak="0" merged="0">' + "".join(inner) + "</hp:p>")


def runs_from_inline(items):
    out = []
    for kind, val in items:
        if kind == "t":
            out.append(text_run(val))
        elif kind == "b":
            out.append(text_run(val, "9"))
        else:
            out.append(equation_xml(val))
    return out or [text_run("")]


CELL_W = [7000, 17760, 17760]

def table_xml(cells):
    global _obj_id, _pid
    _obj_id += 11
    ncol = max(len(r) for r in cells)
    widths = CELL_W if ncol == 3 else [42520 // ncol] * ncol
    rowh, total_h = 2600, 2600 * len(cells)
    parts = [
        f'<hp:tbl id="{_obj_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
        f'rowCnt="{len(cells)}" colCnt="{ncol}" cellSpacing="0" borderFillIDRef="3" noAdjust="0">'
        f'<hp:sz width="42520" widthRelTo="ABSOLUTE" height="{total_h}" heightRelTo="ABSOLUTE" protect="0"/>'
        f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
        f'vertOffset="0" horzOffset="0"/>'
        f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
        f'<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
    ]
    for r, row in enumerate(cells):
        parts.append("<hp:tr>")
        for cidx in range(ncol):
            text = row[cidx] if cidx < len(row) else ""
            is_header = (r == 0)
            bf = "4" if is_header else "3"
            _pid += 1
            # 셀 안의 인라인 수식($...$)·굵게(**)도 처리
            cell_runs = []
            for kind, val in parse_inline(text):
                if kind == "eq":
                    cell_runs.append(equation_xml(val))
                elif kind == "b":
                    cell_runs.append(text_run(val, "9"))
                else:
                    cell_runs.append(text_run(val, "9" if is_header else "0"))
            if not cell_runs:
                cell_runs = [text_run("", "9" if is_header else "0")]
            cell_p = (f'<hp:p id="{_pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" '
                      f'columnBreak="0" merged="0">' + "".join(cell_runs) + "</hp:p>")
            parts.append(
                f'<hp:tc borderFillIDRef="{bf}"><hp:cellAddr colAddr="{cidx}" rowAddr="{r}"/>'
                f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
                f'<hp:cellSz width="{widths[cidx]}" height="{rowh}"/>'
                f'<hp:cellMargin left="283" right="283" top="141" bottom="141"/>'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
                f'linkListIDRef="0" linkListNextIDRef="0" textWidth="{widths[cidx]-566}" fieldName="">'
                f'{cell_p}</hp:subList></hp:tc>'
            )
        parts.append("</hp:tr>")
    parts.append("</hp:tbl>")
    return f'<hp:run charPrIDRef="0">{"".join(parts)}</hp:run>'


def build_body(blocks):
    out = []
    for b in blocks:
        if b[0] == "h":
            cp = {1: "5", 2: "8", 3: "7"}.get(b[1], "7")
            out.append(paragraph([text_run(b[2], cp)]))
        elif b[0] == "hr":
            out.append(paragraph([text_run("─" * 40)]))
        elif b[0] == "eq":
            out.append(paragraph([equation_xml(b[1])]))
        elif b[0] == "table":
            out.append(paragraph([table_xml(b[1])]))
        elif b[0] == "p":
            out.append(paragraph(runs_from_inline(b[1])))
    return "".join(out)


# ===========================================================================
# 4.  Header patching (bold charPrs + table borderFills)
# ===========================================================================
def make_charpr(cp0, cid, height, bold):
    s = re.sub(r'id="0"', f'id="{cid}"', cp0, count=1)
    s = re.sub(r'height="\d+"', f'height="{height}"', s, count=1)
    if bold:
        s = s.replace('<hh:underline', '<hh:bold/>\n        <hh:underline', 1)
    return s


BORDERFILL_3_4 = '''<hh:borderFill id="3" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">
        <hh:slash type="NONE" Crooked="0" isCounter="0"/>
        <hh:backSlash type="NONE" Crooked="0" isCounter="0"/>
        <hh:leftBorder type="SOLID" width="0.12 mm" color="#000000"/>
        <hh:rightBorder type="SOLID" width="0.12 mm" color="#000000"/>
        <hh:topBorder type="SOLID" width="0.12 mm" color="#000000"/>
        <hh:bottomBorder type="SOLID" width="0.12 mm" color="#000000"/>
        <hh:diagonal type="SOLID" width="0.12 mm" color="#000000"/>
      </hh:borderFill>
      <hh:borderFill id="4" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">
        <hh:slash type="NONE" Crooked="0" isCounter="0"/>
        <hh:backSlash type="NONE" Crooked="0" isCounter="0"/>
        <hh:leftBorder type="SOLID" width="0.12 mm" color="#000000"/>
        <hh:rightBorder type="SOLID" width="0.12 mm" color="#000000"/>
        <hh:topBorder type="SOLID" width="0.12 mm" color="#000000"/>
        <hh:bottomBorder type="SOLID" width="0.12 mm" color="#000000"/>
        <hh:diagonal type="SOLID" width="0.12 mm" color="#000000"/>
        <hc:fillBrush><hc:winBrush faceColor="#E2EFDA" hatchColor="#999999" alpha="0"/></hc:fillBrush>
      </hh:borderFill>
    '''


def patch_header(header):
    header = re.sub(r'(<hh:borderFills itemCnt=")2(")', r'\g<1>4\g<2>', header)
    header = header.replace('</hh:borderFills>', BORDERFILL_3_4 + '</hh:borderFills>', 1)
    cp0 = re.search(r'<hh:charPr id="0".*?</hh:charPr>', header, re.S).group(0)
    additions = (make_charpr(cp0, 7, 1100, True) + "\n      "
                 + make_charpr(cp0, 8, 1300, True) + "\n      "
                 + make_charpr(cp0, 9, 1000, True) + "\n      ")
    header = header.replace('</hh:charProperties>', additions + '</hh:charProperties>', 1)
    header = re.sub(r'(<hh:charProperties itemCnt=")7(")', r'\g<1>10\g<2>', header)
    return header



# ===========================================================================
# 5.  Package (pure python)
# ===========================================================================

# ===========================================================================
#  In-memory conversion (no filesystem) — ideal for Streamlit Cloud
# ===========================================================================
def convert_md_to_hwpx_bytes(md_text, split_choices=SPLIT_CHOICES, gap=GAP_BETWEEN_QUESTIONS):
    """Convert markdown text -> HWPX bytes. Returns (data, n_blocks, n_equations)."""
    base = zipfile.ZipFile(io.BytesIO(base64.b64decode(_BASE_ZIP_B64)))
    files = {name: base.read(name) for name in base.namelist()}

    blocks = parse_markdown(md_text)
    blocks = transform_blocks(blocks, split_choices=split_choices, gap=gap)
    body = build_body(blocks)
    base_sec = files["Contents/section0.xml"].decode("utf-8")
    first_end = base_sec.index("</hp:p>") + len("</hp:p>")
    files["Contents/section0.xml"] = (base_sec[:first_end] + body + "\n</hs:sec>\n").encode("utf-8")
    files["Contents/header.xml"] = patch_header(
        files["Contents/header.xml"].decode("utf-8")).encode("utf-8")

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        # mimetype MUST be the first entry and stored uncompressed
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, files["mimetype"])
        for name in files:
            if name == "mimetype":
                continue
            z.writestr(name, files[name], compress_type=zipfile.ZIP_DEFLATED)

    n_eq = sum(1 for b in blocks if b[0] == "eq") + sum(
        1 for b in blocks if b[0] == "p" for k, _ in b[1] if k == "eq")
    return out.getvalue(), len(blocks), n_eq


def _decode(raw):
    for enc in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# ===========================================================================
#  Streamlit UI  (streamlit_app.py 에서 render() 호출)
# ===========================================================================
def render():
    import streamlit as st

    st.subheader("📄 Markdown → HWPX 변환기")
    st.caption("LaTeX 수식이 포함된 마크다운(.md)을 한글(HWPX) 문서로 변환합니다. "
               "수식은 편집 가능한 한글 수식 개체로 들어갑니다.")

    with st.expander("변환 옵션", expanded=False):
        split_choices = st.checkbox("5지선다 보기(①~⑤)를 문항 다음 줄로", value=SPLIT_CHOICES,
                                    key="md_split")
        gap = st.checkbox("문항과 문항 사이에 빈 줄 삽입", value=GAP_BETWEEN_QUESTIONS,
                          key="md_gap")

    tab_file, tab_text = st.tabs(["파일 업로드", "직접 붙여넣기"])
    md_text, src_name = None, "output"

    with tab_file:
        up = st.file_uploader("Markdown 파일 (.md)", type=["md", "markdown", "txt"],
                              key="md_upload")
        if up is not None:
            md_text = _decode(up.getvalue())
            src_name = os.path.splitext(up.name)[0]

    with tab_text:
        pasted = st.text_area("마크다운 내용을 붙여넣으세요", height=220,
                              placeholder="# 제목\n\n$$E = mc^2$$",
                              key="md_paste")
        if pasted.strip():
            md_text = pasted
            if src_name == "output":
                src_name = "document"

    out_name = st.text_input("출력 파일 이름", value=f"{src_name}.hwpx", key="md_outname")

    if st.button("변환하기", type="primary", disabled=(md_text is None),
                 use_container_width=True, key="md_convert"):
        name = out_name.strip() or "output.hwpx"
        if not name.lower().endswith(".hwpx"):
            name += ".hwpx"
        try:
            data, nb, ne = convert_md_to_hwpx_bytes(md_text, split_choices=split_choices, gap=gap)
        except Exception as e:
            st.error(f"변환 중 오류가 발생했습니다: {e}")
            st.exception(e)
            return
        st.success(f"변환 완료!  (블록 {nb}개, 수식 {ne}개)")
        st.download_button("⬇️ HWPX 다운로드", data=data, file_name=name,
                           mime="application/octet-stream",
                           use_container_width=True, key="md_download")
        st.info("한글에서 열었을 때 수식 상자 크기가 어색하면, 그 수식을 더블클릭해 "
                "수식 편집기를 한 번 열었다 닫으면 정확히 다시 계산됩니다.")

    with st.expander("지원 범위 / 참고"):
        st.markdown(
            "- **수식**: 인라인 `$...$`, 디스플레이 `$$...$$` (LaTeX)\n"
            "- **서식**: 제목(`#`~`######`), **굵게**, 가로줄(`---`), 표(`|...|`)\n"
            "- **문항 정리**: 5지선다 보기 줄바꿈, 문항 사이 빈 줄 (옵션에서 조절)\n"
            "- 출력은 HWPX 형식이며 한글 2014 이상에서 열립니다.\n"
            "- 아주 복잡한 수식(조건식 `cases` 등)은 열어서 한 번 확인을 권장합니다.")


if __name__ == "__main__":
    print("이 파일은 모듈입니다. 다음처럼 실행하세요:\n"
          "    pip install -r requirements.txt\n"
          "    streamlit run streamlit_app.py")
