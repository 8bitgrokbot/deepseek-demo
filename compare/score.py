#!/usr/bin/env python3
"""採点: score.py <task> <label> [workdir-override]  -> runs/<task>/<label>/score.json
LLM judge は使わない。全て自動チェック。"""
import sys,os,json,re,subprocess,shutil,tempfile,time,csv,hashlib
ROOT="/workspace/compare_glm"
def read(p):
    try: return open(p,encoding="utf-8").read()
    except Exception: return ""
def summarize(checks):
    ok=sum(1 for v in checks.values() if v is True); return {"passed":ok,"total":len(checks),"checks":checks}

# ---------- T4 ----------
def s_t4(final):
    exp={1:"8",2:"70",3:"1/15",4:"53",5:"いいえ",6:"1267",7:"B",8:"20"}
    got={}
    for l in final.splitlines():
        m=re.match(r"\s*\**Q\s*(\d)\s*[:：]\s*(.+)",l)
        if m: got[int(m.group(1))]=m.group(2).strip()
    def norm(i,a):
        a=a.replace("*","").replace(",","").replace("，","").strip()
        if i==1: n=re.findall(r"\d+",a); return n[0] if n else a
        if i==2: n=re.findall(r"\d+(?:\.\d+)?",a); return str(int(float(n[0]))) if n and float(n[0])==int(float(n[0])) else (n[0] if n else a)
        if i==3:
            if re.search(r"1\s*/\s*15|1/15",a): return "1/15"
            return a
        if i==4: n=re.findall(r"\d+",a); return n[0] if n else a
        if i==5: return "いいえ" if "いいえ" in a else ("はい" if "はい" in a else a)
        if i==6: n=re.findall(r"\d+",a); return n[0] if n else a
        if i==7:
            m=re.search(r"[ABC]",a); return m.group(0) if m else a
        if i==8: n=re.findall(r"\d+(?:\.\d+)?",a); return str(int(float(n[0]))) if n and float(n[0])==int(float(n[0])) else (n[0] if n else a)
    checks={}
    for i,e in exp.items(): checks[f"Q{i}"]=(norm(i,got[i])==e) if i in got else False
    extra={"expected":exp,"got":got}
    other=[l for l in final.splitlines() if l.strip() and not re.match(r"\s*\**Q\s*\d\s*[:：]",l)]
    checks["形式:8行のみ(説明なし)"]=(len(other)==0 and len(got)==8)
    r=summarize(checks); r["answers_correct"]=sum(1 for i in exp if checks[f"Q{i}"]); r.update(extra); return r

# ---------- T5 ----------
MEMO_NUMS=set("12 184,000 171,500 12,500 23 9 80 100 2 300 350 7 3 12 2 7 19".replace(",","").split())
def s_t5(final):
    c={}
    t=final.strip("\n")
    lines=[l.rstrip() for l in t.splitlines()]
    nonempty=[l for l in lines if l.strip()]
    c["コードブロック・前置き無し(1行目が# )"]=bool(nonempty) and nonempty[0].startswith("# ") and not nonempty[0].startswith("## ") and "```" not in t
    title=nonempty[0][2:].strip() if nonempty else ""
    c["タイトル20文字以内"]=0<len(title)<=20
    heads=[l for l in nonempty if l.startswith("#")]
    c["見出しが指定どおり(タイトル+4つ、順序・名称一致)"]=[h for h in heads]==["# "+title,"## 概要","## 決定事項","## 未解決の課題","## 次のアクション"]
    secs={}; cur=None
    for l in lines:
        if l.startswith("## "): cur=l[3:].strip(); secs[cur]=[]
        elif cur is not None and l.strip(): secs[cur].append(l)
    for k in ["概要","決定事項","未解決の課題"]:
        body="".join(secs.get(k,[])); n=body.count("。")
        c[f"{k}:1〜2文・箇条書き無し"]=(1<=n<=2) and not any(x.lstrip().startswith(("-","*","・","1.")) for x in secs.get(k,[])) and body.rstrip().endswith("。")
    acts=secs.get("次のアクション",[])
    bl=[x for x in acts if x.startswith("- ")]
    c["次のアクション:ちょうど5つの「- 」項目"]=(len(bl)==5 and len(acts)==5)
    c["次のアクション:各40文字以内"]=len(bl)>0 and all(len(x[2:].strip())<=40 for x in bl)
    keys=["12,500|12500","23日","石井","高橋","田中","12月7日","350円|350","総会"]
    hit=[k for k in keys if re.search(k,t)]
    nums=set(re.findall(r"\d[\d,]*",t))
    novel=sorted(n for n in (x.replace(",","") for x in nums) if n not in MEMO_NUMS)
    r=summarize(c); r["key_facts_found"]=f"{len(hit)}/{len(keys)}"; r["key_facts_missing"]=[k for k in keys if k not in hit]
    r["numbers_not_in_memo"]=novel; r["action_items"]=[x[2:] for x in bl]; return r

# ---------- T6 ----------
def s_t6(final):
    c={}
    t=final.strip("\n")
    lines=t.split("\n")
    c["1.1行目が『』タイトル/『』全体で1組"]=bool(re.fullmatch(r"『[^』]+』",lines[0].strip())) and t.count("『")==1 and t.count("』")==1
    c["2.タイトル次行が空行"]=len(lines)>1 and lines[1].strip()==""
    last=lines[-1].strip() if lines else ""
    c["12.最終行が「（了）」のみ"]=(last=="（了）")
    body_lines=lines[2:-1] if last=="（了）" else lines[2:]
    body="\n".join(body_lines).strip("\n")
    paras=[p for p in re.split(r"\n\s*\n",body) if p.strip()]
    c["2.本文がちょうど4段落"]=len(paras)==4
    c["3.各段落がちょうど3文(句点)"]=len(paras)>0 and all(p.count("。")==3 and p.strip().endswith("。") for p in paras)
    c["4.第1段落が「雨」で開始"]=bool(paras) and paras[0].strip().startswith("雨")
    n=len(re.sub(r"\s","",body))
    c["5.本文400〜500字"]=400<=n<=500
    c["6.数字(半角・全角)無し"]=not re.search(r"[0-9０-９]",t)
    c["7.カタカナ・長音無し"]=not re.search(r"[ァ-ヺヽヾー･・ｦ-ﾟ]",t)
    c["8.「猫」「時計」「手紙」を含む"]=all(w in body for w in ["猫","時計","手紙"])
    c["9.常体(です・ます無し)"]=not re.search(r"です|ます|でした|ました|ません",t)
    c["10.！？「」無し"]=not re.search(r"[！？!?「」]",t)
    c["11.最終段落の最終文に「鍵」"]=bool(paras) and ("鍵" in (re.findall(r"[^。]+。",paras[-1]) or [""])[-1])
    c["出力が物語のみ(コードブロック・前置き無し)"]="```" not in t and lines[0].strip().startswith("『")
    r=summarize(c); r["body_chars"]=n; r["paragraphs"]=len(paras); return r

# ---------- T7 ----------
def s_t7(work,final):
    c={}
    rows=list(csv.DictReader(open(f"{ROOT}/tasks/t7_tools/assets/sales.csv",encoding="utf-8")))
    reg={};prod={};mon={};skip=0
    for r in rows:
        try:
            q=float(r["quantity"]);u=float(r["unit_price"])
            if q<=0 or u<=0: raise ValueError
        except Exception: skip+=1; continue
        v=q*u; reg[r["region"]]=reg.get(r["region"],0)+v; prod[r["product"]]=prod.get(r["product"],0)+v; mon[r["date"][:7]]=mon.get(r["date"][:7],0)+v
    rep=read(f"{work}/report.md")
    c["report.md が存在"]=bool(rep)
    sections={}; cur=None
    for l in rep.splitlines():
        if l.startswith("## "): cur=l[3:].strip(); sections[cur]=[]
        elif cur: sections[cur].append(l)
    def table(name):
        rows=[]
        for l in sections.get(name,[]):
            if l.strip().startswith("|"):
                cells=[x.strip() for x in l.strip().strip("|").split("|")]
                if len(cells)>=2 and not re.fullmatch(r"[-:\s]+",cells[0]) and re.search(r"\d",cells[1]):
                    rows.append((cells[0],cells[1]))
        return rows
    def eq(rows,exp,order):
        try: got=[(a,int(b.replace(",","").replace("円",""))) for a,b in rows]
        except Exception: return False
        exp=sorted(exp.items(),key=order)
        return got==[(a,int(round(b))) for a,b in exp]
    c["地域別売上(値・降順)"]=eq(table("地域別売上"),reg,lambda x:-x[1])
    top=dict(sorted(prod.items(),key=lambda x:-x[1])[:3])
    c["商品別売上上位3(値・降順)"]=eq(table("商品別売上上位3"),top,lambda x:-x[1])
    c["月別売上(値・古い順)"]=eq(table("月別売上"),mon,lambda x:x[0])
    m=re.search(r"除外した行数\s*[:：]\s*(\d+)","\n".join(sections.get("除外行",[])))
    c["除外行数が正しい"]=bool(m) and int(m.group(1))==skip
    c["カンマ区切り無し"]=not re.search(r"\d,\d{3}","\n".join(sum((sections.get(k,[]) for k in ["地域別売上","商品別売上上位3","月別売上"]),[])))
    c["analyze.py が存在"]=os.path.exists(f"{work}/analyze.py")
    c["sales.csv 未変更"]=hashlib.md5(open(f"{work}/sales.csv","rb").read()).hexdigest()==hashlib.md5(open(f"{ROOT}/tasks/t7_tools/assets/sales.csv","rb").read()).hexdigest() if os.path.exists(f"{work}/sales.csv") else False
    r=summarize(c); r["truth"]={"regions":reg,"top3":top,"months":mon,"skipped":skip}; return r

# ---------- T2 ----------
def s_t2(work):
    tmp=tempfile.mkdtemp(); 
    for f in os.listdir(work):
        if f.endswith(".py"): shutil.copy(f"{work}/{f}",tmp)
    orig=f"{ROOT}/tasks/t2_bugfix/assets/test_utils.py"
    c={"test_utils.py 未変更":read(f"{work}/test_utils.py")==read(orig)}
    shutil.copy(orig,f"{tmp}/test_utils.py"); shutil.copy(f"{ROOT}/tasks/t2_bugfix/hidden_test.py",f"{tmp}/hidden_test.py")
    def run(mod):
        p=subprocess.run(["python3","-m","unittest",mod,"-v"],cwd=tmp,capture_output=True,text=True,timeout=60)
        out=p.stderr; m=re.search(r"Ran (\d+) tests?",out); n=int(m.group(1)) if m else 0
        f=len(re.findall(r"^(?:FAIL|ERROR):",out,re.M)); return n,n-f,out[-800:]
    n,p,o=run("test_utils"); hn,hp,ho=run("hidden_test")
    c[f"公開テスト全通過({p}/{n})"]=(n==11 and p==n)
    c[f"隠しテスト全通過({hp}/{hn})"]=(hn==11 and hp==hn)
    # bug-level
    sys_path=tmp
    code=f"""
import sys;sys.path.insert(0,{tmp!r})
import utils
r={{}}
try: r['moving_average']=utils.moving_average([1,2,3,4],2)==[1.5,2.5,3.5]
except Exception: r['moving_average']=False
try:
    b=['a'];x=utils.add_tag(b,['b']);y=utils.add_tag(['a']);y.append('z');r['add_tag']=(b==['a'] and x==['a','b'] and utils.add_tag(['a'])==['a'])
except Exception: r['add_tag']=False
try: r['parse_duration']=utils.parse_duration('1h30m')==5400 and utils.parse_duration('2h5m10s')==7510
except Exception: r['parse_duration']=False
import json;print(json.dumps(r))
"""
    p2=subprocess.run(["python3","-c",code],capture_output=True,text=True)
    try: bugs=json.loads(p2.stdout.strip().splitlines()[-1])
    except Exception: bugs={}
    for k in ["moving_average","add_tag","parse_duration"]: c[f"バグ修正:{k}"]=bool(bugs.get(k))
    r=summarize(c); r["unittest_tail"]=o; return r

# ---------- browser tasks ----------
def browser(task,label,work,shotprefix):
    code=open(f"{ROOT}/browser_{task}.py").read()
    p=subprocess.run(["/workspace/deepseek_demo_env/venv/bin/python",f"{ROOT}/browser_{task}.py",work,f"{ROOT}/screens/{shotprefix}"],capture_output=True,text=True,timeout=900)
    try: return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception: return {"error":"browser test crashed","stdout":p.stdout[-1500:],"stderr":p.stderr[-1500:],"passed":0,"total":0,"checks":{}}

def main():
    task,label=sys.argv[1:3]; rd=f"{ROOT}/runs/{task}/{label}"
    work=sys.argv[3] if len(sys.argv)>3 else f"{rd}/work"; final=read(f"{rd}/final_text.txt")
    if task=="t1_game": r=browser("t1",label,work,f"t1_{label}")
    elif task=="t2_bugfix": r=s_t2(work)
    elif task=="t3_modify": r=browser("t3",label,work,f"t3_{label}")
    elif task=="t4_logic": r=s_t4(final)
    elif task=="t5_summary": r=s_t5(final)
    elif task=="t6_constraints": r=s_t6(final)
    elif task=="t7_tools": r=s_t7(work,final)
    if len(sys.argv)<=3: json.dump(r,open(f"{rd}/score.json","w"),ensure_ascii=False,indent=1)
    print(json.dumps({k:v for k,v in r.items() if k!="checks"},ensure_ascii=False)[:1500]); 
    for k,v in r.get("checks",{}).items(): print(("PASS " if v is True else "FAIL ")+k)
main()
