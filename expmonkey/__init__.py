import argparse
import os
import re
import sys
import shutil
import tempfile
import subprocess

import argcomplete
import colored
try:
    import pygit2
except ImportError:
    pygit2 = None


def _die(msg):
    sys.stderr.write(msg)
    sys.stderr.write('\n')
    sys.stderr.flush()
    sys.exit(1)


def _get_basedir(path=os.getcwd()):
    path = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(path, '.em')):
            return path
        if path == os.path.dirname(path):
            _die('Project not found, you may want to start with "em init"')
        path = os.path.dirname(path)


def _get_parent_git_path(path=os.getcwd()):
    path = os.path.abspath(path)
    relpath = './'
    while True:
        if os.path.exists(os.path.join(path, '.git')):
            return relpath
        if path == os.path.dirname(path):
            return None
        path = os.path.dirname(path)
        relpath = relpath + '../'


def _get_repo(branch=None, path=os.getcwd()):
    basedir = _get_basedir(path)
    if branch is None:
        path = os.path.join(basedir, '.em/repo')
        if os.path.isfile(path):
            path = open(os.path.join(basedir, path)).read()
    else:
        path = os.path.join(basedir, branch)
    if pygit2 is not None:
        return Pygit2Repository(path)
    else:
        return ShellRepository(path)


class BaseRepository(object):
    def check_output(self, *args):
        try:
            p = subprocess.Popen(args, cwd=self.path, stdout=subprocess.PIPE)
            stdout, stderr = p.communicate()
        except KeyboardInterrupt:
            _die('KeyboardInterrupt')
        if p.returncode != 0:
            raise RuntimeError('Subprocess exits with non-zero return code {}: {}'.format(p.returncode, ' '.join(args)))
        return stdout.decode().strip()

    def remotes(self):
        return self.check_output('git', 'remote').split()

    def get_name(self):
        name = os.path.basename(self.check_output('git', 'remote', 'get-url', self.remote))
        if name.endswith('.git'):
            name = name[:-4]
        return name

    def add_worktree(self, path, branch):
        self.check_output('git', 'worktree', 'add', path, branch)

    def add_worktree_with_first_commit_detached(self, path):
        first_commit_id = self.check_output('git', 'rev-list', '--all', '--topo-order', '--reverse').splitlines()[0]
        self.check_output('git', 'worktree', 'add', '--detach', path, first_commit_id)

    def checkout_orphan(self, branch):
        self.check_output('git', 'checkout', '--orphan', branch)
        self.check_output('git', 'rm', '-rf', '.')

    def list_worktrees(self):
        worktrees = []
        prev_path = None
        prev_head = None
        for line in self.check_output('git', 'worktree', 'list', '--porcelain').splitlines():
            if line.startswith('worktree'):
                prev_path = line.split()[1]
            if line.startswith('HEAD'):
                prev_head = line.split()[1]
            if line.startswith('branch'):
                branch = line.split()[1]
                if branch.startswith('refs/heads/'):
                    branch = branch[len('refs/heads/'):]
                    worktrees.append({
                        'path': prev_path,
                        'head': prev_head,
                        'branch': branch,
                    })
        return worktrees

    def list_worktree_branches(self):
        return list(map(lambda worktree: worktree['branch'], self.list_worktrees()))

    def delete_worktree(self, branch):
        for worktree in self.list_worktrees():
            if worktree['branch'] == branch:
                if os.path.isdir(worktree['path']):
                    shutil.rmtree(worktree['path'])
        self.prune_worktree()

    def remove_worktree(self, path):
        self.check_output('git', 'worktree', 'remove', path)

    def prune_worktree(self):
        self.check_output('git', 'worktree', 'prune')

    def list_local_branches(self):
        branches = []
        for line in self.check_output('git', 'show-ref', '--heads').splitlines():
            branch = line.strip().split()[1]
            if branch.startswith('refs/heads/'):
                branch = branch[len('refs/heads/'):]
                if not branch.startswith('__'):
                    branches.append(branch)
        return branches

    def list_control_branches(self):
        branches = []
        for line in self.check_output('git', 'show-ref', '--heads').splitlines():
            branch = line.strip().split()[1]
            if branch.startswith('refs/heads/'):
                branch = branch[len('refs/heads/'):]
                if branch.startswith('__'):
                    branches.append(branch)
        return branches

    def list_remote_branches(self):
        return [ref['branch'] for ref in self.ls_remotes()]

    def list_all_branches(self):
        local_branches = self.list_local_branches()
        remote_branches = self.list_remote_branches()
        return remote_branches + [branch for branch in local_branches if branch not in remote_branches]

    def get_current_branch(self):
        branch = self.check_output('git', 'rev-parse', '--abbrev-ref', 'HEAD')
        if branch == 'HEAD':
            return None
        return branch

    def create_branch(self, branch, start_point):
        self.check_output('git', 'branch', '--quiet', branch, start_point)

    def delete_branch(self, branch):
        self.check_output('git', 'branch', '--quiet', '-D', branch)

    def fetch(self, refspecs):
        self.check_output('git', 'fetch', '--quiet', self.remote, *refspecs)

    def add_all(self):
        self.check_output('git', 'add', '--all')

    def commit(self, msg):
        if isinstance(msg, str):
            msg = [msg]
        msg_args = []
        for m in msg:
            msg_args.append('-m')
            msg_args.append(m)

        self.check_output('git', 'commit', '--quiet', '--allow-empty', *msg_args)
        return self.rev_parse('HEAD')

    def push(self, refspec):
        self.check_output('git', 'push', '--quiet', self.remote, refspec)

    def ls_remotes(self):
        refs = []
        for line in self.check_output('git', 'ls-remote', '--quiet').splitlines():
            oid, name = line.split()
            if name.startswith('refs/heads/'):
                branch = name[len('refs/heads/'):]
                refs.append({
                    'oid': oid,
                    'branch': branch,
                })
        return refs

    def diff_files(self, src, dst):
        return self.check_output('git', 'diff', '--name-only', src, dst).splitlines()


class ShellRepository(BaseRepository):
    def __init__(self, path):
        self.path = path
        self.remote = self.remotes()[0]

    def rev_parse(self, ref):
        return self.check_output('git', 'rev-parse', '--quiet', ref)

    def status(self):
        deltas = []
        for line in self.check_output('git', 'status', '--porcelain').splitlines():
            st, path = line.split(maxsplit=1)
            deltas.append({
                'status': st,
                'path': path,
            })
        return deltas


class Pygit2Repository(BaseRepository):
    def __init__(self, path):
        self.repo = pygit2.Repository(path)
        self.path = path
        self.remote = list(self.repo.remotes)[0].name

    def status(self):
        deltas = []
        for path, st in self.repo.status().items():
            if st not in [pygit2.GIT_STATUS_CURRENT, pygit2.GIT_STATUS_IGNORED]:
                deltas.append({
                    'status': st,
                    'path': path,
                })
        return deltas

    def rev_parse(self, ref):
        return str(self.repo.lookup_reference_dwim(ref).target)


def _confirm(message, default=False):
    while True:
        if default:
            s = input(message + '  [Y/n]')
        else:
            s = input(message + '  [y/N]')
        s = s.lower()

        if s and s not in ['y', 'n']:
            print('Invalid option')
            continue

        if not s:
            return default
        if s == 'y':
            return True
        if s == 'n':
            return False


def _clone_repository(repo_url, path, tmp_path):
    subprocess.check_output(['git', 'init', tmp_path])
    subprocess.check_output(['git', 'remote', 'add', 'origin', repo_url], cwd=tmp_path)
    subprocess.check_output(['git', 'checkout', '-b', '__empty', '--quiet'], cwd=tmp_path)
    subprocess.check_output(['git', 'commit', '--allow-empty', '-m', 'Empty'], cwd=tmp_path)
    os.rename(tmp_path, path)


def _get_branch(path=os.getcwd()):
    basedir = _get_basedir()
    branch = os.path.relpath(path, basedir)
    if not branch.strip('./'):
        return None
    repo = _get_repo(path)
    return repo.get_current_branch()


def get_branch():
    env_override = os.getenv('EXPMONKEY_BRANCH')
    if env_override:
        return env_override
    branch = _get_branch()
    _check_branch(branch, in_worktree=True, in_branch=True)
    return branch


def get_repo_name():
    env_override = os.getenv('EXPMONKEY_REPO_NAME')
    if env_override:
        return env_override
    repo = _get_repo()
    return repo.get_name()


def _list_checked_out_branches():
    repo = _get_repo()
    basedir = _get_basedir()
    worktrees = repo.list_worktrees()

    basedir = os.path.abspath(basedir)
    branches = []
    for worktree in worktrees:
        if os.path.join(basedir, worktree['branch']) == worktree['path']:
            branches.append(worktree['branch'])
    return branches


def _is_git_repo(path):
    return os.path.exists(os.path.join(path, '.git'))


def _check_branch(branch, in_worktree=None, in_branch=None):
    repo = _get_repo()
    basedir = _get_basedir()
    worktrees = repo.list_worktrees()

    basedir = os.path.abspath(basedir)
    found_in_worktree = False
    for worktree in worktrees:
        if worktree['branch'] == branch:
            if os.path.join(basedir, worktree['branch']) == worktree['path']:
                found_in_worktree = True

    if in_worktree is True and not found_in_worktree:
        _die('Branch "{}" not found in worktree'.format(branch))
    if in_worktree is False and found_in_worktree:
        _die('Branch "{}" already exists in worktree'.format(branch))

    for worktree in worktrees:
        if worktree['branch'] == branch:
            if not os.path.join(basedir, worktree['branch']) == worktree['path']:
                _die('Inconsistency between worktree branch and path, '
                     'branch: "{}", path: "{}"'.format(worktree['branch'], worktree['path']))

    local_branches = repo.list_local_branches()
    if in_branch is True and branch not in local_branches:
        _die('Branch "{}" not found in local branches'.format(branch))
    if in_branch is False and branch in local_branches:
        _die('Branch "{}" already exists in local branches'.format(branch))

    if found_in_worktree:
        if branch not in local_branches:
            _die('Inconsistency between worktree and local branch, '
                 'branch "{}" not found in local branches'.format(branch))

        if not _is_git_repo(os.path.join(basedir, branch)):
            _die('Inconsistency between worktree and local directory, '
                 'branch "{}" not found in local directory'.format(branch))

        current_branch = _get_repo(branch).get_current_branch()
        if current_branch != branch:
            _die('Inconsistency between worktree and branch in directory, '
                 'branch "{}" not the same with branch in directory "{}"'.format(branch, current_branch))

    elif in_worktree is False:
        if _is_git_repo(os.path.join(basedir, branch)):
            _die('Directory "{}" already exists'.format(os.path.join(basedir, branch)))


init_script = '''
function em() {
    _EM_OUTPUT_NEW_PWD=$(mktemp)

    _EM_OUTPUT_NEW_PWD=$_EM_OUTPUT_NEW_PWD expmonkey $@
    if [[ $? -eq 0 ]]; then
        _EM_NEW_PWD=$(cat $_EM_OUTPUT_NEW_PWD)
        if [[ $_EM_NEW_PWD != "" && $_EM_NEW_PWD != $PWD ]]; then
            cd $_EM_NEW_PWD
        fi
    fi

    rm -rf $_EM_OUTPUT_NEW_PWD
}

if [[ -n "$BASH" || $0 == "-bash" ]]; then
    eval "$(register-python-argcomplete em)"
    eval "$(register-python-argcomplete expmonkey)"
fi
if [[ -n "$ZSH" || -n "$ZSH_NAME" || $0 == "-zsh" || $0 == "zsh" ]]; then
    autoload -U bashcompinit
    bashcompinit
    eval "$(register-python-argcomplete em)"
    eval "$(register-python-argcomplete expmonkey)"
fi

export EXPMONKEY_INITED=1
'''


def print_init_script():
    print(init_script)


main_help = '''
Expmonkey

A lightweight experiment management tool based on git worktree

Usage:

mkdir my_exp_dir && cd my_exp_dir

em init <repo url>

em ls -as

em co <exp name>
'''

cp_help = '''
Copy an experiment

Usage:

em cp <Tab> <target-branch-name> # auto complete local branches

em cp .r<Tab> <target-branch-name> # auto complete all branches

em cp <base-branch-name> .<Tab> # complete as base-branch-name

em cp .<Tab> <target-branch-name> # complete as current-branch-name

em cp . <target-branch-name> # copy current branch
'''

co_help = '''
Checkout a remote experiment to local

Usage:

em co <Tab> # auto complete local branches

em co .r<Tab> # auto complete all branches

em co <branch-name> # checkout branch
'''

rm_help = '''
Delete an experiment

Usage:

em rm <branch-name> # remove branch

em rm . # remove current branch

em rm .<Tab> # remove current branch
'''

ls_help = '''
List experiments

Usage:

em ls # list local branches

em ls <filter><Tab> # list local branches with filter

em ls -as # list remote branches with status
'''

cd_help = '''
Goto an experiment workdir

Usage:

em cd <branch-name>

em cd <Tab>

em cd .<Tab>

em cd <filter><Tab>
'''

diff_help = '''
Diff two experiments

Usage:

em diff . <another-exp-name>

em diff .<Tab> <another-exp-name>

em diff .<Tab> .<Tab>

em diff <exp-name1> <exp-name2>

em diff <filter><Tab> <exp-name2>
'''


def main():
    parser = argparse.ArgumentParser(description=main_help)
    subparsers = parser.add_subparsers()

    clone_parser = subparsers.add_parser('clone')
    clone_parser.add_argument('repo', type=str)
    clone_parser.set_defaults(func=clone)

    init_parser = subparsers.add_parser('init')
    init_parser.add_argument('repo', nargs='?', type=str)
    init_parser.set_defaults(func=init)

    empty_parser = subparsers.add_parser('empty')
    empty_parser.add_argument('branch', type=str)
    empty_parser.set_defaults(func=empty)

    cp_parser = subparsers.add_parser('cp', help=cp_help)
    cp_parser.add_argument('src', type=str).completer = _complete_cp_src
    cp_parser.add_argument('dst', type=str).completer = _complete_cp_dst
    cp_parser.set_defaults(func=cp)

    mv_parser = subparsers.add_parser('mv', help='Rename an experiment')
    mv_parser.add_argument('src', type=str).completer = _complete_mv_src
    mv_parser.add_argument('dst', type=str).completer = _complete_mv_dst
    mv_parser.set_defaults(func=mv)

    co_parser = subparsers.add_parser('co', help=co_help)
    co_parser.add_argument('branch', type=str).completer = _complete_co_branch
    co_parser.set_defaults(func=co)

    rm_parser = subparsers.add_parser('rm', help=rm_help)
    rm_parser.add_argument('branch', type=str).completer = _complete_rm_branch
    rm_parser.add_argument('-y', '--yes', action='store_true')
    rm_parser.set_defaults(func=rm)

    ls_parser = subparsers.add_parser('ls', help=ls_help)
    ls_parser.add_argument('-a', '--all', dest='list_all', action='store_true')
    ls_parser.add_argument('-s', '--status', dest='show_status', action='store_true')
    ls_parser.add_argument('branch_filter', type=str, nargs='?')
    ls_parser.set_defaults(func=ls)

    cm_parser = subparsers.add_parser('cm', help='Commit an experiment')
    cm_parser.add_argument('-m', '--message', type=str, required=False)
    cm_parser.set_defaults(func=cm)

    push_parser = subparsers.add_parser('push', help='Push an experiment to remote')
    push_parser.add_argument('-m', '--message', type=str, required=False)
    push_parser.set_defaults(func=push)

    cd_parser = subparsers.add_parser('cd', help=cd_help)
    cd_parser.add_argument('branch', type=str, nargs='?').completer = _complete_cd_branch
    cd_parser.set_defaults(func=cd)

    diff_parser = subparsers.add_parser('diff', help=diff_help)
    diff_parser.add_argument('src', type=str).completer = _complete_diff_src
    diff_parser.add_argument('dst', type=str).completer = _complete_diff_dst
    diff_parser.set_defaults(func=diff)

    argcomplete.autocomplete(parser, always_complete_options=False, validator=lambda _1, _2: True)
    args = parser.parse_args()
    args.func(args)


def cli():
    if not os.getenv('EXPMONKEY_INITED'):
        print(colored.stylize('''Expmonkey autocompletion is not enabled
Please add "source em-init.sh" to your ~/.bashrc or ~/.zshrc
You may want to install fzf for better experience''', colored.fg('red')))
        raise RuntimeError('Expmonkey is not inited')
    main()


def clone(args):
    repo = args.repo
    repo_path = './' + os.path.basename(repo)
    if repo_path.endswith('.git'):
        repo_path = repo_path[:-4]
    if os.path.exists(repo_path):
        raise RuntimeError('Path <{}> exists'.format(repo_path))
    em_path = os.path.join(repo_path, '.em', 'repo')
    os.makedirs(em_path + '.tmp')
    _clone_repository(repo, em_path, tempfile.mkdtemp(dir=em_path + '.tmp'))

    print('Successfully cloned repo: {}'.format(repo))
    _cd(repo_path)


def init(args):
    repo = args.repo
    if os.path.exists('.em/repo'):
        _die('em repo already inited!')

    if repo is None:
        git_path = _get_parent_git_path()
        if git_path is None:
            _die('No git repo found, please specify repo path')
        repo = git_path
    if _is_git_repo(repo):
        os.makedirs('.em', exist_ok=True)
        with open('.em/repo', 'w') as f:
            f.write(os.path.abspath(repo))
    else:
        os.makedirs('.em/repo.tmp', exist_ok=True)
        _clone_repository(repo, '.em/repo', tempfile.mkdtemp(dir='.em/repo.tmp'))

    print('Successfully inited repo: {}'.format(repo))


def empty(args):
    branch = args.branch

    _check_branch(branch, in_worktree=False, in_branch=False)

    repo = _get_repo()
    basedir = _get_basedir()
    if '__empty' in repo.list_control_branches():
        repo.create_branch(branch, '__empty')
        repo.add_worktree(os.path.join(basedir, branch), branch)
    else:
        repo.add_worktree_with_first_commit_detached(os.path.join(basedir, branch))

        repo = _get_repo(branch)
        repo.checkout_orphan(branch)
        repo.commit('Init "{}"'.format(branch))

    _cd(os.path.join(basedir, branch))

    print('Successfully created empty branch: {}'.format(branch))


def _filter_items_with_incomplete(incomplete, items):
    pattern = re.compile(incomplete)
    return list(filter(lambda item: pattern.search(item), items))


def _complete_branches_with_filter(branches, incomplete):
    items = _filter_items_with_incomplete(incomplete, branches)
    return _fzf_select(items)


def _complete_local_branches(prefix):
    repo = _get_repo()
    return _complete_branches_with_filter(repo.list_local_branches(), prefix)


def _complete_all_branches(incomplete):
    repo = _get_repo()
    return _complete_branches_with_filter(repo.list_all_branches(), incomplete)


def _complete_local_branches_not_checked_out(incomplete):
    repo = _get_repo()
    local_branches = repo.list_local_branches()
    checked_out_branches = set(_list_checked_out_branches())
    branches = [branch for branch in local_branches if branch not in checked_out_branches]
    return _complete_branches_with_filter(branches, incomplete)


def _complete_all_branches_not_checked_out(incomplete):
    repo = _get_repo()
    all_branches = repo.list_all_branches()
    checked_out_branches = set(_list_checked_out_branches())
    branches = [branch for branch in all_branches if branch not in checked_out_branches]
    return _complete_branches_with_filter(branches, incomplete)


def _complete_co_branch(prefix, parsed_args, **kwargs):
    if prefix == '.r':
        return _complete_all_branches_not_checked_out('')
    else:
        return _complete_local_branches_not_checked_out(prefix)


def _complete_cp_src(prefix, parsed_args, **kwargs):
    branch = _get_branch()
    if prefix == '.' and branch is not None:
        return [branch]
    elif prefix == '.r':
        return _complete_all_branches('')
    return _complete_local_branches(prefix)


def _complete_cp_dst(prefix, parsed_args, **kwargs):
    if prefix == '.':
        src = parsed_args.src
        if src == '.':
            branch = _get_branch()
            if branch:
                return [branch]
        return [src]
    else:
        return []


def _complete_mv_src(prefix, parsed_args, **kwargs):
    branch = _get_branch()
    if prefix == '.' and branch is not None:
        return [branch]
    return _complete_local_branches(prefix)


def _complete_mv_dst(prefix, parsed_args, **kwargs):
    if prefix == '.':
        src = parsed_args.src
        if src == '.':
            branch = _get_branch()
            if branch:
                return [branch]
        return [src]
    else:
        return []


def _complete_rm_branch(prefix, parsed_args, **kwargs):
    branch = _get_branch()
    if prefix == '.' and branch is not None:
        return [branch]
    return _complete_local_branches(prefix)


def _complete_cd_branch(prefix, parsed_args, **kwargs):
    if prefix == '.':
        branch = _get_branch()
        if branch:
            return [branch]
    return _complete_branches_with_filter(_list_checked_out_branches(), prefix)


def _complete_diff_src(prefix, parsed_args, **kwargs):
    if prefix == '.':
        branch = _get_branch()
        if branch:
            return [branch]
    return _complete_branches_with_filter(_list_checked_out_branches(), prefix)


def _complete_diff_dst(prefix, parsed_args, **kwargs):
    if prefix == '.':
        src = parsed_args.src
        if src == '.':
            branch = _get_branch()
            if branch:
                return [branch]
        return [src]
    return _complete_branches_with_filter(_list_checked_out_branches(), prefix)


def _fzf_select(items):
    if len(items) > 0 and shutil.which('fzf-tmux'):
        try:
            selected_item = subprocess.check_output(
                ['fzf-tmux -d 20'], input='\n'.join(items),
                shell=True, universal_newlines=True,
            ).strip()
        except (subprocess.CalledProcessError, KeyboardInterrupt):
            return []
        return [selected_item]
    else:
        return items


def cp(args):
    src = args.src
    dst = args.dst

    if src == '.':
        branch = _get_branch()
        if branch is None:
            _die('Not in a branch, please specific branch name')
        else:
            src = branch

    assert src[0].isalpha() or src[0].isdigit()
    assert dst[0].isalpha() or dst[0].isdigit()

    basedir = _get_basedir()
    _cp(src, dst)
    _cd(os.path.join(basedir, dst))


def _cp(src, dst):
    basedir = _get_basedir()
    repo = _get_repo()

    checked_out_branches = _list_checked_out_branches()

    if src in checked_out_branches:
        _check_branch(src, in_worktree=True, in_branch=True)
        _check_branch(dst, in_worktree=False, in_branch=False)
        commit_id = _commit(src)
        repo.create_branch(dst, commit_id)
    elif src in repo.list_local_branches():
        _check_branch(src, in_worktree=False, in_branch=True)
        if src != dst:
            _check_branch(dst, in_worktree=False, in_branch=False)
            repo.create_branch(dst, src)
    elif src in repo.list_remote_branches():
        _check_branch(src, in_worktree=False, in_branch=False)
        _check_branch(dst, in_worktree=False, in_branch=False)
        repo.fetch(['refs/heads/{}:refs/heads/{}'.format(src, dst)])
    else:
        _die('Branch "{}" not found'.format(src))

    repo.add_worktree(os.path.join(basedir, dst), dst)

    if src == dst:
        print('Successfully checked out "{}"'.format(src))
    else:
        _commit_after_checkout(src, dst)
        print('Successfully checked out "{}" to "{}"'.format(src, dst))


def mv(args):
    src = args.src
    dst = args.dst

    branch = _get_branch()

    if src == '.':
        if branch is None:
            _die('Not in a branch, please specific branch name')
        else:
            src = branch

    assert src[0].isalpha() or src[0].isdigit()
    assert dst[0].isalpha() or dst[0].isdigit()

    basedir = _get_basedir()
    repo = _get_repo()

    _check_branch(src, in_worktree=True, in_branch=True)
    _check_branch(dst, in_worktree=False, in_branch=False)

    commit_id = _commit(src)
    repo.create_branch(dst, commit_id)
    repo.add_worktree(os.path.join(basedir, dst), dst)

    repo.delete_worktree(src)
    repo.delete_branch(src)

    _commit_after_rename(src, dst)
    print('Successfully renamed "{}" to "{}"'.format(src, dst))
    if branch == src:
        _cd(os.path.join(basedir, dst))


def _commit_after_checkout(src, dst):
    repo = _get_repo(dst)
    repo.commit('Checkout "{}" to "{}"'.format(src, dst))


def _commit_after_rename(src, dst):
    repo = _get_repo(dst)
    repo.commit('Rename "{}" to "{}"'.format(src, dst))


def co(args):
    branch = args.branch

    basedir = _get_basedir()
    _cp(branch, branch)
    _cd(os.path.join(basedir, branch))


def rm(args):
    branch = args.branch
    yes = args.yes

    basedir = _get_basedir()
    repo = _get_repo()
    cur_branch = _get_branch()

    if branch == '.':
        if cur_branch is not None:
            branch = cur_branch
        else:
            _die('Not in a branch, please specific branch name')

    if not yes:
        confirm_remove = _confirm('Are you sure you want to remove branch "{}"?'.format(branch))
        if not confirm_remove:
            print('Aborted!')
            return

    assert branch[0].isalpha() or branch[0].isdigit()

    removed_any = False

    if os.path.isdir(os.path.join(basedir, branch)):
        shutil.rmtree(os.path.join(basedir, branch))
        print('Removed expdir "{}"'.format(branch))
        removed_any = True

    if branch in repo.list_worktree_branches():
        repo.delete_worktree(branch)
        print('Removed worktree "{}"'.format(branch))
        removed_any = True

    if branch in repo.list_local_branches():
        repo.delete_branch(branch)
        print('Removed branch "{}"'.format(branch))
        removed_any = True

    if not removed_any:
        print('Branch "{}" not removed'.format(branch))

    if cur_branch == branch:
        _cd(basedir)


def _checkout(branch):
    _cp(branch, branch)
    _cd(os.path.join(_get_basedir(), branch))


class BranchPrinter(object):
    def __init__(self, cur_branch):
        self.cur_branch = cur_branch
        self.status_to_postfix = {
            'remote': '  (remote)',
            'not checked out': '  (not checked out)',
            'not pushed': '  (not pushed)',
            'modified': '  (modified)',
        }
        self.status_to_color = {
            'remote': 'red',
            'not checked out': 'white',
            'not pushed': 'blue',
            'modified': 'yellow',
        }

    def print(self, branch, status=None):
        if status != 'remote' and branch == self.cur_branch:
            prefix = '* '
        else:
            prefix = '  '

        color = self.status_to_color.get(status)
        text = prefix + branch + self.status_to_postfix.get(status, '')
        if color is not None:
            print(colored.stylize(text, colored.fg(color)))
        else:
            print(text)


def ls(args):
    list_all = args.list_all
    show_status = args.show_status
    branch_filter = args.branch_filter

    repo = _get_repo()
    branch_printer = BranchPrinter(_get_branch())

    remote_branch_name_to_oid = {}
    remote_branches = []
    if list_all or show_status:
        remote_refs = repo.ls_remotes()
        for ref in remote_refs:
            remote_branches.append(ref['branch'])
            remote_branch_name_to_oid[ref['branch']] = ref['oid']

    local_branches = repo.list_local_branches()
    checkout_branches = _list_checked_out_branches()
    if branch_filter is not None:
        local_branches = _filter_items_with_incomplete(branch_filter, local_branches)
        checkout_branches = _filter_items_with_incomplete(branch_filter, checkout_branches)
        remote_branches = _filter_items_with_incomplete(branch_filter, remote_branches)
    not_checkout_branches = [branch for branch in local_branches if branch not in checkout_branches]

    if list_all:
        for branch_name in remote_branches:
            if branch_name not in local_branches:
                branch_printer.print(branch_name, 'remote')

    for branch in not_checkout_branches:
        branch_printer.print(branch, 'not checked out')

    if not show_status:
        for branch in checkout_branches:
            branch_printer.print(branch)
    else:
        for branch in checkout_branches:
            repo = _get_repo(branch)
            local_commit_id = repo.rev_parse('refs/heads/{}'.format(branch))

            deltas = repo.status()

            remote_commit_id = remote_branch_name_to_oid.get(branch)

            local_modified = len(deltas)
            commit_pushed = remote_commit_id == local_commit_id

            if not local_modified and not commit_pushed:
                branch_printer.print(branch, 'not pushed')
            elif local_modified:
                branch_printer.print(branch, 'modified')
            else:
                branch_printer.print(branch)


def cm(args):
    message = args.message

    branch = _get_branch()
    if branch is None:
        _die('Not in a branch')
    _commit(branch, message)

    print('Successfully commited "{}"!'.format(branch))


def _commit(branch, message=None):
    repo = _get_repo(branch)
    head_commit_id = repo.rev_parse('refs/heads/{}'.format(branch))

    repo.add_all()
    deltas = repo.status()

    if len(deltas) > 0:
        if message:
            messages = [message]
        else:
            messages = ['Update "{}"'.format(branch)]
        return repo.commit(messages)
    else:
        return head_commit_id


def push(args):
    message = args.message

    branch = _get_branch()
    if branch is None:
        _die('Not in a branch')
    repo = _get_repo(branch)

    commit_id = _commit(branch, message)

    remote_commit_id = None
    for ref in repo.ls_remotes():
        if ref['branch'] == branch:
            remote_commit_id = ref['oid']

    if commit_id == remote_commit_id:
        print('Remote already up-to-date!')
    else:
        repo.push('refs/heads/{}:refs/heads/{}'.format(branch, branch))
        print('Successfully pushed "{}"!'.format(branch))


def _cd(new_pwd):
    output_path = os.getenv('_EM_OUTPUT_NEW_PWD')
    if output_path:
        with open(output_path, 'w') as f:
            f.write(new_pwd)


def cd(args):
    branch = args.branch

    basedir = _get_basedir()
    if branch is None:
        _cd(basedir)
    else:
        _check_branch(branch, in_worktree=True, in_branch=True)
        path = os.path.join(basedir, branch)
        _cd(path)


def diff(args):
    src = args.src
    dst = args.dst

    basedir = _get_basedir()
    branch = _get_branch()
    if src == '.' and branch is not None:
        src = branch
    if dst == '.' and branch is not None:
        dst = branch

    repo = _get_repo()
    src_repo = _get_repo(src)
    dst_repo = _get_repo(dst)
    src_changes = [delta['path'] for delta in src_repo.status()]
    dst_changes = [delta['path'] for delta in dst_repo.status()]

    diff_files = repo.diff_files(src, dst)
    diff_files = list(sorted(set(src_changes + dst_changes + diff_files)))
    for index, filename in enumerate(diff_files):
        show_diff_file = _confirm(
            '[{}/{}] Vimdiff file "{}"?'.format(index + 1, len(diff_files), filename),
            default=True
        )
        if show_diff_file:
            src_file = os.path.join(src, filename)
            dst_file = os.path.join(dst, filename)
            subprocess.check_call(
                ['vimdiff', src_file, dst_file],
                stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, cwd=basedir
            )


if __name__ == '__main__':
    main()
