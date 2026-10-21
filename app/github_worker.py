import json, os, subprocess, time
from pathlib import Path

try:
    from .progress import Progress
except ImportError:
    from progress import Progress

REPO="DmitryGusenko1/100print"
WORKDIR="/opt/ceo-orchestrator"
STATE=Path(WORKDIR+"/data/worker_state.json")
LOG=Path(WORKDIR+"/logs/github_worker.log")

def log(s):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")

def run(cmd, timeout=3600):
    return subprocess.run(
        cmd,
        cwd=WORKDIR,
        text=True,
        capture_output=True,
        timeout=timeout,
        env={**os.environ, "HOME": WORKDIR},
    )

def load_done():
    if not STATE.exists():
        return set()
    try:
        return set(json.loads(STATE.read_text()).get("done", []))
    except:
        return set()

def save_done(done):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"done": sorted(done)}, indent=2))

def main():
    done=load_done()
    progress = Progress()

    while True:
        try:
            r=run([
                "gh","issue","list",
                "--repo",REPO,
                "--state","open",
                "--limit","50",
                "--json","number,title,body,author"
            ],120)

            issues=json.loads(r.stdout)

            for issue in sorted(issues,key=lambda x:x["number"]):
                num=str(issue["number"])
                author=(issue.get("author") or {}).get("login")

                if author!="DmitryGusenko1" or num in done:
                    continue

                log(f"START issue #{num}")
                previous = progress.read()
                if previous and previous["issue_number"] == int(num):
                    progress.update(num, action="resuming after worker restart")
                else:
                    progress.update(num, "analysis", "analyze issue", "executor starting")

                prompt=f"""
Ты исполнитель CEO Orchestrator.

Выполни GitHub issue #{num} из репозитория {REPO}.

TITLE:
{issue["title"]}

BODY:
{issue.get("body") or ""}

ВАЖНО:
- работать только в {WORKDIR}
- не трогать другие проекты VPS
- не читать чужие .env
- разрешено создавать и менять только свои сервисы ceo-* и ai-business-brain-*; чужие сервисы запрещено трогать
- разрешено создавать и использовать только свои БД ceo_orchestrator и ai_brain; чужие БД запрещено трогать
- реально выполнить задачу
- проверить результат
- при изменениях сделать git add/commit/push
- в конце короткий отчёт DONE / CHANGED / TESTED / NEXT
- ОБЯЗАТЕЛЬНО сообщай фактический этап командой:
  python3 {WORKDIR}/scripts/progress.py --issue {num} --stage STAGE --current "текущая подзадача" --action "последнее действие"
- этапы по порядку: analysis (10%), planning (25%), implementation (40%), integration (60%), tests (75%), commit/push (90%)
- обновляй current при смене подзадачи; процент отражает этап, не время
- при возобновлении сначала прочитай scripts/progress.py и продолжай с сохраненного этапа без уменьшения процента
- done (100%) выставляет worker только после успешного завершения
"""

                stop, heartbeat_thread = progress.start_heartbeat(num)
                try:
                    c=run([
                        "codex","exec",
                        "--skip-git-repo-check",
                        "--dangerously-bypass-approvals-and-sandbox",
                        prompt
                    ],3600)
                    if c.returncode == 0:
                        progress.update(num, "done", "DONE", "executor completed successfully")
                    else:
                        progress.update(num, action=f"executor failed: exit {c.returncode}")
                except Exception as error:
                    progress.update(num, action=f"executor interrupted: {type(error).__name__}")
                    raise
                finally:
                    stop.set()
                    heartbeat_thread.join(timeout=5)

                output=((c.stdout or "")+"\n"+(c.stderr or ""))[-12000:]
                status="DONE" if c.returncode==0 else "FAILED"

                run([
                    "gh","issue","comment",num,
                    "--repo",REPO,
                    "--body",f"## CEO Orchestrator: {status}\n\n```text\n{output}\n```"
                ],120)

                if c.returncode==0:
                    done.add(num)
                    save_done(done)

                log(f"{status} issue #{num}")

        except Exception as e:
            log(f"ERROR {type(e).__name__}: {e}")

        time.sleep(60)

if __name__=="__main__":
    main()
