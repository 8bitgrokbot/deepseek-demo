import sys,json,os,re
sys.path.insert(0,'/workspace/compare_glm')
from bcommon import *
work,shot=sys.argv[1:3]
c={};info={}
html=open(work+"/index.html",encoding="utf-8").read() if os.path.exists(work+"/index.html") else ""
c["index.html が存在"]=bool(html)
if not html:
    print(json.dumps({"passed":0,"total":1,"checks":c})); sys.exit()
ext=[u for u in re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)',html)]
c["外部リソース参照なし"]=len(ext)==0
c["Web Audio API 使用(AudioContext)"]=bool(re.search(r"AudioContext",html))
c["localStorage 使用"]="localStorage" in html
with sync_playwright() as pw:
    srv,b,ctx,pg,errs=open_page(work,8731,pw)
    try:
        pg.goto("http://127.0.0.1:8731/index.html"); pg.wait_for_timeout(1000)
        G=lambda e: pg.evaluate(e)
        c["<canvas id=game> がある"]=G("()=>!!document.querySelector('canvas#game')")
        c["window.__game が公開(必要プロパティ)"]=G("()=>{const g=window.__game;if(!g)return false;return ['state','score','lives','stage','paddleX','ballX','ballY','bricksLeft'].every(k=>k in g)}")
        c["初期stateが'title'"]=G("()=>window.__game&&window.__game.state")=='title'
        c["#start-btn が表示される"]=G("()=>{const b=document.getElementById('start-btn');if(!b)return false;const r=b.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(b).visibility!='hidden'}")
        c["横スクロールなし(390px)"]=G("()=>document.documentElement.scrollWidth<=window.innerWidth+1")
        c["canvasが画面幅に収まる"]=G("()=>{const r=document.querySelector('canvas#game').getBoundingClientRect();return r.width<=window.innerWidth+1&&r.width>200}")
        pg.screenshot(path=shot+"_title.png")
        try: pg.click('#start-btn',timeout=3000)
        except Exception as e: info['start_click_error']=str(e)[:100]
        pg.wait_for_timeout(700)
        st=G("()=>window.__game&&window.__game.state"); c["スタートでstate='playing'"]=(st=='playing')
        info['bricks_start']=G("()=>window.__game&&window.__game.bricksLeft")
        c["ブロック40個以上(5行x8列以上)"]=(info['bricks_start'] or 0)>=40
        p1=G("()=>[__game.ballX,__game.ballY]"); pg.wait_for_timeout(300); p2=G("()=>[__game.ballX,__game.ballY]")
        c["ボールが動く"]=p1!=p2
        pg.screenshot(path=shot+"_play.png")
        T=Touch(ctx,pg)
        box=G("()=>{const r=document.querySelector('canvas#game').getBoundingClientRect();return [r.left,r.top,r.width,r.height,document.querySelector('canvas#game').width,document.querySelector('canvas#game').height]}")
        left,top,w,h,cw,ch=box; sx=w/cw
        x0=G("()=>__game.paddleX")
        T.drag(left+w*0.5,top+h*0.9,left+w*0.15,top+h*0.9,pg=pg); pg.wait_for_timeout(100)
        x1=G("()=>__game.paddleX"); 
        T.drag(left+w*0.15,top+h*0.9,left+w*0.85,top+h*0.9,pg=pg); pg.wait_for_timeout(100)
        x2=G("()=>__game.paddleX")
        c["タッチドラッグでパドルが左右に動く"]=(x1<x0-10 and x2>x1+10)
        info['paddle']=[x0,x1,x2]
        k0=G("()=>__game.paddleX"); pg.keyboard.down('ArrowLeft'); pg.wait_for_timeout(300); pg.keyboard.up('ArrowLeft'); k1=G("()=>__game.paddleX")
        c["左右キーでパドルが動く"]=k1<k0-3
        pg.keyboard.press('p'); pg.wait_for_timeout(200); sp=G("()=>__game.state"); 
        b1=G("()=>[__game.ballX,__game.ballY]"); pg.wait_for_timeout(300); b2=G("()=>[__game.ballX,__game.ballY]")
        c["Pキーで一時停止(state/ボール停止)"]=(sp=='paused' and b1==b2)
        pg.keyboard.press('p'); pg.wait_for_timeout(200); c["Pキーで再開"]=G("()=>__game.state")=='playing'
        pg.screenshot(path=shot+"_play2.png")
        # 自動プレイ: ボールを追従して25秒
        T.drag(left+w*0.5,top+h*0.9,left+w*0.3,top+h*0.9,pg=pg); pg.wait_for_timeout(120); pa=G("()=>__game.paddleX")
        T.drag(left+w*0.3,top+h*0.9,left+w*0.7,top+h*0.9,pg=pg); pg.wait_for_timeout(120); pb=G("()=>__game.paddleX")
        info['calib']=[pa,pb]
        scale=(w*0.4)/((pb-pa) if pb!=pa else 1)
        def scr(bx): return left+w*0.3+(bx-pa)*scale
        s0=G("()=>__game.score"); bl0=G("()=>__game.bricksLeft"); t0=time.time(); pe=0
        T.send('touchStart',scr(G("()=>__game.ballX")),top+h*0.9)
        while time.time()-t0<25:
            bx=G("()=>__game.ballX")
            if G("()=>__game.state")!='playing': break
            T.send('touchMove',min(max(scr(bx),left+2),left+w-2),top+h*0.9); pg.wait_for_timeout(20)
        T.send('touchEnd')
        s1=G("()=>__game.score"); bl1=G("()=>__game.bricksLeft")
        info['autoplay']={'score':[s0,s1],'bricks':[bl0,bl1],'lives':G("()=>__game.lives"),'state':G("()=>__game.state")}
        c["追従プレイでスコアが増える/ブロックが減る"]=(s1>s0 and bl1<bl0)
        pg.screenshot(path=shot+"_autoplay.png")
        c["ライフが3で開始(減少はミス時のみ)"]=G("()=>__game.lives")<=3
        hud=G("()=>document.body.innerText")
        c["画面上にスコア/ライフ/ステージ表示(文字)"]=bool(re.search(r"(?i)score|スコア",hud)) and bool(re.search(r"(?i)lives|life|ライフ|残機|♥|❤",hud)) and bool(re.search(r"(?i)stage|ステージ|level|レベル",hud))
        c["音の切替ボタンがある"]=bool(re.search(r"(?i)mute|sound|音|🔊|🔇|♪",G("()=>document.body.innerHTML")))
        # ミス→ゲームオーバー: パドルを端に放置
        T.drag(left+w*0.5,top+h*0.9,left+w*0.02,top+h*0.9,pg=pg)
        t0=time.time()
        while time.time()-t0<90 and G("()=>__game.state")=='playing':
            T.send('touchStart',left+w*0.02,top+h*0.9); T.send('touchEnd'); pg.wait_for_timeout(500)
        gs=G("()=>__game.state"); info['final_state']=gs; info['lives_end']=G("()=>__game.lives")
        c["ミス放置でstate='gameover'(ライフ0)"]=(gs=='gameover' and G("()=>__game.lives")==0)
        pg.wait_for_timeout(500); pg.screenshot(path=shot+"_gameover.png")
        ls=G("()=>JSON.stringify(Object.fromEntries(Object.entries(localStorage)))"); info['localStorage']=ls[:200]
        c["ハイスコアがlocalStorageに保存される"]=(ls!="{}" and bool(re.search(r"\d",ls)))
        c["ゲームオーバー画面に再挑戦ボタン/ハイスコア表示"]=G("()=>{const t=document.body.innerText;return /high|ハイ|best|最高/i.test(t)}") and G("()=>[...document.querySelectorAll('button')].some(b=>b.getBoundingClientRect().width>0&&getComputedStyle(b).visibility!='hidden')")
        # 再挑戦
        btn=pg.locator('button:visible',has_text=re.compile(r"リトライ|もう一度|再挑戦|リスタート|retry|restart|again|スタート|start",re.I))
        ok=False
        if btn.count():
            try: btn.first.click(timeout=2000); pg.wait_for_timeout(700); ok=G("()=>__game.state")=='playing' and G("()=>__game.lives")==3
            except Exception as e: info['retry_err']=str(e)[:100]
        c["再挑戦でplaying・ライフ3に戻る"]=ok
    except Exception as e:
        info['crash']=str(e)[:300]
    finally:
        info['console_errors']=errs[:8]
        b.close(); srv.terminate()
for n in ['#start-btn が表示される', '<canvas id=game> がある', 'Pキーで一時停止(state/ボール停止)', 'Pキーで再開', 'Web Audio API 使用(AudioContext)', 'canvasが画面幅に収まる', 'index.html が存在', 'localStorage 使用', 'window.__game が公開(必要プロパティ)', 'ゲームオーバー画面に再挑戦ボタン/ハイスコア表示', 'コンソールエラー無し', "スタートでstate='playing'", 'タッチドラッグでパドルが左右に動く', 'ハイスコアがlocalStorageに保存される', 'ブロック40個以上(5行x8列以上)', 'ボールが動く', "ミス放置でstate='gameover'(ライフ0)", 'ライフが3で開始(減少はミス時のみ)', '再挑戦でplaying・ライフ3に戻る', "初期stateが'title'", '外部リソース参照なし', '左右キーでパドルが動く', '横スクロールなし(390px)', '画面上にスコア/ライフ/ステージ表示(文字)', '追従プレイでスコアが増える/ブロックが減る', '音の切替ボタンがある']: c.setdefault(n,False)
c["コンソールエラー無し"]=(len(info.get('console_errors',[]))==0)
ok=sum(1 for v in c.values() if v is True)
print(json.dumps({"passed":ok,"total":len(c),"checks":c,"info":info},ensure_ascii=False,default=str))
