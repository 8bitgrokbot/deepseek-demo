import sys,json,os,re
sys.path.insert(0,'/workspace/compare_glm')
from bcommon import *
work,shot=sys.argv[1:3]
NAMES=["既存API(place/canPlace/setBoard/setPieces/restart/pause等)が残る","実タッチドラッグ設置が動く(回帰確認)","#undoBtn と #undoCount が存在","__game.undo() と undoLeft が公開",
"開始時 undoCount表示が3・undoLeft=3","開始直後はundoBtn disabled","横スクロールなし(390px)","undoBtnが画面内に見える","設置後 盤面に反映・undoBtn有効化",
"ボタンで取り消し: 盤面・ピース(トレイ)・スコアが元に戻る","取り消し後 残り2・表示2","取り消し直後はdisabled・undo()がfalse","ライン消し設置の取り消し: 消えたラインが復元",
"1ゲーム3回まで(4回目はfalse・undoLeft=0・disabled)","リスタートで3に戻り・disabled","ドラッグ設置→ボタンで取り消し","コンソールエラー無し"]
c={n:False for n in NAMES}; info={}
if not os.path.exists(work+"/index.html"):
    print(json.dumps({"passed":0,"total":len(c),"checks":c})); sys.exit()
empty="Array.from({length:8},()=>Array(8).fill(0))"
with sync_playwright() as pw:
    srv,b,ctx,pg,errs=open_page(work,8732,pw)
    G=lambda e,*a: pg.evaluate(e,*a)
    def sec(name,fn):
        try: fn()
        except Exception as e: info.setdefault('section_errors',{})[name]=str(e)[:160]
    def start():
        try: pg.click('#startBtn',timeout=1500)
        except Exception: pass
        G("()=>{if(__game.state!=='playing'&&__game.start)__game.start()}"); pg.wait_for_timeout(400)
    def s_load():
        pg.goto("http://127.0.0.1:8732/index.html"); pg.wait_for_timeout(800)
        c[NAMES[0]]=G("()=>{const g=window.__game;return !!g&&['place','canPlace','setBoard','setPieces','restart','pause','resume','start'].every(k=>typeof g[k]==='function')&&['state','score','highScore','combo','board','pieces'].every(k=>k in g)}")
    sec("load",s_load)
    def s_drag():
        start()
        G(f"()=>{{__game.setBoard({empty});__game.setPieces([[[0,0]],[[0,0]],[[0,0]]])}}"); pg.wait_for_timeout(200)
        geo=G("()=>{const t=document.getElementById('tray');const pc=t&&t.children[0];const cells=document.getElementById('board').children;if(!pc||!cells[36])return null;const a=pc.getBoundingClientRect(),b=cells[36].getBoundingClientRect();return [a.left+a.width/2,a.top+a.height/2,b.left+b.width/2,b.top+b.height/2]}")
        if geo:
            T=Touch(ctx,pg); T.drag(geo[0],geo[1],geo[2],geo[3],steps=15,pg=pg,hold=100); pg.wait_for_timeout(500)
            n=G("()=>__game.board.flat().filter(x=>x).length"); info['drag_filled']=n
            c[NAMES[1]]=(n==1)
            try:
                pg.click('#undoBtn',timeout=2000); pg.wait_for_timeout(300)
                c[NAMES[15]]=(n==1) and G("()=>__game.board.flat().filter(x=>x).length")==0
            except Exception: pass
    sec("drag",s_drag)
    def s_ui():
        pg.goto("http://127.0.0.1:8732/index.html"); pg.wait_for_timeout(800)
        c[NAMES[2]]=G("()=>!!document.getElementById('undoBtn')&&!!document.getElementById('undoBtn').querySelector('#undoCount')")
        c[NAMES[3]]=G("()=>typeof __game.undo==='function'&&typeof __game.undoLeft==='number'")
        start()
        c[NAMES[4]]=G("()=>!!document.getElementById('undoCount')&&document.getElementById('undoCount').textContent.trim()==='3'&&__game.undoLeft===3")
        c[NAMES[5]]=G("()=>{const b=document.getElementById('undoBtn');return !!b&&b.disabled}")
        c[NAMES[6]]=G("()=>document.documentElement.scrollWidth<=window.innerWidth+1")
        c[NAMES[7]]=G("()=>{const b=document.getElementById('undoBtn');if(!b)return false;const r=b.getBoundingClientRect();return r.width>0&&r.height>0&&r.left>=-1&&r.right<=window.innerWidth+1&&r.top>=0&&r.bottom<=window.innerHeight+1}")
        pg.screenshot(path=shot+"_start.png")
    sec("ui",s_ui)
    def s_basic():
        G(f"()=>{{__game.setBoard({empty});__game.setPieces([[[0,0]],[[0,0],[0,1]],[[0,0],[1,0],[1,1]]])}}")
        sc0=G("()=>__game.score")
        G("()=>__game.place(0,3,3)")
        c[NAMES[8]]=bool(G("()=>!!__game.board[3][3]")) and G("()=>!document.getElementById('undoBtn').disabled")
        pg.screenshot(path=shot+"_placed.png")
        pg.click('#undoBtn',timeout=3000); pg.wait_for_timeout(300)
        st=G("()=>({cell:__game.board[3][3],p0:__game.pieces[0]&&__game.pieces[0].cells.length,score:__game.score,left:__game.undoLeft,txt:document.getElementById('undoCount').textContent.trim(),dis:document.getElementById('undoBtn').disabled,filled:__game.board.flat().filter(x=>x).length})")
        info['after_undo']=st
        c[NAMES[9]]=(not st['cell']) and st['p0']==1 and st['score']==sc0 and st['filled']==0
        c[NAMES[10]]=(st['left']==2 and st['txt']=='2')
        c[NAMES[11]]=bool(st['dis']) and G("()=>__game.undo()")==False
        pg.screenshot(path=shot+"_undone.png")
    sec("basic",s_basic)
    def s_line():
        G("()=>__game.restart()"); start()
        row="Array.from({length:8},(_,i)=>Array.from({length:8},(_,j)=>i===0&&j<7?1:0))"
        G(f"()=>{{__game.setBoard({row});__game.setPieces([[[0,0]],[[0,0]],[[0,0],[0,1]]])}}")
        s0=G("()=>({score:__game.score,combo:__game.combo,row0:__game.board[0].filter(x=>x).length})")
        G("()=>__game.place(0,0,7)"); pg.wait_for_timeout(900)
        mid=G("()=>({score:__game.score,row0:__game.board[0].filter(x=>x).length})")
        r=G("()=>__game.undo()"); pg.wait_for_timeout(400)
        s2=G("()=>({score:__game.score,combo:__game.combo,row0:__game.board[0].filter(x=>x).length,p0:!!__game.pieces[0]})")
        info['lineclear']={'before':s0,'mid':mid,'after_undo':s2,'undo_ret':r}
        c[NAMES[12]]=(mid['row0']==0 and r is True and s2['row0']==7 and s2['score']==s0['score'] and s2['combo']==s0['combo'] and s2['p0'])
    sec("line",s_line)
    def s_limit():
        G("()=>__game.restart()"); start()
        rets=[]
        for i in range(4):
            G(f"()=>{{__game.setBoard({empty});__game.setPieces([[[0,0]],[[0,0]],[[0,0]]])}}")
            G("()=>__game.place(0,%d,%d)"%(i,i)); rets.append(G("()=>__game.undo()"))
        info['limit_rets']=rets
        c[NAMES[13]]=(rets==[True,True,True,False] and G("()=>__game.undoLeft")==0 and G("()=>document.getElementById('undoBtn').disabled") and G("()=>document.getElementById('undoCount').textContent.trim()")=='0')
        G("()=>__game.restart()"); pg.wait_for_timeout(300)
        try: pg.click('#startBtn',timeout=500)
        except Exception: pass
        c[NAMES[14]]=G("()=>__game.undoLeft===3&&document.getElementById('undoCount').textContent.trim()==='3'&&document.getElementById('undoBtn').disabled")
        pg.screenshot(path=shot+"_end.png")
    sec("limit",s_limit)
    info['console_errors']=errs[:8]
    b.close(); srv.terminate()
c[NAMES[16]]=(len(info.get('console_errors',[]))==0)
ok=sum(1 for v in c.values() if v is True)
print(json.dumps({"passed":ok,"total":len(c),"checks":c,"info":info},ensure_ascii=False,default=str))
