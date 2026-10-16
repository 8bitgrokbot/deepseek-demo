"""小さなユーティリティ集。各関数の仕様は docstring に書かれている通り。"""


def moving_average(values, window):
    """values の長さ window の移動平均を返す。

    結果は「各位置から始まる window 個の平均」を先頭から順に並べたリストで、
    長さは len(values) - window + 1。window が len(values) より大きい場合は空リスト。
    例: moving_average([1, 2, 3, 4], 2) -> [1.5, 2.5, 3.5]
    window が 1 未満の場合は ValueError を送出する。
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    result = []
    for i in range(len(values) - window + 1):
        chunk = values[i:i + window]
        result.append(sum(chunk) / window)
    return result


def add_tag(item, tags=None):
    """item のコピーに tags を追加した新しいリストを返す。

    tags を省略した場合は、item をそのまま（コピーして）返す。
    呼び出しをまたいで状態が残ってはならない。
    例: add_tag(["a"], ["b"]) -> ["a", "b"]
        add_tag(["a"]) -> ["a"]（何度呼んでも同じ）
    """
    result = list(item)
    if tags:
        result.extend(tags)
    return result


def parse_duration(text):
    """"1h30m"、"45s"、"2h5m10s" のような文字列を秒数(int)に変換する。

    使える単位は h(時間)、m(分)、s(秒)。順序は h, m, s の順で、省略可能。
    空文字列や、単位の無い数字だけの文字列、未知の単位を含む場合は ValueError を送出する。
    例: parse_duration("1h30m") -> 5400
        parse_duration("45s") -> 45
    """
    import re
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", text)
    if not text or m is None:
        raise ValueError("invalid duration: %r" % text)
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def percent_change(old, new):
    """old から new への変化率(%)を、小数第1位で四捨五入して返す。

    old が 0 の場合は None を返す。
    例: percent_change(200, 250) -> 25.0
        percent_change(80, 60) -> -25.0
    """
    if old == 0:
        return None
    return round((new - old) / old * 100, 1)


def chunk(seq, size):
    """seq を長さ size ごとのリストに分割して返す。最後の要素は短くてもよい。

    例: chunk([1, 2, 3, 4, 5], 2) -> [[1, 2], [3, 4], [5]]
    size が 1 未満の場合は ValueError を送出する。
    """
    if size < 1:
        raise ValueError("size must be >= 1")
    return [list(seq[i:i + size]) for i in range(0, len(seq), size)]
