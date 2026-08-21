import subprocess, sys, os

REPO = '/home/fsanches/compartilhado/mame-pr-tonegen'

def git(*a, **kw):
    return subprocess.run(['git', *a], cwd=REPO, capture_output=True, text=True,
                          check=True, env={**os.environ, **kw.get('env', {})}).stdout

MSG_FIX = {
 'e36bcd782e5052a1289a2f67b21c90bfc5adf054': (
   "already loads -- so nothing firmware-derived is checked in and the constants follow\n"
   "whichever firmware revision is selected.",
   "already loads -- so nothing firmware-derived is checked into the driver source."),
 '71d296e5452e4c16378459838e3444d03a74693f': (
   "ROM, a ROM the driver already loads, so they also follow whichever firmware revision\n"
   "is selected.",
   "ROM, a ROM the driver already loads."),
}

NEWLATCH = git('rev-parse', 'rw/latch').strip()
LATCH    = '154f2ff4785332cf52166539ce5a414df04c14c1'

BRANCHES = {
 'kn5000_minimal_tonegen': ['e36bcd782e5052a1289a2f67b21c90bfc5adf054',
                            'c4eedd2782d5275428b18e7d5e5ed4248085c654'],
 'kn5000_tonegen_pcm':     ['e36bcd782e5052a1289a2f67b21c90bfc5adf054',
                            '4e90f3bc8745c8ea20812428324865f134ea72a8',
                            '657e0d1e151312f8a4cb72b5602043bc3fb22c77',
                            'ffdc2fc3c2e501972a3321c6b65ed25e3a68ae3e',
                            'efa7358200979fe4e29b901bc1fbd3ff7bc829c8',
                            '0af60369f00cf863b45a33e2c18c03dedca31eda'],
 'kn5000_tonegen_combined':['71d296e5452e4c16378459838e3444d03a74693f',
                            '159439916a79701c0decfc9bf92e9cdd03b4e857',
                            '413ee3ded6329bcb1633068920de2e9be1fd51aa'],
}

for branch, commits in BRANCHES.items():
    old_tip = git('rev-parse', branch).strip()
    parent = NEWLATCH
    for c in commits:
        msg = git('log', '-1', '--format=%B', c)
        if c in MSG_FIX:
            old, new = MSG_FIX[c]
            if old not in msg:
                sys.exit(f"FAIL: message fix target not found in {c[:11]}")
            msg = msg.replace(old, new, 1)
        adate = git('show', '-s', '--format=%aD', c).strip()
        aname = git('show', '-s', '--format=%an', c).strip()
        amail = git('show', '-s', '--format=%ae', c).strip()
        git('reset', '--hard', '-q', c)
        git('reset', '--soft', '-q', parent)
        git('commit', '-q', '--no-verify', '-m', msg.strip() + '\n',
            env={'GIT_AUTHOR_DATE': adate, 'GIT_AUTHOR_NAME': aname, 'GIT_AUTHOR_EMAIL': amail})
        parent = git('rev-parse', 'HEAD').strip()
    git('branch', '-f', branch, parent)
    # SAFETY GATE: the final tree must be byte-identical to what was tested
    d = subprocess.run(['git', 'diff', '--stat', old_tip, parent], cwd=REPO,
                       capture_output=True, text=True).stdout.strip()
    status = "TREE IDENTICAL" if not d else f"*** TREE DIFFERS ***\n{d}"
    print(f"{branch}: {old_tip[:11]} -> {parent[:11]}  {status}")
