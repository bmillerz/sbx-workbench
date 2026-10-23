"""Run: python3 -I tests/test_session_deck.py — a fake ~/.claude and real git repos, checked one frame at a time.
The rules are the deck plugin's (hooks/register.test.ts); this checks the port keeps them."""
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader

here = os.path.dirname(os.path.abspath(__file__))
sd = SourceFileLoader('sd', os.path.join(here, '..', 'kits', 'claude-config', 'files', 'session-deck')).load_module()

now = time.time()
iso = lambda ago: datetime.fromtimestamp(now - ago, timezone.utc).isoformat().replace('+00:00', 'Z')
home = tempfile.mkdtemp()
jobs, proj = f'{home}/.claude/jobs', f'{home}/.claude/projects/p'
os.makedirs(proj)
p = sd.Pen(colour=False)


def sh(*a, cwd):
    subprocess.run(a, cwd=cwd, check=True, capture_output=True)


def git(*a, cwd):
    sh('git', '-c', 'user.name=t', '-c', 'user.email=t@t', *a, cwd=cwd)


def job(jid, **state):
    os.makedirs(f'{jobs}/{jid}', exist_ok=True)
    with open(f'{jobs}/{jid}/state.json', 'w') as f:
        json.dump(state, f)


def transcript(name, *records, quiet=0):
    path = f'{proj}/{name}.jsonl'
    with open(path, 'w') as f:
        f.write('cut half a line\n' + ''.join(json.dumps(r) + '\n' for r in records))
    os.utime(path, (now - quiet, now - quiet))
    return path


said = lambda who, ago, text, **o: {'type': who, 'timestamp': iso(ago), 'message': {'content': [{'type': 'text', 'text': text}], **o}}
tool = lambda ago, inp: {'type': 'assistant', 'timestamp': iso(ago), 'message': {'content': [{'type': 'tool_use', 'name': 'Bash', 'input': inp}]}}


def frame(deck, cols=100):
    return '\n'.join(p.render(l) for l in deck.frame(p, now, cols))


# ----- formatting -----
assert sd.pretty_model('claude-opus-5-5') == 'Opus 5.5' and sd.pretty_model('claude-haiku-4-5-20251001') == 'Haiku 4.5'
assert sd.pretty_model('opus') == 'Opus' and sd.pretty_model('claude-fable-5-1[1m]') == 'Fable 5.1'
assert sd.clock(12) == '12s' and sd.clock(65) == '1m 5s' and sd.clock(3 * 3600 + 249) == '3h 4m' and sd.clock(2 * 86400 + 3 * 3600) == '2d 3h'
assert sd.ago(30) == 'just now' and sd.ago(185 * 60) == '3h ago' and sd.age(3 * 1440) == '3d'

# ----- what a transcript's end says -----
t = sd.parse_tail('{"half\n' + json.dumps(said('user', 50, 'go')) + '\n'
                  + json.dumps({'type': 'user', 'timestamp': iso(40), 'message': {'content': '<system-reminder>x'}}) + '\n'
                  + json.dumps(tool(30, {'command': 'cd /r/.claude/worktrees/wt-a && git status'})) + '\n')
assert abs(t['reply'] - (now - 50)) < 1, 'an injected reminder is not a prompt'
assert t['tree'] == '/r/.claude/worktrees/wt-a' and not t['last_is_text'], 'a worktree named in the session\'s own tool call'
assert sd.parse_tail(json.dumps(said('user', 5, '[Request interrupted by user]')))['halted'] > 0
assert sd.parse_tail(json.dumps(said('assistant', 5, 'Done.')))['last_is_text']

# ----- a repo with an upstream, worktrees in every state, and a leftover folder -----
origin, repo = f'{home}/origin.git', f'{home}/repo'
sh('git', 'init', '-q', '--bare', '-b', 'main', origin, cwd=home)
sh('git', 'clone', '-q', origin, repo, cwd=home)
git('commit', '-q', '--allow-empty', '-m', 'base', cwd=repo)
git('push', '-q', '-u', 'origin', 'main', cwd=repo)
for n in ('merged-wt', 'new-wt', 'ahead-wt', 'dirty-wt', 'busy-wt'):
    git('worktree', 'add', '-q', '-b', n, f'.claude/worktrees/{n}', cwd=repo)
wt = lambda n: f'{repo}/.claude/worktrees/{n}'
git('commit', '-q', '--allow-empty', '-m', 'wip', cwd=wt('ahead-wt'))
open(f"{wt('dirty-wt')}/note.txt", 'w').close()
os.makedirs(f'{repo}/.claude/worktrees/leftover/vendor')
# Created a day ago: no longer "new", so a merged one is safe to remove.
for n in ('merged-wt', 'busy-wt'):
    os.utime(f'{repo}/.git/worktrees/{n}/HEAD', (now - 86400, now - 86400))
git('commit', '-q', '--allow-empty', '-m', 'feat: older', cwd=repo)
git('commit', '-q', '--allow-empty', '-m', 'feat: newest', cwd=repo)

# ----- sessions -----
job('wait', state='working', tempo='idle', name='wait-job', updatedAt=iso(600), inFlight={'tasks': 0, 'queued': 0},
    linkScanPath=transcript('wait', said('user', 400, 'go'), said('assistant', 300, 'Pushing deploys production, so I will wait.'), quiet=300))
job('busy', state='working', tempo='idle', name='busy-job', updatedAt=iso(600), inFlight={'tasks': 1, 'queued': 0},
    linkScanPath=transcript('busy', said('assistant', 300, 'Waiting on the build.'), quiet=300))
job('mid-tool', state='working', tempo='idle', name='tool-job', updatedAt=iso(600), inFlight={'tasks': 0},
    linkScanPath=transcript('mid-tool', tool(300, {'command': 'ls'}), quiet=300))
job('halted', state='working', tempo='idle', name='halted-job', updatedAt=iso(600),
    linkScanPath=transcript('halted', said('user', 120, '[Request interrupted by user]'), quiet=120))
job('asking', state='blocked', name='asking-job', needs='Push to production?', lastTerminalAt=iso(90), respawnFlags=['--model', 'opus'],
    linkScanPath=transcript('asking', said('assistant', 90, 'Push?', model='claude-opus-5-5'), quiet=90))
job('replied', state='done', name='replied-job', lastTerminalAt=iso(200),
    linkScanPath=transcript('replied', said('assistant', 200, 'Done.'), said('user', 20, 'one more thing')))
job('active', state='done', tempo='active', name='active-job', lastTerminalAt=iso(200), respawnFlags=['--model', 'sonnet'],
    linkScanPath=transcript('active', said('user', 45, 'go on')))
job('in-tree', state='working', tempo='active', name='tree-job', updatedAt=iso(60),
    linkScanPath=transcript('in-tree', said('user', 30, 'go'), {**tool(10, {'command': f"cd {wt('busy-wt')} && git status"}), 'cwd': repo},
                            said('assistant', 5, 'Working.', model='claude-sonnet-5-5')))
job('isolated', state='done', name='isolated-job', lastTerminalAt=iso(600), worktreePath=wt('dirty-wt'),
    linkScanPath=transcript('isolated', said('assistant', 600, 'All done.')), detail='Landed in a worktree')
job('finished', state='done', name='recent-job', lastTerminalAt=iso(3000), detail='Shipped the fix',
    linkScanPath=transcript('finished', said('assistant', 3000, 'Shipped.')))
job('yesterday', state='done', name='old-job', lastTerminalAt=iso(2 * 86400),
    linkScanPath=transcript('yesterday', said('assistant', 2 * 86400, 'Old.')))
# Agents under the working tree-job: one live, one marked finished, one whose last word went quiet, one interrupted.
sub = f'{proj}/in-tree/subagents'
os.makedirs(sub)
for aid, meta, recs, quiet in (
        ('live', {'agentType': 'Explore', 'model': 'sonnet', 'description': 'map the code'}, [tool(5, {'command': 'ls'})], 5),
        ('marked', {'model': 'haiku', 'description': 'marked done', 'finished': True}, [tool(5, {})], 5),
        ('quiet', {'model': 'haiku', 'description': 'said done'}, [said('assistant', 60, 'Here is the summary.')], 60),
        ('stopped', {'model': 'haiku', 'description': 'was stopped'}, [said('user', 30, '[Request interrupted by user]')], 30)):
    with open(f'{sub}/{aid}.meta.json', 'w') as f:
        json.dump(meta, f)
    with open(f'{sub}/{aid}.jsonl', 'w') as f:
        f.write(''.join(json.dumps({**r, 'isSidechain': True}) + '\n' for r in recs))
    os.utime(f'{sub}/{aid}.jsonl', (now - quiet, now - quiet))

deck = sd.Deck(home, repo)
deck.refresh(force=True)
text = frame(deck)
by = {j['name']: j for g in deck.view.values() for j in g}
at = text.index
assert at('NEEDS INPUT') < at('wait-job') < at('WORKING'), 'idle, quiet, last word a finished message: it needs you'
assert at('busy-job') > at('WORKING') and at('tool-job') > at('WORKING'), 'busy, or mid-tool, stays working'
assert by['halted-job']['status'] == 'yours' and 'Interrupted · what should Claude do instead?' in text
assert '◆ asking-job  Opus 5.5' in text and 'Push to production?' in text, 'the transcript names the full model'
assert by['replied-job']['status'] == 'working', 'a fresh reply flips done to working'
assert by['active-job']['status'] == 'working' and 'active-job  Sonnet 5.5' in text, 'tempo active wins; the alias learns the full name'
assert 'old-job' not in text and 'recent-job' in text and 'Shipped the fix' in text, 'completed: the last day only'
assert '└─ ● Explore · Sonnet 5.5  map the code' in text, 'a live agent shows under its session'
assert not any(x in text for x in ('marked done', 'said done', 'was stopped')), 'finished, quiet and interrupted agents do not'
assert '1 working' not in text and f"{len(deck.view['working'])} working · {len(deck.view['needs'])} needs input" in text

# ----- worktrees -----
row = lambda name: next(l for l in text.split('\n') if f'⎇ {name} ' in l and 'old' in l)
assert 'tree-job  Sonnet 5.5  ⎇ busy-wt' in text, 'a session in a worktree shows its branch'
assert 'in use' in row('busy-wt') and 'safe to remove' not in row('busy-wt'), 'a worktree in use is never safe to remove'
assert '1 uncommitted file · in use' in row('dirty-wt'), 'a session between turns that EnterWorktree isolated still holds it'
assert '1 commit to land' in row('ahead-wt')
assert row('new-wt').split('new-wt')[1].split()[0] == 'new', 'a fresh worktree is new, not safe to remove'
assert 'merged · safe to remove' in row('merged-wt')
assert '⎇ leftover  leftover folder · safe to delete' in text
assert 'WORKTREES' in text and '5 open' in text
assert all(t['size_mb'] is None for t in deck.snap['trees']), 'opening measures no sizes'
deck.refresh()
assert next(t for t in deck.snap['trees'] if t['branch'] == 'merged-wt')['size_mb'] is not None, 'the next refresh measures candidates'
assert all(t['size_mb'] is None for t in deck.snap['trees'] if t['branch'] in ('new-wt', 'ahead-wt', 'dirty-wt')), 'only cleanup candidates are measured'

# ----- unpushed commits, as a timeline down to what is live -----
lines = text.split('\n')
newest = next(i for i, l in enumerate(lines) if '(main) feat: newest' in l)
assert '● ' in lines[newest] and 'feat: older' in lines[newest + 1] and '○ (origin/main) live' in lines[newest + 2]
assert 'UNPUSHED ON MAIN' in text and '2 commits' in text
git('push', '-q', cwd=repo)
synced = sd.Deck(home, repo)
synced.refresh(force=True)
assert 'In sync with origin' in frame(synced), 'nothing to push: the section says so'

# ----- health -----
assert '⚠' not in text, 'a healthy view shows no warning'
broken = sd.Deck(home, f'{home}/not-a-repo')
os.makedirs(f'{home}/not-a-repo')
broken.refresh(force=True)
assert '⚠ git worktree list failed' in frame(broken), 'opening reports what failed'
broken.refresh()
assert '⚠ git check failed' in frame(broken), 'a failing check warns'
assert 'Reading…' in frame(sd.Deck(home, repo)), 'before the first read: reading, not empty'

# ----- drawing -----
assert all(len(l) <= 100 for l in text.split('\n')), 'every line fits the terminal'
assert all(len(l) <= 50 for l in frame(deck, 50).split('\n')), 'and a narrow one'
pen = sd.Pen(colour=True)
lit, dim = (''.join(pen.render(l) for l in sd.frame_lines(pen, deck.snap, deck.view, deck.health, t, 100)) for t in (1000.0, 1000.5))
assert '\x1b[38;5;117m● ' in lit and '\x1b[38;5;238m● ' in dim, 'the working dot pulses bright, then dim'
assert '38;2;' not in lit, 'the default palette is 256-colour: 24-bit codes break Terminal.app'
true = sd.Pen(colour=True, truecolor=True)
assert '\x1b[38;2;125;211;252m' in ''.join(true.render(l) for l in sd.frame_lines(true, deck.snap, deck.view, deck.health, 1000.0, 100))

# ----- scrolling -----
assert sd.scrolled(5, '\x1b[B\x1b[B\x1b[B', 20) == 8, 'arrows, one line each'
assert sd.scrolled(5, '\x1bOA', 20) == 4 and sd.scrolled(5, 'jjk', 20) == 6, 'application-mode arrows and j k'
assert sd.scrolled(5, '\x1b[6~', 20) == 25 and sd.scrolled(25, 'b', 20) == 5, 'a page each way'
assert sd.scrolled(2, '\x1b[5~', 20) == 0, 'never above the top'
assert sd.scrolled(40, 'g', 20) == 0 and sd.scrolled(0, 'G', 20) >= 10 ** 6, 'g G jump to the ends'
assert sd.scrolled(5, '\x1b[1;5B', 20) == 5, "a key it doesn't know moves nothing"
assert sd.scrolled(5, '\x1b[<65;10;4M\x1b[<65;10;4M', 20) == 5 + 2 * sd.WHEEL_LINES, 'each wheel notch down scrolls'
assert sd.scrolled(9, '\x1b[<64;10;4M', 20) == 9 - sd.WHEEL_LINES, 'a notch up scrolls back'
assert sd.scrolled(5, '\x1b[<69;10;4M', 20) == 5 + sd.WHEEL_LINES, 'a held modifier still scrolls'
assert sd.scrolled(5, '\x1b[<0;10;4M\x1b[<0;10;4mgjb', 20) == 0, 'a click moves nothing and its digits are not keys'

bar = lambda top, view, total, cols=100: p.render(sd.footer(p, top, view, total, cols))
assert 'scroll' not in bar(0, 40, 30) and 'q quit' in bar(0, 40, 30), 'everything fits: only quit'
assert '↑/↓ scroll   q quit' in bar(0, 20, 50), 'the keys, three spaces apart'
assert bar(0, 20, 50).rstrip().endswith('↓ 30 more') and bar(30, 20, 50).rstrip().endswith('↑ 30 above'), 'where the view stands'
assert all(len(bar(5, 20, 50, c)) == c for c in (100, 40)), 'the bar fills the width and no more'

print('ok')
