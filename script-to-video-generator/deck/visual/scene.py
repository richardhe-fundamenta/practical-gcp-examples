"""Visual renderer harness: assemble an LLM-authored, visualization-heavy page.

Each slide runs model-written JS against a fixed *scene-kit* (`s`). The kit
hands the model raw Rough.js (`s.rc`), `s.add()`, and `s.text()` — so it can
draw literally any shape — while the kit itself owns all the sync plumbing
(`window.__ready`, `SCENE_GROUPS`, `playGroups`) so `deck.render.record` drives this
page (word-timestamp forced-alignment voice sync).

The one structural rule the model must follow is `s.step(cue, fn)`: everything
drawn inside `fn` becomes ONE reveal group tied to `cue` (a verbatim phrase from
the narration). Group 0 (anything drawn before the first step) is the base
frame; content group j+1 aligns to `cues[j]` — exactly the contract
`record_deck` expects.

`build_html(title, slides)` -> `(html, timeline)`.
  slides: [{"narration": str, "base": js_str, "steps": [{"cue": str, "draw": js_str}]}]

SAFETY: the model-written JS is injected via `new Function('s', code)`, so it
MUST be statically vetted first — `deck.visual.safety` neutralizes any snippet
that reaches for the network / storage / DOM / eval before it ever gets here (see
`deck.visual.renderer`).
"""
import base64
import functools
import json
import os
import re

_VENDOR = os.path.join(os.path.dirname(__file__), "vendor")

_SHELL = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
__HEAD_ASSETS__
<style>
  html,body{margin:0;padding:0;background:#0d0d0d;}
  #stage{
    position:relative;width:1080px;height:1920px;overflow:hidden;
    background:
      radial-gradient(120% 90% at 50% 18%, rgba(255,255,255,.05), rgba(0,0,0,0) 55%),
      radial-gradient(140% 120% at 50% 112%, rgba(0,0,0,.55), rgba(0,0,0,0) 60%),
      #22352b;
  }
  #stage::after{
    content:"";position:absolute;inset:0;pointer-events:none;opacity:.06;mix-blend-mode:screen;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter><rect width='140' height='140' filter='url(%23n)'/></svg>");
  }
  #wood{position:absolute;left:0;right:0;bottom:0;height:34px;background:linear-gradient(#6b4a2b,#4a3018);box-shadow:0 -3px 8px rgba(0,0,0,.4);z-index:5;}
  .scene{position:absolute;inset:0;}
  .scene svg{position:absolute;inset:0;width:1080px;height:1920px;}
  /* paint-order:stroke draws a dark halo BEHIND each glyph's fill, so a light
     label stays legible even when it sits over a filled green/salmon/yellow
     shape (white-on-green / white-on-orange were washing out otherwise). */
  text{font-family:'Patrick Hand',cursive;fill:#EDEAE0;
       paint-order:stroke;stroke:#12241c;stroke-width:4px;stroke-linejoin:round;}
  .title{font-family:'Caveat',cursive;font-weight:700;}
</style>
</head>
<body>
<div id="stage"><div id="wood"></div></div>
<script>
const SLIDES = __SLIDES__;
const W=1080, Hh=1920, NS='http://www.w3.org/2000/svg';
// chalk palette (name -> colour); handed to the model as s.color
const CHALK={white:'#EDEAE0',yellow:'#F2C14E',blue:'#7FB8D9',green:'#8BD450',
             salmon:'#E8896C',purple:'#C9A0DC',dim:'#AEB9B0'};
const R={roughness:1.6,bowing:1.3,strokeWidth:3.2};
const stage=document.getElementById('stage');
const CTX=[],SCENE_GROUPS=[];
window.__errors=[];

function el(t,a){const e=document.createElementNS(NS,t);if(a)for(const k in a)e.setAttribute(k,a[k]);return e;}
function strokes(node){node.querySelectorAll('path,line,circle,ellipse,rect,polygon,polyline').forEach(p=>{p.setAttribute('stroke-linecap','round');p.setAttribute('stroke-linejoin','round');});return[...node.querySelectorAll('path')];}
function wrap(str,size,maxW){
  const cpl=Math.max(6,Math.floor(maxW/(size*0.52))),out=[];let cur='';
  for(const w of String(str).split(/\s+/)){
    if((cur+' '+w).trim().length<=cpl)cur=(cur+' '+w).trim();
    else{if(cur)out.push(cur);cur=w;}
  }
  if(cur)out.push(cur);return out;
}

// ---- the scene-kit `s` handed to the LLM's draw code ----
// Raw Rough.js freedom (s.rc) + s.add()/s.text() that also register the drawn
// nodes into the CURRENT reveal group so voice-sync just works. s.step(cue,fn)
// advances the group. Convenience s.arrow() for the most common connector.
function makeKit(c){
  const s={
    rc:c.rc, svg:c.svg, W:W, H:Hh, color:CHALK, R:R,
    // safe drawing area (below the title band, above the chalk tray)
    SAFE:{x:70, y:250, w:940, h:1560, cx:W/2},
    add(node){                       // any SVG/Rough node -> current group, draw-on
      c.ink.appendChild(node);
      const ps=strokes(node);
      if(ps.length)c.actions.push({kind:'draw',paths:ps,dur:640,group:c.g});
      return node;
    },
    text(x,y,str,o){                 // hand-written text, fades+rises in on its group
      o=o||{};
      const size=o.size||46,anchor=o.anchor||'start',color=o.color||CHALK.white,maxW=o.maxW||900;
      const lines=wrap(str,size,maxW),lineH=Math.round(size*1.18);
      const t=el('text',{x,y,'font-size':size,fill:color,'text-anchor':anchor});
      if(o.title)t.setAttribute('class','title');
      t.style.opacity=0;
      lines.forEach((ln,i)=>{const ts=el('tspan',{x,dy:i===0?0:lineH});ts.textContent=ln;t.appendChild(ts);});
      c.labels.appendChild(t);
      c.actions.push({kind:'fade',el:t,dur:520,group:c.g});
      return t;
    },
    label(x,y,str,o){return s.text(x,y,str,o);},
    arrow(x1,y1,x2,y2,o){            // hand-drawn arrow (line + head) as one node
      o=o||{};const color=o.color||CHALK.salmon,sw=o.strokeWidth||R.strokeWidth;
      const g=el('g'),a=o.head||18,ang=Math.atan2(y2-y1,x2-x1),op={...R,stroke:color,strokeWidth:sw};
      [c.rc.line(x1,y1,x2,y2,op),
       c.rc.line(x2,y2,x2-a*Math.cos(ang-0.4),y2-a*Math.sin(ang-0.4),op),
       c.rc.line(x2,y2,x2-a*Math.cos(ang+0.4),y2-a*Math.sin(ang+0.4),op)
      ].forEach(p=>g.appendChild(p));
      return s.add(g);
    },
    step(cue,fn){                    // one reveal group tied to `cue`
      c.g=c.G++;
      try{fn();}catch(e){window.__errors.push('scene '+c.i+' step "'+cue+'": '+e.message);}
    },
  };
  return s;
}

function buildScene(slide,i){
  const wrapDiv=document.createElement('div');wrapDiv.className='scene';
  const svg=el('svg',{viewBox:'0 0 '+W+' '+Hh});
  const defs=el('defs');
  defs.innerHTML="<filter id='chalk"+i+"' x='-20%' y='-20%' width='140%' height='140%'>"+
    "<feTurbulence type='fractalNoise' baseFrequency='0.012 0.02' numOctaves='3' seed='"+(i+3)+"' result='n'/>"+
    "<feDisplacementMap in='SourceGraphic' in2='n' scale='4'/></filter>";
  svg.appendChild(defs);
  const ink=el('g',{filter:'url(#chalk'+i+')'}),labels=el('g');
  svg.appendChild(ink);svg.appendChild(labels);wrapDiv.appendChild(svg);
  stage.insertBefore(wrapDiv,document.getElementById('wood'));

  const c={rc:rough.svg(svg),svg,ink,labels,actions:[],g:0,G:1,i};
  const s=makeKit(c);
  // group 0 = base frame (title / static structure), drawn before any step
  try{new Function('s',slide.base||'')(s);}
  catch(e){window.__errors.push('scene '+i+' base: '+e.message);}
  // each step is one cue-aligned reveal group (group index auto-advances)
  (slide.steps||[]).forEach(st=>s.step(st.cue,()=>{new Function('s',st.draw||'')(s);}));

  // hide everything until its group plays (draw-on / fade-in). opacity:0 too, so
  // FILLED shapes stay hidden: strokeDashoffset only masks stroked paths, but a
  // Rough.js fill (fillStyle:'solid') is a separate filled path the dash trick
  // can't hide — without opacity it would show from the slide's first frame.
  c.actions.forEach(a=>{
    if(a.kind==='draw')a.paths.forEach(p=>{const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;p.style.opacity=0;});
    else if(a.kind==='fade')a.el.style.opacity=0;
  });
  CTX[i]=c;SCENE_GROUPS[i]=c.G;
}

SLIDES.forEach(buildScene);
window.SCENE_GROUPS=SCENE_GROUPS;
document.querySelectorAll('.scene').forEach(d=>d.style.display='none');

// Reveal groups [gStart,gEnd) of scene i over durMs. This is the contract
// deck.render.record drives the page through.
window.playGroups=function(i,gStart,gEnd,durMs){
  document.querySelectorAll('.scene').forEach((d,j)=>{d.style.display=j===i?'block':'none';});
  const c=CTX[i];if(!c)return;
  const acts=c.actions.filter(a=>a.group>=gStart&&a.group<gEnd);
  if(!acts.length)return;
  const over=140,base=acts.reduce((s,a)=>s+a.dur,0)-over*Math.max(0,acts.length-1);
  // Fit the group's intrinsic animation into the window the recorder gives
  // (durMs). Cap at 2.4x for tiny groups, but apply NO lower floor: a dense
  // group (many s.add/s.text in one step) must be free to compress so it
  // finishes BEFORE the slide advances. animation = min(2.4*base, 0.7*durMs) is
  // always <= durMs, so every group completes within its window (a very dense
  // group just draws faster rather than getting cut off mid-draw).
  let sc=1;
  if(durMs&&durMs>0){sc=Math.min(2.4,(durMs*0.7)/Math.max(1,base));}
  const tl=anime.timeline({easing:'easeInOutSine',autoplay:true});
  acts.forEach((a,idx)=>{
    const off=idx===0?'+=0':'-='+Math.round(over*sc);
    const d=Math.round(a.dur*sc);
    if(a.kind==='draw'){a.paths.forEach(p=>{p.style.opacity=1;});tl.add({targets:a.paths,strokeDashoffset:[anime.setDashoffset,0],duration:d},off);}
    else if(a.kind==='fade'){tl.add({targets:a.el,opacity:[0,1],translateY:[18,0],duration:d,easing:'easeOutQuad'},off);}
  });
};
// Static preview: reveal a slide's FINAL frame (no animation) for GUI review,
// since the recorder isn't here to drive playGroups.
window.showFinal=function(i){
  document.querySelectorAll('.scene').forEach((d,j)=>{d.style.display=j===i?'block':'none';});
  const c=CTX[i];if(!c)return;
  c.actions.forEach(a=>{
    if(a.kind==='draw')a.paths.forEach(p=>{p.style.strokeDashoffset=0;p.style.opacity=1;});
    else if(a.kind==='fade'){a.el.style.opacity=1;a.el.style.transform='none';}
  });
};
window.__ready=true;
</script>
</body>
</html>
"""


@functools.lru_cache(maxsize=1)
def _head_assets():
    """Rough.js + anime.js + the two fonts, all inlined from deck/visual/vendor so
    the recorded page needs NO network — a hard requirement for rendering inside a
    zero-egress sandbox. Fonts go in as base64 @font-face; the libs go in verbatim
    (minus any sourceMappingURL comment that would trigger a fetch)."""
    def _js(name):
        src = open(os.path.join(_VENDOR, name), encoding="utf-8").read()
        return re.sub(r"(?m)^//# sourceMappingURL=.*$", "", src)

    def _font_face(family, weight, fname):
        b64 = base64.b64encode(open(os.path.join(_VENDOR, fname), "rb").read()).decode()
        return (f"@font-face{{font-family:'{family}';font-weight:{weight};"
                f"font-style:normal;font-display:swap;"
                f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}")

    return (
        "<style>"
        + _font_face("Caveat", "600 700", "caveat.woff2")
        + _font_face("Patrick Hand", "400", "patrick-hand.woff2")
        + "</style>\n"
        + "<script>/* roughjs 4.6.6 (vendored) */\n" + _js("rough.js") + "\n</script>\n"
        + "<script>/* animejs 3.2.2 (vendored) */\n" + _js("anime.min.js") + "\n</script>"
    )


def build_html(title, slides):
    """Return (html_document, timeline).

    slides: [{"narration": str, "base": js, "steps": [{"cue": str, "draw": js}]}]
    timeline: the per-slide {"narration", "cues"} list record_deck consumes
    (cues[j] aligns to reveal group j+1 == steps[j])."""
    payload = [{"base": s.get("base", ""),
                "steps": [{"cue": st.get("cue", ""), "draw": st.get("draw", "")}
                          for st in s.get("steps", [])]}
               for s in slides]
    timeline = [{"narration": s["narration"],
                 "cues": [st.get("cue", "") for st in s.get("steps", [])]}
                for s in slides]
    doc = (_SHELL
           .replace("__TITLE__", title)
           .replace("__HEAD_ASSETS__", _head_assets())
           .replace("__SLIDES__", json.dumps(payload)))
    return doc, timeline


# Preview-only: the stage is a fixed 1080x1920 portrait canvas (what the
# recorder captures). In the GUI's short iframe that gets clipped, so scale the
# WHOLE stage down to fit the viewport and centre it — recorded HTML is untouched.
_PREVIEW_FIT = r"""
<style>html,body{overflow:hidden;background:#0d0d0d;}</style>
<script>
(function(){
  function fit(){
    var st=document.getElementById('stage');if(!st)return;
    var sc=Math.min(window.innerWidth/1080, window.innerHeight/1920);
    st.style.transformOrigin='top left';
    st.style.transform='scale('+sc+')';
    st.style.position='absolute';st.style.top='0';
    st.style.left=Math.max(0,(window.innerWidth-1080*sc)/2)+'px';
  }
  window.addEventListener('resize',fit);
  window.addEventListener('load',fit);
  fit();
})();
</script>
"""


def build_preview_html(title, scene):
    """A single-slide page that immediately shows that slide's FINAL frame (all
    reveals drawn) for a static GUI preview — the recorder isn't driving it, and
    the full portrait stage is scaled to fit the review iframe."""
    doc, _ = build_html(title, [scene])
    doc = doc.replace("window.__ready=true;",
                      "window.__ready=true;window.showFinal(0);")
    return doc.replace("</body>", _PREVIEW_FIT + "</body>")
