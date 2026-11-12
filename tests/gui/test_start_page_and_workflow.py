"""Start Page, workflow strip, empty states and About dialog (the professional-shell package)."""
import os

os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")


# ------------------------------------------------------------------ pure logic (no Qt)
def test_stage_states_follow_the_facts():
    from core.workflow_status import (ACTIVE, ERROR, IDLE, OK, RESULTS, RUN, SETUP, VALIDATE, WARN, WorkflowFacts,
                                      stage_states)
    from ui.shell.workflow_strip import stage_for_page
    s = stage_states(WorkflowFacts())
    assert (s[SETUP].state, s[VALIDATE].state, s[RUN].state, s[RESULTS].state) == (OK, IDLE, IDLE, IDLE)
    s = stage_states(WorkflowFacts(validated=True, errors=2, warnings=1))
    assert s[VALIDATE].state == ERROR and s[VALIDATE].badge == "2"
    s = stage_states(WorkflowFacts(validated=True, warnings=3))
    assert s[VALIDATE].state == WARN and s[VALIDATE].badge == "3"
    s = stage_states(WorkflowFacts(validated=True, running=1, queued=2))
    assert s[RUN].state == ACTIVE and "1 running" in s[RUN].badge
    s = stage_states(WorkflowFacts(completed=2, results_loaded=1))
    assert s[RESULTS].state == OK and s[RESULTS].badge == "3"
    assert stage_for_page("runner") == RUN and stage_for_page("results") == RESULTS
    assert stage_for_page("imt") == SETUP


def test_apply_template_sets_system_link_and_imt_keys():
    from core.scenario_templates import TEMPLATES, apply_template, find_template

    class Var:
        def __init__(self):
            self.value = None

        def set(self, v):
            self.value = v

    class State:
        def __init__(self):
            self.vars = {}

        def get(self, k):
            return self.vars.setdefault(k, Var())

    assert len(TEMPLATES) == 7 and len({t.key for t in TEMPLATES}) == 7
    tpl = find_template("s3_sss")
    system, link, imt = Var(), Var(), State()
    apply_template(tpl, system_var=system, link_var=link, imt_state=imt)
    assert (system.value, link.value) == ("SINGLE_SPACE_STATION", "UPLINK")
    assert imt.vars["topo_type"].value == "MACROCELL" and imt.vars["macro_intersite"].value == "1500"
    assert find_template("nope") is None


# ------------------------------------------------------------------ widgets
def test_start_page_tab_and_template_card(win):
    page = win.start_page
    assert win.doc_tabs.tabText(win.doc_tabs.indexOf(page)) == "Start"
    chosen = []
    page.template_chosen.connect(chosen.append)
    page._cards[1].chosen.emit(page._cards[1].template.key)
    assert chosen == ["s2_macro_ses"]
    page.refresh_recent()
    assert page.recent_list.isVisibleTo(page) != page.lbl_no_recent.isVisibleTo(page)


def test_template_applies_to_window_state(win):
    from core.scenario_templates import find_template
    tpl = find_template("s5_haps")
    win._on_template_chosen(tpl.key)
    assert win.state_model.var_system.get() == "HAPS"
    assert win.state_model.var_imt_link.get() == "DOWNLINK"
    assert win.tab_imt.state.get("topo_type").get() == "MACROCELL"
    assert win.doc_tabs.currentWidget() is win.tab_preview


def test_workflow_strip_reflects_validation(win):
    from core.workflow_status import VALIDATE, RUN, RESULTS
    from core.validation import Issue, ERROR
    strip = win.workflow_strip
    win.problems_panel.set_issues([Issue(ERROR, "imt", "Frequency", "bad")])
    win._validated = True
    win._refresh_workflow()
    assert strip.state_of(VALIDATE).state == "error" and strip.state_of(VALIDATE).badge == "1"
    assert win.problems_panel.empty_state.widget.isHidden()
    win.problems_panel.set_issues([])
    win._refresh_workflow()
    assert strip.state_of(VALIDATE).state == "ok"
    assert not win.problems_panel.empty_state.widget.isHidden()
    win._switch_page("runner", "Execution Engine")
    assert strip._buttons[RUN].property("current") is True
    win._switch_page("results", "Analysis & Results")
    assert strip._buttons[RESULTS].property("current") is True
    assert strip._buttons[RUN].property("current") is False


def test_new_project_forgets_previous_validation(win):
    from core.workflow_status import VALIDATE
    win.problems_panel.set_issues([])
    win._validated = True
    win._refresh_workflow()
    assert win.workflow_strip.state_of(VALIDATE).state == "ok"
    assert win.new_project()
    assert win.workflow_strip.state_of(VALIDATE).state == "idle"


def test_stage_click_jumps(win):
    win.workflow_strip.stage_clicked.emit("results")
    assert win.doc_tabs.currentWidget() is win.tab_results
    win.workflow_strip.stage_clicked.emit("setup")
    assert win.current_key == "general"


def test_empty_states_and_about(win):
    from PySide6.QtGui import QGuiApplication
    from ui.shell.about_dialog import AboutDialog, build_lines
    assert win.jobs_panel.empty_state.widget.headline.text() == "No simulations in the queue"
    assert win.tab_results.empty_state.isVisibleTo(win.tab_results) == (win.tab_results.lb_dirs.count() == 0)
    lines = build_lines()
    assert any("Python" in ln for ln in lines) and lines[0]
    dlg = AboutDialog(win, tokens=win.tk, lines=["Version test", "Python x"])
    dlg.copy_build_info()
    assert QGuiApplication.clipboard().text().startswith("Version test")
    dlg.deleteLater()


def test_every_learn_link_is_resolvable():
    from ui.shell.start_page import LEARN_LINKS, find_learn_link
    assert {link.kind for link in LEARN_LINKS} <= {"help", "handbook", "manual", "url"}
    assert all(find_learn_link(link.key) is link for link in LEARN_LINKS)
    assert all(link.target for link in LEARN_LINKS if link.kind in ("manual", "url"))


def test_start_page_preference_roundtrip():
    from ui.shell.start_page import set_start_page_enabled, start_page_enabled
    before = start_page_enabled()
    try:
        set_start_page_enabled(False)
        assert start_page_enabled() is False
        set_start_page_enabled(True)
        assert start_page_enabled() is True
    finally:
        set_start_page_enabled(before)
