# -*- coding: utf-8 -*-

import sys
import os
from collections import namedtuple
from datetime import datetime
from html.parser import HTMLParser
from html import unescape
from hashlib import md5
from configparser import NoOptionError, RawConfigParser
import threading
# noinspection PyCompatibility
import regex
import subprocess as sp
import platform
from helpers import log
if 'windows' in platform.platform().lower():
    # noinspection PyPep8Naming
    from classes._Git_Windows import git, GitError
else:
    from sh.contrib import git


# Python 3.5.0 is the bare minimum needed to run SmokeDetector
if tuple(int(x) for x in platform.python_version_tuple()) < (3, 5, 0):
    raise RuntimeError("SmokeDetector requires Python version 3.5 or newer to run.")

# However, we're considering the potential to deprecate 3.5 so we need to prepare
# from this with a warning in the logs about it.
if tuple(int(x) for x in platform.python_version_tuple()) < (3, 6, 0):
    log('warning', 'SmokeDetector may remove support for versions of Python before '
                   '3.6.0 in the future, please consider upgrading your instances of '
                   'SmokeDetector to use Python 3.6 or newer.')

CommitInfo = namedtuple('CommitInfo', ['id', 'id_full', 'author', 'message'])

git_url = git.config("--get", "remote.origin.url").strip()
git_url_split = git_url.split("/")
git_user_repo = "Charcoal-SE/SmokeDetector"
if git_url[0:19] == "https://github.com/":
    git_user_repo = "{}/{}".format(git_url_split[3], git_url_split[4][0:-4])


def git_commit_info():
    try:
        data = sp.check_output(['git', 'rev-list', '-1', '--pretty=%H%n%an%n%s', 'HEAD'],
                               stderr=sp.STDOUT).decode('utf-8')
    except sp.CalledProcessError as e:
        raise OSError("Git error:\n" + e.output) from e
    _, full_id, author, message = data.strip().split("\n")
    return CommitInfo(id=full_id[:7], id_full=full_id, author=author, message=message)


def git_ref():
    git_cp = sp.run(['git', 'symbolic-ref', '--short', '-q', 'HEAD'], stdout=sp.PIPE)
    return git_cp.stdout.decode("utf-8").strip()  # not on branch = empty output


# We don't need strip_escape_chars() anymore, see commit message of 1931d30804a675df07887ce0466e558167feae57


# noinspection PyClassHasNoInit,PyDeprecation,PyUnresolvedReferences
class GlobalVars:
    on_windows = 'windows' in platform.platform().lower()

    false_positives = []
    whitelisted_users = set()
    blacklisted_users = dict()
    blacklisted_usernames = []
    blacklisted_websites = []
    blacklisted_numbers = []
    watched_numbers = []
    blacklisted_numbers_normalized = None
    watched_numbers_normalized = None
    bad_keywords = []
    watched_keywords = {}
    ignored_posts = []
    auto_ignored_posts = []
    startup_utc_date = datetime.utcnow()
    startup_utc = startup_utc_date.strftime("%H:%M:%S")
    latest_questions = []
    api_backoff_time = 0
    deletion_watcher = None

    metasmoke_last_ping_time = datetime.now()
    not_privileged_warning = \
        "You are not a privileged user. Please see " \
        "[the privileges wiki page](https://charcoal-se.org/smokey/Privileges) for " \
        "information on what privileges are and what is expected of privileged users."

    experimental_reasons = {  # Don't widely report these
        "potentially bad keyword in answer",
        "potentially bad keyword in body",
        "potentially bad keyword in title",
        "potentially bad keyword in username",
        "potentially bad NS for domain in title",
        "potentially bad NS for domain in body",
        "potentially bad NS for domain in answer",
        "potentially bad ASN for hostname in title",
        "potentially bad ASN for hostname in body",
        "potentially bad ASN for hostname in answer",
        "potentially bad IP for hostname in title",
        "potentially bad IP for hostname in body",
        "potentially bad IP for hostname in answer",
        "potentially problematic NS configuration in title",
        "potentially problematic NS configuration in body",
        "potentially problematic NS configuration in answer",
        "toxic body detected",
        "toxic answer detected",
    }

    parser = HTMLParser()
    parser.unescape = unescape

    code_privileged_users = None

    # these are loaded in GlobalVars.reload()
    commit = None
    commit_with_author = None
    on_branch = None

    s = ""
    s_reverted = ""
    s_norestart = ""
    s_norestart2 = ""
    apiquota = -1
    bodyfetcher = None
    cookies = {}
    se_sites = []
    why_data = []
    notifications = []
    listen_to_these_if_edited = []
    multiple_reporters = []
    api_calls_per_site = {}
    reason_weights = {}
    metasmoke_ids = {}

    standby_message = ""
    standby_mode = False

    api_request_lock = threading.Lock()

    num_posts_scanned = 0
    post_scan_time = 0
    posts_scan_stats_lock = threading.Lock()

    config_parser = RawConfigParser()

    if os.path.isfile('config') and "pytest" not in sys.modules:
        config_parser.read('config')
        log('debug', "Configuration loaded from \"config\"")
    else:
        config_parser.read('config.ci')
        if "pytest" in sys.modules and os.path.isfile('config'):  # Another config found while running in pytest
            log('debug', "Running in pytest, force load config from \"config.ci\"")
        else:
            log('debug', "Configuration loaded from \"config.ci\"")

    config = config_parser["Config"]  # It's a collections.OrderedDict now

    site_id_dict = {}
    post_site_id_to_question = {}

    location = config.get("location", "Continuous Integration")

    metasmoke_ws = None
    metasmoke_down = False
    metasmoke_failures = 0  # Consecutive count, not cumulative

    chatexchange_u = config.get("ChatExchangeU")
    chatexchange_p = config.get("ChatExchangeP")

    metasmoke_host = config.get("metasmoke_host")
    metasmoke_key = config.get("metasmoke_key")
    metasmoke_ws_host = config.get("metasmoke_ws_host")

    git_name = config.get("git_username", "SmokeDetector")
    git_email = config.get("git_useremail", "smokey@erwaysoftware.com")

    github_username = config.get("github_username")
    github_password = config.get("github_password")

    perspective_key = config.get("perspective_key")

    flovis_host = config.get("flovis_host")
    flovis = None

    # Miscellaneous
    log_time_format = config.get("log_time_format", "%H:%M:%S")

    # environ_or_none replaced by os.environ.get (essentially dict.get)
    bot_name = os.environ.get("SMOKEDETECTOR_NAME", git_name)
    bot_repo_slug = os.environ.get("SMOKEDETECTOR_REPO", git_user_repo)
    bot_repository = "//github.com/{}".format(bot_repo_slug)
    chatmessage_prefix = "[{}]({})".format(bot_name, bot_repository)

    valid_content = """This is a totally valid post that should never be caught. Any blacklist or watchlist item that triggers on this item should be avoided. java.io.BbbCccDddException: nothing wrong found. class Safe { perfect valid code(int float &#%$*v a b c =+ /* - 0 1 2 3 456789.EFGQ} English 中文Français Español Português Italiano Deustch ~@#%*-_/'()?!:;" vvv kkk www sss ttt mmm absolute std::adjacent_find (power).each do |s| bbb end ert zal l gsopsq kdowhs@ xjwk* %_sooqmzb xjwpqpxnf.  Please don't blacklist disk-partition.com, it's a valid domain (though it also gets spammed rather frequently)."""  # noqa: E501

    @staticmethod
    def reload():
        GlobalVars.commit = commit = git_commit_info()

        GlobalVars.commit_with_author = "`{}` ({}: {})".format(
            commit.id, commit.author, commit.message)

        GlobalVars.on_branch = git_ref()
        GlobalVars.s = "[ {} ] SmokeDetector started at [rev {}]({}/commit/{}) (running on {}, Python {})".format(
            GlobalVars.chatmessage_prefix, GlobalVars.commit_with_author, GlobalVars.bot_repository,
            GlobalVars.commit.id, GlobalVars.location, platform.python_version())
        GlobalVars.s_reverted = \
            "[ {} ] SmokeDetector started in [reverted mode](" \
            "https://charcoal-se.org/smokey/SmokeDetector-Statuses#reverted-mode) " \
            "at [rev {}]({}/commit/{}) (running on {})".format(
                GlobalVars.chatmessage_prefix, GlobalVars.commit_with_author, GlobalVars.bot_repository,
                GlobalVars.commit.id, GlobalVars.location)
        GlobalVars.s_norestart = "[ {} ] Blacklists reloaded at [rev {}]({}/commit/{}) (running on {})".format(
            GlobalVars.chatmessage_prefix, GlobalVars.commit_with_author, GlobalVars.bot_repository,
            GlobalVars.commit.id, GlobalVars.location)
        GlobalVars.s_norestart2 = "[ {} ] FindSpam module reloaded at [rev {}]({}/commit/{}) (running on {})".format(
            GlobalVars.chatmessage_prefix, GlobalVars.commit_with_author, GlobalVars.bot_repository,
            GlobalVars.commit.id, GlobalVars.location)
        GlobalVars.standby_message = \
            "[ {} ] SmokeDetector started in [standby mode](" \
            "https://charcoal-se.org/smokey/SmokeDetector-Statuses#standby-mode) " \
            "at [rev {}]({}/commit/{}) (running on {})".format(
                GlobalVars.chatmessage_prefix, GlobalVars.commit_with_author, GlobalVars.bot_repository,
                GlobalVars.commit.id, GlobalVars.location)
        log('debug', "GlobalVars loaded")


GlobalVars.reload()
