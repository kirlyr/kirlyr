#!/usr/bin/env python3
"""Chess.com last-game SVG replay for a GitHub profile README.

Run locally:
    pip install python-chess==1.999
    python scripts/chess_replay.py

Demo (does not need Internet or python-chess):
    python scripts/chess_replay.py --demo
"""

from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

BASE_DIR = Path(__file__).resolve().parents[1]
API_ROOT = "https://api.chess.com/pub/player"
SYMBOLS = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
}
BOARD_X, BOARD_Y, CELL = 65, 138, 76
BOARD_W = CELL * 8
SVG_W, SVG_H = 738, 860


def h(value: object) -> str:
    return escape(str(value), {'"': '&quot;', "'": '&apos;'})


def api_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "kirlyr-chess-replay/1.0 (+https://github.com/kirlyr/kirlyr)",
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def last_game(username: str) -> dict:
    archives_url = f"{API_ROOT}/{username.lower()}/games/archives"
    archives = api_json(archives_url).get("archives") or []
    if not archives:
        raise RuntimeError(f"No public monthly game archives found for Chess.com user '{username}'.")

    # Archives are ascending by month. Walk backwards until a completed PGN is found.
    for archive_url in reversed(archives):
        games = api_json(archive_url).get("games") or []
        eligible = [
            game for game in games
            if game.get("pgn") and game.get("rules", "chess") == "chess"
        ]
        if eligible:
            return max(eligible, key=lambda game: int(game.get("end_time") or 0))
    raise RuntimeError(f"No standard completed PGN games available for Chess.com user '{username}'.")


def parse_game(game: dict, username: str) -> tuple[list[dict], dict]:
    try:
        import chess
        import chess.pgn
    except ModuleNotFoundError as error:
        raise RuntimeError("Install python-chess first: python -m pip install python-chess==1.999") from error

    pgn_text = game.get("pgn") or ""
    parsed = chess.pgn.read_game(io.StringIO(pgn_text))
    if parsed is None:
        raise RuntimeError("Chess.com returned no parseable PGN for this game.")
    if parsed.errors:
        raise RuntimeError("PGN contains invalid moves: " + "; ".join(map(str, parsed.errors[:2])))

    board = parsed.board()
    white_name = str(game.get("white", {}).get("username") or parsed.headers.get("White") or "White")
    black_name = str(game.get("black", {}).get("username") or parsed.headers.get("Black") or "Black")
    is_black = black_name.casefold() == username.casefold()
    player_side = "black" if is_black else "white"
    states = [{"pieces": piece_map(board), "san": "START", "from": None, "to": None, "move": 0}]

    for move_number, move in enumerate(parsed.mainline_moves(), 1):
        san = board.san(move)
        origin = chess.square_name(move.from_square)
        destination = chess.square_name(move.to_square)
        board.push(move)
        states.append({
            "pieces": piece_map(board),
            "san": san,
            "from": origin,
            "to": destination,
            "move": move_number,
        })

    if len(states) == 1:
        raise RuntimeError("The latest PGN contains no completed moves.")
    meta = {
        "username": username,
        "white": white_name,
        "black": black_name,
        "result": str(parsed.headers.get("Result") or "*"),
        "date": str(parsed.headers.get("UTCDate") or parsed.headers.get("Date") or ""),
        "time_control": str(game.get("time_control") or parsed.headers.get("TimeControl") or ""),
        "game_url": str(game.get("url") or f"https://www.chess.com/member/{username}"),
        "player_side": player_side,
        "ply": len(states) - 1,
    }
    return states, meta


def piece_map(board) -> dict[str, str]:
    import chess
    return {chess.square_name(square): piece.symbol() for square, piece in board.piece_map().items()}


def square_xy(name: str, flipped: bool) -> tuple[int, int]:
    file_index = ord(name[0]) - ord("a")
    rank_index = int(name[1]) - 1
    col = 7 - file_index if flipped else file_index
    row = rank_index if flipped else 7 - rank_index
    return BOARD_X + col * CELL, BOARD_Y + row * CELL


def square_center(name: str, flipped: bool) -> tuple[int, int]:
    x, y = square_xy(name, flipped)
    return x + CELL // 2, y + CELL // 2


def colors_and_caption(meta: dict) -> tuple[str, str]:
    side = meta["player_side"]
    if meta["result"] == "1/2-1/2":
        return "DRAW", "#d29922"
    if meta["result"] == ("1-0" if side == "white" else "0-1"):
        return "WIN", "#3fb950"
    if meta["result"] in ("1-0", "0-1"):
        return "LOSS", "#f85149"
    return "GAME", "#8b949e"


def scene_markup(state: dict, index: int, flipped: bool, durations: list[float]) -> str:
    result = [f'<g class="frame frame-{index}">']
    if state["from"] and state["to"]:
        for square in (state["from"], state["to"]):
            sx, sy = square_xy(square, flipped)
            result.append(f'<rect x="{sx}" y="{sy}" width="{CELL}" height="{CELL}" fill="#e3b341" opacity="0.30"/>')

    # Keep the moving piece separate so its start/destination coordinates can glide.
    to_square = state["to"]
    for square, piece in sorted(state["pieces"].items()):
        if to_square == square:
            continue
        result.append(piece_use(piece, square, flipped))

    if to_square and to_square in state["pieces"]:
        piece = state["pieces"][to_square]
        ox, oy = square_center(state["from"], flipped)
        tx, ty = square_center(to_square, flipped)
        result.append(f'<g class="moving moving-{index}" style="--dx:{ox-tx}px;--dy:{oy-ty}px">')
        result.append(piece_use(piece, to_square, flipped))
        result.append('</g>')

    # One small status chip is visible per replay step.
    label = f'{(index + 1)//2}{". " if index % 2 else "... "}{state["san"]}' if index else 'Initial position'
    result.extend([
        f'<text x="65" y="815" fill="#c9d1d9" font-size="20" font-family="Arial, sans-serif">{h(label)}</text>',
        f'<text x="670" y="815" text-anchor="end" fill="#8b949e" font-size="17" font-family="Arial, sans-serif">{index}/{len(durations)-1} ply</text>',
        '</g>',
    ])
    return "\n".join(result)


def piece_use(piece: str, square: str, flipped: bool) -> str:
    cx, cy = square_center(square, flipped)
    return f'<use href="#piece-{piece}" x="{cx}" y="{cy}"/>'


def pct(value: float) -> str:
    return format(value * 100, '.6f').rstrip('0').rstrip('.') or '0'


def render_svg(states: list[dict], meta: dict) -> str:
    """Render self-contained animated SVG; no external fonts/images/scripts."""
    flipped = meta["player_side"] == "black"
    # Start 1.5s, each move 1.15s, linger 2.5s at the end.
    durations = [1.5] + [1.15] * (len(states) - 2) + [2.5]
    total = sum(durations)
    frame_css: list[str] = []
    cursor = 0.0
    for index, delay in enumerate(durations):
        start = cursor / total
        end = (cursor + delay) / total
        if index == 0:
            frame_css.append(
                f'@keyframes scene-{index}{{0%{{opacity:1}}{pct(end)}%{{opacity:0}}100%{{opacity:0}}}}'
            )
        else:
            frame_css.append(
                f'@keyframes scene-{index}{{0%{{opacity:0}}{pct(start)}%{{opacity:1}}{pct(end)}%{{opacity:0}}100%{{opacity:0}}}}'
            )
        frame_css.append(f'.frame-{index}{{animation:scene-{index} {total:.2f}s steps(1,end) infinite}}')
        if index and states[index]["from"] and states[index]["to"]:
            move_end = min(cursor + 0.45, cursor + delay)
            frame_css.append(
                f'@keyframes slide-{index}{{0%,{pct(start)}%{{transform:translate(var(--dx),var(--dy))}}'
                f'{pct(move_end/total)}%,100%{{transform:translate(0,0)}}}}'
            )
            frame_css.append(f'.moving-{index}{{animation:slide-{index} {total:.2f}s linear infinite}}')
        cursor += delay

    title, highlight = colors_and_caption(meta)
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" viewBox="0 0 {SVG_W} {SVG_H}" role="img" aria-label="Animated replay of the last Chess.com game by {h(meta["username"])}">',
        f'<title>Last Chess.com game — {h(meta["white"])} vs {h(meta["black"])}</title>',
        '<desc>Animated move-by-move chess replay generated from a public Chess.com PGN. Animation loops automatically.</desc>',
        '<defs>',
        '<style><![CDATA[',
        '.frame{opacity:0}.frame-0{opacity:1}',
        *frame_css,
        ']]></style>',
    ]
    for kind, symbol in SYMBOLS.items():
        fill = '#ffffff' if kind.isupper() else '#20252c'
        stroke = '#30363d' if kind.isupper() else '#f0f6fc'
        svg.append(
            f'<g id="piece-{kind}"><text text-anchor="middle" dominant-baseline="central" '
            f'font-family="DejaVu Sans,Segoe UI Symbol,Arial Unicode MS,sans-serif" font-size="61" '
            f'font-weight="bold" fill="{fill}" stroke="{stroke}" stroke-width="1.5" paint-order="stroke"'
            f'>{symbol}</text></g>'
        )
    svg.extend([
        '</defs>',
        '<rect width="738" height="860" rx="22" fill="#0d1117"/>',
        '<rect x="23" y="22" width="692" height="815" rx="17" fill="#161b22" stroke="#30363d"/>',
        '<text x="65" y="74" fill="#f0f6fc" font-size="28" font-weight="bold" font-family="Arial,sans-serif">LAST GAME REPLAY</text>',
        f'<text x="65" y="107" fill="#8b949e" font-size="17" font-family="Arial,sans-serif">{h(meta["white"])}  vs  {h(meta["black"])}</text>',
        f'<rect x="570" y="51" width="100" height="38" rx="18" fill="{highlight}" opacity="0.17"/>',
        f'<text x="620" y="77" text-anchor="middle" fill="{highlight}" font-size="18" font-weight="bold" font-family="Arial,sans-serif">{h(title)}</text>',
        f'<rect x="{BOARD_X}" y="{BOARD_Y}" width="{BOARD_W}" height="{BOARD_W}" rx="3" fill="#8b949e"/>',
    ])

    for row in range(8):
        for col in range(8):
            x, y = BOARD_X + col * CELL, BOARD_Y + row * CELL
            color = '#7796aa' if (row + col) % 2 == 0 else '#253546'
            svg.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{color}"/>')

    # File/rank labels, respecting board orientation.
    for col in range(8):
        file_name = chr(ord('h') - col) if flipped else chr(ord('a') + col)
        svg.append(f'<text x="{BOARD_X + col * CELL + CELL//2}" y="769" text-anchor="middle" fill="#8b949e" font-size="15" font-family="Arial,sans-serif">{file_name}</text>')
    for row in range(8):
        rank_name = str(row + 1) if flipped else str(8 - row)
        svg.append(f'<text x="47" y="{BOARD_Y + row * CELL + 43}" text-anchor="middle" fill="#8b949e" font-size="15" font-family="Arial,sans-serif">{rank_name}</text>')

    for index, state in enumerate(states):
        svg.append(scene_markup(state, index, flipped, durations))

    svg.extend([
        f'<text x="65" y="784" fill="#8b949e" font-size="15" font-family="Arial,sans-serif">Chess.com · {h(meta["date"])} · {h(meta["time_control"])} · replay loops</text>',
        '</svg>',
    ])
    return '\n'.join(svg) + '\n'


def demo_game(username: str) -> tuple[list[dict], dict]:
    """Dependency-free example, intentionally labelled DEMO until API sync runs."""
    pieces = {}
    for file in 'abcdefgh':
        pieces[f'{file}2'] = 'P'
        pieces[f'{file}7'] = 'p'
    for file, piece in zip('abcdefgh', 'RNBQKBNR'):
        pieces[f'{file}1'] = piece
        pieces[f'{file}8'] = piece.lower()
    moves = [('e2', 'e4', 'e4'), ('e7', 'e5', 'e5'), ('g1', 'f3', 'Nf3'), ('b8', 'c6', 'Nc6'), ('f1', 'c4', 'Bc4'), ('g8', 'f6', 'Nf6')]
    states = [{'pieces': dict(pieces), 'san': 'START', 'from': None, 'to': None, 'move': 0}]
    for i, (origin, dest, san) in enumerate(moves, 1):
        pieces[dest] = pieces.pop(origin)
        states.append({'pieces': dict(pieces), 'san': san, 'from': origin, 'to': dest, 'move': i})
    meta = {'username': username + ' (DEMO)', 'white': 'Demo White', 'black': 'Demo Black', 'result': '*', 'date': 'DEMO ONLY', 'time_control': '', 'game_url': f'https://www.chess.com/member/{username}', 'player_side': 'white', 'ply': len(moves)}
    return states, meta


def replace_readme_block(readme: Path, meta: dict, img_path: str = 'assets/chess/last-game.svg') -> bool:
    if not readme.is_file():
        return False
    original = readme.read_text(encoding='utf-8')
    begin = '<!-- chess-replay:start -->'
    end = '<!-- chess-replay:end -->'
    if begin not in original or end not in original:
        print('README does not contain chess-replay markers, leaving it unchanged.')
        return False
    game_url = meta['game_url']
    if not game_url.startswith('https://www.chess.com/'):
        game_url = f'https://www.chess.com/member/{meta["username"]}'
    block = '\n'.join([
        begin,
        f'[![Animated Chess.com replay]({img_path})]({game_url})',
        '',
        f'**{meta["white"]} vs {meta["black"]}** · {meta["result"]} · [View this game on Chess.com]({game_url})',
        end,
    ])
    i = original.index(begin)
    j = original.index(end, i) + len(end)
    result = original[:i] + block + original[j:]
    if result != original:
        readme.write_text(result, encoding='utf-8')
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', default=os.environ.get('CHESSCOM_USER', 'kirlur'))
    parser.add_argument('--output', type=Path, default=BASE_DIR / 'assets/chess/last-game.svg')
    parser.add_argument('--meta', type=Path, default=BASE_DIR / 'assets/chess/last-game.json')
    parser.add_argument('--readme', type=Path, default=BASE_DIR / 'README.md')
    parser.add_argument('--demo', action='store_true', help='Offline preview; never presents demo as your real Chess.com game')
    args = parser.parse_args()
    try:
        states, meta = demo_game(args.user) if args.demo else parse_game(last_game(args.user), args.user)
        if not args.demo and meta['player_side'] not in ('white', 'black'):
            raise RuntimeError('Invalid player side')
        if args.demo:
            print('Generating demo replay; NOT real Chess.com data')
        svg = render_svg(states, meta)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.meta.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(svg, encoding='utf-8')
        args.meta.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        if not args.demo:
            replace_readme_block(args.readme, meta)
        print(f'Wrote {args.output} ({len(states) - 1} plies; {len(svg)} bytes)')
        return 0
    except (RuntimeError, ValueError, urllib.error.URLError, OSError, KeyError) as exc:
        print(f'Chess replay generation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
