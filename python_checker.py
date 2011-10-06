import re
import signal
from subprocess import Popen, PIPE

import sublime
import sublime_plugin

try:
    from local_settings import CHECKERS
except ImportError as e:
    print '''
Please create file local_settings.py in the same directory with
python_checker.py. Add to local_settings.py list of your checkers.

Example:

CHECKERS = [('/Users/vorushin/.virtualenvs/checkers/bin/pep8', []),
            ('/Users/vorushin/.virtualenvs/checkers/bin/pyflakes', [])]

First parameter is path to command, second - optional list of arguments.
If you want to disable line length checking in pep8, set second parameter
to ['--ignore=E501'].
'''
    raise e


global view_messages
view_messages = {}


class PythonCheckerCommand(sublime_plugin.EventListener):
    def on_activated(self, view):
        signal.signal(signal.SIGALRM, lambda s, f: check_and_mark(view))
        signal.alarm(1)

    def on_deactivated(self, view):
        signal.alarm(0)

    def on_post_save(self, view):
        check_and_mark(view)

    def on_selection_modified(self, view):
        global view_messages
        lineno = view.rowcol(view.sel()[0].end())[0]
        if view.id() in view_messages and lineno in view_messages[view.id()]:
            view.set_status('python_checker', view_messages[view.id()][lineno])
        else:
            view.erase_status('python_checker')


def check_and_mark(view):
    if not 'python' in view.settings().get('syntax').lower():
        return

    messages = []

    for checker, args in CHECKERS:
        try:
            p = Popen([checker, view.file_name()] + args, stdout=PIPE,
                stderr=PIPE)
            stdout, stderr = p.communicate(None)
            if stdout:
                print stdout
            if stderr:
                print stderr
            messages += parse_messages(stdout)
            messages += parse_messages(stderr)
        except OSError:
            print "Checker could not be found:", checker

    outlines = [view.full_line(view.text_point(m['lineno'], 0)) \
                for m in messages]
    view.erase_regions('python_checker_outlines')
    view.add_regions('python_checker_outlines',
        outlines,
        'keyword',
        sublime.DRAW_EMPTY | sublime.DRAW_OUTLINED)

    underlines = []
    for m in messages:
        if m['col']:
            a = view.text_point(m['lineno'], m['col'])
            underlines.append(sublime.Region(a, a))

    view.erase_regions('python_checker_underlines')
    view.add_regions('python_checker_underlines',
        underlines,
        'keyword',
        sublime.DRAW_EMPTY_AS_OVERWRITE | sublime.DRAW_OUTLINED)

    line_messages = {}
    for m in (m for m in messages if m['text']):
        if m['lineno'] in line_messages:
            line_messages[m['lineno']] += ';' + m['text']
        else:
            line_messages[m['lineno']] = m['text']

    global view_messages
    view_messages[view.id()] = line_messages


def parse_messages(checker_output):
    '''
    Examples of lines in checker_output

    pep8 on *nix
    /Users/vorushin/Python/answers/urls.py:24:80: E501 line too long \
    (96 characters)

    pyflakes on *nix
    /Users/vorushin/Python/answers/urls.py:4: 'from django.conf.urls.defaults \
    import *' used; unable to detect undefined names

    pyflakes, invalid syntax message (3 lines)
    /Users/vorushin/Python/answers/urls.py:14: invalid syntax
    dict_test = {key: value for (key, value) in [('one', 1), ('two': 2)]}
                                                                    ^

    pyflakes on Windows
    c:\Python26\Scripts\pildriver.py:208: 'ImageFilter' imported but unused
    '''

    pep8_re = re.compile(r'.*:(\d+):(\d+):\s+(.*)')
    pyflakes_re = re.compile(r'.*:(\d+):\s+(.*)')

    messages = []
    for i, line in enumerate(checker_output.splitlines()):
        if pep8_re.match(line):
            lineno, col, text = pep8_re.match(line).groups()
        elif pyflakes_re.match(line):
            lineno, text = pyflakes_re.match(line).groups()
            col = 1
            if text == 'invalid syntax':
                col = invalid_syntax_col(checker_output, i)
        else:
            continue
        messages.append({'lineno': int(lineno) - 1,
                         'col': int(col) - 1,
                         'text': text})

    return messages


def invalid_syntax_col(checker_output, line_index):
    '''
    For error messages like this:

    /Users/vorushin/Python/answers/urls.py:14: invalid syntax
    dict_test = {key: value for (key, value) in [('one', 1), ('two': 2)]}
                                                                    ^
    '''
    for line in checker_output.splitlines()[line_index + 1:]:
        if line.startswith(' ') and line.find('^') != -1:
            return line.find('^')
