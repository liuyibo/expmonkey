# 🐒 ExpMonkey: Unleash Your Experiments with Git Magic! 🍌

Welcome to ExpMonkey, the nimble experiment management tool that transforms the way you handle your research and development projects. By harnessing the power of git worktrees, ExpMonkey offers a command-line sanctuary for your branches, treating each one as a unique adventure in the jungle of innovation. Ready to swing from experiment to experiment with the grace of a seasoned primate? 🌿 Let's dive in!

## 🌟 Spotlight Features

Embark on a journey with ExpMonkey and discover a world where managing multiple experiments feels like a walk in the park:

- 🍌 **Parallel Universe Workflow**: Each git branch becomes an alternate reality, with its own directory to tinker in. Work on multiple fronts without ever tangling your vines.

- 🍌 **Jungle Gym Navigation**: Leap between branches with a simple command. It's like having a map of the entire jungle at your fingertips.

- 🍌 **Git Sorcery Enhanced**: ExpMonkey casts a spell on the standard git rituals, streamlining branch antics and conjuring up tools specifically for the experimental alchemist.

- 🍌 **Branch Alchemy**: Transmute, clone, and compare experiments with the dexterity of a monkey's tail, all thanks to ExpMonkey's clever branch wizardry.

- 🍌 **Chant Autocompletion**: Invoke the spirits of speed and precision with our autocompletion incantations, banishing typos to the shadow realm.

- 🍌 **Fuzzy Oracle Integration**: Consult the `fzf` oracle for visions of branches and commits, selecting your path with the clarity of a shaman's trance.

## 📜 Prerequisites

Before you embark on this quest, ensure you have the following relics:

- Python 3.x
- Git
- Optional: `fzf` for an enhanced soothsaying interface

## 🛠 Installation: Summoning ExpMonkey

Invoke ExpMonkey into your realm with these ancient incantations:

1. Conjure the Python package:
```shell
pip3 install expmonkey
```

2. (Optional) Weave `em-init-script` into your shell's tapestry for autocompletion and arcane abilities:
```bash
echo 'source <(em-init-script)' >> ~/.bashrc
```

3. (Optional) Summon `fzf` for a mystical user experience:
``` bash
git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
~/.fzf/install
```
Consult the [fzf grimoire](https://github.com/junegunn/fzf#installation) for more details.

## 📗 Grimoire of Usage

Harness the power of ExpMonkey as you navigate the treacherous terrain of experiments:

### 🌱 Sprout a New Repository
```bash
em clone git@github.com:megvii-research/RevCol.git
```

### 📜 Parchment of Experiments
```bash
em ls -as
```

### 🌿 Branch Out with Forks
```bash
em cp <base-branch-name> <new-branch-name>
```

### 🚀 Propel Your New Creation
```bash
em cd <new-branch-name>
# Enchant with your changes
em push
```

## 🧙‍♂️ Command Incantations

### The Dot Trick 🐒🐒🐒
ExpMonkey's eyes gleam when spotting a `.`. Behold the magic:

### 🕳️ Conjure from the Void
Create an empty experiment:
``` shell
em empty <branch-name>
```

### 🔍 Scrying List
Peer into the branches:
``` shell
em ls # unveil local branches
em ls <filter-regex> # filter through local branches
em ls -as # reveal remote branches with status
```

`em ls -as` illuminates branches with enchanted hues:

|  Color   | Meaning  |
|  ----  | ----  |
| Red  | Distant Lands (Remote) |
| White  | Uncharted (Not Checked out) |
| Blue  | Whispering Winds (Not Pushed) |
| Yellow  | Altered Realms (Modified) |
| Normal  | Harmony (Clean) |

`em ls` is a swift spell, while `em ls -as` consults distant spirits, requiring more time.

### 🌟 Starry Copy
Craft a new branch from existing strands of fate:
``` shell
em cp <Tab> <target-branch-name> # divine local branches
em cp .r<Tab> <target-branch-name> # divine all branches
em cp <base-branch-name> .<Tab> # scribe as base-branch-name
em cp .<Tab> <target-branch-name> # scribe as current-branch-name
em cp . <target-branch-name> # duplicate current branch
```

### 🌀 Portal to Another Branch
Step into another experiment:
``` shell
em co <Tab> # divine local branches
em co .r<Tab> # divine all branches
em co <branch-name> # step through the portal
```

### 🗑️ Banish an Experiment
Cast away an unwanted branch:
``` shell
em rm <branch-name> # banish branch
em rm . # banish current branch
```

### 🌌 Push to the Cosmos
Send your experiment into the vast unknown:
``` shell
em push # launch it skyward
```

### 📛 Rename Your Destiny
Alter the name of your journey:
``` shell
em mv <current-branch-name> <target-branch-name>
```

### 🔮 Gaze into Differences
Witness the divergence between realms:
``` shell
em diff <branch1> <branch2>
```

## 📜 License

This project is a tome of knowledge, open to all seekers under the [MIT License](LICENSE).