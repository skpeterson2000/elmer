"""QR codes, in the standard library, because a hall may have no internet.

Players join a table by pointing a phone at the code on it. That code has to
be drawn on a Raspberry Pi that may be sitting in a hall with no uplink, on an
operating system that refuses `pip install` under PEP 668, from a package that
is not in apt. Every route out of that ends either in a dependency ELMER
cannot promise or in a hand-typed URL, and eight hundred people are not going
to hand-type a URL.

So: byte mode, error correction level M, versions 1 to 10, which covers any
join address a table will ever need. Written from ISO/IEC 18004 rather than
adapted from a library, and verified by reading the modules back out - see
`selftest`, which undoes the mask, walks the placement in reverse, repairs the
result with the same Reed-Solomon field, and checks the payload survives.

Level M corrects about 15% of codewords. That is the right trade for a card
propped on a table that will get thumbed, spilled on, and photographed at an
angle from four feet away.
"""

# ---------------------------------------------------------------- GF(256)
# The field the whole of Reed-Solomon happens in: byte values, with the
# primitive polynomial x^8 + x^4 + x^3 + x^2 + 1 that QR specifies.
PRIMITIVE = 0x11D
_EXP = [0] * 512
_LOG = [0] * 256


def _build_tables():
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= PRIMITIVE
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_build_tables()


def _mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _poly_mul(p, q):
    out = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        if a:
            for j, b in enumerate(q):
                out[i + j] ^= _mul(a, b)
    return out


def generator_poly(n):
    """The generator polynomial for n error-correction codewords."""
    g = [1]
    for i in range(n):
        g = _poly_mul(g, [1, _EXP[i]])
    return g


def ec_codewords(data, n):
    """The n Reed-Solomon check bytes for one block of data codewords."""
    g = generator_poly(n)
    rem = list(data) + [0] * n
    for i in range(len(data)):
        coef = rem[i]
        if coef:
            for j, gj in enumerate(g):
                rem[i + j] ^= _mul(gj, coef)
    return rem[len(data):]


# ------------------------------------------------------- version geometry
# For each version at level M: (ec per block, [(blocks, data codewords), ...]).
# The totals are checked in selftest against the version's codeword count, so
# a typo here cannot pass silently.
BLOCKS_M = {
    1:  (10, [(1, 16)]),
    2:  (16, [(1, 28)]),
    3:  (26, [(1, 44)]),
    4:  (18, [(2, 32)]),
    5:  (24, [(2, 43)]),
    6:  (16, [(4, 27)]),
    7:  (18, [(4, 31)]),
    8:  (22, [(2, 38), (2, 39)]),
    9:  (22, [(3, 36), (2, 37)]),
    10: (26, [(4, 43), (1, 44)]),
}

TOTAL_CODEWORDS = {1: 26, 2: 44, 3: 70, 4: 100, 5: 134,
                   6: 172, 7: 196, 8: 242, 9: 292, 10: 346}

ALIGNMENT = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
    7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50],
}


def size_of(version):
    return version * 4 + 17


def data_capacity(version):
    """How many data codewords a version holds at level M."""
    _, groups = BLOCKS_M[version]
    return sum(n * k for n, k in groups)


def _smallest_version(payload_len):
    for v in sorted(BLOCKS_M):
        count_bits = 8 if v <= 9 else 16
        # 4 mode bits + the character count + the bytes themselves.
        needed = (4 + count_bits + payload_len * 8 + 7) // 8
        if needed <= data_capacity(v):
            return v
    raise ValueError(f"{payload_len} bytes is too long for version 10 at "
                     f"level M - shorten the join address")


# ------------------------------------------------------------- bit stream
def _encode_data(payload, version):
    """Mode, length, bytes, terminator and padding, as a list of codewords."""
    count_bits = 8 if version <= 9 else 16
    bits = []

    def put(value, n):
        for i in range(n - 1, -1, -1):
            bits.append((value >> i) & 1)

    put(0b0100, 4)                       # byte mode
    put(len(payload), count_bits)
    for byte in payload:
        put(byte, 8)

    capacity = data_capacity(version) * 8
    put(0, min(4, capacity - len(bits)))  # terminator
    while len(bits) % 8:
        bits.append(0)
    words = [int("".join(str(b) for b in bits[i:i + 8]), 2)
             for i in range(0, len(bits), 8)]
    # The specified alternating pad, which is what a decoder expects to find:
    # 0xEC then 0x11, starting from the first pad byte regardless of how many
    # real codewords came before it.
    pad = (0xEC, 0x11)
    while len(words) < data_capacity(version):
        words.append(pad[(len(words) - len(bits) // 8) % 2])
    return words


def _interleave(words, version):
    """Split into blocks, add check bytes, and interleave as the spec says."""
    ec_per, groups = BLOCKS_M[version]
    blocks, at = [], 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(words[at:at + size])
            at += size
    ecs = [ec_codewords(b, ec_per) for b in blocks]

    out = []
    for i in range(max(len(b) for b in blocks)):
        for b in blocks:
            if i < len(b):
                out.append(b[i])
    for i in range(ec_per):
        for e in ecs:
            out.append(e[i])
    return out


# ---------------------------------------------------------------- matrix
def _reserved(version):
    """Which cells hold function patterns and may not carry data."""
    n = size_of(version)
    res = [[False] * n for _ in range(n)]

    def block(r0, c0, h, w):
        for r in range(r0, r0 + h):
            for c in range(c0, c0 + w):
                if 0 <= r < n and 0 <= c < n:
                    res[r][c] = True

    # Finder, separator, format information and the dark module, as one
    # rectangle per corner. Reserving only the finder and separator leaves the
    # format cells looking free: data gets written into them and the format
    # information then overwrites it, which corrupts the stream a byte at a
    # time and is invisible until something reads the code back.
    block(0, 0, 9, 9)                    # top left, including row 8 and col 8
    block(0, n - 8, 9, 8)                # top right
    block(n - 8, 0, 8, 9)                # bottom left, including the dark module
    block(6, 0, 1, n)                    # timing
    block(0, 6, n, 1)
    for r in ALIGNMENT[version]:
        for c in ALIGNMENT[version]:
            if (r < 8 and c < 8) or (r < 8 and c > n - 9) or \
               (r > n - 9 and c < 8):
                continue
            block(r - 2, c - 2, 5, 5)
    if version >= 7:
        block(n - 11, 0, 3, 6)
        block(0, n - 11, 6, 3)
    return res


def _draw_function(m, version):
    n = size_of(version)

    def finder(r0, c0):
        for r in range(-1, 8):
            for c in range(-1, 8):
                if not (0 <= r0 + r < n and 0 <= c0 + c < n):
                    continue
                edge = max(abs(r - 3), abs(c - 3))
                m[r0 + r][c0 + c] = 1 if edge in (0, 1, 3) else 0

    finder(0, 0)
    finder(0, n - 7)
    finder(n - 7, 0)
    for i in range(n):
        bit = 1 if i % 2 == 0 else 0
        if m[6][i] is None:
            m[6][i] = bit
        if m[i][6] is None:
            m[i][6] = bit
    for r in ALIGNMENT[version]:
        for c in ALIGNMENT[version]:
            if (r < 8 and c < 8) or (r < 8 and c > n - 9) or \
               (r > n - 9 and c < 8):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    m[r + dr][c + dc] = 1 if max(abs(dr), abs(dc)) != 1 else 0
    m[n - 8][8] = 1                      # the dark module, always set


def _format_bits(mask):
    """BCH(15,5) format information for level M, XORed with the spec mask."""
    value = (0b00 << 3) | mask          # level M is 00
    bits = value << 10
    for i in range(4, -1, -1):
        if bits & (1 << (i + 10)):
            bits ^= 0x537 << i
    return ((value << 10) | bits) ^ 0x5412


def _version_bits(version):
    """BCH(18,6) version information, for versions 7 and up."""
    bits = version << 12
    for i in range(5, -1, -1):
        if bits & (1 << (i + 12)):
            bits ^= 0x1F25 << i
    return (version << 12) | bits


def _place_format(m, version, mask):
    n = size_of(version)
    bits = _format_bits(mask)
    for i in range(15):
        bit = (bits >> i) & 1
        # Copy one: up column 8 beside the top-left finder, then left along
        # row 8. Numbering runs from the least significant bit at (0, 8) to
        # the most significant at (8, 0) - the mirror of copy two, which is
        # what makes a reader able to check one against the other.
        #
        # This was written transposed, with every row and column the wrong way
        # round. Copy two was right, so the two copies disagreed and no reader
        # could recover the mask - the code looked perfect and scanned as
        # nothing. A round trip through this module's own reader could never
        # have caught it, because the reader made the same mistake.
        if i < 6:
            m[i][8] = bit
        elif i == 6:
            m[7][8] = bit
        elif i == 7:
            m[8][8] = bit
        elif i == 8:
            m[8][7] = bit
        else:
            m[8][14 - i] = bit
        # Copy two: bits 0-6 run up column 8 from the bottom, bits 7-14 run
        # along row 8 from the right. Bit 7 belongs in the row, not the
        # column - (n-8, 8) is the dark module and is not format information.
        if i < 7:
            m[n - 1 - i][8] = bit
        else:
            m[8][n - 15 + i] = bit
    if version >= 7:
        vbits = _version_bits(version)
        for i in range(18):
            bit = (vbits >> i) & 1
            r, c = i // 3, i % 3
            m[n - 11 + c][r] = bit
            m[r][n - 11 + c] = bit


def _mask_fn(mask):
    return (
        lambda r, c: (r + c) % 2 == 0,
        lambda r, c: r % 2 == 0,
        lambda r, c: c % 3 == 0,
        lambda r, c: (r + c) % 3 == 0,
        lambda r, c: (r // 2 + c // 3) % 2 == 0,
        lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
        lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
        lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
    )[mask]


def _place_data(m, res, version, stream):
    """The zigzag: two columns at a time, right to left, alternating up/down."""
    n = size_of(version)
    bits = [(w >> i) & 1 for w in stream for i in range(7, -1, -1)]
    at = 0
    col = n - 1
    upward = True
    while col > 0:
        if col == 6:                     # the vertical timing column is skipped
            col -= 1
        rows = range(n - 1, -1, -1) if upward else range(n)
        for r in rows:
            for c in (col, col - 1):
                if res[r][c]:
                    continue
                m[r][c] = bits[at] if at < len(bits) else 0
                at += 1
        upward = not upward
        col -= 2
    return at


def _penalty(m, n):
    """The spec's four penalty rules, used to choose the least-bad mask."""
    score = 0
    for line in list(m) + [list(col) for col in zip(*m)]:
        run, prev = 1, line[0]
        for cell in line[1:]:
            if cell == prev:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run, prev = 1, cell
        if run >= 5:
            score += 3 + (run - 5)
    for r in range(n - 1):
        for c in range(n - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    pattern = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
    for line in list(m) + [list(col) for col in zip(*m)]:
        for i in range(n - 10):
            if line[i:i + 11] == pattern or line[i:i + 11] == pattern[::-1]:
                score += 40
    dark = sum(sum(row) for row in m)
    score += 10 * (abs(dark * 100 // (n * n) - 50) // 5)
    return score


def encode(text, version=None):
    """The QR matrix for `text`, as a list of rows of 0/1."""
    payload = text.encode("utf-8")
    version = version or _smallest_version(len(payload))
    words = _encode_data(payload, version)
    stream = _interleave(words, version)
    res = _reserved(version)
    n = size_of(version)

    best, best_score = None, None
    for mask in range(8):
        m = [[None] * n for _ in range(n)]
        _draw_function(m, version)
        _place_data(m, res, version, stream)
        fn = _mask_fn(mask)
        for r in range(n):
            for c in range(n):
                if not res[r][c] and m[r][c] is not None and fn(r, c):
                    m[r][c] ^= 1
        _place_format(m, version, mask)
        grid = [[cell or 0 for cell in row] for row in m]
        score = _penalty(grid, n)
        if best_score is None or score < best_score:
            best, best_score = grid, score
    return best


def as_svg(text, module=8, quiet=4, dark="#000", light="#fff"):
    """The code as an SVG, which is what a browser wants and scales cleanly."""
    grid = encode(text)
    n = len(grid)
    side = (n + quiet * 2) * module
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{side}" '
             f'height="{side}" viewBox="0 0 {side} {side}" '
             f'shape-rendering="crispEdges" role="img" '
             f'aria-label="Join code">',
             f'<rect width="{side}" height="{side}" fill="{light}"/>']
    for r, row in enumerate(grid):
        c = 0
        while c < n:
            if row[c]:
                start = c
                while c < n and row[c]:
                    c += 1
                parts.append(
                    f'<rect x="{(start + quiet) * module}" '
                    f'y="{(r + quiet) * module}" '
                    f'width="{(c - start) * module}" height="{module}" '
                    f'fill="{dark}"/>')
            else:
                c += 1
    parts.append("</svg>")
    return "".join(parts)


# ------------------------------------------------------------- verification
def _read_back(grid, version):
    """Walk the placement in reverse and recover the data codewords.

    Written deliberately as its own traversal rather than by reusing the
    writer, so that a mistake in the zigzag shows up as a mismatch instead of
    being made twice and cancelling out.
    """
    n = size_of(version)
    res = _reserved(version)
    # Recover the mask from the format information, the way a reader does.
    raw = 0
    for i in range(15):
        if i < 6:
            bit = grid[i][8]
        elif i == 6:
            bit = grid[7][8]
        elif i == 7:
            bit = grid[8][8]
        elif i == 8:
            bit = grid[8][7]
        else:
            bit = grid[8][14 - i]
        raw |= bit << i
    mask = (raw ^ 0x5412) >> 10 & 0b111

    fn = _mask_fn(mask)
    bits = []
    col, upward = n - 1, True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(n - 1, -1, -1) if upward else range(n)
        for r in rows:
            for c in (col, col - 1):
                if res[r][c]:
                    continue
                bit = grid[r][c]
                if fn(r, c):
                    bit ^= 1
                bits.append(bit)
        upward = not upward
        col -= 2

    words = [int("".join(str(b) for b in bits[i:i + 8]), 2)
             for i in range(0, len(bits) - len(bits) % 8, 8)]

    # Undo the interleave.
    ec_per, groups = BLOCKS_M[version]
    sizes = []
    for count, size in groups:
        sizes += [size] * count
    blocks = [[] for _ in sizes]
    at = 0
    for i in range(max(sizes)):
        for b, size in enumerate(sizes):
            if i < size:
                blocks[b].append(words[at])
                at += 1
    return [w for b in blocks for w in b]


def _decode_payload(data_words, version):
    """Pull the text back out of the recovered data codewords."""
    bits = []
    for w in data_words:
        for i in range(7, -1, -1):
            bits.append((w >> i) & 1)
    mode = int("".join(str(b) for b in bits[:4]), 2)
    if mode != 0b0100:
        raise ValueError(f"expected byte mode, read {mode:04b}")
    count_bits = 8 if version <= 9 else 16
    length = int("".join(str(b) for b in bits[4:4 + count_bits]), 2)
    start = 4 + count_bits
    out = bytearray()
    for i in range(length):
        chunk = bits[start + i * 8:start + (i + 1) * 8]
        out.append(int("".join(str(b) for b in chunk), 2))
    return out.decode("utf-8")


def selftest(verbose=False):
    """Check the tables, the field, and a round trip through real matrices."""
    problems = []

    # The block tables must account for exactly the version's codewords.
    for v, total in TOTAL_CODEWORDS.items():
        ec_per, groups = BLOCKS_M[v]
        got = sum(count * (size + ec_per) for count, size in groups)
        if got != total:
            problems.append(f"version {v}: blocks total {got}, want {total}")

    # GF(256) must be a field: every non-zero element has an inverse.
    for a in range(1, 256):
        inv = _EXP[255 - _LOG[a]] if _LOG[a] else 1
        if _mul(a, inv) != 1:
            problems.append(f"GF(256): {a} has no inverse")
            break

    # A known Reed-Solomon generator, as a check on the polynomial maths.
    if generator_poly(10)[0] != 1 or len(generator_poly(10)) != 11:
        problems.append("generator polynomial for 10 EC codewords is wrong")

    # Round trip: encode, read the modules back, decode.
    cases = ["http://192.168.1.50:5000/j/7",
             "http://elmer.local:5000/j/12?t=Table%2012",
             "A", "x" * 100]
    for text in cases:
        try:
            version = _smallest_version(len(text.encode()))
            grid = encode(text)
            if len(grid) != size_of(version):
                problems.append(f"{text[:20]!r}: matrix is the wrong size")
                continue
            back = _decode_payload(_read_back(grid, version), version)
            if back != text:
                problems.append(f"{text[:20]!r}: round trip gave {back[:20]!r}")
            elif verbose:
                print(f"  ok   v{version} {size_of(version)}x{size_of(version)}"
                      f"  {text[:44]}")
        except Exception as exc:
            problems.append(f"{text[:20]!r}: {type(exc).__name__}: {exc}")

    # The two format copies must agree. This is the only check here that does
    # not rest on the writer's own assumptions: a copy placed wrongly still
    # round-trips through a reader that shares the mistake, but it cannot
    # match the copy on the other side of the matrix.
    for text in ("A", "http://192.168.1.50:5000/j/7", "x" * 100):
        grid = encode(text)
        one, two = _read_format(grid, 1), _read_format(grid, 2)
        if one != two:
            problems.append(f"{text[:16]!r}: format copies disagree "
                            f"({one:015b} vs {two:015b})")
        else:
            # Unmasking leaves five data bits at the top: two of error
            # correction level, then three of mask number.
            data = (one ^ 0x5412) >> 10
            if (data >> 3) & 0b11 != 0b00:
                problems.append(f"{text[:16]!r}: format says level "
                                f"{(data >> 3) & 0b11:02b}, not M")
            if (data & 0b111) > 7:
                problems.append(f"{text[:16]!r}: mask out of range")

    # The three finder patterns must be where a scanner looks for them.
    grid = encode("test")
    n = len(grid)
    for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):
        if grid[r0 + 3][c0 + 3] != 1 or grid[r0 + 1][c0 + 2] != 0:
            problems.append(f"finder pattern at {r0},{c0} is malformed")
    if grid[n - 8][8] != 1:
        problems.append("the dark module is not set")
    return problems


def _read_format(grid, which):
    """Read one of the two format-information copies out of a finished matrix.

    Both copies carry the same fifteen bits in different places. Reading them
    separately and comparing is the one structural check available from inside
    this module that does not simply repeat the writer's own assumptions - a
    transposed copy agrees with a reader that shares the mistake, but it cannot
    agree with the *other* copy.
    """
    n = len(grid)
    raw = 0
    for i in range(15):
        if which == 1:
            if i < 6:
                bit = grid[i][8]
            elif i == 6:
                bit = grid[7][8]
            elif i == 7:
                bit = grid[8][8]
            elif i == 8:
                bit = grid[8][7]
            else:
                bit = grid[8][14 - i]
        else:
            bit = grid[n - 1 - i][8] if i < 7 else grid[8][n - 15 + i]
        raw |= bit << i
    return raw
