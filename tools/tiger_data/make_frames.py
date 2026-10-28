"""Render the badge's office tiger from editable drawing commands.

Run with desktop Python and Pillow; writes 156 palette PNGs to the app's assets.
The badge itself only loads those PNGs, one at a time.
"""
import math, re, io, sys, json
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image, ImageDraw, ImageFont, ImageChops

OUT = Path(__file__).resolve().parent
W,H,S = 960,640,2
INK='#111b28'; NAVY='#50314f'; LIGHT='#96576d'; CREAM='#ffedce'; GOLD='#f5ff80'

def contours(path):
    tokens=re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',path)
    i=0; cmd=None; p=(0,0); start=p; old=None; result=[]; pts=[]
    def num():
        nonlocal i
        n=float(tokens[i]);i+=1;return n
    while i<len(tokens):
        if tokens[i].isalpha():cmd=tokens[i];i+=1
        c=cmd.upper(); rel=cmd.islower()
        def xy():
            x,y=num(),num();return (x+p[0],y+p[1]) if rel else (x,y)
        if c=='Z':
            if pts:result.append(pts);pts=[]
            p=start;old=None;cmd=None;continue
        if c=='M':
            if pts:result.append(pts)
            p=xy();start=p;pts=[p];cmd='l' if rel else 'L';old=None
        elif c in ('L','H','V'):
            if c=='L':p=xy()
            elif c=='H':p=(num()+(p[0] if rel else 0),p[1])
            else:p=(p[0],num()+(p[1] if rel else 0))
            pts.append(p);old=None
        elif c in ('C','S','Q','T'):
            p0=p
            if c in ('C','Q'):a=xy()
            else:a=(2*p[0]-old[0],2*p[1]-old[1]) if old else p
            if c in ('C','S'):b=xy();end=xy()
            else:end=xy()
            for j in range(1,19):
                t=j/18;u=1-t
                if c in ('C','S'):pt=tuple(u*u*u*p0[k]+3*u*u*t*a[k]+3*u*t*t*b[k]+t*t*t*end[k] for k in (0,1))
                else:pt=tuple(u*u*p0[k]+2*u*t*a[k]+t*t*end[k] for k in (0,1))
                pts.append(pt)
            old=b if c in ('C','S') else a;p=end
        else:raise ValueError('Unsupported path command '+str(cmd))
    if pts:result.append(pts)
    return result

class Art:
    def __init__(self,img):self.im=img;self.d=ImageDraw.Draw(img)
    def box(self,b):return tuple(round(v*S) for v in b)
    def ellipse(self,b,fill,outline=None,w=2):self.d.ellipse(self.box(b),fill,outline,width=round(w*S))
    def rect(self,b,fill,r=0,outline=None,w=2):self.d.rounded_rectangle(self.box(b),radius=round(r*S),fill=fill,outline=outline,width=round(w*S))
    def line(self,pts,fill,w=2):
        ps=[(round(x*S),round(y*S)) for x,y in pts];self.d.line(ps,fill=fill,width=round(w*S),joint='curve')
        if w>3:
            rr=w/2
            for x,y in (pts[0],pts[-1]):self.ellipse((x-rr,y-rr,x+rr,y+rr),fill,w=0)
    def path(self,path,fill=None,stroke=None,w=2,dx=0,dy=0):
        for pts in contours(path):
            pts=[(x+dx,y+dy) for x,y in pts]
            if fill:self.d.polygon([(round(x*S),round(y*S)) for x,y in pts],fill)
            if stroke:self.line(pts,stroke,w)
    def poly(self,pts,fill,stroke=None,w=2):
        self.d.polygon([(round(x*S),round(y*S)) for x,y in pts],fill)
        if stroke:self.line(pts+[pts[0]],stroke,w)
    def text(self,pos,txt,size,fill,font='Arial Rounded Bold.ttf',anchor=None):
        f=ImageFont.truetype('/System/Library/Fonts/Supplemental/'+font,round(size*S))
        self.d.text(tuple(v*S for v in pos),txt,font=f,fill=fill,anchor=anchor)

def logo_image():
    root=ET.parse(OUT/'tiger-data-logo.svg').getroot()
    img=Image.new('RGBA',(1314,290));
    for el in root:
        if el.tag.endswith('mask'):continue
        for e in el.iter():
            if not e.tag.endswith('path'):continue
            cs=contours(e.attrib['d']);mask=Image.new('L',img.size);d=ImageDraw.Draw(mask)
            def area(ps):return sum(ps[k][0]*ps[(k+1)%len(ps)][1]-ps[(k+1)%len(ps)][0]*ps[k][1] for k in range(len(ps)))
            orient=1 if area(max(cs,key=lambda p:abs(area(p))))>0 else -1
            for ps in sorted(cs,key=lambda p:-abs(area(p))):d.polygon(ps,fill=255 if area(ps)*orient>0 else 0)
            color=e.attrib.get('fill','#f5ff80')
            if color.startswith('url'):color=GOLD
            lay=Image.new('RGBA',img.size,color);img.alpha_composite(Image.composite(lay,Image.new('RGBA',img.size),mask))
    return img.resize((round(345*S),round(345*290/1314*S)),Image.Resampling.LANCZOS)

LOGO=logo_image()
def background():
    im=Image.new('RGB',(W*S,H*S));d=ImageDraw.Draw(im)
    for y in range(H*S):
        f=y/(H*S);d.line((0,y,W*S,y),fill=tuple(int(a+(b-a)*f) for a,b in zip((30,46,55),(16,29,39))))
    a=Art(im)
    # Architectural panels and distant city window.
    for x in [62,245,535,899]:a.line([(x,0),(x,475)],'#2a3c44',1)
    a.rect((615,51,893,369),'#304953',18,outline='#4a6166',w=2)
    a.rect((626,62,882,357),'#49626a',12)
    for x,y,ww in [(635,235,37),(683,187,44),(740,218,39),(790,151,42),(845,204,26)]:
        a.rect((x,y,x+ww,357),'#344d58',2)
        for yy in range(y+13,347,24):
            for xx in range(x+8,x+ww-4,14):a.rect((xx,yy,xx+4,yy+6),'#657b7c',1)
    a.line([(754,62),(754,357)],'#273e48',7);a.line([(626,222),(882,222)],'#273e48',7)
    # Branded wall sign; logo pixels retain official shapes and colors.
    a.rect((81,61,481,169),'#111f29',12)
    a.line([(98,177),(465,177)],'#425353',2)
    im.paste(LOGO,(108*S,77*S),LOGO)
    # Plant.
    a.path('M129 498 C128 442 146 396 137 337',stroke='#6c8b70',w=6)
    for p in ['M137 389 C100 392 81 371 91 357 C121 350 141 373 137 389Z','M137 416 C169 412 184 391 173 379 C149 379 135 398 137 416Z','M135 357 C110 342 115 311 130 304 C146 316 151 341 135 357Z','M131 451 C98 449 88 430 96 418 C118 415 135 432 131 451Z']:
        a.path(p,'#708b69')
    a.poly([(104,477),(157,477),(149,536),(114,536)],'#ba9072')
    a.rect((100,472,161,485),'#d0a58a',5)
    a.ellipse((188,553,847,594),'#0d1822')
    return im
BG=background()

def mix(c1,c2,f):
    return tuple(round(a+(b-a)*f) for a,b in zip(c1,c2))
def smooth(x):x=max(0,min(1,x));return x*x*(3-2*x)

def state(t):
    # Ten-second loop: work, notice a problem, flush red, wind up, slam, recover.
    anger=smooth((t-4.1)/1.05)*(1-smooth((t-7.75)/1.3))
    lift=0
    if 5.35<t<5.95:lift=smooth((t-5.35)/.6)
    elif 5.95<=t<6.16:lift=1-smooth((t-5.95)/.21)
    elif 6.45<t<6.8:lift=.68*smooth((t-6.45)/.35)
    elif 6.8<=t<6.99:lift=.68*(1-smooth((t-6.8)/.19))
    impacts=[6.16,6.99]
    shake=sum(7*math.sin((t-e)*72)*math.exp(-(t-e)*11) for e in impacts if 0<=t-e<.5)
    hit=max([max(0,1-(t-e)/.35) if t>=e else 0 for e in impacts])
    return anger,lift,shake,hit

def frame(t):
    im=BG.copy();a=Art(im);anger,lift,shake,hit=state(t)
    idea=smooth((t-10)/.35)*(1-smooth((t-12.4)/.6))
    typing=(t<4.3 or t>8.65) and idea<.1
    bob=(math.sin(t*9)*1.8 if typing else -lift*8+hit*8)
    fur=mix((238,159,61),(240,57,49),anger)
    shade=mix((202,112,41),(191,33,41),anger)
    muzzle=mix((255,237,206),(255,167,143),anger*.78)
    # Rolling chair and animated striped tail.
    a.line([(344,511),(344,571)],INK,15)
    a.line([(300,582),(344,566),(396,582)],'#364653',9)
    for x in (299,393):a.ellipse((x-9,578,x+9,591),'#0a141e')
    a.rect((267,348,443,522),'#10202c',36,outline='#415362',w=3)
    a.rect((279,360,431,505),'#1b2f3b',30)
    tail=-14*math.sin(t*2.6)*(1+anger*.6)
    a.path(f'M300 487 C232 520 201 487 213 {436+tail} C222 {407+tail} 245 {410+tail} 243 {437+tail}',stroke=INK,w=23)
    a.path(f'M300 487 C232 520 201 487 213 {436+tail} C222 {407+tail} 245 {410+tail} 243 {437+tail}',stroke=fur,w=16)
    for x,y in [(277,496),(249,496),(224,481),(215,457+tail*.7)]:a.line([(x-3,y-7),(x+3,y+7)],INK,6)
    a.ellipse((235,429+tail,251,447+tail),INK)
    # Suit, blouse, lapels and gold brooch.
    a.path('M311 388 Q375 365 442 388 Q475 404 488 520 L288 520 Q285 433 311 388Z',NAVY,INK,4,dy=bob)
    a.poly([(348,380+bob),(413,380+bob),(403,478+bob),(375,506+bob)],CREAM)
    a.poly([(348,382+bob),(367,402+bob),(380,390+bob),(394,403+bob),(413,382+bob),(401,431+bob),(363,431+bob)],'#c56d59')
    a.poly([(327,382+bob),(349,380+bob),(378,488+bob),(329,446+bob),(343,425+bob),(320,420+bob)],LIGHT,INK,2)
    a.poly([(415,380+bob),(435,390+bob),(449,420+bob),(425,428+bob),(438,449+bob),(378,488+bob)],'#324b6b',INK,2)
    a.ellipse((376,482+bob,383,489+bob),GOLD)
    a.rect((430,440+bob,455,444+bob),'#a0b6c2',1)
    # Neck and head.
    a.path('M351 352 L352 385 Q380 408 410 385 L411 352Z',fur,INK,3,dy=bob)
    # Ears set behind the cheeks.
    for x in [302,452]:
        a.ellipse((x-26,204+bob,x+26,261+bob),fur,INK,4)
        a.ellipse((x-15,216+bob,x+15,247+bob),shade)
        a.ellipse((x-8,219+bob,x+10,244+bob),'#ebb393')
    a.path('M300 263 C296 226 334 207 375 208 C421 206 457 229 459 270 L471 293 L461 310 L470 324 L453 333 C440 368 408 385 377 383 C342 383 312 367 300 339 L283 330 L294 314 L283 299Z',fur,INK,4,dy=bob)
    # Cheek fur and forehead stripes.
    for path in ['M302 268 L331 282 L303 288Z','M293 297 L326 306 L300 317Z','M304 328 L331 326 L316 345Z','M455 269 L430 282 L459 289Z','M462 299 L435 307 L457 319Z','M451 332 L428 329 L441 348Z','M349 211 L355 243 L368 257 L368 211Z','M390 209 L390 240 L403 251 L411 214Z','M371 210 L374 234 L381 245 L386 210Z']:
        a.path(path,INK,dy=bob)
    # A swept magenta fringe echoes Erin's hair while leaving the tiger stripes visible.
    a.path('M317 244 Q329 202 373 206 Q353 222 339 250 L317 268Z','#a83770',INK,2,dy=bob)
    a.path('M324 243 Q338 219 357 216',stroke='#e378aa',w=4,dy=bob)
    # Cream cheeks, muzzle and chin.
    a.path('M321 309 C334 297 354 300 373 310 C393 296 424 297 438 313 C453 339 426 368 380 371 C342 373 312 348 321 309Z',muzzle,dy=bob)
    a.ellipse((341,318+bob,383,348+bob),muzzle)
    a.ellipse((377,316+bob,423,348+bob),muzzle)
    # Eyes glance toward screen; blink occasionally.
    blink=(1.9<t<2.04) or (9.25<t<9.39)
    for x in [346,410]:
        eyeh=2 if blink else 14-anger*6
        y=291+bob
        a.ellipse((x-17,y-eyeh,x+18,y+eyeh),'#fff9df',INK,2)
        if not blink:
            gaze=-idea*5
            a.ellipse((x+2,y-eyeh+3+gaze,x+13,y+eyeh-2+gaze),'#43543d')
            a.ellipse((x+6,y-eyeh+3+gaze,x+11,y+eyeh-2+gaze),INK)
            a.ellipse((x+7,y-5+gaze,x+10,y-2+gaze),'#ffffff')
        # Expressive lashes remain visible at badge resolution.
        side=-1 if x<380 else 1
        a.line([(x+side*15,y-8),(x+side*24,y-18)],INK,3)
        a.line([(x+side*16,y-3),(x+side*26,y-8)],INK,3)
        a.line([(x+side*12,y-11),(x+side*17,y-22)],INK,3)
    # Fine gold aviator frames, matching the supplied portrait.
    for x in (345,411):
        a.ellipse((x-26,273+bob,x+26,313+bob),None,'#e3bc64',3)
    a.path('M371 288 Q378 281 385 288 M319 283 L306 277 M437 283 L450 277',stroke='#e3bc64',w=3,dy=bob)
    # Brows tilt sharply inward as she becomes angry.
    a.line([(327,267+bob-anger*6),(359,267+bob+anger*12)],INK,6)
    a.line([(395,267+bob+anger*12),(429,264+bob-anger*6)],INK,6)
    a.path('M366 314 Q380 309 395 314 L383 328 Q380 331 376 327Z','#442b2c',INK,2,dy=bob)
    a.line([(381,328+bob),(381,337+bob)],INK,2)
    if anger>.35:
        a.path('M361 350 Q382 336 403 349',stroke=INK,w=3,dy=bob)
        if lift>.3:a.path('M365 350 Q382 340 400 349 L398 357 Q382 365 367 358Z','#7f2936',INK,2,dy=bob)
    else:
        a.path('M358 337 Q371 349 381 338 Q392 348 405 335',stroke=INK,w=2.6,dy=bob)
    for x,y in [(344,326),(351,334),(415,325),(409,335)]:a.ellipse((x,y+bob,x+3,y+3+bob),'#775144')
    for p in ['M340 339 L306 334','M342 346 L312 351','M418 338 L451 332','M419 346 L448 351']:
        a.path(p,stroke='#61463d',w=1.4,dy=bob)
    # Gold hoop earrings.
    for x in [309,450]:
        a.ellipse((x-8,324+bob,x+8,347+bob),'#e3bc64',INK,1)
        a.ellipse((x-4,328+bob,x+4,342+bob),shade)
    # Desktop: shaken only when keyboard is hit.
    a.rect((191+shake,520,875+shake,553),'#a77f59',7,outline=INK,w=3)
    a.rect((197+shake,513,870+shake,533),'#dcb88c',6,outline=INK,w=3)
    a.line([(212,556),(212,621)],INK,11);a.line([(849,556),(849,621)],INK,11)
    a.line([(217,539),(847,539)],'#805e43',2)
    # Keyboard base and individual keys.
    kx=shake;ky=hit*3
    a.poly([(415+kx,486+ky),(636+kx,486+ky),(658+kx,518+ky),(405+kx,518+ky)],'#121f2c',INK,3)
    a.line([(409+kx,521+ky),(654+kx,521+ky)],'#71828b',3)
    for row in range(3):
        for col in range(13):
            x=424+col*16-row*2+kx;y=491+row*7+ky
            active=typing and (col+row*4+int(t*14))%19==0
            a.rect((x,y,x+11,y+4),GOLD if active else '#7c9098',1)
    a.rect((473+kx,513+ky,583+kx,517+ky),'#7c9098',1)
    # Monitor angled slightly toward the tiger, with a small terminal.
    a.poly([(711+shake,445),(737+shake,445),(741+shake,499),(705+shake,499)],'#263b4b',INK,3)
    a.rect((681+shake,498,773+shake,508),'#41566a',5,outline=INK,w=2)
    a.rect((614+shake,281,838+shake,455),'#182736',12,outline=INK,w=4)
    a.rect((625+shake,293,826+shake,438),'#0e1c27',5)
    for x in [636,646,656]:a.ellipse((x+shake,302,x+5+shake,307),'#6c858a')
    a.line([(634+shake,317),(817+shake,317)],'#2b424d',1)
    a.text((638+shake,330),'SELECT *',15,GOLD,font='Andale Mono.ttf')
    a.text((638+shake,351),'FROM tiger_data;',12,'#adc1bd',font='Andale Mono.ttf')
    if 4.1<t<7.75:
        a.text((638+shake,385),'ERROR: try again',11,'#ff8278',font='Andale Mono.ttf')
    else:
        a.text((638+shake,385),'> '+('running...' if t<4.1 else 'query complete'),11,'#89c3a4',font='Andale Mono.ttf')
    if int(t*2)%2==0:a.rect((639+shake,414,646+shake,417),GOLD)
    a.ellipse((721+shake,444,728+shake,450),GOLD)
    # Coffee with gently moving steam.
    a.ellipse((779+shake,479-hit*7,811+shake,508-hit*7),'#e9dabb',INK,3)
    a.ellipse((785+shake,485-hit*7,804+shake,502-hit*7),'#30414a')
    a.rect((751+shake,477-hit*7,793+shake,517-hit*7),CREAM,8,outline=INK,w=3)
    a.ellipse((752+shake,473-hit*7,792+shake,485-hit*7),'#d3b794',INK,2)
    a.ellipse((758+shake,477-hit*7,786+shake,481-hit*7),'#624b3c')
    for j in range(2):
        sx=762+j*16;sy=math.sin(t*2+j)*4
        a.path(f'M{sx} 463 Q{sx-7+sy} 452 {sx} 442 Q{sx+7-sy} 433 {sx+2} 426',stroke='#81908b',w=2)
    # Sleeves connect shoulders to wrists, then large articulated paws.
    for idx,(shoulder,elbow,base) in enumerate([((324,411+bob),(346,468),(471,489)),((444,411+bob),(484,461),(564,491))]):
        tap=math.sin(t*31+idx*math.pi)*4 if typing else 0
        px=base[0]+lift*(-23 if idx==0 else -9)+shake
        py=base[1]-lift*133+tap+hit*7
        ex=elbow[0]+lift*14;ey=elbow[1]-lift*20
        a.line([shoulder,(ex,ey),(px-16,py-4)],INK,39)
        a.line([shoulder,(ex,ey),(px-16,py-4)],NAVY if idx==0 else '#68405f',32)
        a.line([(px-24,py-5),(px-12,py-4)],CREAM,30)
        a.ellipse((px-20,py-21,px+24,py+12),fur,INK,3)
        if lift>.1:
            for j in range(3):a.path(f'M{px-10+j*10} {py-13} Q{px-7+j*10} {py-7} {px-9+j*10} {py-3}',stroke=shade,w=2)
            a.ellipse((px-24,py-12,px-10,py+6),fur,INK,2)
        else:
            for j in range(3):a.line([(px-7+j*10,py+2),(px-6+j*10,py+10)],shade,2)
        a.path(f'M{px-12} {py-19} L{px-3} {py-10} L{px+2} {py-20}Z',INK)
    # Steam, anger vein, and brief impact rays.
    if anger>.65:
        ax=439;ay=247+bob
        a.path(f'M{ax} {ay-8} L{ax} {ay} L{ax+8} {ay} M{ax-4} {ay+3} L{ax-11} {ay+3} L{ax-11} {ay+11}',stroke='#a5222b',w=3)
        for j in range(2):
            xx=288+j*181;yy=228-(t*28+j*11)%30
            a.path(f'M{xx} {yy+22} Q{xx-13} {yy+10} {xx} {yy} Q{xx+13} {yy-10} {xx} {yy-20}',stroke='#d3c9b9',w=3)
    if hit>0:
        for x,y,xx,yy in [(409,469,390,450),(506,461,501,434),(589,465,602,443),(660,483,684,469)]:
            a.line([(x,y),(x+(xx-x)*hit,y+(yy-y)*hit)],GOLD,4)
        # Two keys bounce up and fall back.
        for j in range(2):
            xx=515+j*48+(1-hit)*17;yy=482-math.sin((1-hit)*math.pi)*56
            a.rect((xx,yy,xx+13,yy+9),'#b0c0bf',2,outline=INK,w=2)
    # A warm lightbulb pops up above her head during the final three seconds.
    if idea>0:
        cx=546;cy=155-idea*15
        glow=mix((30,46,55),(245,255,128),idea)
        a.ellipse((cx-31,cy-34,cx+31,cy+28),glow,INK,3)
        a.poly([(cx-18,cy+20),(cx+18,cy+20),(cx+13,cy+43),(cx-13,cy+43)],glow,INK,3)
        a.path(f'M{cx-12} {cy+1} L{cx-5} {cy+13} L{cx+5} {cy+13} L{cx+12} {cy+1}',stroke='#b07737',w=3)
        a.rect((cx-15,cy+39,cx+15,cy+48),'#9daeb1',3,outline=INK,w=2)
        a.line([(cx-10,cy+52),(cx+10,cy+52)],GOLD,4)
        for angle in (-150,-105,-60,-15,30):
            r=math.radians(angle)
            a.line([(cx+45*math.cos(r),cy+45*math.sin(r)),
                    (cx+(45+14*idea)*math.cos(r),cy+(45+14*idea)*math.sin(r))],glow,4)
        a.ellipse((490,208,501,219),glow)
        a.ellipse((472,227,479,234),glow)
    return im.resize((W,H),Image.Resampling.LANCZOS)

def main():
    dest=OUT.parents[1]/'badge'/'apps'/'tiger_data'/'assets'/'frames'
    dest.mkdir(parents=True,exist_ok=True)
    # Share one palette across calm, tantrum and idea frames to prevent shimmer.
    atlas=Image.new('RGB',(320*4,213*2))
    for i,t in enumerate((0,2,4.8,5.8,6.2,7,9,11.5)):
        atlas.paste(frame(t).resize((320,213),Image.Resampling.LANCZOS),((i%4)*320,(i//4)*213))
    palette=atlas.quantize(colors=128,method=Image.Quantize.MEDIANCUT)
    for n in range(156):
        small=frame(n/12).resize((320,213),Image.Resampling.LANCZOS)
        small.quantize(palette=palette,dither=Image.Dither.NONE).save(dest/('%03d.png'%n),optimize=True)
        if n%30==0:print('Rendered %d/156'%n,flush=True)
    print('Saved 156 frames at 12 fps (13 seconds)',flush=True)

if __name__=='__main__':main()
