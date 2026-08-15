# Findability in the Anthropic plugin directory

Measured 2026-08-15 by reading the catalog, the directory pages and the network traffic behind them.

## The finding that decides everything else

**Browsing is closed to a new plugin, and no amount of naming fixes that.** The directory at `claude.com/plugins` sorts by install count. The top entry carries 1,134,112 installs. A new plugin enters at zero, which puts it below every one of the 2,281 catalog entries that has ever been installed.

The browsable directory is four pages. The catalog is 2,281 plugins. Most of the catalog cannot be reached by browsing at all, in any order, by anybody.

So findability here is a search problem and a referral problem. It is not a listing problem.

## What the surface actually is

The GitHub repository is a read-only nightly mirror and says so. The real surface is the web directory, and it serves Claude Cowork as well as Claude Code, which makes the audience far larger than the repository's 349 stars suggest. An earlier estimate used those stars and was wrong by orders of magnitude.

Submission goes through `clau.de/plugin-directory-submission`, not a pull request. Pull requests against the mirror are closed automatically.

Installation is by exact name: `claude plugin install <name>@claude-community`. The name is the address.

## Every lever available, and there are only two

A catalog entry carries four fields: `name`, `description`, `source`, `homepage`. There is no keywords field, no tags field, and no category field in the schema. Of 2,281 entries, 156 carry a stray `category` key, so it is not a facet anyone can filter on.

The directory's only filter is "Works with", offering Cowork and Claude Code. There are no topic categories, no ratings, and no recently-added section.

**That leaves the name and the description.** Everything below follows from that.

### The name

It is the install command, the sort key of the underlying catalog, and the first thing a search matches. `honest-skills` says nothing about what the plugin does. Someone searching for what we offer would type "prose", "writing", "clarity", "commit", "code quality" or "lint", and none of those appear in it.

The counter-argument is real: the name is also the brand, it is already published at v0.4.0, and renaming breaks every existing install command and every link. A name is worth choosing carefully once and then leaving alone.

### The description

The only field with room to carry search terms, and the only one that can be revised freely. Card display truncates it to roughly 150 characters, so it has two jobs that pull apart: the first 150 characters have to sell, and the remainder has to be findable.

Rival counts for terms a person would actually type, across the 2,281 entries:

| Query | Rivals |
|---|---|
| sitrep | 1 |
| technical debt | 2 |
| readability | 3 |
| root cause | 10 |
| clarity | 10 |
| prose | 11 |
| slop | 12 |
| code quality | 23 |
| lint | 30 |
| evidence | 58 |
| writing | 90 |
| quality | 121 |
| review | 314 |

The useful terms are the ones almost nobody has claimed. "sitrep" returns one rival, "readability" three, "root cause" ten. Those are the terms worth owning, and the current description already carries some of them by accident rather than by design.

"quality" and "review" are unwinnable and not worth a word.

## What to do, in order of return

1. **Do not compete on browse.** It is decided by installs and installs come from elsewhere. Treat the directory as a place people arrive at, not a place they discover.
2. **Write the description for the uncontested terms.** "sitrep", "root cause", "readability", "clarity", "prose", "commit message". Do it honestly: every one of those is something the plugin genuinely does, so this costs nothing in accuracy.
3. **Bring installs from outside.** awesome-claude-code, where a two-entry category exists, is the cheapest source. Every install there raises the directory rank, which is the only thing that opens browse.
4. **Leave the name alone unless renaming happens before any real install base exists.** The window for that closes as soon as the plugin is listed.

## What this argument cannot see

Whether the directory's search matches the description at all, or only the name. Nothing observable from outside settles it, and the whole of point 2 depends on it. Testing it means being listed first, which makes the test unavailable until after the decision it should inform.

Install counts are also the directory's own numbers with no method attached. A count could be installs, unique installers, or attempts, and the ranking those produce differ.
