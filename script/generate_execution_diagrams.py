#!/usr/bin/env python3
"""Generate source-grounded README SVGs; PNG exports are made from these SVGs."""
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'docs' / 'images'
BG, PANEL, INK, MUTED = '#171b20', '#222830', '#f3eee6', '#b9c1ca'
BRONZE, GREEN, BLUE = '#d7ad77', '#91c8a0', '#8cbde4'


class Diagram:
    def __init__(self, title, subtitle, tag, height=1050):
        self.height = height
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{height}" viewBox="0 0 1600 {height}" role="img" aria-labelledby="title desc">',
                      f'<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}. Includes savings mechanisms, verification and optional OpenViking memory.</desc>',
                      f'<rect width="1600" height="{height}" fill="{BG}"/>',
                      '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10" fill="#d7ad77"/></marker><marker id="return" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10" fill="#8cbde4"/></marker></defs>']
        self.text(64, 52, 'OPENRAGNAR / BROWSER EXECUTION', 19, BRONZE, weight=600)
        self.text(64, 111, title, 43, INK, weight=600)
        self.text(64, 155, subtitle, 23, MUTED)
        self.text(64, 196, tag, 18, GREEN)

    def text(self, x, y, value, size=21, color=INK, weight=400):
        self.parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}">{escape(value)}</text>')

    def box(self, x, y, width, title, lines, accent=BRONZE, height=130):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="14" fill="{PANEL}" stroke="#39424c"/>')
        self.parts.append(f'<rect x="{x+18}" y="{y+19}" width="4" height="25" rx="2" fill="{accent}"/>')
        self.text(x+34, y+40, title, 25, INK, 600)
        for i, line in enumerate(lines):
            self.text(x+22, y+76+i*27, line, 19, MUTED)

    def line(self, x1, y1, x2, y2, returning=False):
        color, marker = (BLUE, 'return') if returning else (BRONZE, 'arrow')
        self.parts.append(f'<path d="M{x1} {y1}L{x2} {y2}" fill="none" stroke="{color}" stroke-width="2" marker-end="url(#{marker})"/>')

    def return_path(self, right, left, y, bottom, label):
        self.parts.append(f'<path d="M{right} {y}V{bottom}H{left}V{y}" fill="none" stroke="{BLUE}" stroke-width="2" marker-end="url(#return)"/>')
        self.text(left+26, bottom-12, label, 20, BLUE)

    def note(self, y, title, lines, x=64, width=1472, accent=GREEN):
        self.box(x, y, width, title, lines, accent, 62+len(lines)*27)

    def memory(self, y, mode, direct_only=False):
        self.text(64, y, 'OPTIONAL MEMORY / NOT A BROWSER-ACTION HOP', 18, BRONZE, 600)
        self.box(64, y+22, 435, 'Local evidence + outbox', mode, GREEN, 150)
        self.line(515, y+80, 605, y+80)
        self.text(517, y+63, 'upload', 17, MUTED)
        self.line(605, y+128, 515, y+128, True)
        self.text(518, y+154, 'hints', 17, MUTED)
        self.box(625, y+22, 390, 'OpenViking', ['Scoped outcomes + failure lessons', 'Navigation hints in path 2', 'Vector-only upload processing'], BRONZE, 150)
        savings = ['Fixed guidance for recurring failures', 'No reflection pass for uploads', 'Embedding / storage costs may apply'] if direct_only else ['Local cache avoids remote retrieval', 'Proven reuse can skip inference', 'Live checks still required; costs apply']
        self.box(1040, y+22, 496, 'Memory savings', savings, GREEN, 150)

    def save(self, name):
        y = self.height-55
        self.parts.append(f'<path d="M64 {y-24}H1536" stroke="#39424c"/>')
        self.text(64, y+5, 'Savings = mechanisms, not measured Claude quota or billing reductions. 10× speed remains a target.', 19, MUTED)
        self.parts.append('</svg>')
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / (name+'.svg')).write_text('\n'.join(self.parts)+'\n')


def direct():
    d = Diagram('01  Direct browser tools', 'Claude plans each request; OpenRagnar forwards it and compacts the result.', 'IMPLEMENTED / NO JEV OR VISION INFERENCE ADDED')
    boxes = [(64, 290, 'Claude', ['Task planning + tool arguments', 'Overall completion + recovery']),
             (480, 350, 'OpenRagnar', ['stdio MCP → loopback HTTP MCP', 'Short docs + bounded text output']),
             (970, 300, 'BrowserOS Neo', ['Execute browser operations', 'Read / click / fill / evaluate'])]
    for x, w, title, lines in boxes:
        d.box(x, 250, w, title, lines)
    d.line(366, 312, 466, 312)
    d.text(374, 286, 'request', 17, MUTED)
    d.line(844, 312, 956, 312)
    d.text(861, 286, 'dispatch', 17, MUTED)
    d.line(1284, 312, 1390, 312)
    d.box(1404, 250, 132, 'Page', ['Live site'], height=130)
    d.return_path(1120, 655, 392, 440, 'Neo result → OpenRagnar')
    d.return_path(640, 210, 452, 500, 'Compact result → Claude')
    d.note(550, 'SAVING AT THE GATEWAY: less browser text for Claude', ['Shorter instructions and descriptions; recognized duplicates removed.', 'Oversized text becomes a preview + recoverable artifact. Claude still chooses the next step.'])
    d.note(700, 'NO ADDED INFERENCE: direct tools need no decision-provider key', ['Browser operations still cost time. Direct screenshots can still reach Claude.', 'Tool success is an MCP outcome; Claude must establish the overall task result.'], accent=BLUE)
    d.memory(858, ['Metadata-only direct outcomes', 'Identical failure → fixed guidance', 'No automatic replay of writes'], direct_only=True)
    d.height = 1120
    # Adjust root/canvas to include the complete memory row and footer.
    d.parts[0] = d.parts[0].replace('1050', '1120')
    d.parts[2] = d.parts[2].replace('1050', '1120')
    d.save('browser-path-direct')


def jev():
    d = Diagram('02  Jev-assisted public navigation', 'One Claude tool call can contain several observed-link decisions and browser steps.', 'IMPLEMENTED / openragnar_navigate / PUBLIC SAME-ORIGIN LINKS ONLY', 1260)
    d.box(64, 250, 290, 'Claude', ['Goal + start URL + successText', 'maxSteps: default 4, cap 6'])
    d.box(480, 250, 350, 'OpenRagnar', ['Observe → decide → recheck', 'Navigate → verify → repeat'])
    d.box(970, 250, 300, 'BrowserOS Neo', ['Observe page + visible links', 'Execute checked navigation'])
    d.box(1404, 250, 132, 'Page', ['Live site'])
    d.line(366, 312, 466, 312); d.text(375, 287, '1 call', 17, MUTED)
    d.line(844, 312, 956, 312); d.text(853, 287, 'browser', 17, MUTED)
    d.line(1284, 312, 1390, 312)
    d.box(480, 470, 350, 'Jev / decision model', ['Observed options → choice', 'Probability + usage returned'], BLUE)
    d.line(575, 395, 575, 453); d.text(595, 431, 'goal + options', 18, MUTED)
    d.line(760, 455, 760, 395, True)
    d.return_path(1120, 910, 390, 635, 'Page evidence')
    d.return_path(450, 210, 390, 635, 'Result → Claude')
    d.note(686, 'SAVING INSIDE THE LOOP: avoid intermediate Claude planning turns', ['Jev chooses among current links; OpenRagnar executes and verifies. Jev never controls Neo directly.', 'Bounded inputs reduce decision context. Eligible local routes skip Jev and advisory recall.'])
    d.note(836, 'MEASURED MECHANISM: 5 → 4 Neo calls for a one-link task in 0.4.7', ['One recheck + navigation request replaces two. A separate final observation remains.', 'Versus 0.4.6: ~6.4% lower median in 6 runs/version with deterministic selection; not a Claude benchmark.'], accent=BLUE)
    d.memory(994, ['2 local text-verified successes', '30-day task / route matching', 'Failure revokes reuse eligibility'])
    d.save('browser-path-jev')


def combined():
    d = Diagram('03  Jev + vision in one task', 'Two existing tools, coordinated by Claude: navigation first, visual grounding when needed.', 'IMPLEMENTED AS SEPARATE CALLS / NO AUTONOMOUS JEV + VISION LOOP', 1470)
    d.text(64, 247, 'A / NAVIGATE: openragnar_navigate', 18, BRONZE, 600)
    for x, w, title, lines in [(64, 270, 'Claude', ['Delegate public navigation']), (390, 320, 'OpenRagnar', ['Observe + verify link + text']), (770, 290, 'Jev', ['Bounded link choice']), (1150, 386, 'Neo + page', ['Execute via OpenRagnar'])]:
        d.box(x, 270, w, title, lines, height=108)
    for a, b in [(346,376),(722,756),(1072,1136)]: d.line(a,322,b,322)
    d.text(1100, 257, 'choice → Ragnar → Neo', 17, MUTED)
    d.return_path(1330, 190, 390, 433, 'Neo → OpenRagnar verification → Claude: result + page ID; Claude chooses visual stage')
    d.text(64, 493, 'B / GROUND ONE TARGET: openragnar_visual_act', 18, BRONZE, 600)
    for x, w, title, lines in [(64, 270, 'Claude', ['Page ID + target + point/click']), (390, 320, 'OpenRagnar', ['Capture through Neo', 'Check memory + freshness']), (770, 290, 'Vision model', ['Screenshot → coordinates', 'Local starting path']), (1150, 386, 'Neo + page', ['Freshness guard → one click', 'Check requested text afterward'])]:
        d.box(x, 516, w, title, lines)
    for a, b in [(346,376),(722,756),(1072,1136)]: d.line(a,580,b,580)
    d.text(1090, 501, 'point → Ragnar → Neo', 17, MUTED)
    d.return_path(1330, 190, 660, 710, 'Neo → OpenRagnar → Claude: coordinates + click/verification status + usage; no screenshot returned')
    d.note(754, 'SAVING AT VISION: keep screenshot interpretation out of Claude’s context', ['The selected grounder receives the screenshot; Claude receives a compact report.', 'Local vision avoids cloud vision API charges but consumes local compute. OpenRouter is an explicit option.'])
    d.note(904, 'SAVING ON REPEATS: verified local evidence can avoid vision inference', ['Two independent model-grounded, text-verified clicks can qualify on the identical task and scene.', 'Fresh screenshots + DOM/viewport checks remain. Changed scenes miss reuse; failures revoke eligibility.'], accent=BLUE)
    d.note(1054, 'COST BOUNDARY: use each model only when needed', ['Navigation gets bounded decisions; visual targeting gets grounding. Claude coordinates the handoff.', 'Controlled learned visual repeats: 0.261–0.282 s, zero local inference tokens; not Claude quota savings.'])
    d.memory(1210, ['Routes + private visual evidence', 'Visual coordinates remain local', 'Generic visual outcomes upload'])
    d.save('browser-path-jev-vision')


if __name__ == '__main__':
    direct()
    jev()
    combined()
