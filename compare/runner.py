#!/usr/bin/env python3
"""公平比較ランナー: run.py <task_id> <model_label>  (label: deepseek | glm)
同一プロンプトファイル、同一設定、新規サンドボックス(/work, /xdg)、-m だけ違う。"""
import sys,os,subprocess,time,json,shutil,re,signal
ROOT="/workspace/compare_glm"
MODELS={"deepseek":"opencode/deepseek-v4.1-flash-free","glm":"opencode/glm-5.3-flash-free"}
TIMEOUT=1200
INFRA=re.compile(r"server_error|Streaming response failed|provider.internal|provider.transport|Model unavailable|no-route|provider.quota|ECONNRESET|socket connection|Connection lost|rate.?limit|429|Too Many|overloaded|ETIMEDOUT|ENOTFOUND|fetch failed|ECONNREFUSED|EAI_AGAIN|503|502|504",re.I)
def run(task,label,cont=False):
    model=MODELS[label]; tdir=f"{ROOT}/tasks/{task}"
    prompt=open(f"{tdir}/prompt.txt",encoding="utf-8").read()
    attempts=[]; first=1
    if cont:
        prev=[json.loads(l) for l in open(f"{ROOT}/results.jsonl") if json.loads(l)["task"]==task and json.loads(l)["model_label"]==label][-1]
        attempts=prev["attempts"]; first=len(attempts)+1
        rd0=f"{ROOT}/runs/{task}/{label}"; shutil.move(rd0,f"{rd0}.attempt{len(attempts)}_discarded")
    for a in range(first,7):
        rd=f"{ROOT}/runs/{task}/{label}"
        if os.path.exists(rd): shutil.move(rd,f"{rd}.attempt{a-1}_discarded")
        work=f"{rd}/work"; xdg=f"{rd}/xdg"
        os.makedirs(work); 
        if os.path.isdir(f"{tdir}/assets"): shutil.copytree(f"{tdir}/assets",work,dirs_exist_ok=True)
        for d in ("config/opencode","data","state","cache"): os.makedirs(f"{xdg}/{d}",exist_ok=True)
        os.makedirs(f"{xdg}/data/opencode",exist_ok=True); shutil.copy(f"{ROOT}/auth.template.json",f"{xdg}/data/opencode/auth.json"); os.chmod(f"{xdg}/data/opencode/auth.json",0o600)
        shutil.copy(f"{ROOT}/opencode.jsonc",f"{xdg}/config/opencode/opencode.jsonc")
        cmd=["bwrap","--ro-bind","/","/","--dev","/dev","--proc","/proc","--tmpfs","/tmp","--tmpfs","/workspace","--tmpfs","/cursor","--tmpfs","/home/box",
             "--ro-bind","/home/box/.opencode","/home/box/.opencode","--bind",work,"/tmp/work","--bind",xdg,"/tmp/xdg","--unshare-pid","--die-with-parent","--chdir","/tmp/work","--clearenv",
             "--setenv","PATH","/usr/local/bin:/usr/bin:/bin","--setenv","HOME","/home/box","--setenv","LANG","C.UTF-8",
             "--setenv","XDG_CONFIG_HOME","/tmp/xdg/config","--setenv","XDG_DATA_HOME","/tmp/xdg/data","--setenv","XDG_STATE_HOME","/tmp/xdg/state","--setenv","XDG_CACHE_HOME","/tmp/xdg/cache",
             "/home/box/.opencode/bin/opencode","run","--standalone","--auto","--format","json","-m",model,prompt]
        t0=time.time(); timed_out=False
        p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        try: out,err=p.communicate(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            timed_out=True; os.killpg(p.pid,signal.SIGKILL); out,err=p.communicate()
        sec=round(time.time()-t0,1)
        open(f"{rd}/events.jsonl","w").write(out or ""); open(f"{rd}/stderr.txt","w").write(err or "")
        ev=[]
        for l in (out or "").splitlines():
            try: ev.append(json.loads(l))
            except: pass
        errs=[(e.get("error") or {}).get("message",str(e))[:300] for e in ev if e.get("type")=="error"]
        tools=[e for e in ev if e.get("type")=="tool_use"]
        toolnames={}
        for e in tools:
            n=(e.get("part") or {}).get("tool","?"); toolnames[n]=toolnames.get(n,0)+1
        toks={"input":0,"output":0,"reasoning":0}
        for e in ev:
            if e.get("type")=="step_finish":
                t=(e.get("part") or {}).get("tokens") or {}
                toks["input"]+=t.get("input",0) or 0; toks["output"]+=t.get("output",0) or 0; toks["reasoning"]+=t.get("reasoning",0) or 0
        texts=[(e["part"]["messageID"],e["part"].get("text","")) for e in ev if e.get("type")=="text"]
        final=""
        if texts:
            last=texts[-1][0]; final="\n".join(t for m,t in texts if m==last)
        open(f"{rd}/final_text.txt","w").write(final)
        files={}
        for dp,dn,fn in os.walk(work):
            for f in fn:
                fp=os.path.join(dp,f); files[os.path.relpath(fp,work)]=os.path.getsize(fp)
        att={"attempt":a,"sec":sec,"rc":p.returncode,"timed_out":timed_out,"errors":errs,"stderr_tail":(err or "")[-300:],"tool_calls":len(tools),"tool_names":toolnames,"tokens":toks,"final_chars":len(final),"files":files}
        attempts.append(att)
        infra=bool(errs) and all(INFRA.search(x) for x in errs)
        if timed_out and not infra: break
        if not errs and p.returncode!=0 and INFRA.search(err or ""): infra=True
        if infra and a<6:
            time.sleep(min(30*a,180)); continue
        break
    res={"task":task,"model_label":label,"model":model,"attempts":attempts,"retries":len(attempts)-1,"final_attempt":attempts[-1]["attempt"],
         "sec_final":attempts[-1]["sec"],"sec_total":round(sum(x["sec"] for x in attempts),1),"timed_out":attempts[-1]["timed_out"],
         "errors_final":attempts[-1]["errors"],"continued_after_infra_timeout":cont,"started":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(t0))}
    open(f"{ROOT}/results.jsonl","a").write(json.dumps(res,ensure_ascii=False)+"\n")
    print(json.dumps(res,ensure_ascii=False)[:600],flush=True)
if __name__=="__main__": run(sys.argv[1],sys.argv[2],len(sys.argv)>3 and sys.argv[3]=="continue")
