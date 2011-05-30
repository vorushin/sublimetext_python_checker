from subprocess import Popen, PIPE

import sublime
import sublime_plugin


CHECKERS = ['/Users/vorushin/.virtualenvs/answers/bin/pep8',
            '/Users/vorushin/.virtualenvs/answers/bin/pyflakes']


global view_messages
view_messages = {}


class PythonCheckerCommand(sublime_plugin.EventListener):
    def on_load(self, view):
        check_and_mark(view)

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

    for checker in CHECKERS:
        p = Popen([checker, view.file_name()], stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate(None)
        if stdout:
            print stdout
        if stderr:
            print stderr
        messages += parse_messages(stdout)
        messages += parse_messages(stderr)

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
    messages = []
    for i, line in enumerate(checker_output.splitlines()):
        first_colon = line.find(':')
        if first_colon == -1:
            continue
        second_colon = line.find(':', first_colon + 1)
        third_colon = line.find(':', second_colon + 1)
        try:
            lineno = int(line[first_colon + 1:second_colon]) - 1
            if third_colon != -1:
                col = int(line[second_colon + 1:third_colon]) - 1
                text = line[third_colon + 1:]
            else:
                col = None
                text = line[second_colon + 1:]
            text = text.strip()
            if text == 'invalid syntax':
                col = invalid_syntax_col(checker_output, i)
        except ValueError:
            continue

        messages.append({'lineno': lineno, 'col': col, 'text': text})

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
