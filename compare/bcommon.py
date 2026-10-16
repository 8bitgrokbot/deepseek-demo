import subprocess,sys,time,json,os
from playwright.sync_api import sync_playwright
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
def open_page(work,port,pw):
    srv=subprocess.Popen([sys.executable,"-m","http.server",str(port),"--bind","127.0.0.1","-d",work],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    time.sleep(1)
    b=pw.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
    ctx=b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,has_touch=True,is_mobile=True,user_agent=UA)
    pg=ctx.new_page(); errs=[]
    pg.on('console',lambda m: errs.append('console.'+m.type+': '+m.text) if (m.type=='error' and not m.text.startswith('Failed to load resource')) else None)
    pg.on('response',lambda r: errs.append('http%d: %s'%(r.status,r.url)) if (r.status>=400 and 'favicon' not in r.url) else None)
    pg.on('pageerror',lambda e: errs.append('pageerror: '+str(e)))
    pg.on('requestfailed',lambda r: errs.append('requestfailed: '+r.url) if 'favicon' not in r.url else None)
    return srv,b,ctx,pg,errs
class Touch:
    def __init__(self,ctx,pg): self.c=ctx.new_cdp_session(pg)
    def send(self,t,x=None,y=None):
        self.c.send('Input.dispatchTouchEvent',{'type':t,'touchPoints':([{'x':x,'y':y}] if x is not None else [])})
    def drag(self,x0,y0,x1,y1,steps=12,pg=None,hold=0):
        self.send('touchStart',x0,y0)
        for i in range(1,steps+1):
            self.send('touchMove',x0+(x1-x0)*i/steps,y0+(y1-y0)*i/steps)
            if pg: pg.wait_for_timeout(16)
        if hold and pg: pg.wait_for_timeout(hold)
        self.send('touchEnd')
