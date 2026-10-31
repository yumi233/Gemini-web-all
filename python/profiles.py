"""Private persistent browser profiles, explicitly bound to one backend account."""
import contextlib,fcntl,json,os,re,uuid
from pathlib import Path
os.umask(0o077)
def root():
 p=Path(os.environ['GEMINI_WEB_ALL_RUNTIME'])/'profiles';p.mkdir(parents=True,exist_ok=True,mode=0o700);return p

def profile_path(token):
 if not isinstance(token,str) or not re.fullmatch(r'[0-9a-f]{32}',token):raise ValueError('Invalid browser profile')
 return root()/token

@contextlib.contextmanager
def locked(name):
 with (root()/(name+'.lock')).open('a') as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise ValueError('This account browser is busy; do not resubmit')
  try:yield
  finally:fcntl.flock(f,fcntl.LOCK_UN)

def registry():
 p=root()/'accounts.json';return json.loads(p.read_text()) if p.exists() else {}

def lookup(account_id):
 if account_id is None:raise ValueError('Select an explicit image account')
 row=registry().get(str(int(account_id)))
 if not row:raise ValueError('This account needs a persistent browser login; existing cookies are retained')
 return row

def bind(account_id,token,email):
 p=profile_path(token)
 if not p.is_dir() or not email or '@' not in email:raise ValueError('Incomplete browser identity')
 with locked('registry'):
  rows=registry();key=str(int(account_id))
  if any(v['profile']==token and k!=key for k,v in rows.items()):raise ValueError('Browser profile is already assigned to another account')
  if key in rows and rows[key]['email'].casefold()!=email.casefold():raise ValueError('Account identity mismatch; existing profile retained')
  rows[key]={'profile':token,'email':email}
  tmp=root()/('accounts-'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps(rows));tmp.replace(root()/'accounts.json')

def identity(html):
 m=re.search(r'"oPEP7c":"([^"@\s]+@[^"\s]+)"',html);return m.group(1) if m else None

def launch_options(headless=True,proxy=None):
 from login import executable
 result={'executable_path':executable(),'headless':headless}
 proxy=proxy or os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
 if proxy:result['proxy']={'server':proxy}
 return result

if __name__=='__main__':
 import sys
 try:
  request=json.load(sys.stdin);bind(request['account_id'],request['profile'],request['email']);print(json.dumps({'ok':True}))
 except Exception as e:print(json.dumps({'error':str(e) if isinstance(e,ValueError) else type(e).__name__}));sys.exit(1)
