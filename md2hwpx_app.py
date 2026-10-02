"""Markdown (+LaTeX, +이미지) -> HWPX converter.

streamlit_app.py 에서 render() 를 호출해 사용합니다.
HWPX 변환은 파이썬 표준 라이브러리만 사용하며, 기본 A4와 A4/B4 2단 템플릿은
base64 로 내장되어 있습니다. 업로드된 파일(마크다운/이미지)은 디스크에 쓰지 않고
메모리에서만 처리됩니다.

[이식 기능]
- 5지선다 보기(①~⑤)를 문항(점수) 다음 줄로 자동 분리 (SPLIT_CHOICES)
- 문항과 문항 사이에 빈 줄 2줄 자동 삽입 (GAP_BETWEEN_QUESTIONS)
- 수식 델리미터 확장: `$...$`/`$$...$$` 외에 ChatGPT 등 AI가 흔히 쓰는 `\\(...\\)`(인라인),
  `\\[...\\]`(디스플레이) 델리미터도 인식
- 집합 중괄호: LaTeX `\\{...\\}` / `\\left\\{...\\right\\}`를 한컴의 표시용
  `LEFT {... RIGHT }` 문법으로 변환 (`{...}` 그룹 문법과 구분)
- 이미지 인라인 삽입: `![설명](파일명)` 마크다운 문법 + 같은 이름의 업로드된 이미지 파일을
  매칭해 편집 가능한 실제 그림 개체(hp:pic)로 삽입 (플레이스홀더가 아님)
"""
import base64, hashlib, html, io, os, re, zipfile

from exam_templates import EXAM_A4_ZIP_B64, EXAM_B4_ZIP_B64

# --- 이식 기능 스위치 -------------------------------------------------------
SPLIT_CHOICES = True          # ①②③④⑤ 보기를 문항 다음 줄로 내림
GAP_BETWEEN_QUESTIONS = True  # 새 문항 앞에 빈 줄 삽입
QUESTION_GAP_LINES = 2        # 문항과 다음 문항 사이의 빈 줄 수
ATTACH_PARTICLES = True       # `$x$ 의 값` -> `x의 값`: 수식 뒤 조사 앞의 공백 제거
CENTER_DISPLAY_EQUATIONS = True   # 별행 수식($$...$$, \[...\])을 가운데 정렬
DEFAULT_OUTPUT_TEMPLATE = "A4"
CONVERTER_VERSION = "2026.10.02-2"

# --- embedded base HWPX template (real Hancom-saved skeleton) --------------
_BASE_ZIP_B64 = """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"""

OUTPUT_TEMPLATES = {
    "A4": _BASE_ZIP_B64,
    "A4_2단": EXAM_A4_ZIP_B64,
    "B4_2단": EXAM_B4_ZIP_B64,
}


def _extract_base(dst):
    data = base64.b64decode(_BASE_ZIP_B64)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dst)

FRAC = (r"\frac", r"\dfrac", r"\tfrac", r"\cfrac")
KEYWORDS = {
    "sum", "prod", "int", "oint", "lim", "log", "ln", "exp", "max", "min",
    "sin", "cos", "tan", "cot", "sec", "csc", "sinh", "cosh", "tanh",
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta",
    "eta", "theta", "vartheta", "iota", "kappa", "lambda", "mu", "nu",
    "xi", "pi", "varpi", "rho", "sigma", "tau", "upsilon", "phi", "varphi",
    "chi", "psi", "omega", "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi",
    "Sigma", "Upsilon", "Phi", "Psi", "Omega", "partial", "nabla",
    "cdot", "times", "div", "ast", "circ", "cdots", "ldots", "dots", "vdots", "ddots",
    "in", "notin", "subset", "supset", "subseteq", "supseteq", "cup", "cap", "forall", "exists",
    "sim", "approx", "equiv", "propto",
}
# 아래 대응은 한글에서 직접 렌더링해 확인한 키워드만 쓴다. (예: `=>`는 화살표가 아니라
# 글자 그대로 찍히고, `\perp`·`\setminus`·`\mathbb`는 이름을 그대로 넘기면 글자로 찍힌다.)
SYMBOL = {
    r"\pm": " +- ", r"\mp": " -+ ",
    r"\leq": " <= ", r"\le": " <= ", r"\geq": " >= ", r"\ge": " >= ",
    r"\leqslant": " <= ", r"\geqslant": " >= ",
    r"\neq": " != ", r"\ne": " != ",
    r"\ll": " << ", r"\gg": " >> ",
    r"\infty": " inf ", r"\to": " -> ", r"\rightarrow": " -> ", r"\longrightarrow": " -> ",
    r"\gets": " <- ", r"\leftarrow": " <- ",
    r"\Rightarrow": " RARROW ", r"\Longrightarrow": " RARROW ",
    r"\Leftarrow": " LARROW ", r"\impliedby": " ~ LARROW ~ ",
    r"\implies": " ~ RARROW ~ ",
    r"\leftrightarrow": " lrarrow ", r"\Leftrightarrow": " LRARROW ", r"\iff": " ~ LRARROW ~ ",
    r"\mapsto": " MAPSTO ",
    r"\cdot": " cdot ", r"\times": " times ", r"\div": " div ",
    r"\mid": " ~ vert ~ ",
    r"\vert": " | ", r"\lvert": " | ", r"\rvert": " | ",
    r"\|": " DLINE ", r"\Vert": " DLINE ", r"\lVert": " DLINE ", r"\rVert": " DLINE ",
    r"\langle": " LEFT < ", r"\rangle": " RIGHT > ",
    r"\lfloor": " LFLOOR ", r"\rfloor": " RFLOOR ", r"\lceil": " LCEIL ", r"\rceil": " RCEIL ",
    r"\emptyset": " EMPTYSET ", r"\varnothing": " EMPTYSET ",
    r"\forall": " FORALL ", r"\exists": " EXIST ",
    r"\neg": " LNOT ", r"\lnot": " LNOT ",
    r"\land": " WEDGE ", r"\wedge": " WEDGE ", r"\lor": " LOR ", r"\vee": " LOR ",
    r"\supset": " SUPERSET ", r"\ni": " OWNS ",
    r"\subseteq": " SUBSETEQ ", r"\supseteq": " SUPSETEQ ",
    r"\setminus": " - ",
    r"\therefore": " THEREFORE ", r"\because": " BECAUSE ",
    r"\perp": " BOT ", r"\parallel": " PARALLEL ", r"\degree": " DEG ",
    r"\ell": " LITER ", r"\colon": " : ",
    r"\prod": " PROD ", r"\coprod": " COPROD ",
    r"\iint": " dint ", r"\iiint": " tint ", r"\bigcup": " UNION ", r"\bigcap": " INTER ",
    r"\ldots": " ldots ", r"\dots": " ldots ", r"\dotsc": " ldots ",
    r"\cdots": " cdots ", r"\dotsb": " cdots ",
    r"\vdots": " vdots ", r"\ddots": " ddots ",
    # 간격: 한컴 수식에서 `는 1/4칸, ~는 한 칸이다. (`\!`는 버린다)
    r"\,": " ` ", r"\;": " ~ ", r"\:": " ~ ", r"\ ": " ~ ", r"\>": " ~ ",
    r"\quad": " ~~ ", r"\qquad": " ~~~~ ", r"\!": " ",
    # 조판에만 영향을 주는 명령은 버린다.
    r"\limits": " ", r"\nolimits": " ", r"\textstyle": " ", r"\scriptstyle": " ",
    r"\nonumber": " ", r"\notag": " ", r"\hline": " ",
}
SIZERS = r"\\(?:Biggl|Biggr|Bigg|biggl|biggr|bigg|Bigl|Bigr|Big|bigl|bigr|big)\b"
DISPLAY_STYLES = r"\\displaystyle\b"
ACCENTS = {
    r"\vec": "vec", r"\hat": "hat", r"\bar": "bar", r"\tilde": "tilde", r"\dot": "dot",
    r"\ddot": "ddot", r"\acute": "acute", r"\grave": "grave", r"\check": "check",
    r"\under": "under", r"\arch": "arch",
    r"\overline": "bar", r"\underline": "under", r"\widehat": "hat", r"\widetilde": "tilde",
    r"\overrightarrow": "vec", r"\overleftrightarrow": "dyad", r"\overarc": "arch",
}
# \left, \right 뒤에 오는 이름 있는 구분자. LFLOOR 류는 그 자체가 자동 크기 괄호라 LEFT/RIGHT 없이 쓴다.
_DELIM = {
    r"\{": "{", r"\}": "}", r"\lbrace": "{", r"\rbrace": "}", r"\lbrack": "[", r"\rbrack": "]",
    r"\langle": "<", r"\rangle": ">", r"\vert": "|", r"\lvert": "|", r"\rvert": "|",
    r"\|": "DLINE", r"\Vert": "DLINE", r"\lVert": "DLINE", r"\rVert": "DLINE",
}
_BARE_DELIM = {r"\lfloor": "LFLOOR", r"\rfloor": "RFLOOR", r"\lceil": "LCEIL", r"\rceil": "RCEIL"}
# 위·아래에 글자를 얹는 관계 기호: 한컴 문법은 REL 기호 {위} {아래}
_STACKED_ARROWS = {
    r"\xrightarrow": "rarrow", r"\xleftarrow": "larrow", r"\xleftrightarrow": "lrarrow",
    r"\xRightarrow": "RARROW", r"\xLeftarrow": "LARROW", r"\xLeftrightarrow": "LRARROW",
}
_DOUBLE_STRUCK = {"N": "\u2115", "Z": "\u2124", "Q": "\u211a", "R": "\u211d", "C": "\u2102"}
_SCRIPT_CAPITALS = {"B": "\u212c", "E": "\u2130", "F": "\u2131", "H": "\u210b",
                    "I": "\u2110", "L": "\u2112", "M": "\u2133", "R": "\u211b"}


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


def _rows(body):
    """환경 본문의 행 구분 `\\\\`(뒤따르는 `[2pt]` 포함)을 한컴의 `#`으로 바꾼다."""
    return re.sub(r"\\\\\s*(?:\[[^\]]*\])?", " # ", body).strip().rstrip("#").strip()


def _repl_text(m):
    """`\\text{...}`: 한컴은 따옴표 안 글자를 기울여 쓰고 양끝 공백을 버리므로,
    rm 으로 세우고 양끝 공백은 `~`로 내보낸다. (rm 은 닫는 중괄호 뒤까지 번져서 it 로 닫는다)"""
    text = m.group(1).replace('"', "")
    body = text.strip()
    if not body:
        return " ~ "
    return ((" ~ " if text[:1].isspace() else " ") + '{rm "' + body + '" it}'
            + (" ~ " if text[-1:].isspace() else " "))


def _repl_letters(table, fallback):
    def repl(m):
        letters = m.group(1).strip()
        if letters and all(ch in table or (fallback and ch.isascii() and ch.isupper())
                           for ch in letters):
            return " " + "".join(table.get(ch) or fallback(ch) for ch in letters) + " "
        return " {it " + letters + "} "
    return repl


def _preprocess(s):
    s = s.strip()
    # JSON/Markdown 경유 중 명령 앞의 백슬래시가 두 번 보존된 경우에도
    # 논리 함의 명령으로 인식한다. cases 내부의 행 구분 ``\\``은 건드리지 않는다.
    s = s.replace(r"\\implies", r"\implies")
    # ``\displaystyle`` only controls TeX layout.  If it reaches the generic
    # command fallback below, Hancom visibly renders the word "displaystyle".
    s = re.sub(DISPLAY_STYLES, "", s)
    s = re.sub(r"\\(?:tag|label)\s*\{[^{}]*\}", "", s)
    def repl_cases(m):
        return " cases{" + _rows(m.group(1)) + "} "
    s = re.sub(r"\\begin\{cases\}(.*?)\\end\{cases\}", repl_cases, s, flags=re.S)
    # Vmatrix(이중 세로줄)와 Bmatrix(중괄호)는 전용 키워드가 없어 자동 크기 괄호로 감싼다.
    matrix_names = {"matrix": ("matrix{", "}"), "smallmatrix": ("matrix{", "}"),
                    "pmatrix": ("pmatrix{", "}"), "bmatrix": ("bmatrix{", "}"),
                    "vmatrix": ("dmatrix{", "}"),
                    "Vmatrix": ("LEFT DLINE matrix{", "} RIGHT DLINE"),
                    "Bmatrix": ("LEFT { matrix{", "} RIGHT }")}
    def repl_matrix(m):
        prefix, suffix = matrix_names[m.group(1)]
        return " " + prefix + _rows(m.group(2)) + suffix + " "
    s = re.sub(r"\\begin\{(matrix|smallmatrix|pmatrix|bmatrix|vmatrix|Vmatrix|Bmatrix)\}(.*?)\\end\{\1\}",
               repl_matrix, s, flags=re.S)
    s = re.sub(r"\\begin\{array\}\s*(?:\{[^{}]*\})?(.*?)\\end\{array\}",
               lambda m: " matrix{" + _rows(m.group(1)) + "} ", s, flags=re.S)
    # 정렬 환경: `&`를 남겨야 한글이 그 자리(보통 등호)에 맞춰 줄을 세운다.
    s = re.sub(r"\\begin\{(aligned|align\*?|split|eqnarray\*?|alignat\*?|flalign\*?)\}(.*?)\\end\{\1\}",
               lambda m: " eqalign{" + _rows(m.group(2)) + "} ", s, flags=re.S)
    s = re.sub(r"\\begin\{(gathered|gather\*?|equation\*?|multline\*?)\}(.*?)\\end\{\1\}",
               lambda m: " " + _rows(m.group(2)) + " ", s, flags=re.S)
    s = re.sub(r"\\substack\s*\{([^{}]*)\}", lambda m: " pile{" + _rows(m.group(1)) + "} ", s)
    s = re.sub(r"\\boxed\s*\{", " box {", s)
    for cmd in (r"\text", r"\textrm", r"\textnormal", r"\textbf", r"\textit", r"\mbox"):
        s = re.sub(re.escape(cmd) + r"\s*\{([^{}]*)\}", _repl_text, s)
    s = re.sub(r"\\mathbb\s*\{([^{}]*)\}", _repl_letters(_DOUBLE_STRUCK, None), s)
    s = re.sub(r"\\(?:mathcal|mathscr)\s*\{([^{}]*)\}",
               _repl_letters(_SCRIPT_CAPITALS, lambda ch: chr(0x1D49C + ord(ch) - 65)), s)
    for cmd, opening, closing in ((r"\mathbf", "{bold ", "}"), (r"\boldsymbol", "{bold ", "}"),
                                  (r"\bm", "{bold ", "}"), (r"\mathit", "{it ", "}"),
                                  (r"\mathrm", "{rm ", " it}"), (r"\operatorname", "{rm ", " it}"),
                                  (r"\mathsf", "{rm ", " it}"), (r"\mathtt", "{rm ", " it}")):
        s = re.sub(re.escape(cmd) + r"\s*\{([^{}]*)\}",
                   lambda m: " " + opening + m.group(1) + closing + " ", s)
    s = re.sub(SIZERS, "", s)
    return s


def latex_to_hwp(src):
    s = _preprocess(src)
    out, i = [], 0
    set_depth = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\[A-Za-z]+|\\.", s[i:], re.S)
            if not m:
                i += 1
                continue
            cmd = m.group(0)
            # 한컴 수식에서 일반 { }는 여러 항을 묶는 제어문자라 화면에
            # 표시되지 않는다. LaTeX의 이스케이프된 중괄호만 표시용
            # LEFT { ... RIGHT } 구문으로 바꿔 집합 괄호를 보존한다.
            if cmd == r"\{":
                set_depth += 1
                out.append(" LEFT { "); i += len(cmd); continue
            if cmd == r"\}":
                set_depth = max(0, set_depth - 1)
                out.append(" RIGHT } "); i += len(cmd); continue
            if cmd == "\\\\":
                out.append(" # "); i += len(cmd); continue
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
                    out.append(" root {" + latex_to_hwp(n) + "} of {" + latex_to_hwp(x) + "} ")
                else:
                    x, i = _read_arg(s, i + len(cmd))
                    out.append(" sqrt {" + latex_to_hwp(x) + "} ")
                continue
            if cmd in ACCENTS:
                a, i = _read_arg(s, i + len(cmd))
                out.append(" " + ACCENTS[cmd] + " {" + latex_to_hwp(a) + "} ")
                continue
            if cmd in (r"\underbrace", r"\overbrace"):
                body, i = _read_arg(s, i + len(cmd))
                mark, label, j = ("_" if cmd == r"\underbrace" else "^"), "", i
                while j < len(s) and s[j] == " ":
                    j += 1
                if j < len(s) and s[j] == mark:
                    label, i = _read_arg(s, j + 1)
                body, label = latex_to_hwp(body), latex_to_hwp(label)
                # 한컴은 UNDERBRACE {아래 글자} {본문}, OVERBRACE {본문} {위 글자} 순서다.
                if cmd == r"\underbrace":
                    out.append(" UNDERBRACE {" + label + "} {" + body + "} ")
                else:
                    out.append(" OVERBRACE {" + body + "} {" + label + "} ")
                continue
            if cmd in (r"\overset", r"\stackrel", r"\underset"):
                label, i = _read_arg(s, i + len(cmd))
                base, i = _read_arg(s, i)
                label, base = latex_to_hwp(label), latex_to_hwp(base)
                if cmd == r"\underset":
                    out.append(" REL " + base + " {} {" + label + "} ")
                else:
                    out.append(" REL " + base + " {" + label + "} {} ")
                continue
            if cmd in _STACKED_ARROWS:
                j, below = i + len(cmd), ""
                while j < len(s) and s[j] == " ":
                    j += 1
                if j < len(s) and s[j] == "[" and "]" in s[j:]:
                    k = s.index("]", j)
                    below, j = s[j + 1:k], k + 1
                above, i = _read_arg(s, j)
                out.append(" REL " + _STACKED_ARROWS[cmd] + " {" + latex_to_hwp(above)
                           + "} {" + latex_to_hwp(below) + "} ")
                continue
            if cmd == r"\not":
                # `\not\in`, `\not=`는 전용 기호로, 나머지는 한컴의 not 접두로 부정한다.
                target, j = _read_arg(s, i + len(cmd))
                if target == r"\in":
                    out.append(" notin "); i = j
                elif target == "=":
                    out.append(" != "); i = j
                else:
                    out.append(" not "); i += len(cmd)
                continue
            if cmd in (r"\left", r"\right"):
                j = i + len(cmd)
                while j < len(s) and s[j].isspace():
                    j += 1
                dm = re.match(r"\\[A-Za-z]+|\\.|.", s[j:], re.S)
                token = dm.group(0) if dm else ""
                j += len(token)
                if token in _BARE_DELIM:
                    out.append(" " + _BARE_DELIM[token] + " ")
                elif token and token != ".":
                    delim = _DELIM.get(token, token)
                    out.append((" LEFT " if cmd == r"\left" else " RIGHT ") + delim + " ")
                    if delim == "{" and cmd == r"\left":
                        set_depth += 1
                    elif delim == "}" and cmd == r"\right":
                        set_depth = max(0, set_depth - 1)
                i = j
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
        if c == "," and set_depth:
            out.append(",~")
            i += 1
            continue
        out.append(c)
        i += 1
    return re.sub(r"[ \t]+", " ", "".join(out)).strip()


# ---------------------------------------------------------------------------
# 수식 상자 크기 추정
# HWPX는 수식마다 가로·세로·기준선을 직접 적어 둔다. 아래 수치는 한글이 같은 스크립트에
# 대해 스스로 계산해 저장한 상자(HYhwpEQ, baseUnit 1000) 47개에 맞춘 em 단위 값이다.
# 세로와 기준선은 몇 % 안, 가로는 대체로 10% 안에서 맞는다.
# ---------------------------------------------------------------------------
_ASCENT, _DESCENT, _AXIS, _SCRIPT_SCALE, _RULE_GAP, _ROW_GAP = 0.84, 0.135, 0.36, 0.7, 0.15, 0.15
_EQ_TOKEN = re.compile(r'"[^"]*"|\+-|-\+|!=|<=>|<->|<=|>=|=>|->|<-|==|<<|>>|[A-Za-z]+|\d+(?:\.\d+)?|\S')
_GRID = {"matrix": 0.1, "pmatrix": 0.25, "bmatrix": 0.25, "dmatrix": 0.25, "cases": 0.8,
         "eqalign": 0.0, "pile": 0.0}
_TOP_ALIGNED = {"eqalign", "pile"}
_STACKED = {"sum": 1.15, "prod": 1.15, "coprod": 1.15, "union": 1.0, "inter": 1.0, "lim": 1.45}
_INTEGRALS = {"int": 1.0, "dint": 1.4, "tint": 1.8, "oint": 1.0}
_GLYPHS = {"(": 0.38, ")": 0.38, "[": 0.35, "]": 0.35, "|": 0.3, ",": 0.4, ".": 0.3, "'": 0.28,
           "!": 0.35, "/": 0.5, "`": 0.25, "~": 0.35, "=": 1.09, "+": 1.09, "-": 1.09,
           "<": 1.09, ">": 1.09, "&": 0.0}
_ACCENT_WORDS = set(ACCENTS.values())
_FUNCTION_WORDS = set("sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh log ln lg exp "
                      "max min det gcd mod arg".split())
_GREEK_WORDS = set("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi "
                   "omicron pi rho sigma tau upsilon phi chi psi omega varepsilon vartheta varpi "
                   "varsigma varphi hbar inf".split())
_SYMBOL_WORDS = set("times div cdot rarrow larrow lrarrow mapsto vert dline bot parallel deg "
                    "emptyset forall exist lnot wedge lor superset subset subseteq supseteq owns "
                    "in notin cup cap therefore because liter ldots cdots vdots ddots lfloor "
                    "rfloor lceil rceil sim approx equiv propto partial nabla angle triangle "
                    "circ ast pm mp".split())


def _eq_text_width(text):
    return sum(1.0 if ord(ch) > 0x2E7F else 0.68 if ch.isupper() or ord(ch) > 0x7F else 0.5
               for ch in text)


def _eq_split(tokens, separator):
    parts, depth = [[]], 0
    for token in tokens:
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        if token == separator and depth == 0:
            parts.append([])
        else:
            parts[-1].append(token)
    return parts


def _eq_stack(heights, first):
    """쌓인 행들의 (기준선 위, 아래) 높이. first 가 있으면 첫 행 기준선에 매달고, 없으면 수식 축에 가운데 맞춘다."""
    total = sum(heights) + _ROW_GAP * (len(heights) - 1)
    if first is not None:
        return first, total - first
    return total / 2 + _AXIS, total / 2 - _AXIS


class _EqLayout:
    """한컴 수식 스크립트를 (가로, 기준선 위, 기준선 아래) em 값으로 대략 조판한다."""

    def __init__(self, tokens):
        self.tokens, self.pos = tokens, 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def group(self):
        depth, start = 0, self.pos
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            self.pos += 1
            depth += token == "{"
            depth -= token == "}"
            if depth == 0:
                return self.tokens[start + 1:self.pos - 1]
        return self.tokens[start + 1:]

    def sequence(self):
        width, above, below = 0.0, _ASCENT, _DESCENT
        while self.peek() is not None:
            box = self.scripted()
            if self.peek() in ("over", "atop"):
                self.pos += 1
                lower = self.scripted()
                box = (max(box[0], lower[0]) + 0.43, _AXIS + _RULE_GAP + box[1] + box[2],
                       lower[1] + lower[2] + _RULE_GAP - _AXIS)
            width += box[0]
            above, below = max(above, box[1]), max(below, box[2])
        return width, above, below

    def scripted(self):
        word = (self.peek() or "").lower()
        width, above, below = self.atom()
        lower = upper = None
        while self.peek() in ("_", "^"):
            marker = self.tokens[self.pos]
            self.pos += 1
            if marker == "_":
                lower = self.atom()
            else:
                upper = self.atom()
        scripts = [box for box in (lower, upper) if box]
        if word in _STACKED:
            for box in scripts:
                width = max(width, _SCRIPT_SCALE * box[0] + 0.1)
            if upper:
                above += _SCRIPT_SCALE * (upper[1] + upper[2]) + 0.1
            if lower:
                below += _SCRIPT_SCALE * (lower[1] + lower[2]) + 0.1
            return width, above, below
        if word in _INTEGRALS:
            if scripts:
                width += _SCRIPT_SCALE * max(box[0] for box in scripts) + 0.38
            return width, (max(above, 1.6) if upper else above), (max(below, 0.98) if lower else below)
        if scripts:
            width += _SCRIPT_SCALE * max(box[0] for box in scripts) + 0.03
        if upper:
            above = max(above, max(0.35, above - 0.53) + _SCRIPT_SCALE * (upper[1] + upper[2]))
        if lower:
            below = max(below, max(0.0, below - _DESCENT) + _SCRIPT_SCALE * (lower[1] + lower[2]) - 0.35)
        return width, above, below

    def atom(self):
        token = self.peek()
        if token is None:
            return 0.0, _ASCENT, _DESCENT
        if token == "{":
            return _EqLayout(self.group()).rows()
        self.pos += 1
        word = token.lower()
        if word in ("left", "right"):
            if self.peek() is not None:
                self.pos += 1
            return 0.45, _ASCENT, _DESCENT
        if word == "sqrt":
            width, above, below = self.atom()
            return width + 1.15, above + 0.15, below
        if word == "root":
            degree = self.atom()
            if self.peek() == "of":
                self.pos += 1
            width, above, below = self.atom()
            return width + 1.1 + 0.3 * degree[0], above + 0.15, below
        if word in _GRID and self.peek() == "{":
            rows = [[_EqLayout(cell).sequence() for cell in _eq_split(row, "&")]
                    for row in _eq_split(self.group(), "#")]
            columns = max(len(row) for row in rows)
            width = sum(max((row[k][0] for row in rows if k < len(row)), default=0.0)
                        for k in range(columns))
            if word not in _TOP_ALIGNED:
                width += 0.675 * (columns - 1)
            heights = [max(cell[1] for cell in row) + max(cell[2] for cell in row) for row in rows]
            first = max(cell[1] for cell in rows[0]) if word in _TOP_ALIGNED else None
            return (width + _GRID[word],) + _eq_stack(heights, first)
        if word in ("underbrace", "overbrace"):
            first, second = self.atom(), self.atom()
            body, label = (second, first) if word == "underbrace" else (first, second)
            extra = 0.32 + _SCRIPT_SCALE * (label[1] + label[2])
            return (max(body[0], _SCRIPT_SCALE * label[0]),
                    body[1] + (extra if word == "overbrace" else 0),
                    body[2] + (extra if word == "underbrace" else 0))
        if word == "rel":
            base, upper, lower = self.atom(), self.atom(), self.atom()
            return (max(base[0], _SCRIPT_SCALE * upper[0], _SCRIPT_SCALE * lower[0]) + 0.3,
                    base[1] + (_SCRIPT_SCALE * (upper[1] + upper[2]) if upper[0] else 0),
                    base[2] + (_SCRIPT_SCALE * (lower[1] + lower[2]) if lower[0] else 0))
        if word in _ACCENT_WORDS or word == "box":
            width, above, below = self.atom()
            if word == "under":
                return width + 0.15, above, below + 0.15
            return width + 0.15, above + 0.2, below
        if word in ("rm", "it", "bold", "not"):
            return 0.0, _ASCENT, _DESCENT
        if word in _STACKED:
            return (_STACKED[word], 0.95, _DESCENT) if word == "lim" else (_STACKED[word], 0.92, 0.22)
        if word in _INTEGRALS:
            return _INTEGRALS[word], 1.1, 0.5
        if token.startswith('"'):
            return _eq_text_width(token[1:-1]), _ASCENT, _DESCENT
        if word in _FUNCTION_WORDS:
            return 0.5 * len(token) + 0.2, _ASCENT, _DESCENT
        if word in _GREEK_WORDS:
            return 0.62, _ASCENT, _DESCENT
        if word in _SYMBOL_WORDS or (len(token) > 1 and token.isupper()):
            return 1.25, _ASCENT, _DESCENT
        if len(token) > 1 and not token.isalnum():
            return 1.2, _ASCENT, _DESCENT
        if token[0].isdigit():
            return 0.5 * len(token), _ASCENT, _DESCENT
        if token in _GLYPHS:
            return _GLYPHS[token], _ASCENT, _DESCENT
        return _eq_text_width(token), _ASCENT, _DESCENT

    def rows(self):
        lines = [_EqLayout(row).sequence() for row in _eq_split(self.tokens, "#")]
        if len(lines) == 1:
            return lines[0]
        return (max(line[0] for line in lines),) + _eq_stack([line[1] + line[2] for line in lines],
                                                              lines[0][1])


def estimate_equation_box(script, base_unit=1000):
    """한컴 수식 스크립트의 (가로, 세로, 기준선 %)를 HWPUNIT 로 추정한다."""
    try:
        width, above, below = _EqLayout(_EQ_TOKEN.findall(script)).rows()
    except (IndexError, ValueError):   # 괄호가 안 맞는 등 조판할 수 없는 스크립트
        width, above, below = 0.6 * len(script), _ASCENT, _DESCENT
    height = above + below
    return (min(max(int((width + 0.1) * base_unit), 500), 42000), int(height * base_unit),
            round(above / height * 100))


# ===========================================================================
# 2.  Markdown parsing
# ===========================================================================
_IMG_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
_LIST_RE = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
_LATEX_COMMAND_RE = re.compile(
    r"\\(?:frac|dfrac|tfrac|sqrt|sum|prod|int|oint|lim|log|ln|exp|"
    r"sin|cos|tan|vec|hat|bar|overline|begin|left|right|infty|implies)(?![A-Za-z])"
)


def _clean_latex_source(text):
    """Normalize Markdown-escaped operators inside an identified math span."""
    return text.strip().replace(r"\_", "_").replace(r"\^", "^")


def _is_bare_bracket_math_start(text):
    """Recognize AI-style display math written as `[ ... ]`."""
    return text.startswith("[") and bool(_LATEX_COMMAND_RE.search(text))


_NUMBERED_LINE_RE = re.compile(r"^\s*(?:\*\*)?\d+\.")
_SOLUTION_HEADING_RE = re.compile(r"풀이|해설|정답|증명")
_SOLUTION_MARK_RE = re.compile(r"[가-힣]{0,4}(?:풀이|해설|증명)(?:과정)?")
_PROBLEM_MARK_RE = re.compile(r"(?:문제|문항|예제|유제)\d*")


def _marker_text(runs):
    """문단의 글자만 모아 공백·괄호·쌍점을 뺀 것(`**간단 풀이:**` -> `간단풀이`)."""
    text = "".join(val for kind, val in runs if kind in ("t", "b"))
    return re.sub(r"[\s:：\[\]()<>【】]", "", text)


def parse_markdown(text):
    return _parse_markdown(text)[0]


def _parse_markdown(text):
    """(blocks, steps) 를 돌려준다. steps 는 번호로 시작하지만 문항이 아니라
    풀이 단계·번호 목록인 문단의 blocks 인덱스 집합이다(문항 간격을 넣지 않을 대상).

    번호 문단을 문항이 아닌 것으로 보는 경우:
    - 빈 줄 없이 번호 줄이 바로 이어질 때 (`1. …` 다음 줄이 `2. …`): 번호 목록
    - `풀이`·`해설`·`정답`·`증명` 제목이나 `**간단 풀이:**` 같은 표시 문단 아래에 있을 때.
      제목으로 시작한 풀이는 같은 수준 이상의 다른 제목에서, 표시 문단으로 시작한 풀이는
      다음 제목·가로줄·`**문제:**` 표시에서 끝난다.
    """
    blocks, lines = [], text.replace("\r\n", "\n").split("\n")
    steps = set()
    solution_level = None      # 풀이 제목의 수준(#의 개수). None 이면 풀이 구간이 아님
    solution_mark = False      # `**간단 풀이:**` 같은 표시 문단 아래인지

    def numbered(k):
        return 0 <= k < len(lines) and bool(_NUMBERED_LINE_RE.match(lines[k]))

    def add_paragraph(k, runs):
        nonlocal solution_mark
        if numbered(k):
            if solution_level is not None or solution_mark or numbered(k - 1) or numbered(k + 1):
                steps.add(len(blocks))
        else:
            mark = _marker_text(runs)
            if _PROBLEM_MARK_RE.fullmatch(mark):
                solution_mark = False
            elif _SOLUTION_MARK_RE.fullmatch(mark) or mark.startswith("정답"):
                solution_mark = True
        blocks.append(("p", runs))

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        st = line.strip()
        if not st:
            i += 1; continue
        m_img = _IMG_RE.match(st)
        if m_img:
            blocks.append(("img", m_img.group(1), m_img.group(2).strip())); i += 1; continue
        if re.match(r"^-{3,}$", st):
            solution_mark = False
            blocks.append(("hr",)); i += 1; continue
        if st.startswith("```"):
            # 코드 블록: 울타리(```) 줄은 버리고, 안쪽 줄은 수식·굵게 해석 없이 그대로 싣는다.
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                blocks.append(("p", [("t", lines[i].rstrip())])); i += 1
            i += 1; continue
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
        if st.startswith("\\["):
            # ChatGPT류 AI가 흔히 쓰는 디스플레이 수식 델리미터: \[ ... \]
            buf = st
            while "\\]" not in buf and i + 1 < len(lines):
                i += 1; buf += "\n" + lines[i].strip()
            content = buf.strip()
            if content.startswith("\\["):
                content = content[2:]
            if content.endswith("\\]"):
                content = content[:-2]
            blocks.append(("eq", _clean_latex_source(content))); i += 1; continue
        if _is_bare_bracket_math_start(st):
            # Some AI outputs use bare square brackets instead of \[ ... \].
            # Only accept a standalone block containing a known LaTeX command
            # so ordinary Markdown links and bracketed prose remain text.
            buf = st
            while not buf.rstrip().endswith("]") and i + 1 < len(lines):
                i += 1; buf += "\n" + lines[i].strip()
            content = buf.strip()
            if content.startswith("[") and content.endswith("]"):
                blocks.append(("eq", _clean_latex_source(content[1:-1])))
                i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            solution_mark = False
            if _SOLUTION_HEADING_RE.search(m.group(2)):
                if solution_level is None or level < solution_level:
                    solution_level = level
            elif solution_level is not None and level <= solution_level:
                solution_level = None
            blocks.append(("h", level, m.group(2).strip())); i += 1; continue
        if _LIST_RE.match(line):
            add_paragraph(i, parse_inline(line.strip())); i += 1; continue
        # 시험지 Markdown은 빈 줄 없이도 문제/조건/해설을 줄 단위로 작성하는
        # 경우가 많다. 연속 줄을 한 문단으로 합치면 여러 수식 개체의 고정 폭이
        # 누적되어 한글에서 큰 공백과 겹침이 생기므로 원본 줄을 각각 보존한다.
        add_paragraph(i, parse_inline(line.strip()))
        i += 1
    return blocks, steps


def _split_table_row(row):
    """표의 한 행을 `|`로 나눈다. 수식 `$...$` 안의 `|`(절댓값 등)와 `\\|`는 칸을 나누지 않는다."""
    cells, in_math, k = [""], False, 0
    row = row.strip()
    while k < len(row):
        ch = row[k]
        if ch == "\\" and k + 1 < len(row):
            cells[-1] += row[k:k + 2]; k += 2; continue
        if ch == "$":
            in_math = not in_math
        if ch == "|" and not in_math:
            cells.append("")
        else:
            cells[-1] += ch
        k += 1
    if cells and not cells[0].strip():
        cells.pop(0)
    if cells and not cells[-1].strip():
        cells.pop()
    return [c.strip() for c in cells]


def parse_table(rows):
    cells = [_split_table_row(r) for r in rows]
    # 구분 행(`|---|:-:|--:|`)은 싣지 않는다. 대시가 하나뿐인 `:-:`도 구분 행이다.
    return [r for r in cells if not all(re.match(r"^:?-+:?$", c or "-") for c in r)]


# 인라인 수식 델리미터: $...$ (LaTeX 표준) 또는 \(...\) (ChatGPT 등 AI가 흔히 씀)
_INLINE_TOKEN_RE = re.compile(
    r"`([^`\n]*)`|\*\*(.+?)\*\*|\\\((.+?)\\\)|\$(?!\$)(.+?)(?<!\$)\$", re.S
)


def _split_parenthesized_latex(text):
    """Split `(\\frac...)`-style AI math from otherwise ordinary text."""
    runs, start, i = [], 0, 0
    while i < len(text):
        if text[i] != "(":
            i += 1
            continue
        depth, j = 1, i + 1
        while j < len(text) and depth:
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
            j += 1
        if depth:
            break
        content = text[i + 1:j - 1]
        if _LATEX_COMMAND_RE.search(content):
            if i > start:
                runs.append(("t", text[start:i]))
            runs.append(("eq", _clean_latex_source(content)))
            start = j
        i = j
    if start < len(text):
        runs.append(("t", text[start:]))
    return runs


def parse_inline(text):
    runs = []
    pos = 0
    for m in _INLINE_TOKEN_RE.finditer(text):
        if m.start() > pos:
            runs.extend(_split_parenthesized_latex(text[pos:m.start()]))
        if m.group(1) is not None:
            runs.append(("t", m.group(1)))
        elif m.group(2) is not None:
            # Bold text may itself contain inline equations. Parse its contents
            # again, preserving bold styling for text while keeping equations
            # as editable equation objects.
            for inner_kind, inner_value in parse_inline(m.group(2)):
                runs.append((inner_kind if inner_kind == "eq" else "b", inner_value))
        else:
            eq_content = m.group(3) if m.group(3) is not None else m.group(4)
            runs.append(("eq", _clean_latex_source(eq_content)))
        pos = m.end()
    if pos < len(text):
        runs.extend(_split_parenthesized_latex(text[pos:]))
    return _attach_particles(runs) if ATTACH_PARTICLES else runs


# 수식 바로 뒤에 붙여 쓰는 말: 조사, 조사끼리 겹친 꼴, '이다'의 활용형.
_PARTICLES = set("""은 는 이 가 을 를 의 에 와 과 도 로 으로 만 나 이나 며 이며 고 이고 면 이면 든 이든 란 이란 야 이야 들 씩 뿐 랑 이랑
    에서 에게 한테 께 까지 부터 보다 처럼 마다 조차 마저 밖에 만큼 대로 끼리 로서 으로서 로써 으로써 로부터 으로부터 라도 이라도 라고 이라고 라는 이라는 라면 이라면 라 이라
    에는 에도 에만 에서는 에서도 에서의 에의 에게는 에게서 까지의 까지는 부터의 부터는 와의 과의 와는 과는 와도 과도 로의 으로의 로는 으로는 로도 으로도 만의 만은 만을 만이 보다는 보다도
    은커녕 는커녕 이라고는 이라든지 라든지 이든지 든지 이거나 거나 이지만 지만 인데 이므로 므로 이어서 여서 이어야 여야 이라서 라서 이니 이니까 니까
    이다 다 입니다 이었다 였다 이었고 였고 일 인 임 임을 임이 임에 인지 일까 이어도 여도 이면서 면서 이자 이기 이기도 이기에""".split())


def _attach_particles(runs):
    """`$x$ 의 값`처럼 수식과 조사 사이에 띄어 쓴 공백을 없앤다(→ `x의 값`).
    조사가 아닌 낱말(`$x$ 그리고`)과 영문·숫자·문장부호 앞의 공백은 그대로 둔다."""
    out = list(runs)
    for k in range(1, len(out)):
        kind, val = out[k]
        if kind not in ("t", "b") or out[k - 1][0] != "eq":
            continue
        rest = val.lstrip(" \t")
        word = re.match(r"[가-힣]+", rest)
        if rest != val and word and word.group(0) in _PARTICLES:
            out[k] = (kind, rest)
    return out


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


def transform_blocks(blocks, split_choices=SPLIT_CHOICES, gap=GAP_BETWEEN_QUESTIONS, steps=()):
    """파싱된 blocks에 보기 줄바꿈/문항 간격을 적용한 새 blocks 반환.
    steps: 번호로 시작하지만 문항이 아닌(풀이 단계·번호 목록) 문단의 인덱스 — _parse_markdown 참고."""
    out = []
    seen_question = False
    for idx, b in enumerate(blocks):
        if b[0] != "p":
            out.append(b)
            continue
        runs = b[1]
        is_q = _is_question(runs) and idx not in steps
        if is_q and seen_question and gap:
            out.extend(("p", [("t", "")]) for _ in range(QUESTION_GAP_LINES))
        if split_choices:
            q_runs, c_runs = _split_choice_runs(runs)
            # A paragraph that already starts with ① contains choices only.
            # Do not emit its empty "question" half: that produced a visible
            # blank line between the question and the five choices.
            if q_runs:
                out.append(("p", q_runs))
            if c_runs is not None:
                out.append(("p", c_runs))
        else:
            out.append(("p", runs))
        if is_q:
            seen_question = True
    # Never emit an empty Markdown paragraph. In particular, a choices-only
    # paragraph must follow its question immediately in the HWPX body.
    return [b for b in out if not (b[0] == "p" and not b[1])]


# ===========================================================================
# 3.  HWPX emission
# ===========================================================================
_eq_id, _obj_id, _pid, _pic_id = 1200000000, 1300000000, 100, 1400000000
_images = []   # [(item_id, bindata_name, media_type, raw_bytes), ...] -- reset per convert call

# HWPUNIT: 1/7200 inch. 그림 표시 크기(sz/orgSz/imgRect)는 mm 기준,
# imgClip/imgDim 은 "이미지 원본 픽셀을 96dpi로 가정한" HWPUNIT 기준.
# (실제 한글이 저장한 hwpx를 역공학해서 확인한 값)
HWPUNIT_PER_MM = 7200 / 25.4
HWPUNIT_PER_PX96 = 7200 / 96


def esc(s):
    return html.escape(s, quote=True)


def _image_size(raw):
    """이미지 바이트의 헤더만 읽어서 (width_px, height_px, ext) 를 돌려준다. (외부 라이브러리 불필요)"""
    head = raw[:32]
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        w = int.from_bytes(head[16:20], "big")
        h = int.from_bytes(head[20:24], "big")
        return w, h, "png"
    if head[:2] == b"\xff\xd8":
        pos = 2
        while pos + 4 <= len(raw):
            if raw[pos] != 0xFF:
                break
            marker = raw[pos + 1]
            pos += 2
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h = int.from_bytes(raw[pos + 3:pos + 5], "big")
                w = int.from_bytes(raw[pos + 5:pos + 7], "big")
                return w, h, "jpg"
            seglen = int.from_bytes(raw[pos:pos + 2], "big")
            pos += seglen
        raise ValueError("JPEG SOF marker를 찾지 못했습니다")
    if head[:6] in (b"GIF87a", b"GIF89a"):
        w = int.from_bytes(head[6:8], "little")
        h = int.from_bytes(head[8:10], "little")
        return w, h, "gif"
    if head[:2] == b"BM":
        w = int.from_bytes(head[18:22], "little")
        h = abs(int.from_bytes(head[22:26], "little", signed=True))
        return w, h, "bmp"
    raise ValueError("지원하지 않는 이미지 형식입니다 (PNG/JPEG/GIF/BMP만 지원)")


_MEDIA_TYPE = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "bmp": "image/bmp"}


def picture_xml(raw, filename, width_mm=None, max_width_mm=150.0):
    global _pic_id
    px_w, px_h, ext = _image_size(raw)

    if width_mm is None:
        width_mm = max_width_mm
    width_mm = min(width_mm, max_width_mm)
    height_mm = width_mm * px_h / px_w

    idx = len(_images) + 1
    item_id = f"image{idx}"
    bindata_name = f"BinData/image{idx}.{ext}"
    _images.append((item_id, bindata_name, _MEDIA_TYPE[ext], raw))

    _pic_id += 3
    inst_id = _pic_id + 1
    w = round(width_mm * HWPUNIT_PER_MM)
    h = round(height_mm * HWPUNIT_PER_MM)
    cw = round(px_w * HWPUNIT_PER_PX96)
    ch = round(px_h * HWPUNIT_PER_PX96)

    return (
        f'<hp:run charPrIDRef="0"><hp:pic id="{_pic_id}" zOrder="0" numberingType="PICTURE" '
        f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" '
        f'groupLevel="0" instid="{inst_id}" reverse="0">'
        f'<hp:offset x="0" y="0"/>'
        f'<hp:orgSz width="{w}" height="{h}"/>'
        f'<hp:curSz width="0" height="0"/>'
        f'<hp:flip horizontal="0" vertical="0"/>'
        f'<hp:rotationInfo angle="0" centerX="{w // 2}" centerY="{h // 2}" rotateimage="1"/>'
        f'<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        f'<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
        f'<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
        f'<hc:img binaryItemIDRef="{item_id}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
        f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/>'
        f'<hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
        f'<hp:imgClip left="0" right="{cw}" top="0" bottom="{ch}"/>'
        f'<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        f'<hp:imgDim dimwidth="{cw}" dimheight="{ch}"/>'
        f'<hp:effects/>'
        f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
        f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
        f'vertOffset="0" horzOffset="0"/>'
        f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
        f'<hp:shapeComment>{esc(filename)}</hp:shapeComment>'
        f'</hp:pic><hp:t/></hp:run>'
    )


def equation_xml(latex):
    global _eq_id
    _eq_id += 7
    script = latex_to_hwp(latex)
    bu = 1000
    width, height, base_line = estimate_equation_box(script, bu)
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


def runs_from_inline(items, text_cp="0", bold_cp="9"):
    out = []
    for kind, val in items:
        if kind == "t":
            out.append(text_run(val, text_cp))
        elif kind == "b":
            out.append(text_run(val, bold_cp))
        else:
            out.append(equation_xml(val))
    return out or [text_run("")]


CELL_W = [7000, 17760, 17760]
A4_TEXT_WIDTH = 42520      # 기본 A4 양식의 본문 너비(HWPUNIT)
# 본문 한 단의 너비와 가운데 정렬 문단 모양 id. convert_md_to_hwpx_bytes 가 고른 양식에 맞춰
# 변환하는 동안만 바꿔 두며, 그 밖(qr_tool·capture_tool 의 직접 호출)에서는 기본값 그대로다.
_column_width = A4_TEXT_WIDTH
_center_para = "0"

def table_xml(cells):
    global _obj_id, _pid
    _obj_id += 11
    ncol = max(len(r) for r in cells)
    # 표 전체 너비를 단 너비에 맞춘다(2단 양식에서 표가 단 밖으로 넘치지 않도록).
    total_w = _column_width
    if ncol == 3:
        widths = [w * total_w // sum(CELL_W) for w in CELL_W]
    else:
        widths = [total_w // ncol] * ncol
    rowh, total_h = 2600, 2600 * len(cells)
    parts = [
        f'<hp:tbl id="{_obj_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
        f'rowCnt="{len(cells)}" colCnt="{ncol}" cellSpacing="0" borderFillIDRef="3" noAdjust="0">'
        f'<hp:sz width="{sum(widths)}" widthRelTo="ABSOLUTE" height="{total_h}" heightRelTo="ABSOLUTE" protect="0"/>'
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


def build_body(blocks, images=None):
    images = images or {}
    out = []
    for b in blocks:
        if b[0] == "h":
            cp = {1: "5", 2: "8", 3: "7"}.get(b[1], "7")
            # Headings can contain the same inline Markdown as body paragraphs.
            # Keep heading text styled while emitting math as editable equations.
            out.append(paragraph(runs_from_inline(parse_inline(b[2]), cp, cp)))
        elif b[0] == "hr":
            out.append(paragraph([text_run("─" * max(8, 40 * _column_width // A4_TEXT_WIDTH))]))
        elif b[0] == "eq":
            out.append(paragraph([equation_xml(b[1])], para_pr=_center_para))
        elif b[0] == "table":
            out.append(paragraph([table_xml(b[1])]))
        elif b[0] == "p":
            out.append(paragraph(runs_from_inline(b[1])))
        elif b[0] == "img":
            alt, ref = b[1], b[2]
            name = os.path.basename(ref)
            raw = images.get(name)
            if raw is None:
                out.append(paragraph([text_run(f"[이미지를 찾을 수 없습니다: {alt or ref} "
                                                f"— 같은 이름의 이미지 파일을 함께 업로드하세요]")]))
            else:
                try:
                    # 그림은 원래 크기(96dpi 기준)로 넣되 단 너비를 넘으면 단 너비에 맞춰 줄인다.
                    px_w = _image_size(raw)[0]
                    out.append(paragraph([picture_xml(
                        raw, name, width_mm=px_w * HWPUNIT_PER_PX96 / HWPUNIT_PER_MM,
                        max_width_mm=_column_width / HWPUNIT_PER_MM)]))
                except ValueError as e:
                    out.append(paragraph([text_run(f"[이미지 삽입 실패: {alt or name} - {e}]")]))
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
def _hashkey(raw):
    """content.hpf manifest item의 hashkey 속성값.
    실제 한글이 어떤 알고리즘을 쓰는지는 알 수 없지만(리버스엔지니어링으로 MD5가 아님을 확인),
    실제로 한글에서 임의값으로도 정상적으로 열리는 것을 확인했다(강제 검증됨) —
    그래도 재현 가능하도록 내용 기반 MD5를 써 둔다."""
    return base64.b64encode(hashlib.md5(raw).digest()).decode()


def reset_images():
    """picture_xml 이 모으는 그림 목록 초기화. 본문 XML을 만들기 전에 호출한다
    (같은 프로세스에서 여러 번 변환해도 이미지 번호가 섞이지 않도록)."""
    global _images
    _images = []


def package_hwpx(body_xml, section_patch=None, header_patch=None, template_b64=None):
    """본문 XML(hp:p 문단들) -> HWPX bytes.
    템플릿의 첫 문단(구역 설정) 뒤에 body_xml 을 붙이고, patch_header 를 적용한 뒤,
    picture_xml 로 모아 둔 그림을 BinData/ 와 manifest 에 넣어 zip 으로 묶는다.
    section_patch / header_patch: 완성된 section0.xml / header.xml 문자열을 받아 고친 문자열을 돌려주는 함수(선택).
    template_b64: 생략하면 기존 기본 템플릿을 사용한다."""
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(template_b64 or _BASE_ZIP_B64))) as base:
        files = {name: base.read(name) for name in base.namelist()}

    base_sec = files["Contents/section0.xml"].decode("utf-8")
    first_end = base_sec.index("</hp:p>") + len("</hp:p>")
    sec = base_sec[:first_end] + body_xml + "\n</hs:sec>\n"
    if section_patch:
        sec = section_patch(sec)
    files["Contents/section0.xml"] = sec.encode("utf-8")

    header = patch_header(files["Contents/header.xml"].decode("utf-8"))
    if header_patch:
        header = header_patch(header)
    files["Contents/header.xml"] = header.encode("utf-8")

    if _images:
        for item_id, bindata_name, media_type, raw in _images:
            files[bindata_name] = raw
        hpf = files["Contents/content.hpf"].decode("utf-8")
        items_xml = "".join(
            f'<opf:item id="{item_id}" href="{bindata_name}" media-type="{media_type}" '
            f'isEmbeded="1" hashkey="{esc(_hashkey(raw))}"/>'
            for item_id, bindata_name, media_type, raw in _images
        )
        hpf = hpf.replace("</opf:manifest>", items_xml + "</opf:manifest>", 1)
        files["Contents/content.hpf"] = hpf.encode("utf-8")

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
    return out.getvalue()


def _template_layout(template_b64):
    """양식의 (본문 한 단 너비 HWPUNIT, paraPr 개수)를 읽는다. 읽지 못하면 (A4 본문 너비, 0)."""
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(template_b64))) as base:
        section = base.read("Contents/section0.xml").decode("utf-8")
        header = base.read("Contents/header.xml").decode("utf-8")
    count = re.search(r'<hh:paraProperties itemCnt="(\d+)"', header)
    page = re.search(r'<hp:pagePr[^>]*\swidth="(\d+)"', section)
    margin = re.search(r"<hp:margin[^>]*/>", section)
    if not (page and margin):
        return A4_TEXT_WIDTH, int(count.group(1)) if count else 0
    width = int(page.group(1)) - sum(
        int(m.group(1)) for side in ("left", "right", "gutter")
        for m in [re.search(rf'\s{side}="(\d+)"', margin.group(0))] if m)
    columns = re.search(r"<hp:colPr[^>]*>", section)
    n_col = int(re.search(r'colCount="(\d+)"', columns.group(0)).group(1)) if columns else 1
    gap = re.search(r'sameGap="(\d+)"', columns.group(0)) if columns else None
    width = (width - (int(gap.group(1)) if gap else 0) * (n_col - 1)) // max(n_col, 1)
    return width, int(count.group(1)) if count else 0


def _add_center_parapr(header, new_id):
    """paraPr id=0 을 복제해 가운데 정렬로 바꾼 문단 모양을 new_id 로 덧붙인다(별행 수식용)."""
    pp0 = re.search(r'<hh:paraPr id="0".*?</hh:paraPr>', header, re.S)
    if not pp0:
        return header
    centered = pp0.group(0).replace('id="0"', f'id="{new_id}"', 1)
    centered = re.sub(r'(<hh:align horizontal=")[A-Z_]+(")', r"\g<1>CENTER\g<2>", centered, count=1)
    header = header.replace("</hh:paraProperties>", centered + "</hh:paraProperties>", 1)
    return re.sub(r'(<hh:paraProperties itemCnt=")(\d+)(")',
                  lambda m: f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}", header, count=1)


def convert_md_to_hwpx_bytes(md_text, split_choices=SPLIT_CHOICES,
                             gap=GAP_BETWEEN_QUESTIONS, images=None,
                             template=DEFAULT_OUTPUT_TEMPLATE):
    """Convert markdown text -> HWPX bytes using the selected page template.

    images: {파일명: bytes} (선택). template: OUTPUT_TEMPLATES의 표시 이름.
    Returns (data, n_blocks, n_equations).
    """
    global _column_width, _center_para
    reset_images()
    if template not in OUTPUT_TEMPLATES:
        raise ValueError(f"지원하지 않는 출력 양식입니다: {template}")
    blocks, steps = _parse_markdown(md_text)
    blocks = transform_blocks(blocks, split_choices=split_choices, gap=gap, steps=steps)
    column_width, n_para = _template_layout(OUTPUT_TEMPLATES[template])
    header_patch = None
    try:
        _column_width = column_width
        if CENTER_DISPLAY_EQUATIONS and n_para:
            _center_para = str(n_para)
            header_patch = lambda header: _add_center_parapr(header, n_para)
        data = package_hwpx(build_body(blocks, images=images), header_patch=header_patch,
                            template_b64=OUTPUT_TEMPLATES[template])
    finally:
        _column_width, _center_para = A4_TEXT_WIDTH, "0"
    n_eq = sum(1 for b in blocks if b[0] == "eq") + sum(
        1 for b in blocks if b[0] == "p" for k, _ in b[1] if k == "eq")
    return data, len(blocks), n_eq


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
               "수식은 편집 가능한 한글 수식 개체로 들어갑니다. "
               "`![설명](파일명)` 이미지 문법도 편집 가능한 그림 개체로 삽입됩니다. "
               f"(변환기 {CONVERTER_VERSION})")

    with st.expander("변환 옵션", expanded=False):
        template = st.radio("출력 양식", options=list(OUTPUT_TEMPLATES),
                            index=list(OUTPUT_TEMPLATES).index(DEFAULT_OUTPUT_TEMPLATE),
                            horizontal=True, key="md_template")
        split_choices = st.checkbox("5지선다 보기(①~⑤)를 문항 다음 줄로", value=SPLIT_CHOICES,
                                    key="md_split")
        gap = st.checkbox("문항과 다음 문항 사이에만 빈 줄 2줄 삽입 (문제-보기 사이는 붙임)", value=GAP_BETWEEN_QUESTIONS,
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

    img_files = st.file_uploader(
        "이미지 파일 (마크다운에서 `![설명](파일명)` 으로 참조한 것과 같은 이름이어야 합니다)",
        type=["png", "jpg", "jpeg", "gif", "bmp"], accept_multiple_files=True, key="md_images")
    images = {f.name: f.getvalue() for f in (img_files or [])}

    out_name = st.text_input("출력 파일 이름", value=f"{src_name}.hwpx", key="md_outname")

    if st.button("변환하기", type="primary", disabled=(md_text is None),
                 use_container_width=True, key="md_convert"):
        name = out_name.strip() or "output.hwpx"
        if not name.lower().endswith(".hwpx"):
            name += ".hwpx"
        try:
            data, nb, ne = convert_md_to_hwpx_bytes(md_text, split_choices=split_choices, gap=gap,
                                                     images=images, template=template)
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
            "- **수식**: 인라인 `$...$` / `\\(...\\)`, 디스플레이 `$$...$$` / `\\[...\\]` (LaTeX)\n"
            "- **집합 중괄호**: `A=\\{1,2,3\\}` 또는 `A=\\left\\{x\\mid x>0\\right\\}` "
            "(원소 사이는 `~`, `\\mid`는 `~ vert ~`로 변환)\n"
            "- **띄어쓰기**: `$x$ 의 값`처럼 수식과 조사 사이를 띄어 쓰면 `x의 값`으로 붙입니다 "
            "(조사가 아닌 낱말은 그대로 띄움)\n"
            "- **서식**: 제목(`#`~`######`), **굵게**, 가로줄(`---`), 표(`|...|`), "
            "별행 수식은 가운데 정렬\n"
            "- **이미지**: `![설명](파일명)` — 같은 이름의 이미지 파일을 위에서 함께 업로드하면 "
            "편집 가능한 그림 개체로 삽입됩니다 (PNG/JPEG/GIF/BMP). 원래 크기로 넣고 "
            "단 너비보다 클 때만 줄입니다\n"
            "- **출력 양식**: 기본 A4, A4 2단, B4 2단 중 선택\n"
            "- **문항 정리**: 5지선다 보기 줄바꿈, 문항 사이 빈 줄 2줄 (옵션에서 조절)\n"
            "- 출력은 HWPX 형식이며 한글 2014 이상에서 열립니다.\n"
            "- 아주 복잡한 수식(조건식 `cases` 등)은 열어서 한 번 확인을 권장합니다.")


if __name__ == "__main__":
    print("이 파일은 모듈입니다. 다음처럼 실행하세요:\n"
          "    pip install -r requirements.txt\n"
          "    streamlit run streamlit_app.py")
