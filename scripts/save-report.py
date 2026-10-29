"""Keep generated reports on a dedicated branch. Never copy runner credentials."""
import datetime,json,pathlib,re,shutil,subprocess,sys
source=pathlib.Path(sys.argv[1])
if not (source/'report.json').exists():
    source.mkdir(parents=True,exist_ok=True)
    (source/'report.json').write_text(json.dumps({'ok':False,'checks':[{'name':'workflow-execution','ok':False,'code':'RUNNER_FAILURE'}]}))
    (source/'report.md').write_text('# Webmaster check\n\nROSSO: il controllo non è stato completato. Nessun dato sensibile salvato.\n')
work=pathlib.Path('/tmp/agora-reports-branch')
def git(*args, cwd=None,check=True):return subprocess.run(['git',*args],cwd=cwd,check=check,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
found=git('fetch','origin','reports:refs/remotes/origin/reports',check=False).returncode==0
if found:git('worktree','add','-B','reports',str(work),'refs/remotes/origin/reports')
else:
    git('worktree','add','--detach',str(work),'HEAD');git('checkout','--orphan','reports',cwd=work);git('rm','-rf','.',cwd=work)
root=work/'reports';root.mkdir(exist_ok=True)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d-%H%M');dest=root/stamp;dest.mkdir(exist_ok=True)
for file in source.iterdir():
    if file.is_file() and (file.name in ['report.json','report.md'] or re.fullmatch(r'[a-z0-9-]+\.png',file.name)):shutil.copy2(file,dest/file.name)
folders=sorted(d for d in root.iterdir() if d.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}-\d{4}',d.name))
for old in folders[:-30]:shutil.rmtree(old)
git('config','user.name','agora-webmaster[bot]',cwd=work);git('config','user.email','agora-webmaster[bot]@users.noreply.github.com',cwd=work)
git('add','reports',cwd=work);git('commit','-m','Record webmaster check '+stamp,cwd=work);git('push','origin','HEAD:reports',cwd=work)
