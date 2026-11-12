#!/usr/bin/env python3
"""Render an HSG lecture deck (deck.json, see hsg_deck.py) as an online presentation.

  python render_html.py deck.json                 # writes <deck folder>/html/index.html and html/assets/
  python render_html.py deck.json --out DIR
  python render_html.py deck.json --shots DIR     # also screenshots for the check: one PNG per slide,
                                                  # a contact sheet and the phone view
  python render_html.py deck.json --shots DIR --slides 2,4-6   # only these slides (fast)

In a window of 1000px or wider it shows one 16:9 slide, centred. In a narrower window (phone) it still shows one
slide at a time, filling the window with the content in one column; a slide taller than the window scrolls
within itself. Printing gives one slide per page (PDF).
Keys: arrows or space to move, O overview, F full screen, N speaker notes (a button in the panel moves them to their own window).
"""
import argparse, html, json, math, re, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hsg_deck as hd

esc = html.escape


def plain(text):
    """A headline without its **bold** marks, for the browser tab and the overview."""
    return text.replace("**", "")

# Gill Sans Nova (the font of the official HSG template) is used where it is installed, then Gill Sans MT Pro; both are
# licensed and never copied into the page. Elsewhere the page falls back to the bundled Gillius ADF No2 (GPL with font
# exception), and for the serif (Palatino Linotype on the template) to TeX Gyre Pagella (GUST Font License).
# As on the template: Regular for headlines and text, Light for the large titles, Bold for bold.
FONTS = [
    ("HSGSans", 300, "normal", ["Gill Sans Nova Light", "GillSansNova-Light", "Gill Sans MT Pro Light", "GillSansMTPro-Light",
                                "Gill Sans Light", "GillSans-Light"], "GilliusADFNo2-Regular.otf"),
    ("HSGSans", 300, "italic", ["Gill Sans Nova Light Italic", "GillSansNova-LightItalic", "Gill Sans MT Pro Light Italic",
                                "GillSansMTPro-LightItalic", "Gill Sans Light Italic", "GillSans-LightItalic"], "GilliusADFNo2-Italic.otf"),
    ("HSGSans", 400, "normal", ["Gill Sans Nova", "GillSansNova", "Gill Sans MT Pro Book", "GillSansMTPro-Book",
                                "Gill Sans", "GillSans"], "GilliusADFNo2-Regular.otf"),
    ("HSGSans", 400, "italic", ["Gill Sans Nova Italic", "GillSansNova-Italic", "Gill Sans MT Pro Book Italic",
                                "GillSansMTPro-BookItalic", "Gill Sans Italic", "GillSans-Italic"], "GilliusADFNo2-Italic.otf"),
    ("HSGSans", 700, "normal", ["Gill Sans Nova Bold", "GillSansNova-Bold", "Gill Sans MT Pro Bold", "GillSansMTPro-Bold",
                                "Gill Sans Bold", "GillSans-Bold"], "GilliusADFNo2-Bold.otf"),
    ("HSGSans", 700, "italic", ["Gill Sans Nova Bold Italic", "GillSansNova-BoldItalic", "Gill Sans MT Pro Bold Italic",
                                "GillSansMTPro-BoldItalic", "Gill Sans Bold Italic", "GillSans-BoldItalic"], "GilliusADFNo2-BoldItalic.otf"),
    ("HSGSerif", 400, "normal", ["Palatino Linotype", "PalatinoLinotype-Roman", "Palatino", "Palatino-Roman", "Book Antiqua"],
     "texgyrepagella-regular.otf"),
    ("HSGSerif", 400, "italic", ["Palatino Linotype Italic", "PalatinoLinotype-Italic", "Palatino Italic", "Palatino-Italic"],
     "texgyrepagella-italic.otf"),
]

CSS = r"""
*{box-sizing:border-box}
html,body{margin:0;height:100%}
/* One unit (U) is 1% of a 16:9 slide; the template slide is 13.33in wide, so 1U = 9.6pt.
   Type scale of the HSG template, fixed for every deck: headline 32pt (3.33U), body 18.7pt (1.94U), sub-points 14pt (1.46U),
   small 12pt (1.25U), source 8pt (.83U). Headlines and text are Gill Sans Regular, large titles Light, bold Bold. */
:root{--ctl:60px;--bar:var(--ctl);--u:min(1vw,calc((100vh - var(--bar))/56.25));--u:min(1vw,calc((100dvh - var(--bar))/56.25));
  --s-h1:5.2U;--s-h2:3.33U;--s-kick:2.1U;--s-body:1.94U;--s-mid:1.6U;--s-sub:1.46U;--s-small:1.25U;--s-tiny:.83U;
  --green:#00802F;--dgreen:#0A5F2D;--salmon:#EB6969;--teal:#73A5AF;--row-a:#CBD8CD;--row-b:#E7EDE8;--yellow:#FFF04B;
  --fg:#000000;--body:#1a1a1a;--quiet:#595959;--line:#d9d9d9;--k-stage:#e4e4e4}
body{font-family:HSGSans,"Gill Sans Nova","Gill Sans MT Pro","Gill Sans MT","Gill Sans",Calibri,sans-serif;font-weight:400;
  -webkit-font-smoothing:antialiased;overflow:hidden;background:var(--k-stage);color:var(--fg)}
h1,h2,h3,p,ul,ol,dl,dd,figure,pre{margin:0;padding:0}
b,strong,th{font-weight:700}
a{color:var(--green);text-underline-offset:.15em}
a:focus-visible,button:focus-visible{outline:2px solid currentColor;outline-offset:2px}
code,pre{font-family:"Courier New",Courier,"Liberation Mono",monospace;font-weight:400}
mark{background:var(--yellow);color:inherit;padding:0 .1em}
sub,sup{font-size:.65em;line-height:0}

.slide{position:absolute;left:50%;top:calc((100% - var(--bar))/2);width:100U;height:56.25U;transform:translate(-50%,-50%);
  overflow:hidden;visibility:hidden;background:#fff;color:var(--fg)}
.slide.active{visibility:visible;z-index:2}.slide.leaving{visibility:visible;z-index:1}
/* the title sits in the template's title box (4.1U to 10.8U, text on its bottom line); content starts at 14U */
.frame{position:relative;z-index:1;width:100%;height:100%;padding:4.1U 3.92U 5U;display:flex;flex-direction:column;min-width:0}
.headrow{display:flex;justify-content:space-between;align-items:flex-end;gap:3U;min-height:6.7U;flex:none}
h2{font-size:var(--s-h2);font-weight:400;line-height:1.08;letter-spacing:-.005em;color:var(--fg);max-width:78U;text-wrap:balance}
.lead{font-size:var(--s-body);line-height:1.25;margin-top:3.2U;max-width:86U;color:var(--body)}
.main{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:flex-start;padding:3.2U 0 .6U}
.l-menu .main,.l-quiz .main,.l-image .main,.l-gallery .main,.l-people .main,.l-syllabus .main{justify-content:safe center}
.lead+.main{padding-top:2.6U}
.source{position:absolute;left:3.92U;bottom:2.1U;max-width:84U;font-size:var(--s-tiny);line-height:1.3;color:var(--quiet);z-index:2}
.dfoot{position:absolute;left:3.92U;bottom:2.1U;font-size:var(--s-tiny);color:var(--quiet);z-index:2}
.source~.dfoot{display:none}
/* the slide number in the green HSG tab, bottom right */
.pn{position:absolute;right:3.94U;top:51.41U;width:2.33U;height:2.56U;z-index:3;display:grid;place-items:center;padding:.45U 0 0 .45U;
  font-size:1.1U;font-weight:400;color:#fff;font-variant-numeric:tabular-nums}
.pn svg{position:absolute;inset:0;width:100%;height:100%;fill:var(--green);z-index:-1}

/* running text: paragraphs without a mark, points with a dash as on the template */
.copy{display:grid;gap:1.5U;align-content:start;min-width:0}
.copy p{font-size:var(--s-body);line-height:1.25;color:var(--body)}
ul.dash{list-style:none;display:grid;gap:.9U}
ul.dash>li{position:relative;padding-left:2.2U;font-size:var(--s-body);line-height:1.25;color:var(--body)}
ul.dash>li::before{content:"-";position:absolute;left:.1U}
ul.dash ul{list-style:none;display:grid;gap:.25U;margin-top:.35U}
ul.dash ul li{position:relative;padding-left:1.8U;font-size:var(--s-sub);line-height:1.25;color:var(--body)}
ul.dash ul li::before{content:"-";position:absolute;left:0}
.dense ul.dash>li,.dense .copy p{font-size:var(--s-mid)}
.dense ul.dash{gap:.6U}
.group h3{font-size:2.4U;font-weight:400;line-height:1.15;color:var(--fg);margin-bottom:.5U}
.group ul.dash{gap:.2U}
.dense .group ul.dash>li,.dense .group p{font-size:var(--s-mid)}
.groups{display:grid;gap:3U}
.defs{display:grid;grid-template-columns:auto 1fr;gap:.45U 4U;font-size:var(--s-mid);line-height:1.25;color:var(--body)}
.defs dt{position:relative;padding-left:2.2U}
.defs dt::before{content:"-";position:absolute;left:.1U}
.after{font-size:var(--s-body);line-height:1.3;color:var(--body);margin-top:2.6U;padding-left:24U}

/* copy on the left, picture, box or code on the right */
.split{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:4U;align-items:center}
.split.wide{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.l-code .split{align-items:start}
.pic{display:flex;flex-direction:column;align-items:center;min-height:0}
.pic img{display:block;max-width:100%;max-height:34U;width:auto;height:auto;object-fit:contain}
.pic.shadow img{filter:drop-shadow(.35U .35U .55U rgba(0,0,0,.38))}
.pic figcaption{font-size:var(--s-tiny);color:var(--quiet);margin-top:.9U;text-align:center;max-width:44U}

/* boxes: green for a question to the room, an outline for an example or a note, teal for a remark */
.box{border-radius:.9U;padding:1.3U 2U;font-size:var(--s-mid);line-height:1.25;text-wrap:balance}
.box.green{background:var(--green);border:.12U solid var(--dgreen);color:#fff;text-align:center}
.box.outline{background:#fff;border:.12U solid var(--green);color:var(--body);border-radius:0}
.box.teal{background:var(--teal);border:.12U solid #5d8f99;color:#fff;border-radius:0}
.box h3{font-size:var(--s-mid);font-weight:700;margin-bottom:.4U}
.box a{color:inherit}
.callout{flex:none;max-width:34U;margin-bottom:-1U}
.callout.wide{max-width:48U}
.callout.box{font-size:var(--s-sub)}

pre.code{font-size:1.3U;line-height:1.35;padding:1.6U 2U;white-space:pre;overflow:hidden;tab-size:4}
pre.code.small{font-size:1.05U}
pre.code.outline{background:#fff;border:.12U solid var(--green);color:#262626}
pre.code.teal{background:var(--teal);border:.12U solid #5d8f99;color:#fff}
.codecap{font-size:var(--s-tiny);color:var(--quiet);margin-top:.8U}

/* table: green header, rows in two green tints, white rules */
table.t{width:100%;border-collapse:collapse;font-size:var(--s-mid);line-height:1.2}
.t th{background:var(--green);color:#fff;text-align:left;padding:.75U 1U}
.t td{padding:.65U 1U;color:var(--body);vertical-align:top}
.t tr:nth-child(odd) td{background:var(--row-a)}
.t tr:nth-child(even) td{background:var(--row-b)}
.t th+th,.t td+td{border-left:.15U solid #fff}
.t tr+tr td{border-top:.15U solid #fff}
.t td:first-child{font-weight:700;color:var(--fg)}
.t.many{font-size:var(--s-sub)}
.t.many td{padding:.45U 1U}

/* menu: the topics of the day in a thin green frame */
.menu{border:.12U solid var(--green);padding:2.6U 2.4U;width:66U;display:grid;gap:.35U}
.menu p{font-size:var(--s-sub);line-height:1.3;color:var(--body)}
.menu p.cur{font-weight:700;color:var(--green)}

/* quiz: questions in green boxes, staggered in two columns */
.quiz{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:2.6U 3U;align-items:center}
.quiz .box{justify-self:start;max-width:40U}
.quiz .box:nth-child(even){justify-self:end}
.quiz.n3 .box:last-child{grid-column:1/-1;justify-self:center}

/* task: a salmon label set at an angle, as on the template's homework slides */
.task{position:relative;flex:1;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);align-items:center;gap:4U}
.task .copy{align-self:start}
.stamp{justify-self:center;background:var(--salmon);border:.12U solid #d65b5b;border-radius:1.1U;color:#fff;font-size:3U;line-height:1.2;
  padding:1.7U 2.8U;transform:rotate(-9deg);text-align:center;max-width:44U;text-wrap:balance}
.task .go{position:absolute;right:4U;bottom:2U;font-size:var(--s-sub)}
.task.solo{grid-template-columns:1fr}

.gallery{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:3U;align-items:end}
.gallery .pic img{max-height:30U}
.gallery.qr{max-width:60U;margin:0 auto;align-items:start}
.gallery.qr .pic img{width:24U;height:24U;max-height:none;margin:0 auto}
/* three tiles with an icon (an emoji, or a coloured dot) each */
.tiles3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:2.4U;margin-top:2U}
.tile{border:.1U solid #ccc;border-radius:1U;padding:2.6U 2.4U;font-size:var(--s-body);line-height:1.35}
.ticon{display:block;font-size:4U;line-height:1;margin-bottom:1.6U}
.ticon.dot{width:4U;height:4U;border-radius:50%;background:#EB6969}
/* decor: emojis or dots scattered behind the slide */
.odots,.emojis{position:absolute;inset:0;pointer-events:none;z-index:-1}
.odots i{position:absolute;width:calc(var(--d)*1U);height:calc(var(--d)*1U);border-radius:50%;background:#EB6969;opacity:.9}
.emojis span{position:absolute;line-height:1}
.people{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:3U;align-items:end;justify-items:center}
.person{display:flex;flex-direction:column;align-items:center;text-align:center;gap:1.4U}
.person img{width:13U;height:16U;object-fit:cover;display:block;filter:drop-shadow(.35U .35U .55U rgba(0,0,0,.38))}
.person .name{font-size:var(--s-small);line-height:1.25;color:var(--fg)}
.person .role{font-size:var(--s-small);line-height:1.25;color:var(--body)}
.people.n1 img,.people.n2 img{width:17U;height:21U}

/* quote: the quote is the headline, right aligned, the picture below on the left */
.l-quote .headrow{justify-content:flex-end}
.l-quote h2{font-weight:300;text-align:right;max-width:64U;line-height:1.15;text-wrap:balance}
.attr{font-size:var(--s-mid);text-align:right;color:var(--body);margin-top:1U}
.qbody{flex:1;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:4U;align-items:end;padding:2U 0 1U}
.qbody .pic{align-items:flex-start}
.qbody .pic img{width:100%;max-height:30U;object-position:left bottom}
.qbody ul.dash>li{font-size:var(--s-sub)}

/* questions and study slides carry the template's pictures: the figure on the question mark and the light bulb */
.figure{display:flex;justify-content:center;align-items:center}
.figure img{width:22U;height:auto;display:block}
.bulb{position:absolute;right:4U;top:2.2U;width:10U;height:auto;z-index:2}
.l-study .headrow{padding-right:12U}
.l-questions .split{grid-template-columns:minmax(0,1fr) 24U}
.takeh{font-size:var(--s-mid);color:var(--body);margin-bottom:1.6U}
.l-questions ul.dash{gap:1.5U}

.l-questions .after{padding-left:30U}
.l-questions.bare .main{justify-content:flex-end}
.l-questions.bare .figure{justify-content:flex-end;padding-right:2U}
.l-questions.bare .figure img{width:24U}

/* syllabus: the course plan, one bar per session; the current one is teal; assignments in salmon on the right */
.plan{display:grid;grid-template-columns:11U 6U minmax(0,1fr) 23U;column-gap:1.6U;align-items:center}
.legend{grid-column:1;display:grid;gap:1U;align-self:center}
.legend span{display:grid;place-items:center;height:3.4U;font-size:1.05U;color:#fff}
.lg-l{background:var(--green)}.lg-e{background:var(--dgreen)}.lg-a{background:var(--salmon)}
.rows{grid-column:2/4;display:grid;grid-template-columns:6U minmax(0,1fr);column-gap:1.6U;row-gap:.4U;align-items:center}
.l-syllabus .main{padding-top:1.4U}
.rows .date{font-size:.72U;color:var(--quiet);text-align:right;font-variant-numeric:tabular-nums}
.rows .bar{height:2.15U;display:grid;place-items:center;font-size:1.1U;color:#fff;background:var(--green);border-bottom:.15U solid #00591f;padding:0 1U;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rows .bar.ex{background:var(--dgreen)}
.rows .bar.cur{background:var(--teal);border-color:#5d8f99}
.rows .brk{grid-column:2;height:.45U;background:#111;margin:.3U 0}
.assign{grid-column:4;display:grid;row-gap:.4U;align-self:stretch}
.assign div{background:var(--salmon);color:#fff;font-size:1.05U;display:grid;place-items:center;text-align:center;padding:1U;margin:.3U 0}

/* title slide: logo, title and the course on the left, the gear on the right, the green wedge at the foot */
.l-title .frame,.l-section .frame{padding:0;display:block}
.logo{position:absolute;left:3.9U;top:3.4U;width:24.3U;height:auto;z-index:2}
.art{position:absolute;inset:0;overflow:hidden;z-index:0}
.gear{position:absolute;left:47.65U;top:-1.9U;width:53.2U;height:53.2U;object-fit:contain}
/* the other title slides of the official template: "photo" (a photo behind the whole slide), "side" (a photo strip on the
   right) and "slanted" (a slanted photo with a green frame); the last two have no wedge and a black tagline */
.bgphoto{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.tblock.t-photo{width:87U}
.tblock.t-side{width:52.11U}.tblock.t-slanted{width:49.25U}
.tpic{position:absolute;object-fit:cover;z-index:1}
.tpic.side{left:65.24U;top:0;width:34.76U;height:56.25U}
.tpic.slanted{left:62.91U;top:4.9U;width:37.09U;height:41.54U;clip-path:polygon(0 21.87%,100% 0,100% 100%,15.27% 92.29%)}
.tframe{position:absolute;left:63.01U;top:17.77U;width:26.46U;height:29.42U;overflow:visible;z-index:0}
.tagline.side,.tagline.slanted{top:51.5U;color:var(--fg);z-index:2}
.tagline.side{left:9.06U;right:auto}
.tagline.slanted{right:3.92U}
.veil{position:absolute;inset:0;z-index:1;background:linear-gradient(to top right,#fff 0%,rgba(255,255,255,.6) 50%,rgba(255,255,255,0) 100%)}
.wedge{position:absolute;left:50U;top:34.65U;width:50U;height:21.6U;background:var(--green);z-index:2;
  clip-path:polygon(100% 0,100% 100%,3.65% 100%,0 52.9%)}
.tagline{position:absolute;right:4U;top:15.65U;z-index:3;font-size:1.39U;color:#fff}
.tblock{position:absolute;left:9U;top:12U;width:44U;height:19.6U;z-index:2;display:flex;flex-direction:column;justify-content:flex-end}
.kicker{font-size:var(--s-kick);line-height:1.2;color:var(--fg);margin-bottom:2.2U}
.subtitle{font-size:var(--s-kick);line-height:1.2;color:var(--fg);margin-top:1.6U}
h1{font-size:var(--s-h1);font-weight:300;line-height:1.08;letter-spacing:-.01em;color:var(--fg);text-wrap:balance}
.tbody{position:absolute;left:9U;top:34.2U;width:40U;z-index:2;font-size:1.67U;line-height:1.3;color:var(--fg)}
.tbody .affil{margin-top:0;font-size:.75em;font-style:italic;color:#595959}
.tbody.t-slanted{top:36.2U}
.tevent{position:absolute;left:9U;top:51.5U;z-index:2;font-size:1.2525U;color:#595959}   /* as .affil: .75 of .tbody */
.tbody p+p{margin-top:2.2U}
.l-section .tblock{top:14U;height:20U;width:70U}
.l-section .wedge{left:62U;width:38U;top:40.25U;height:16U}


/* canvas: a slide copied from PowerPoint; every object sits where it was (x, y, w, h in U), text keeps its size,
   click animations become steps (the arrow keys reveal them one by one; overview, print and phone show all);
   the headline may use the full width, as the HSG font is a little wider than the Light of many source decks */
.l-canvas h2{max-width:92U;text-wrap:wrap}
.l-canvas.ta-t .headrow{align-items:flex-start}  /* the PowerPoint title hangs from the top of its box */
.l-canvas .dfoot{z-index:0}  /* the footer line lies behind the objects, so a filled box covers it */
.cv{position:absolute;inset:0;z-index:1}
.cv .it{position:absolute}
.cv .off{visibility:hidden}
.cv svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.cv .tx{position:absolute;inset:0;display:flex;flex-direction:column;color:var(--fg);line-height:1.2;font-weight:400}
.cv .tx.m{justify-content:center}.cv .tx.b{justify-content:flex-end}
.cv .tx.nw{white-space:nowrap}
.cv .tx p{margin:0;min-height:1.2em;flex:none}
.cv .tx .bu{display:inline-block}
.cv .tx b{font-weight:700}
.cv .tx .mono{font-family:"Courier New",Courier,"Liberation Mono",monospace;font-weight:400}
.cv .tx .serif{font-family:HSGSerif,"Palatino Linotype",Palatino,serif}
.cv .tx.v270{writing-mode:vertical-rl;transform:rotate(180deg)}.cv .tx.v90{writing-mode:vertical-rl}
.cv .pimg{position:absolute;inset:0;overflow:hidden}
.cv .pimg video{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:#000}
.cv .pimg img{position:absolute;display:block;max-width:none}
.cv .yt{border:0;padding:0;margin:0;background:none;cursor:pointer;width:100%;height:100%}.cv .yt iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.cv .it.shadow .pimg{filter:drop-shadow(.35U .35U .55U rgba(0,0,0,.38))}
.cv table{position:absolute;inset:0;border-collapse:collapse;table-layout:fixed;width:100%}
.cv td{padding:0;vertical-align:middle;line-height:1.2;border:.1U solid #fff}
.cv td.head{background:var(--green);color:#fff}.cv td.a{background:var(--row-a)}.cv td.b{background:var(--row-b)}
.cv td .tx{position:static;display:block;padding:.3U .8U}
.cv td.head .tx{color:#fff}

/* references between slides and lectures: pills above the slide, links inside the text; all open in a new tab */
.refs{position:absolute;top:.9U;right:3.92U;z-index:4;display:flex;gap:.8U;justify-content:flex-end;max-width:92U}
.refs.left{right:auto;left:3.92U}
.refs.bottom{top:auto;bottom:2U;right:9U}
a.ref{display:inline-flex;align-items:center;gap:.6U;height:2.3U;padding:0 1.2U;border:.12U solid var(--green);border-radius:1.15U;
  background:#fff;color:var(--green);font-size:var(--s-small);line-height:1;text-decoration:none;white-space:nowrap}
a.ref b{font-weight:600}
a.ref .lab{max-width:34U;overflow:hidden;text-overflow:ellipsis}
a.ref:hover,a.ref:focus-visible{background:var(--green);color:#fff}
a.ref svg{width:1.1U;height:1.1U;flex:none;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
a.il,.copy a.il{color:var(--green)!important;text-decoration:underline;text-decoration-thickness:.1U;text-underline-offset:.25U}
a.il:hover{background:var(--green);color:#fff!important}
.cv a.il{color:inherit!important;text-decoration:none}
.cv a.il:hover{background:rgba(0,128,47,.18);color:inherit!important}
.cv a.il span{text-decoration:underline;text-decoration-thickness:.1U;text-underline-offset:.25U}
.cv a.il span:not([style*='color']){color:var(--green)}
.rows a.bar{text-decoration:underline;text-underline-offset:.3U;cursor:pointer}
.rows a.bar:hover{filter:brightness(1.15)}

/* the controls: a pill that floats under the slide, as in the FuSo decks, in HSG green */
.controls{position:fixed;left:0;right:0;bottom:0;height:var(--ctl);display:grid;place-items:center;z-index:7;pointer-events:none;
  color:#111;font-family:system-ui,sans-serif;font-size:13px;font-weight:600}
.pill{pointer-events:auto;display:flex;align-items:center;height:44px;padding:0 6px;border-radius:22px;background:#fff;
  border:1px solid #ddd;box-shadow:0 4px 18px rgba(0,0,0,.1);transition:opacity .25s,transform .25s}
.pill>div{display:flex;align-items:center;gap:2px}
.pill .sep{width:1px;height:20px;background:#ddd;margin:0 8px}
.controls button,.controls a.tbtn{border:0;background:transparent;color:inherit;font:inherit;text-decoration:none;height:34px;padding:0 12px;border-radius:17px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;gap:7px;white-space:nowrap}
.controls [hidden]{display:none}
.controls svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round;flex:none}
.controls button:hover,.controls a.tbtn:hover,body.show-notes #notesBtn,body:has(.overview.open) #ovBtn,body.auto #autoBtn{background:#f0f0f0}
.controls button:focus-visible,.controls a.tbtn:focus-visible{outline:2px solid #00802F;outline-offset:2px}
.controls .nav button{width:32px;height:32px;padding:0;background:#00802F;color:#fff}
.controls .nav button:not(:disabled):hover{background:#0A5F2D}
.controls .nav button:disabled{opacity:.3;cursor:default}
.nav svg{stroke-width:2.25}
.count{min-width:60px;text-align:center;font-variant-numeric:tabular-nums}
:root:not(:fullscreen) .fs-on,:root:fullscreen .fs-off{display:none}
body:not(.auto) .auto-on,body.auto .auto-off{display:none}
.progress{position:fixed;left:0;right:0;bottom:0;height:3px;background:#ddd}
.progress span{display:block;height:100%;width:0;background:#00802F;transition:width .3s}
:root:fullscreen{--bar:0px}
:root:fullscreen .progress{bottom:0;background:transparent}
:root:fullscreen .pill{opacity:0;transform:translateY(10px);pointer-events:none}
:root:fullscreen body.awake .pill,:root:fullscreen .pill:has(:focus-visible){opacity:1;transform:none;pointer-events:auto}
:root:fullscreen body:not(.awake){cursor:none}

.overview{position:fixed;inset:0;z-index:10;display:none;overflow:auto;padding:5U 5U 8U;background:#fff}
.overview.open{display:block}
.overview h2{font-size:3U}
.ov-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(20U,1fr));gap:1.4U;margin-top:3U}
.ov-grid button{all:unset;cursor:pointer;box-sizing:border-box;min-height:10U;padding:1.6U;background:#f2f2f2;border-left:.5U solid var(--green);
  color:#111;font-size:1.25U;line-height:1.25;display:flex;flex-direction:column;gap:.6U}
.ov-grid button:focus-visible{outline:2px solid currentColor}
.ov-grid small{font-size:.9U;color:var(--quiet)}
.notes-view{position:fixed;left:0;right:0;bottom:var(--bar);z-index:6;display:none;max-height:42%;overflow:auto;padding:2U 5U;
  background:#f2f2f2;color:#111;border-top:1px solid #ddd;font-size:1.4U;line-height:1.45;white-space:pre-wrap}
body.show-notes .notes-view{display:block}
.notes-view button{float:right;margin:0 0 1U 2U;font:inherit;font-size:.9U;padding:.3U .8U;cursor:pointer}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}

/* windows narrower than 1000px: still one slide at a time, but the slide fills the window and its content
   reflows into one column; a slide taller than the window scrolls within itself */
@media (max-width:999px),(max-height:480px){
  .tiles3{grid-template-columns:1fr}.odots,.emojis{display:none}
  :root{--u:8px;--s-h1:34px;--s-h2:25px;--s-kick:17px;--s-body:17px;--s-mid:16px;--s-sub:15px;--s-small:14px;--s-tiny:12px}
  body{background:#fff}
  .slide{left:0;top:0;width:100%;height:calc(100% - var(--bar));transform:none;overflow-y:auto}
  .frame{height:auto;min-height:100%;display:block;padding:30px 20px 70px}
  .headrow{display:block;min-height:0}
  .callout{margin:16px 0 0;max-width:none}
  .lead{margin-top:16px}
  .main{display:block;padding:22px 0 0}
  .split,.split.wide,.task,.qbody,.quiz,.gallery,.people,.l-questions .split{grid-template-columns:1fr;gap:24px}
  .split>*{min-width:0}
  .quiz .box,.quiz .box:nth-child(even){justify-self:stretch;max-width:none}
  .after,.l-questions .after{padding-left:0}
  .defs{grid-template-columns:1fr;gap:2px}.defs dd{padding-left:22px;margin-bottom:8px}
  .menu{width:auto;padding:18px}
  .pic img{max-height:none}
  .figure img{width:150px}
  .bulb{width:64px;top:16px;right:16px}
  .l-study .headrow{padding-right:72px}
  table.t{font-size:14px}.t th,.t td{padding:6px 7px}
  .tablewrap{overflow-x:auto}
  pre.code,pre.code.small{font-size:12px;overflow-x:auto}
  .stamp{font-size:22px;transform:rotate(-5deg);margin:20px 0}
  .task .go{position:static;display:block;margin-top:20px}
  .plan{display:block}.legend{display:flex;gap:8px;margin-bottom:16px}.legend span{flex:1;height:30px;font-size:12px}
  .rows{grid-template-columns:62px 1fr;row-gap:5px}.rows .date{font-size:10px}.rows .bar{height:26px;font-size:12px;white-space:normal}
  .assign{display:flex;flex-wrap:wrap;gap:6px;margin-top:16px}.assign div{font-size:12px;padding:8px;margin:0}
  .person img{width:120px;height:148px}
  .l-quote h2{text-align:left}.attr{text-align:left}
  .l-title .frame,.l-section .frame{display:flex;flex-direction:column;padding:24px 20px 0}
  .logo,.tblock,.tbody,.tagline,.tevent{position:static;width:auto;height:auto}
  .tevent{font-size:11.25px;margin-bottom:24px}
  .logo{width:190px;margin-bottom:44px}
  .tbody{margin:26px 0 30px;font-size:15px}
  .gear{left:auto;right:-70px;top:-50px;width:210px;height:210px}
  .l-title .tblock{width:auto;height:auto}
  .l-title .tpic{position:static;width:auto;height:200px;margin:0 -20px;clip-path:none}
  .tframe{display:none}
  .tagline.side,.tagline.slanted{margin-top:auto;padding:18px 0;font-size:15px}
  .l-title .frame,.l-section .frame{overflow:hidden}
  .wedge{position:static;width:auto;height:auto;clip-path:none;margin:auto -20px 0;padding:26px 20px 18px;display:flex;justify-content:flex-end;
    clip-path:polygon(100% 0,100% 100%,0 100%,0 40%)}
  .tagline{font-size:15px}
  .l-section .wedge{width:auto;height:90px;margin-top:40px}
  .source,.dfoot{position:static;display:block;margin-top:24px}
  .pn{position:absolute;top:auto;bottom:16px;right:16px;width:30px;height:33px;font-size:12px}
  .refs{position:static;flex-wrap:wrap;justify-content:flex-start;margin:0 0 14px;max-width:none}
  a.ref{height:auto;min-height:30px;padding:6px 12px;white-space:normal;line-height:1.2;border-radius:16px}
  .cv{position:relative;inset:auto;width:100vw;height:56.25vw;margin:30px -20px 0;--u:1vw;overflow:hidden}
  .slide.active .cv .off{visibility:visible}
  .pill{width:100%;height:100%;padding:3px 10px 0;border-radius:0;border:0;box-shadow:none;justify-content:space-between}
  .pill .sep{display:none}
  .tools button,.tools a.tbtn{flex-direction:column;gap:3px;height:48px;min-width:56px;padding:0 6px;border-radius:10px;font-size:10.5px}
  .tools svg{width:20px;height:20px}
  .controls .nav button{width:38px;height:38px}
  .progress{bottom:calc(var(--ctl) - 3px)}
}
@media print{
  @page{size:13.333in 7.5in;margin:0}
  :root{--u:.13333in;--bar:0px}
  html,body{height:auto}
  body{overflow:visible;background:#fff}
  .slide{position:relative;left:auto;top:auto;transform:none;visibility:visible;height:7.5in;width:100%;break-after:page}
  .controls,.overview,.notes-view{display:none!important}
  a.ref{border-color:#00802F}
  .cv .off{visibility:visible}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
"""

JS = r"""
(()=>{const slides=[...document.querySelectorAll('.slide')],root=document.documentElement,body=document.body,
 ov=document.getElementById('overview'),nt=document.getElementById('notesText');
const by=id=>document.getElementById(id);
let cur=0,step=0,arrived=false;{const h=location.hash.replace(/^#\/?/,'');if(/^\d+$/.test(h)){if(+h>=1&&+h<=slides.length){cur=+h-1;arrived=true}}else if(h){const i=slides.findIndex(s=>s.dataset.id===decodeURIComponent(h));if(i>=0){cur=i;arrived=true}}}
const maxStep=()=>+slides[cur].dataset.steps||0,stepping=()=>!matchMedia('(max-width:999px),(max-height:480px)').matches;
// PowerPoint effects (data-an, see pptx_canvas.py): stepping forward plays the effects of the new step with their
// delays and durations; going back or jumping shows the end state of the step at once. A motion path is a list of
// offsets (U) from the place of the shape on the slide; a spin adds its angle.
const A=e=>e._an||(e._an=JSON.parse(e.dataset.an||'[]'));
const pose=(e,upto)=>{let t=[0,0],r=0;for(const f of A(e))if(f.s<=upto){if(f.k==='path')t=f.pts[f.pts.length-1];if(f.k==='rot')r+=f.by}return[t,r]};
const tr=t=>`calc(var(--u)*${t[0]}) calc(var(--u)*${t[1]})`;
function show(play){play=play&&stepping();
 slides[cur].querySelectorAll('.it[data-s],.it[data-e],.it[data-an],.tx p[data-s]').forEach(e=>{const a=+e.dataset.s||0,x=e.dataset.e?+e.dataset.e:1e9;
  e.getAnimations().forEach(n=>n.cancel());
  const now=play?A(e).filter(f=>f.s===step):[];
  e.classList.toggle('off',!(step>=a&&step<x)&&!now.some(f=>f.k==='out'));
  let [t,r]=pose(e,now.length?step-1:step);e.style.translate=tr(t);e.style.rotate=r+'deg';
  for(const f of now){const o={delay:f.d,duration:Math.max(f.dur,1),easing:'ease-in-out'};
   if(f.k==='in')e.animate({opacity:[0,1]},{...o,duration:f.fx==='appear'?1:o.duration,fill:'backwards'});
   else if(f.k==='out')e.animate({opacity:[1,0]},{...o,duration:f.fx==='appear'?1:o.duration,fill:'forwards'});
   else if(f.k==='path')e.animate({translate:f.pts.map(tr)},{...o,easing:'linear',fill:'forwards'});
   else if(f.k==='rot'){e.animate({rotate:[r+'deg',(r+f.by)+'deg']},{...o,fill:'forwards'});r+=f.by}
   else if(f.k==='cmd'){const v=e.querySelector('video'),y=e.querySelector('.yt');if(v||y)e.animate([],{duration:f.d}).onfinish=()=>
     y?f.c!=='pause'&&y.click():f.c==='pause'?v.pause():f.c==='toggle'&&!v.paused?v.pause():v.play()}}});
 by('prev').disabled=cur===0&&step===0;by('next').disabled=cur===slides.length-1&&step>=maxStep();tick()}
// auto-advance (decks with "autoadvance"): every N seconds the next step or slide, after the last slide the first again
const ab=by('autoBtn');let timer;
function tick(){clearTimeout(timer);if(ab&&body.classList.contains('auto'))timer=setTimeout(()=>cur===slides.length-1&&step>=maxStep()?go(0):next(),ab.dataset.sec*1000)}
const auto=()=>{if(ab){body.classList.toggle('auto');tick()}};if(ab)ab.onclick=auto;
// the transition into a slide, when stepping forward to it: fade (the slide fades in over the last one) or Morph
// (objects with the same picture or text move and resize from their place on the last slide; the rest crossfades)
function transition(o,s){const t=JSON.parse(s.dataset.tr||'null');if(!t||o===s)return;
 o.classList.add('leaving');const bg0=s.style.background,run=[],hid=[],opt={duration:t.dur,easing:'ease-in-out'};
 if(t.k==='morph'){const cv=s.querySelector('.cv'),ocv=o.querySelector('.cv'),used=new Set(),R=e=>e.getBoundingClientRect(),mt=new Set();
  if(cv&&ocv)for(const e of cv.querySelectorAll(':scope>.it[data-m]')){
   const m=[...ocv.querySelectorAll(':scope>.it[data-m]')].find(x=>!used.has(x)&&x.dataset.m===e.dataset.m);if(!m)continue;
   used.add(m);mt.add(e);m.style.visibility='hidden';hid.push(m);const a=R(m),b=R(e),end=e.style.translate||'0px 0px';
   run.push(e.animate({translate:[`${a.left+a.width/2-b.left-b.width/2}px ${a.top+a.height/2-b.top-b.height/2}px`,end],
    scale:[`${a.width/b.width} ${a.height/b.height}`,'1 1']},opt))}
  s.style.background='transparent';
  for(const e of s.querySelectorAll(':scope>:not(.frame),.frame>:not(.cv),.cv>.it'))if(!mt.has(e))run.push(e.animate({opacity:[0,1]},opt));
  for(const e of o.querySelectorAll(':scope>:not(.frame),.frame>:not(.cv),.cv>.it'))run.push(e.animate({opacity:[1,0]},{...opt,fill:'forwards'}))}
 else run.push(s.animate({opacity:[0,1]},opt));
 Promise.all(run.map(a=>a.finished.catch(()=>0))).then(()=>{o.classList.remove('leaving');s.style.background=bg0;
  hid.forEach(e=>e.style.visibility='');o.getAnimations({subtree:true}).forEach(a=>a.cancel())})}
function go(n,end){const old=slides[cur],fw=!end&&n===cur+1&&stepping();document.getAnimations().forEach(a=>a.cancel());old.querySelectorAll('video').forEach(v=>v.pause());old.querySelectorAll('.yt iframe').forEach(x=>x.remove());
 cur=Math.max(0,Math.min(slides.length-1,n));step=end?maxStep():0;
 slides.forEach((s,i)=>{s.classList.toggle('active',i===cur);s.setAttribute('aria-hidden',i!==cur)});
 slides[cur].scrollTop=0;
 by('count').textContent=(cur+1)+' / '+slides.length;
 by('progress').style.width=((cur+1)/slides.length*100)+'%';
 upNotes();
 history.replaceState(null,'','#/'+(slides[cur].dataset.id||cur+1));ov.classList.remove('open');show(!end);fitCanvas(slides[cur]);if(fw)transition(old,slides[cur]);
}
const next=()=>{if(stepping()&&step<maxStep()){step++;show(true)}else go(cur+1)},prev=()=>{if(stepping()&&step>0){step--;show()}else go(cur-1,true)};
by('prev').onclick=prev;by('next').onclick=next;
addEventListener('hashchange',()=>{const h=decodeURIComponent(location.hash.replace(/^#\/?/,'')),i=/^\d+$/.test(h)?+h-1:slides.findIndex(s=>s.dataset.id===h);if(i>=0&&i!==cur)go(i)});
document.addEventListener('click',e=>{const y=e.target.closest('.yt');if(!y||y.querySelector('iframe'))return;const f=document.createElement('iframe');
 f.src=y.dataset.yt+(y.dataset.yt.includes('?')?'&':'?')+'autoplay=1';f.allow='autoplay; encrypted-media; fullscreen';f.allowFullscreen=true;
 f.title=y.getAttribute('aria-label');y.append(f)});
by('ovBtn').onclick=()=>ov.classList.toggle('open');
// speaker notes: N shows them in a panel in this tab, its button moves them to their own window for the presenter's screen
// (the window follows the slides and passes keys back)
let nw=null;
function upNotes(){const t=slides[cur].querySelector('.notes');nt.textContent=t?t.content.textContent:'';if(!nw||nw.closed)return;const d=nw.document;
 d.getElementById('c').textContent=(cur+1)+' / '+slides.length+'   '+(slides[cur].dataset.title||'');
 d.getElementById('n').textContent=t?t.content.textContent:''}
const notes=()=>body.classList.toggle('show-notes');
const notesWin=()=>{body.classList.remove('show-notes');if(nw&&!nw.closed){nw.focus();return}
 nw=window.open('','hsg-notes','width=720,height=520');if(!nw)return;const d=nw.document;d.title='Speaker notes';
 d.body.innerHTML='<p id="c"></p><div id="n"></div>';
 d.body.style.cssText='margin:0;padding:24px 32px;font:26px/1.5 system-ui,sans-serif;background:#fff;color:#111';
 d.getElementById('c').style.cssText='margin:0 0 16px;font-size:18px;color:#666';
 d.getElementById('n').style.whiteSpace='pre-wrap';
 d.onkeydown=key;upNotes()};
if(by('notesBtn')){by('notesBtn').onclick=notes;by('popBtn').onclick=notesWin}
if(!document.fullscreenEnabled)by('fsBtn').hidden=true;
let idle;const pill=document.querySelector('.pill'),wake=()=>{body.classList.add('awake');clearTimeout(idle);
 idle=setTimeout(()=>{if(!pill.matches(':hover'))body.classList.remove('awake')},2500)};
['mousemove','touchstart'].forEach(t=>document.addEventListener(t,wake,{passive:true}));
by('fsBtn').onclick=()=>document.fullscreenElement?document.exitFullscreen():root.requestFullscreen();
const grid=ov.querySelector('.ov-grid');
slides.forEach((s,i)=>{const b=document.createElement('button'),sm=document.createElement('small');
 sm.textContent=(i+1)+(s.dataset.time?'  ·  '+s.dataset.time:'');b.append(sm,s.dataset.title);b.onclick=()=>go(i);grid.append(b)});
function key(e){if(e.ctrlKey||e.metaKey||e.altKey)return;
 const inCtl=e.target instanceof Element&&e.target.closest('a,button');const k=e.key;
 if(['ArrowRight','PageDown'].includes(k)||(k===' '&&!inCtl)){e.preventDefault();next()}
 else if(['ArrowLeft','PageUp'].includes(k)){e.preventDefault();prev()}
 else if(k==='Home')go(0);else if(k==='End')go(slides.length-1);
 else if(k==='o'||k==='O')ov.classList.toggle('open');else if(k==='Escape')ov.classList.remove('open');
 else if(k==='f'||k==='F')by('fsBtn').click();else if(k==='n'||k==='N')notes();else if(k==='a'||k==='A')auto()}
document.addEventListener('keydown',key);
let x0=null;document.addEventListener('touchstart',e=>{x0=e.touches[0].clientX},{passive:true});
document.addEventListener('touchend',e=>{if(x0===null)return;const d=e.changedTouches[0].clientX-x0;x0=null;
 if(Math.abs(d)>60)(d<0?next():prev())},{passive:true});
function place(){if(matchMedia('(max-width:999px),(max-height:480px)').matches)return;
 const boxes=s=>{const out=[];s.querySelectorAll('.frame img,.cv img,.cv table,.cv svg path,.frame .box,.frame li,.frame td,.cv .tx p,.frame p,.frame h2').forEach(el=>{
  if(el.closest('.refs')||el.matches('.dfoot,.source,.pn')||el.closest('.pn'))return;
  if(el.matches('svg path')&&el.getAttribute('fill')==='none')return;
  let r;if(el.matches('p,li,h2,td')){const g=document.createRange();g.selectNodeContents(el);r=g.getBoundingClientRect()}else if(el.matches('.pimg img')){r=el.parentElement.getBoundingClientRect()}else r=el.getBoundingClientRect();
  if(r.width>1&&r.height>1)out.push(r)});return out};
 slides.forEach(s=>{const rf=s.querySelector('.refs');if(!rf)return;const prevVis=s.style.visibility;s.style.visibility='hidden';const bx=boxes(s);
  for(const c of ['','left','bottom']){rf.classList.remove('left','bottom');if(c)rf.classList.add(c);const q=rf.getBoundingClientRect();
   if(!bx.some(r=>r.right>q.left&&r.left<q.right&&r.bottom>q.top&&r.top<q.bottom))break}
  s.style.visibility=prevVis})}
// canvas text that runs out of its box (Gill Sans Regular is wider than the Light of many source decks) shrinks until it
// fits, as with PowerPoint's "shrink text on overflow", by at most 14%; if that is not enough it overflowed in PowerPoint too
let fontsOk=false;
function fitCanvas(s){const cv=s.querySelector('.cv');if(!fontsOk||!cv||!cv.clientWidth||s.dataset.fit)return;s.dataset.fit=1;
 const leaves=t=>t.scrollHeight>t.clientHeight+1||t.scrollWidth>t.clientWidth+1;
 for(const t of cv.querySelectorAll(':scope>.it>.tx:not(.v270):not(.v90)')){let f=1;
  while(leaves(t)&&f>.87){f-=.02;t.style.setProperty('--f',f.toFixed(2))}
  if(leaves(t))t.style.removeProperty('--f')}}
Promise.all([...document.fonts].filter(f=>f.family.replace(/"/g,'')==='HSGSans').map(f=>f.load().catch(()=>0)))
 .then(()=>document.fonts.ready).then(()=>{fontsOk=true;slides.forEach(fitCanvas);root.dataset.fit=1});
window.hsgDeck={go,next,prev,count:slides.length,place};(document.fonts&&document.fonts.ready?document.fonts.ready:Promise.resolve()).then(place);go(cur,arrived)})();
"""

# the slide number tab of the template (master freeform, 2.33U x 2.56U)
TAB = '<svg viewBox="0 0 3106057 3403600" preserveAspectRatio="none" aria-hidden="true"><path d="M0 711200L3106057 0V3403600L449943 3222171Z"/></svg>'


def units(text):
    """Write the slide unit U as CSS: 1U is 1% of the slide width."""
    return re.sub(r"(-?\d*\.?\d+)U\b", r"calc(\1*var(--u))", text)


def css():
    out = units(CSS)
    faces = ""
    for fam, w, style, local, file in FONTS:
        src = ",".join(f'local("{n}")' for n in local) + f",url(assets/{file}) format('opentype')"
        faces += f"@font-face{{font-family:{fam};font-weight:{w};font-style:{style};font-display:swap;src:{src}}}\n"
    return faces + out


def _f(v):
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _poly(pts):
    return "M" + "L".join(f"{_f(x)} {_f(y)}" for x, y in pts) + "Z"


def _ell(cx, cy, rx, ry):
    return f"M{_f(cx - rx)} {_f(cy)}A{_f(rx)} {_f(ry)} 0 1 1 {_f(cx + rx)} {_f(cy)}A{_f(rx)} {_f(ry)} 0 1 1 {_f(cx - rx)} {_f(cy)}Z"


def _round(w, h, r):
    r = min(r, w / 2, h / 2)
    return (f"M{_f(r)} 0H{_f(w - r)}A{_f(r)} {_f(r)} 0 0 1 {_f(w)} {_f(r)}V{_f(h - r)}A{_f(r)} {_f(r)} 0 0 1 {_f(w - r)} {_f(h)}"
            f"H{_f(r)}A{_f(r)} {_f(r)} 0 0 1 0 {_f(h - r)}V{_f(r)}A{_f(r)} {_f(r)} 0 0 1 {_f(r)} 0Z")


def _curved_right_arrow(w, h, adj1, adj2, adj3):
    """The curvedRightArrow preset of OOXML (presetShapeDefinitions.xml): the arrow body and its back part."""
    ss = min(w, h)
    a2 = min(max(adj2, 0), .5 * h / ss)
    a1 = min(max(adj1, 0), a2)
    th, aw = ss * a1, ss * a2
    hR = h / 2 - (th + aw) / 4
    q7 = hR * 2
    idx = math.sqrt(max(q7 * q7 - th * th, 0)) * w / q7
    ah = ss * min(max(adj3, 0), idx / ss)
    dy = math.sqrt(max(w * w - ah * ah, 0)) * hR / w
    y3, y5 = hR + th, hR + dy
    y7 = y3 + dy
    dh = (aw - th) / 2
    y4, y8, y6, x1 = y5 - dh, y7 + dh, h - aw / 2, w - ah
    sw = math.atan2(dy, ah)
    dang2 = math.atan2(th / 2, idx)
    pts, cur = [], [0.0, 0.0]

    def move(x, y):
        pts.append(f"M{_f(x)} {_f(y)}")
        cur[:] = [x, y]

    def line(x, y):
        pts.append(f"L{_f(x)} {_f(y)}")
        cur[:] = [x, y]

    def arc(st, swa):
        # OOXML arcTo: the current point lies on the ellipse (w, hR) at the visual angle st
        def par(a):
            return math.atan2(w * math.sin(a), hR * math.cos(a))
        t0 = par(st)
        cx, cy = cur[0] - w * math.cos(t0), cur[1] - hR * math.sin(t0)
        for k in range(1, 25):
            t = par(st + swa * k / 24)
            line(cx + w * math.cos(t), cy + hR * math.sin(t))

    pi = math.pi
    move(0, hR)
    arc(pi, -sw)
    line(x1, y4); line(w, y6); line(x1, y8); line(x1, y7)
    arc(pi - sw, sw)
    pts.append("Z")
    move(0, hR)
    arc(pi, pi / 2)
    line(w, th)
    arc(1.5 * pi, dang2 - pi / 2)
    pts.append("Z")
    return "".join(pts)


def _callout(w, h, adj, circles):
    """An ellipse with a pointer to (adj1, adj2); cloudCallout adds two small circles on the way."""
    a1, a2 = adj.get("adj1", -20833) / 100000, adj.get("adj2", 62500) / 100000
    cx, cy, rx, ry = w / 2, h / 2, w / 2, h / 2
    tx, ty = cx + a1 * w, cy + a2 * h
    th = math.atan2((ty - cy) / ry, (tx - cx) / rx)
    if circles:
        d = _ell(cx, cy, rx, ry)
        for k, r in ((0.55, min(w, h) * .09), (0.8, min(w, h) * .06)):
            d += _ell(cx + (tx - cx) * k * (1 + 0.45 / max(1e-6, math.hypot((tx - cx) / rx, (ty - cy) / ry))) * 0.78 + 0, cy + (ty - cy) * k * 0.95, r, r)
        return d
    dl = 0.28
    p1 = (cx + rx * math.cos(th + dl), cy + ry * math.sin(th + dl))
    p2 = (cx + rx * math.cos(th - dl), cy + ry * math.sin(th - dl))
    return f"M{_f(p1[0])} {_f(p1[1])}A{_f(rx)} {_f(ry)} 0 1 1 {_f(p2[0])} {_f(p2[1])}L{_f(tx)} {_f(ty)}Z"


def shape_paths(g, w, h, adj):
    """The outline of a preset PowerPoint shape of w x h U as SVG path data; adj holds the shape's adjust values."""
    m = min(w, h)
    A = lambda name, dflt: adj.get(name, dflt) / 100000
    if g in ("rect", "flowChartProcess"):
        return [f"M0 0H{_f(w)}V{_f(h)}H0Z"]
    if g == "roundRect":
        return [_round(w, h, m * A("adj", 16667))]
    if g in ("flowChartAlternateProcess", "flowChartTerminator"):
        return [_round(w, h, m / 6 if g == "flowChartAlternateProcess" else m / 2)]
    if g == "ellipse":
        return [_ell(w / 2, h / 2, w / 2, h / 2)]
    if g in ("rightArrow", "leftArrow", "leftRightArrow"):
        sh, hl = h * A("adj1", 50000), m * A("adj2", 50000)
        y0, y1 = (h - sh) / 2, (h + sh) / 2
        if g == "rightArrow":
            return [_poly([(0, y0), (w - hl, y0), (w - hl, 0), (w, h / 2), (w - hl, h), (w - hl, y1), (0, y1)])]
        if g == "leftArrow":
            return [_poly([(w, y0), (hl, y0), (hl, 0), (0, h / 2), (hl, h), (hl, y1), (w, y1)])]
        return [_poly([(0, h / 2), (hl, 0), (hl, y0), (w - hl, y0), (w - hl, 0), (w, h / 2), (w - hl, h), (w - hl, y1), (hl, y1), (hl, h)])]
    if g in ("downArrow", "upArrow"):
        sw, hl = w * A("adj1", 50000), m * A("adj2", 50000)
        x0, x1 = (w - sw) / 2, (w + sw) / 2
        if g == "downArrow":
            return [_poly([(x0, 0), (x1, 0), (x1, h - hl), (w, h - hl), (w / 2, h), (0, h - hl), (x0, h - hl)])]
        return [_poly([(x0, h), (x1, h), (x1, hl), (w, hl), (w / 2, 0), (0, hl), (x0, hl)])]
    if g == "curvedRightArrow":
        return [_curved_right_arrow(w, h, A("adj1", 25000), A("adj2", 50000), A("adj3", 25000))]
    if g in ("wedgeEllipseCallout", "cloudCallout"):
        return [_callout(w, h, adj, g == "cloudCallout")]
    if g in ("wedgeRectCallout", "wedgeRoundRectCallout"):
        a1, a2 = A("adj1", -20833), A("adj2", 62500)
        tx, ty = w / 2 + a1 * w, h / 2 + a2 * h
        base = _round(w, h, m * .1667) if g == "wedgeRoundRectCallout" else f"M0 0H{_f(w)}V{_f(h)}H0Z"
        sx = min(max(tx, w * .2), w * .8)
        return [base, _poly([(sx - w * .06, h if ty > h else 0), (tx, ty), (sx + w * .06, h if ty > h else 0)])]
    if g == "foldedCorner":
        f = m * A("adj", 16667)
        return [f"M0 0H{_f(w)}V{_f(h - f)}L{_f(w - f)} {_f(h)}H0Z", f"M{_f(w - f)} {_f(h)}V{_f(h - f)}H{_f(w)}"]
    if g == "snip1Rect":
        d = m * A("adj", 16667)
        return [_poly([(0, 0), (w - d, 0), (w, d), (w, h), (0, h)])]
    if g == "can":
        ry = h * A("adj", 25000) / 2
        return [f"M0 {_f(ry)}A{_f(w / 2)} {_f(ry)} 0 0 1 {_f(w)} {_f(ry)}V{_f(h - ry)}A{_f(w / 2)} {_f(ry)} 0 0 1 0 {_f(h - ry)}Z",
                f"M0 {_f(ry)}A{_f(w / 2)} {_f(ry)} 0 0 0 {_f(w)} {_f(ry)}"]
    if g == "plus":
        d = m * A("adj", 25000)
        return [_poly([(d, 0), (w - d, 0), (w - d, d), (w, d), (w, h - d), (w - d, h - d), (w - d, h), (d, h), (d, h - d), (0, h - d), (0, d), (d, d)])]
    if g == "triangle":
        return [_poly([(0, h), (w * A("adj", 50000), 0), (w, h)])]
    if g == "diamond":
        return [_poly([(w / 2, 0), (w, h / 2), (w / 2, h), (0, h / 2)])]
    if g == "hexagon":
        x = m * A("adj", 25000)
        return [_poly([(0, h / 2), (x, 0), (w - x, 0), (w, h / 2), (w - x, h), (x, h)])]
    if g == "parallelogram":
        x = m * A("adj", 25000)
        return [_poly([(x, 0), (w, 0), (w - x, h), (0, h)])]
    if g == "cloud":
        return [_ell(w / 2, h / 2, w / 2, h / 2)]
    if g == "leftBrace":
        return [f"M{_f(w)} 0C{_f(w * .4)} 0 {_f(w * .5)} {_f(h * .1)} {_f(w * .5)} {_f(h * .25)}V{_f(h * .4)}C{_f(w * .5)} {_f(h * .45)} {_f(w * .3)} {_f(h * .5)} 0 {_f(h * .5)}"
                f"C{_f(w * .3)} {_f(h * .5)} {_f(w * .5)} {_f(h * .55)} {_f(w * .5)} {_f(h * .6)}V{_f(h * .75)}C{_f(w * .5)} {_f(h * .9)} {_f(w * .4)} {_f(h)} {_f(w)} {_f(h)}"]
    if g == "mathEqual":
        th, gap = h * A("adj1", 23520), h * A("adj2", 11760)
        x0, x1 = w * (1 - .7349) / 2, w * (1 + .7349) / 2
        y2, y3 = (h - gap) / 2, (h + gap) / 2
        return [f"M{_f(x0)} {_f(y2 - th)}H{_f(x1)}V{_f(y2)}H{_f(x0)}Z", f"M{_f(x0)} {_f(y3)}H{_f(x1)}V{_f(y3 + th)}H{_f(x0)}Z"]
    if g == "arc":
        return [f"M{_f(w / 2)} 0A{_f(w / 2)} {_f(h / 2)} 0 0 1 {_f(w)} {_f(h / 2)}"]
    if g in ("line", "straightConnector1"):
        return [f"M0 0L{_f(w)} {_f(h)}"]
    if g == "curvedConnector2":
        return [f"M0 0C{_f(w / 2)} 0 {_f(w)} {_f(h / 2)} {_f(w)} {_f(h)}"]
    if g == "curvedConnector3":
        x = w * A("adj1", 50000)
        return [f"M0 0C{_f(x)} 0 {_f(x)} {_f(h)} {_f(w)} {_f(h)}"]
    if g == "bentConnector2":
        return [f"M0 0H{_f(w)}V{_f(h)}"]
    if g == "bentConnector3":
        x = w * A("adj1", 50000)
        return [f"M0 0H{_f(x)}V{_f(h)}H{_f(w)}"]
    return [f"M0 0H{_f(w)}V{_f(h)}H0Z"]


class Html:
    def __init__(self, deck, base, out):
        self.deck, self.base, self.out = deck, base, out
        self.assets = out / "assets"
        self.files = {}

    def asset(self, rel):
        """Copy a deck image next to the page and return its relative URL."""
        src = (self.base / rel).resolve()
        if src not in self.files:
            name = re.sub(r"[^A-Za-z0-9._-]", "-", src.name)
            if name in set(self.files.values()):
                name = f"{len(self.files)}-{name}"
            shutil.copyfile(src, self.assets / name)
            self.files[src] = name
        return "assets/" + self.files[src]

    def ref_url(self, to):
        """The address of another slide, relative to this page (decks live in sibling folders); "#/id" in this deck."""
        folder, sid, _, _ = hd.resolve(to, self.base)
        return f"#/{sid}" if folder == self.base.name else f"../../{folder}/html/index.html#/{sid}"

    @staticmethod
    def new_tab(url):
        """Link attributes: a slide of this deck opens in the same tab, everything else in a new one."""
        return "" if url.startswith("#") else ' target="_blank" rel="noopener" title="Opens in a new tab"'

    def ref_chip(self, r):
        folder, sid, tslide, tdeck = hd.resolve(r["to"], self.base)
        kind = r.get("kind", "see")
        word = {"recap": "Recap", "next": "Pointer", "see": "See also"}[kind]
        where = tdeck.get("ref_label") or plain(tdeck["title"])
        title = r.get("label") or plain(tslide["title"]).replace("\n", " ")
        ext = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17L17 7M9 7h8v8"/></svg>'
        return (f'<a class="ref" href="{self.ref_url(r["to"])}" target="_blank" rel="noopener" title="{esc(where)}: {esc(title)} (opens in a new tab)">'
                f'<b>{word}</b><span class="lab">{esc(where)}: {esc(title)}</span>{ext}</a>')

    @staticmethod
    def htitle(text):
        """Escape a headline and apply its one inline mark, **bold**; a line break is written as \\n."""
        return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", esc(text)).replace("\n", "<br>")

    def mark(self, text):
        """Escape a text and apply the inline marks: **bold**, *italic*, `code`, ==marker==, x_{2}, 2^{n}, [link](url),
        [link](08#slide-id) for another slide (opens in a new tab)."""
        t = esc(text)
        codes = []
        t = re.sub(r"`([^`]+)`", lambda m: codes.append(m.group(1)) or f"\x00{len(codes) - 1}\x00", t)
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
        t = hd.INLINE_REF.sub(lambda m: (lambda u: f'<a class="il" href="{u}"{self.new_tab(u)}>{m.group(1)}</a>')(self.ref_url(m.group(2))), t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*", r"<em>\1</em>", t)
        t = re.sub(r"==([^=]+)==", r"<mark>\1</mark>", t)
        t = re.sub(r"_\{([^}]*)\}", r"<sub>\1</sub>", t)
        t = re.sub(r"\^\{([^}]*)\}", r"<sup>\1</sup>", t)
        t = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", t)
        return t.replace("\n", "<br>")

    def points(self, pts):
        if not pts:
            return ""
        li = ""
        for p in pts:
            if isinstance(p, dict):
                sub = "".join(f"<li>{self.mark(x)}</li>" for x in p.get("sub", []))
                li += f"<li>{self.mark(p['text'])}" + (f"<ul>{sub}</ul>" if sub else "") + "</li>"
            else:
                li += f"<li>{self.mark(p)}</li>"
        return f'<ul class="dash">{li}</ul>'

    def paras(self, ps):
        return "".join(f"<p>{self.mark(p)}</p>" for p in ps or [])

    def box(self, b, cls=""):
        st = b.get("style", "green")
        head = f'<h3>{esc(b["heading"])}</h3>' if b.get("heading") else ""
        return f'<div class="box {st}{cls}">{head}{self.mark(b["text"])}</div>'

    def picture(self, p, cls=""):
        shadow = " shadow" if p.get("shadow", True) else ""
        cap = f'<figcaption>{self.mark(p["caption"])}</figcaption>' if p.get("caption") else ""
        return f'<figure class="pic{shadow}{cls}"><img src="{self.asset(p["image"])}" alt="{esc(p["alt"])}">{cap}</figure>'

    def code(self, code, style="outline", caption=None):
        small = " small" if len(code.split("\n")) > 13 or max(len(l) for l in code.split("\n")) > 52 else ""
        cap = f'<p class="codecap">{self.mark(caption)}</p>' if caption else ""
        return f'<div><pre class="code {style}{small}">{esc(code)}</pre>{cap}</div>'

    def head(self, s):
        h = f'<h2>{self.htitle(s["title"])}</h2>'
        wide = " wide" if s.get("callout", {}).get("wide") else ""
        c = f'<aside class="callout box {s["callout"].get("style", "green")}{wide}">{self.mark(s["callout"]["text"])}</aside>' if s.get("callout") else ""
        lead = f'<p class="lead">{self.mark(s["lead"])}</p>' if s.get("lead") else ""
        return f'<div class="headrow"><div>{h}</div>{c}</div>{lead}'

    def main(self, s, inner, cls=""):
        return f'{self.head(s)}<div class="main{cls}">{inner}</div>'

    @staticmethod
    def density(*parts):
        """Running text is set at body size; when there is a lot of it, one step smaller (never smaller than that)."""
        return " dense" if len(" ".join(hd.words(p) for p in parts).split()) > 55 else ""

    # ---- layouts: each returns the inside of .frame

    def l_title(self, s):
        pic, st = s.get("picture"), s.get("style", "gear")
        src, alt = (self.asset(pic["image"]), esc(pic["alt"])) if pic else ("assets/title-photo.jpg", "")
        if st == "photo":                              # the template's title slide 1: a photo behind the whole slide
            art = f'<img class="bgphoto" src="{src}" alt="{alt}">'
        else:
            art = (f'<img class="gear" src="{self.asset(pic["image"])}" alt="{esc(pic["alt"])}">' if pic else
                   '<img class="gear" src="assets/title-gear.png" alt="Word cloud of research topics in the shape of a gear">'
                   ) + '<div class="veil"></div>'
        kick = f'<p class="kicker">{esc(s["kicker"])}</p>' if s.get("kicker") else ""
        body = ""
        if s.get("presenters"):
            body += f'<p>{esc(", ".join(s["presenters"]))}</p>'
        if s.get("affiliation"):                       # grey lines right under the names, as on the template
            body += '<p class="affil">' + "<br>".join(esc(x) for x in s["affiliation"]) + "</p>"
        if s.get("meta"):
            body += "<p>" + "<br>".join(esc(x) for x in s["meta"]) + "</p>"
        logo = '<img class="logo" src="assets/hsg_logo.png" alt="University of St.Gallen">'
        sub = f'<p class="subtitle">{esc(s["subtitle"])}</p>' if s.get("subtitle") else ""
        head = f'<div class="tblock t-{st}">{kick}<h1>{self.htitle(s["title"])}</h1>{sub}</div>'
        tbody = f'<div class="tbody t-{st}">{body}</div>' if body else ""
        event = " | ".join(esc(s[k]) for k in ("date", "venue") if s.get(k))   # bottom left, on the tagline's line
        tbody += f'<p class="tevent">{event}</p>' if event else ""
        if st in ("side", "slanted"):                  # the template's title slides 2 and 3
            frame = ('<svg class="tframe" viewBox="0 0 26.46 29.42" preserveAspectRatio="none" aria-hidden="true"><polygon '
                     'points="0,6.51 26.46,0 26.39,29.42 3.89,27.27" fill="none" stroke="#00802F" stroke-width=".56"/></svg>'
                     if st == "slanted" else "")
            return (logo + head + tbody + frame + f'<img class="tpic {st}" src="{src}" alt="{alt}">'
                    f'<p class="tagline {st}">From insight to impact.</p>')
        return (f'<div class="art">{art}</div>{logo}{head}{tbody}'
                + '<div class="wedge"><p class="tagline">From insight to impact.</p></div>')

    def l_section(self, s):
        kick = f'<p class="kicker">{esc(s["kicker"])}</p>' if s.get("kicker") else ""
        return (f'<img class="logo" src="assets/hsg_logo.png" alt="University of St.Gallen">'
                f'<div class="tblock">{kick}<h1>{self.htitle(s["title"])}</h1></div><div class="wedge"></div>')

    def l_menu(self, s):
        cur = s.get("current")
        cur = set(cur if isinstance(cur, list) else [cur])
        items = "".join(f'<p{" class=cur" if i in cur else ""}>{self.mark(x)}</p>' for i, x in enumerate(s["items"], 1))
        return self.main(s, f'<div class="menu">{items}</div>')

    def text_copy(self, s):
        c = self.paras(s.get("paragraphs")) + self.points(s.get("points"))
        if s.get("defs"):
            c += '<dl class="defs">' + "".join(f"<dt>{self.mark(a)}</dt><dd>{self.mark(b)}</dd>" for a, b in s["defs"]) + "</dl>"
        if s.get("groups"):
            c += '<div class="groups">' + "".join(
                f'<div class="group"><h3>{esc(g["heading"])}</h3>{self.paras(g.get("paragraphs"))}{self.points(g.get("points"))}</div>'
                for g in s["groups"]) + "</div>"
        return f'<div class="copy">{c}</div>'

    def aside(self, a):
        if a.get("image"):
            return self.picture(a)
        if a.get("box"):
            return self.box(a["box"])
        return self.code(a["code"])

    def l_text(self, s):
        dense = self.density(s.get("paragraphs"), s.get("points"), s.get("groups"), s.get("defs"))
        copy = self.text_copy(s) if any(s.get(k) for k in ("paragraphs", "points", "defs", "groups")) else ""
        if s.get("tiles"):
            copy += '<div class="tiles3">' + "".join(
                f'<div class="tile"><span class="ticon{" dot" if t["icon"] == "dot" else ""}" aria-hidden="true">'
                f'{"" if t["icon"] == "dot" else esc(t["icon"])}</span><p>{self.mark(t["text"])}</p></div>' for t in s["tiles"]) + "</div>"
        if s.get("aside"):
            wide = " wide" if s["aside"].get("code") else ""
            copy = f'<div class="split{wide}">{copy}{self.aside(s["aside"])}</div>'
        after = f'<p class="after">{self.mark(s["after"])}</p>' if s.get("after") else ""
        return self.main(s, copy + after, dense)

    def l_study(self, s):
        dense = self.density(s.get("lead"), s.get("groups"))
        body = self.text_copy(s)
        if s.get("aside"):
            body = f'<div class="split">{body}{self.aside(s["aside"])}</div>'
        return '<img class="bulb" src="assets/lightbulb.jpg" alt="Drawing of a lit light bulb">' + self.main(s, body, dense)

    def l_questions(self, s):
        fig = '<div class="figure"><img src="assets/questions.png" alt="A figure sits thinking on a large green question mark"></div>'
        if not s.get("points"):
            return self.main(s, fig)
        copy = (f'<p class="takeh">{esc(s.get("heading", "Take-Home"))}</p>' if s.get("heading", "Take-Home") else "") + self.points(s["points"])
        after = f'<p class="after">{self.mark(s["after"])}</p>' if s.get("after") else ""
        return self.main(s, f'<div class="split"><div>{copy}</div>{fig}</div>{after}')

    def l_table(self, s):
        head = "".join(f"<th>{self.mark(c)}</th>" for c in s["columns"])
        rows = "".join("<tr>" + "".join(f"<td>{self.mark(c)}</td>" for c in r) + "</tr>" for r in s["rows"])
        many = " many" if len(s["rows"]) > 7 or len(s["columns"]) > 4 else ""
        after = f'<p class="after" style="padding-left:0">{self.mark(s["after"])}</p>' if s.get("after") else ""
        return self.main(s, f'<div class="tablewrap"><table class="t{many}"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>{after}')

    def l_code(self, s):
        code = self.code(s["code"], s.get("style", "outline"), s.get("caption"))
        copy = self.paras(s.get("paragraphs")) + self.points(s.get("points"))
        inner = f'<div class="split wide"><div class="copy">{copy}</div>{code}</div>' if copy else code
        return self.main(s, inner, " dense" if copy else "")

    def l_quiz(self, s):
        boxes = "".join(f'<div class="box green">{self.mark(x)}</div>' for x in s["items"])
        quiz = f'<div class="quiz n{len(s["items"])}">{boxes}</div>'
        if s.get("aside"):
            quiz = f'<div class="split wide">{quiz}{self.picture(s["aside"])}</div>'
        return self.main(s, quiz)

    def l_task(self, s):
        copy = f'<div class="copy">{self.paras(s["paragraphs"])}</div>' if s.get("paragraphs") else ""
        link = (f'<a class="go" href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s.get("label") or s["url"])}</a>'
                if s.get("url") else "")
        return self.main(s, f'<div class="task{"" if copy else " solo"}">{copy}<p class="stamp">{self.mark(s["stamp"])}</p>{link}</div>')

    def l_image(self, s):
        return self.main(s, self.picture(s, " big"))

    def l_gallery(self, s):
        pics = "".join(self.picture(it) for it in s["items"])
        after = f'<p class="after" style="padding-left:0">{self.mark(s["after"])}</p>' if s.get("after") else ""
        qr = " qr" if s.get("style") == "qr" else ""
        return self.main(s, f'<div class="gallery{qr}" style="--n:{len(s["items"])}">{pics}</div>{after}')

    def l_people(self, s):
        out = ""
        for it in s["items"]:
            img = f'<img src="{self.asset(it["photo"])}" alt="{esc(it.get("alt") or "Portrait of " + it["name"])}">' if it.get("photo") else ""
            role = f'<p class="role">{esc(it["role"]).replace(chr(10), "<br>")}</p>' if it.get("role") else ""
            out += f'<div class="person">{img}<div><p class="name">{esc(it["name"])}</p>{role}</div></div>'
        n = len(s["items"])
        return self.main(s, f'<div class="people n{n}" style="--n:{n}">{out}</div>')

    def l_quote(self, s):
        h = f'<div class="headrow"><div><h2>{self.htitle(s["title"])}</h2>' + (
            f'<p class="attr">{esc(s["attribution"])}</p>' if s.get("attribution") else "") + "</div></div>"
        pic = self.picture(s["picture"]) if s.get("picture") else "<div></div>"
        pts = self.points(s.get("points"))
        return h + f'<div class="qbody">{pic}<div>{pts}</div></div>'

    def l_syllabus(self, s):
        cur = s.get("current")
        cur = set(cur if isinstance(cur, list) else [cur])
        rows = ""
        for i, it in enumerate(s["items"], 1):
            cls = " cur" if i in cur else " ex" if it.get("kind") == "exercise" else ""
            if it.get("href"):
                rows += (f'<span class="date">{esc(it["date"])}</span><a class="bar{cls}" href="{self.ref_url(it["href"])}" target="_blank" '
                         f'rel="noopener" title="Open the slides of this session in a new tab">{esc(it["title"])}</a>')
            else:
                rows += f'<span class="date">{esc(it["date"])}</span><div class="bar{cls}">{esc(it["title"])}</div>'
            if s.get("break_after") == i:
                rows += '<span></span><div class="brk" aria-label="Break"></div>'
        legend = '<div class="legend"><span class="lg-l">Lecture</span><span class="lg-e">Exercise</span><span class="lg-a">Assignment</span></div>'
        # assignment boxes span the rows of their sessions: one grid row per session, plus one for the break
        n = len(s["items"]) + (1 if s.get("break_after") else 0)
        def row(i):
            return i + (1 if s.get("break_after") and i > s["break_after"] else 0)
        boxes = "".join(f'<div style="grid-row:{row(a["from"])}/{row(a["to"]) + 1}">{esc(a["title"])}</div>'
                        for a in s.get("assignments", []))
        assign = f'<div class="assign" style="grid-template-rows:repeat({n},auto)">{boxes}</div>' if boxes else ""
        return self.main(s, f'<div class="plan">{legend}<div class="rows">{rows}</div>{assign}</div>')


    # ---- canvas: a slide copied from PowerPoint (see pptx_canvas.py)

    @staticmethod
    def cv_pos(it):
        st = f'left:{_f(it["x"])}%;top:{_f(it["y"] / .5625)}%;width:{_f(it["w"])}%;height:{_f(it["h"] / .5625)}%'
        if it.get("rot"):
            st += f';transform:rotate({it["rot"]}deg)'
        return st

    @staticmethod
    def cv_attrs(it):
        a = f' data-s="{it["s"]}"' if it.get("s") else ""
        a += f" data-an='{esc(json.dumps(it['an'], separators=(',', ':')))}'" if it.get("an") else ""
        m = it.get("src") or "".join(r.get("t", "") for p in (it.get("tx") or {}).get("p", []) for r in p["r"]).strip()
        a += f' data-m="{esc(m)}"' if m else ""      # Morph pairs objects with the same picture or text
        return a + (f' data-e="{it["e"]}"' if it.get("e") is not None else "")

    def cv_text(self, tx, cls=""):
        if not tx:
            return ""
        ins = tx.get("i", [.8, .4, .8, .4])
        v = {"vert270": " v270", "vert": " v90"}.get(tx.get("v"), "")
        out = ""
        for p in tx["p"]:
            st = f'text-align:{ {"c": "center", "r": "right", "j": "justify"}.get(p["al"], "left") }'
            if p.get("pl") or p.get("in"):
                st += f';padding-left:calc({p.get("pl", 0)}*var(--u));text-indent:calc({p.get("in", 0)}*var(--u))'
            if p.get("ls"):
                st += f';line-height:{p["ls"] * 1.2:.3f}'
            if p.get("sb"):
                st += f';margin-top:calc({p["sb"]}*var(--u))'
            if p.get("sa"):
                st += f';margin-bottom:calc({p["sa"]}*var(--u))'
            runs = ""
            if p.get("bu"):
                runs += f'<span class="bu" style="width:calc({-p.get("in", -1.8)}*var(--u));text-indent:0">{esc(p["bu"])}</span>'
            for r in p["r"]:
                if r.get("br"):
                    runs += "<br>"
                    continue
                rs = f'font-size:calc({r["sz"]}*var(--u)*var(--f,1))'
                if r.get("c"):
                    rs += f';color:{r["c"]}'
                if r.get("u") or r.get("st"):
                    rs += ";text-decoration:" + " ".join(x for x, k in (("underline", "u"), ("line-through", "st")) if r.get(k))
                if r.get("i"):
                    rs += ";font-style:italic"
                if r.get("ff"):
                    rs += f";font-family:'{r['ff']}',HSGSans,sans-serif"
                if r.get("bl"):
                    rs += f';vertical-align:{"super" if r["bl"] > 0 else "sub"};font-size:calc({r["sz"] * .65}*var(--u)*var(--f,1))'
                c = f' class="{r["f"]}"' if r.get("f") else ""
                body = esc(r["t"])
                body = f"<b>{body}</b>" if r.get("b") else body
                span = f'<span{c} style="{rs}">{body}</span>'
                if r.get("href"):
                    h = r["href"]
                    url = h if h.startswith(("http://", "https://")) else self.ref_url(h)
                    span = f'<a class="il" href="{esc(url)}"{self.new_tab(url)}>{span}</a>'
                runs += span
            first = max((r.get("sz", 1.9) for r in p["r"] if "sz" in r), default=1.9)
            ds = f' data-s="{p["s"]}"' if p.get("s") else ""
            out += f'<p{ds} style="{st};font-size:calc({first}*var(--u)*var(--f,1))">{runs}</p>'
        pad = f'padding:calc({ins[1]}*var(--u)) calc({ins[2]}*var(--u)) calc({ins[3]}*var(--u)) calc({ins[0]}*var(--u))'
        return f'<div class="tx {tx.get("a", "t")}{" nw" if tx.get("nw") else ""}{v}{cls}" style="{pad}">{out}</div>'

    def cv_shape(self, it, n):
        w, h = it["w"], it["h"]
        g = it.get("g", "rect")
        svg = ""
        if it.get("fill") or it.get("ln"):
            if g == "path":
                paths = [(p["d"], p["fill"], p["stroke"]) for p in it["paths"]]
            else:
                paths = [(d, k == 0 or g == "mathEqual", True) for k, d in enumerate(shape_paths(g, w, h, it.get("adj", {})))]
            col, lw = it.get("ln"), it.get("lw", .1)
            is_line = g in ("line", "straightConnector1", "curvedConnector2", "curvedConnector3", "bentConnector2", "bentConnector3", "arc")
            defs, marks = "", ""
            for pos, key in (("start", "head"), ("end", "tail")):
                if it.get(key) and col:
                    self.nmark = getattr(self, "nmark", 0) + 1      # ids are unique in the page, not only in the slide
                    mid = f"m{self.nmark}{pos[0]}"
                    big = 5 if it[key] in ("triangle", "arrow", "stealth") else 3.5
                    shape = ('<circle cx="5" cy="5" r="4.5"/>' if it[key] == "oval" else
                             '<path d="M0 0L10 5L0 10z"/>' if it[key] != "arrow" else '<path d="M1 1L9 5L1 9" fill="none" stroke="' + col + '" stroke-width="1.6"/>')
                    defs += (f'<marker id="{mid}" viewBox="0 0 10 10" refX="{9 if it[key] != "oval" else 5}" refY="5" markerWidth="{big}" markerHeight="{big}" '
                             f'orient="auto-start-reverse" fill="{col}">{shape}</marker>')
                    marks += f' marker-{pos}="url(#{mid})"'
            dash = ""
            if it.get("dash") and it["dash"] != "solid":
                u = lw
                dash = f' stroke-dasharray="{_f(u * 3)} {_f(u * 2)}"' if "dash" in it["dash"].lower() else f' stroke-dasharray="{_f(u)} {_f(u * 1.5)}"'
            flip = ""
            if it.get("fx") or it.get("fy"):
                sx, sy = (-1 if it.get("fx") else 1), (-1 if it.get("fy") else 1)
                flip = f' transform="translate({_f(w) if sx < 0 else 0} {_f(h) if sy < 0 else 0}) scale({sx} {sy})"'
            body = ""
            for d, fl, stk in paths:
                fill = it.get("fill") if (fl and not is_line) else None
                fa = f' fill-opacity="{it["fa"]}"' if it.get("fa") and fill else ""
                stroke = f' stroke="{col}" stroke-width="{_f(lw)}" stroke-linejoin="round" stroke-linecap="round"{dash}' if col and stk else ""
                body += f'<path d="{d}" fill="{fill or "none"}"{fa}{stroke}{marks if is_line or g == "path" else ""}/>'
            svg = f'<svg viewBox="0 0 {_f(w)} {_f(h)}" preserveAspectRatio="none" aria-hidden="true"><defs>{defs}</defs><g{flip}>{body}</g></svg>'
        return f'<div class="it" style="{self.cv_pos(it)}"{self.cv_attrs(it)}>{svg}{self.cv_text(it.get("tx"))}</div>'

    def cv_pic(self, it):
        cl, ct, cr, cb = it.get("crop", [0, 0, 0, 0])
        iw, ih = 1 - cl - cr, 1 - ct - cb
        st = f"left:{_f(-cl / iw * 100)}%;top:{_f(-ct / ih * 100)}%;width:{_f(100 / iw)}%;height:{_f(100 / ih)}%"
        cls = " shadow" if it.get("shadow") else ""
        if it.get("fx") or it.get("fy"):                 # a mirrored picture
            st += f';transform:scale({-1 if it.get("fx") else 1},{-1 if it.get("fy") else 1})'
        if it.get("video"):
            src = (self.base / it["video"]).resolve()
            served = self.out / "media" / src.name      # the copy already published with the deck
            if not src.exists() and not served.exists():
                print(f"WARNING: video {it['video']} not found (neither {src} nor {served}); showing its poster only", file=sys.stderr)
            if src.exists() or served.exists():
                if src.exists() and src != served.resolve():
                    (self.out / "media").mkdir(exist_ok=True)
                    shutil.copyfile(src, served)
                typ = {"mov": "video/quicktime", "mp4": "video/mp4", "webm": "video/webm"}.get(src.suffix[1:].lower(), "video/mp4")
                return (f'<div class="it{cls}" style="{self.cv_pos(it)}"{self.cv_attrs(it)}><div class="pimg">'
                        f'<video controls preload="none" poster="{self.asset(it["src"])}" aria-label="{esc(it.get("alt", ""))}">'
                        f'<source src="media/{src.name}" type="{typ}"></video></div></div>')
        if it.get("embed"):                  # online video: the poster, replaced by the player on click (as in PowerPoint)
            return (f'<div class="it{cls}" style="{self.cv_pos(it)}"{self.cv_attrs(it)}><button class="pimg yt" data-yt="{esc(it["embed"])}" '
                    f'aria-label="Play video: {esc(it.get("alt", ""))}"><img src="{self.asset(it["src"])}" alt="" style="{st}"></button></div>')
        return (f'<div class="it{cls}" style="{self.cv_pos(it)}"{self.cv_attrs(it)}><div class="pimg">'
                f'<img src="{self.asset(it["src"])}" alt="{esc(it.get("alt", ""))}" style="{st}"></div></div>')

    def cv_table(self, it):
        rows = ""
        tot = sum(it["cols"]) or 1
        cols = "".join(f'<col style="width:{_f(c / tot * 100)}%">' for c in it["cols"])
        for r in it["rows"]:
            tds = ""
            for c in r["cells"]:
                if c.get("hm"):
                    continue
                k = c.get("fill", "")
                st = f' style="background:{k}"' if k.startswith("#") else ""
                cls = f' class="{k}"' if k in ("head", "a", "b") else ""
                span = f' colspan="{c["cs"]}"' if c.get("cs") else ""
                tds += f'<td{cls}{st}{span}>{self.cv_text(c.get("tx"))}</td>'
            rows += f'<tr style="height:{_f(r["h"] / .5625 / (it["h"] / .5625) * 100)}%">{tds}</tr>'
        return f'<div class="it" style="{self.cv_pos(it)}"{self.cv_attrs(it)}><table><colgroup>{cols}</colgroup>{rows}</table></div>'

    def l_canvas(self, s):
        out = ""
        for n, it in enumerate(s.get("items", [])):
            if it["k"] == "shape":                         # a horizontal or vertical line has no area; give it a hairline box
                it = {**it, "w": max(it["w"], .05), "h": max(it["h"], .05)}
            out += getattr(self, "cv_" + {"shape": "shape", "pic": "pic", "table": "table"}[it["k"]])(*((it, n) if it["k"] == "shape" else (it,)))
        head = f'<div class="headrow"><div><h2>{self.htitle(s["title"])}</h2></div></div>' if s.get("title") else ""
        return head + f'<div class="cv">{out}</div>'

    def theme(self):
        """An optional theme: a CSS file named in the deck, set on top of the template; files it links with url() are copied."""
        if not self.deck.get("theme"):
            return ""
        path = (self.base / self.deck["theme"]).resolve()

        def copy(m):
            ref = m.group(1).strip("'\"")
            if re.match(r"(data:|https?:|#)", ref):
                return m.group(0)
            src = (path.parent / ref).resolve()
            shutil.copyfile(src, self.assets / src.name)
            return f'url("assets/{src.name}")'
        return "\n<style>" + units(re.sub(r"url\(([^)]+)\)", copy, path.read_text(encoding="utf-8"))) + "</style>"

    def page(self):
        d = self.deck
        n_all = len(d["slides"])
        sections = ""
        for n, s in enumerate(d["slides"], 1):
            lay = s["layout"]
            inner = getattr(self, "l_" + lay)(s)
            if s.get("decor"):
                dots = "".join(f'<i style="left:{it["x"]}%;top:{it["y"]}%;--d:{it["size"]}"></i>' for it in s["decor"] if not it.get("emoji"))
                emo = "".join(f'<span style="left:{it["x"]}%;top:{it["y"]}%;font-size:calc({it["size"]}*var(--u));transform:rotate({it.get("rot", 0)}deg)">'
                              f'{esc(it["emoji"])}</span>' for it in s["decor"] if it.get("emoji"))
                inner = ((f'<div class="odots" aria-hidden="true">{dots}</div>' if dots else "")
                         + (f'<div class="emojis" aria-hidden="true">{emo}</div>' if emo else "") + inner)
            extra = ""
            if lay not in ("title", "section"):
                if s.get("source"):
                    extra += f'<p class="source">{self.mark(s["source"])}</p>'
                if d.get("footer"):
                    extra += f'<p class="dfoot">{esc(d["footer"])}</p>'
                extra += f'<span class="pn" aria-hidden="true">{TAB}{n}</span>'
            if s.get("refs"):
                pos = " bottom" if s.get("refs_at") == "bottom" else ""
                extra += (f'<nav class="refs{pos}" aria-label="Related slides, they open in a new tab">'
                          + "".join(self.ref_chip(r) for r in s["refs"]) + "</nav>")
            notes = f'<template class="notes">{esc(s["notes"])}</template>' if s.get("notes") else ""
            t = f' data-time="{esc(str(s["time"]))}"' if s.get("time") else ""
            bare = " bare" if lay == "questions" and not s.get("points") else ""
            bare += " ta-t" if s.get("ta") == "t" else ""
            steps = max([i.get("s", 0) for i in s.get("items", [])] + [p.get("s", 0) for i in s.get("items", [])
                        for p in (i.get("tx") or {}).get("p", [])] + [a["s"] for i in s.get("items", []) for a in i.get("an", [])]
                        + [0]) if lay == "canvas" else 0
            ds = (f' data-steps="{steps}"' if steps else "") + (f' data-id="{esc(s["id"])}"' if s.get("id") else "")
            ds += f" data-tr='{esc(json.dumps(s['transition']))}'" if s.get("transition") else ""
            ds += f' style="background:{esc(s["bg"])}"' if s.get("bg") else ""      # background copied from PowerPoint
            sections += (f'<section class="slide l-{lay}{bare}{" active" if n == 1 else ""}" id="s{n}" data-title="{esc(plain(s["title"]) or f"Slide {n}")}"{t}{ds} '
                         f'aria-label="Slide {n} of {n_all}"><div class="frame">{inner}</div>{extra}{notes}</section>\n')

        def ico(paths, cls=""):
            c = f' class="{cls}"' if cls else ""
            return f'<svg{c} viewBox="0 0 24 24" aria-hidden="true">{paths}</svg>'
        sq = "".join(f'<rect x="{x}" y="{y}" width="7" height="7" rx="1.5"/>' for x in (4, 13) for y in (4, 13))
        back, fwd = '<path d="M15 5l-7 7 7 7"/>', '<path d="M9 5l7 7-7 7"/>'
        note = '<rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="M8 9h8M8 12.5h8M8 16h4"/>'
        grow, shrink = '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>', '<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/>'
        notes_btn = f'<button id="notesBtn" title="Speaker notes (N)">{ico(note)}Notes</button>' if any(s.get("notes") for s in d["slides"]) else ""
        dl = '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>'
        pv = d.get("pdf_version")
        pdf_btn = (f'<a class="tbtn" id="pdfBtn" href="{esc(d["pdf"])}" download title="Download the slides as PDF'
                   f'{", version of " + esc(pv) if pv else ""}">{ico(dl)}PDF{" (" + esc(pv) + ")" if pv else ""}</a>'
                   if d.get("pdf") else "")
        play, pause = '<path d="M8 5l11 7-11 7z"/>', '<path d="M8 5v14M16 5v14"/>'
        sec = d.get("autoadvance")
        auto_btn = (f'<button id="autoBtn" data-sec="{sec}" title="Advance every {sec:g} seconds (A)">{ico(play, "auto-off")}'
                    f'{ico(pause, "auto-on")}Auto</button>') if sec else ""
        ctl = ('<div class="controls" role="navigation" aria-label="Presentation controls"><div class="pill"><div class="nav">'
               f'<button id="prev" title="Previous slide (←)" aria-label="Previous slide">{ico(back)}</button>'
               f'<span class="count" id="count">1 / {n_all}</span>'
               f'<button id="next" title="Next slide (→)" aria-label="Next slide">{ico(fwd)}</button>'
               '</div><i class="sep"></i><div class="tools">'
               f'<button id="ovBtn" title="All slides (O)">{ico(sq)}Overview</button>{notes_btn}{pdf_btn}{auto_btn}'
               f'<button id="fsBtn" title="Full screen (F)">{ico(grow, "fs-off")}<span class="fs-off">Full screen</span>'
               f'{ico(shrink, "fs-on")}<span class="fs-on">Exit</span></button></div></div>'
               '<div class="progress" aria-label="Slide progress"><span id="progress"></span></div></div>')
        return f"""<!doctype html>
<html lang="{esc(d.get('lang', 'en'))}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(plain(d['title']))} | University of St.Gallen</title>
<style>{css()}</style>{self.theme()}
</head>
<body>
<main aria-label="{esc(plain(d['title']))}">
{sections}</main>
{ctl}
<div class="overview" id="overview" role="dialog" aria-label="Slide overview"><h2>{esc(plain(d['title']))}</h2><div class="ov-grid"></div></div>
<div class="notes-view" id="notesView" aria-label="Speaker notes"><button id="popBtn" title="Notes in their own window">Open in<br>separate window</button><div id="notesText"></div></div>
<script>{JS}</script>
<script>{REVIEW_JS}</script>
</body>
</html>
"""

    def write(self):
        self.assets.mkdir(parents=True, exist_ok=True)
        for *_, f in FONTS:
            shutil.copyfile(hd.ASSETS / "fonts" / f, self.assets / f)
        for f in ("hsg_logo.png", "title-gear.png", "title-photo.jpg", "questions.png", "lightbulb.jpg"):
            shutil.copyfile(hd.ASSETS / f, self.assets / f)
        (self.out / "index.html").write_text(self.page(), encoding="utf-8")
        return self.out / "index.html"


OVERFLOW_JS = """() => {
  const s=document.querySelector('.slide.active'), f=s.querySelector('.frame'), bad=[];
  const fr=f.getBoundingClientRect();
  if(!s.matches('.l-canvas')&&(f.scrollHeight>f.clientHeight+1||f.scrollWidth>f.clientWidth+1)) bad.push('content is larger than the slide');
  for(const el of f.querySelectorAll('.main,.copy,.box,.pic,.menu,table,pre,.plan,.qbody,.stamp,.person')){
    if(el.matches('.main')&&el.scrollHeight>el.clientHeight+1) bad.push('the content runs into the foot of the slide');
    if(el.matches('pre')&&el.scrollWidth>el.clientWidth+1) bad.push('a code line is wider than its box');
    const r=el.getBoundingClientRect();
    if(!el.matches('.stamp')&&(r.bottom>fr.bottom+1||r.right>fr.right+1)) bad.push('a block reaches past the slide');
  }
  const pn=s.querySelector('.pn'), src=s.querySelector('.source');
  if(pn){const p=pn.getBoundingClientRect();
    for(const el of f.querySelectorAll('p:not(.cv *),li,td:not(.cv *),img:not(.cv *),pre,.box,.stamp')){const r=el.getBoundingClientRect();
      if(r.width&&r.right>p.left&&r.left<p.right&&r.bottom>p.top&&r.top<p.bottom){bad.push('something covers the slide number');break}}}
  if(src){const q=src.getBoundingClientRect();
    for(const el of f.querySelectorAll('.main>*')){const r=el.getBoundingClientRect();
      if(r.bottom>q.top+1&&r.left<q.right){bad.push('the content runs into the source line');break}}}
  const rf=s.querySelector('.refs');
  if(rf&&!matchMedia('(max-width:999px)').matches){const q=rf.getBoundingClientRect();
    for(const el of s.querySelectorAll('.cv .tx p,.cv img,.cv svg path,.cv table,.frame p:not(.dfoot):not(.source),.frame img,.frame li,.frame .box')){
      if(rf.contains(el))continue;let r;if(el.matches('p,li')){const g=document.createRange();g.selectNodeContents(el);r=g.getBoundingClientRect()}else if(el.matches('.pimg img'))r=el.parentElement.getBoundingClientRect();else r=el.getBoundingClientRect();if(!r.width||!r.height)continue;
      if(el.matches('svg path')&&(el.getAttribute('fill')==='none'))continue;
      if(r.right>q.left&&r.left<q.right&&r.bottom>q.top&&r.top<q.bottom){bad.push('the reference links cover content (set refs_at to bottom or move the link)');break}}}
  const m=f.querySelector('.main');
  if(m&&m.children.length&&!s.matches('.l-menu,.l-task,.bare')){const top=m.getBoundingClientRect().top+parseFloat(getComputedStyle(m).paddingTop);
    let lo=Infinity,hi=0;for(const c of m.children){const r=c.getBoundingClientRect();lo=Math.min(lo,r.top);hi=Math.max(hi,r.bottom)}
    const zone=m.getBoundingClientRect().bottom-top, fill=(hi-lo)/zone;
    if(fill<0.4) bad.push('THIN: the content fills only '+Math.round(fill*100)+'% of the slide');}
  return [...new Set(bad)];
}"""


# Review comments: only with ?review in the address (index.html?review), never while presenting. A box per slide,
# saved in the browser (localStorage); "Copy all" puts every comment with its slide number and title on the clipboard.
REVIEW_JS = r"""
(()=>{if(!/[?&]review\b/.test(location.search))return;
const slides=[...document.querySelectorAll('.slide')],K='hsg-review:'+document.title;
let c={};try{c=JSON.parse(localStorage.getItem(K))||{}}catch(e){}
const st=document.createElement('style');st.textContent=`#review{position:fixed;right:12px;bottom:72px;width:320px;z-index:50;background:#fff;
 border:2px solid #00802f;border-radius:6px;padding:8px;font:14px system-ui,sans-serif;box-shadow:0 2px 10px rgba(0,0,0,.25)}
#review b{display:block;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#review textarea{width:100%;box-sizing:border-box;font:inherit;resize:vertical;margin:6px 0 4px}#review button{font:inherit}
#review.min textarea,#review.min div{display:none}@media print{#review{display:none}}`;
const p=document.createElement('div');p.id='review';
p.innerHTML='<b title="click to fold"></b><textarea rows="5" placeholder="Comment on this slide (Esc to leave the box)"></textarea>'
 +'<div><button data-a="copy"></button> <button data-a="clear">Clear all</button></div>';
document.head.append(st);document.body.append(p);
const h=p.querySelector('b'),t=p.querySelector('textarea'),cp=p.querySelector('[data-a=copy]');
const cur=()=>slides.findIndex(s=>s.classList.contains('active'));
const title=n=>(slides[n-1]&&slides[n-1].dataset.title)||'';
const save=()=>{localStorage.setItem(K,JSON.stringify(c));cp.textContent='Copy all ('+Object.keys(c).length+')'};
let last=-1;const show=()=>{const i=cur();if(i===last)return;last=i;h.textContent='Slide '+(i+1)+': '+title(i+1);t.value=c[i+1]||'';save()};
h.onclick=()=>p.classList.toggle('min');
t.addEventListener('keydown',e=>{e.stopPropagation();if(e.key==='Escape')t.blur()});
t.addEventListener('input',()=>{const n=cur()+1;if(t.value.trim())c[n]=t.value;else delete c[n];save()});
cp.onclick=()=>{const txt=Object.keys(c).sort((a,b)=>a-b).map(n=>'Slide '+n+' ('+title(n)+'):\n'+c[n].trim()).join('\n\n');
 const done=()=>{cp.textContent='Copied';setTimeout(save,1500)};
 navigator.clipboard.writeText(txt).then(done,()=>{const a=document.createElement('textarea');a.value=txt;document.body.append(a);
  a.select();document.execCommand('copy');a.remove();done()})};
p.querySelector('[data-a=clear]').onclick=()=>{if(confirm('Delete all comments?')){c={};last=-1;show()}};
const mo=new MutationObserver(show);slides.forEach(s=>mo.observe(s,{attributes:true,attributeFilter:['class']}));show()})();
"""


def shots(index, folder, n, sel=None):
    """Screenshots for the visual check (all slides, or only the indices in sel). Returns a list of overflow messages."""
    from playwright.sync_api import sync_playwright
    from PIL import Image
    folder.mkdir(parents=True, exist_ok=True)
    full = sel is None
    sel = list(range(n)) if full else sel
    if full:
        for old in list(folder.glob("slide-*.png")) + list(folder.glob("phone-*.png")) + list(folder.glob("contact*.png")):
            old.unlink()
    problems, thin = [], []
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge")
        except Exception:
            b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 810})
        pg.goto(index.as_uri())
        pg.evaluate("document.fonts.ready")
        pg.wait_for_function("document.documentElement.dataset.fit")
        pg.wait_for_timeout(300)
        paths = []
        for i in sel:
            pg.evaluate("i => window.hsgDeck.go(i, true)", i)
            pg.wait_for_timeout(60)
            for msg in pg.evaluate(OVERFLOW_JS):
                (thin if msg.startswith("THIN") else problems).append(f"slide {i + 1}: {msg.replace('THIN: ', '')}")
            path = folder / f"slide-{i + 1:02d}.png"
            pg.screenshot(path=str(path))
            paths.append(path)
        pg.close()
        ph = b.new_page(viewport={"width": 390, "height": 844})
        ph.goto(index.as_uri())
        ph.evaluate("document.fonts.ready")
        ph.wait_for_function("document.documentElement.dataset.fit")
        ph.wait_for_timeout(300)
        phones = []
        for i in sel:
            ph.set_viewport_size({"width": 390, "height": 844})
            ph.evaluate("i => window.hsgDeck.go(i, true)", i)
            ph.wait_for_timeout(60)
            wide, tall = ph.evaluate("() => { const s = document.querySelector('.slide.active');"
                                     " return [s.scrollWidth > s.clientWidth + 1, s.scrollHeight - s.clientHeight]; }")
            if wide:
                problems.append(f"slide {i + 1}, phone: something is wider than the screen and does not wrap")
            if tall > 0:                      # show the whole slide, not only the part above the fold
                ph.set_viewport_size({"width": 390, "height": 844 + tall})
                ph.wait_for_timeout(60)
            path = folder / f"phone-{i + 1:02d}.png"
            ph.screenshot(path=str(path))
            phones.append(path)
        b.close()
    if not full:                              # a few slides: no contact sheets
        return problems
    pw = 300
    for c, start in enumerate(range(0, len(phones), 6), 1):
        ims = [Image.open(x).convert("RGB") for x in phones[start:start + 6]]
        ims = [im.resize((pw, im.height * pw // im.width)) for im in ims]
        sheet = Image.new("RGB", (len(ims) * (pw + 12) + 12, max(im.height for im in ims) + 24), "#888888")
        for k, im in enumerate(ims):
            sheet.paste(im, (12 + k * (pw + 12), 12))
        sheet.save(folder / f"contact-phone-{c:02d}.png")
    cols, tw = 3, 640
    th = tw * 810 // 1440
    for c, start in enumerate(range(0, len(paths), 9), 1):
        chunk = paths[start:start + 9]
        rows = -(-len(chunk) // cols)
        sheet = Image.new("RGB", (cols * tw + (cols + 1) * 12, rows * th + (rows + 1) * 12), "#888888")
        for j, pth in enumerate(chunk):
            t = Image.open(pth).convert("RGB").resize((tw, th))
            sheet.paste(t, (12 + (j % cols) * (tw + 12), 12 + (j // cols) * (th + 12)))
        sheet.save(folder / f"contact-{c:02d}.png")
    if thin:
        print("Thin slides (add the example, picture or question that the headline needs, or merge with a neighbour):")
        for m in thin:
            print("  - " + m)
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("--out", help="output folder (default: html/ next to the deck)")
    ap.add_argument("--shots", help="folder for check screenshots (keep it outside the repo)")
    ap.add_argument("--slides", help="with --shots: only these slides, e.g. 2 or 2,4-6 (fast; no contact sheets)")
    a = ap.parse_args()
    deck, base, warnings = hd.load(a.deck)
    out = Path(a.out).resolve() if a.out else base / "html"
    index = Html(deck, base, out).write()
    print(f"Saved {index} ({len(deck['slides'])} slides)")
    hd.report(warnings)
    if a.shots:
        n = len(deck["slides"])
        sel = None
        if a.slides:
            sel = sorted({k - 1 for part in a.slides.split(",") for k in
                          range(int(part.split("-")[0]), int(part.split("-")[-1]) + 1) if 1 <= k <= n})
        problems = shots(index, Path(a.shots).resolve(), n, sel)
        print(f"Screenshots in {Path(a.shots).resolve()}: slide-NN.png, contact-NN.png, phone-NN.png, contact-phone-NN.png")
        if problems:
            print("OVERFLOW, shorten the text or split the slide (never change sizes):", file=sys.stderr)
            for m in problems:
                print("  - " + m, file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()
