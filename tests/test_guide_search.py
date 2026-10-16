from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.guide import filter_channels
from nostalgiabox.view import ChannelView
from tests.test_app import build_app, send


def type_query(app, value):
    send(app, Action.SEARCH)
    for char in value:
        app.handle_event(InputEvent(Action.TEXT, char))


def test_case_accents_numbers_and_word_search():
    rows = (ChannelView(2, 'Pokémon', 'The First Episode'), ChannelView(12, 'Arthur', 'Welcome'))
    assert filter_channels(rows, 'POKEMON first') == (rows[0],)
    assert filter_channels(rows, '02') == (rows[0],)
    assert filter_channels(rows, '12') == (rows[1],)
    assert filter_channels(rows, 'absent') == ()


def test_typing_shortcut_letters_filters_without_quitting(tmp_path):
    app, player, _ = build_app(tmp_path)
    app._running = True
    app.start()
    current = player.current
    type_query(app, 'qsf')
    assert app._running
    assert app.guide_query == 'qsf'
    assert app.snapshot().channels == ()
    send(app, Action.ENTER)
    assert player.current == current
    send(app, Action.BACKSPACE)
    assert app.guide_query == 'qs'
    send(app, Action.BACK)
    assert app.guide_query == '' and app.guide_open
    send(app, Action.BACK)
    assert not app.guide_open and app._running


def test_filtered_selection_tunes_correct_number(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    type_query(app, 'arthur')
    rows = app.snapshot().channels
    assert len(rows) == 1 and rows[0].number == 3
    send(app, Action.ENTER)
    assert app.lineup.current.number == 3
    assert not app.guide_open and app.guide_query == ''


def test_plain_letters_keep_viewing_shortcuts(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    app.handle_event(InputEvent(Action.TEXT, 'g'))
    assert app.guide_open
    app.handle_event(InputEvent(Action.TEXT, 'm'))
    assert app.muted
