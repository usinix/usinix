# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Pauses the viewport effects while the view is being navigated.

Ambient occlusion has to be recomputed for every frame the camera moves, and
on a heavy model or a modest GPU that is what makes orbiting sluggish.  So
while the camera of a view moves the effects of that view are switched off,
and switched back on a moment after it stops ("adaptive degradation" in
other CAD programs).

* Movement is detected with a sensor on the camera node: it fires whatever
  moves the camera (mouse, SpaceMouse, navigation cube, animations) and does
  not fire when something else changes -- dragging a light keeps its shadows
  live.
* Pausing only flips a switch (ambient occlusion) and the ``isActive`` flag of
  the shadow group: nothing is rebuilt, so resuming is instant.
"""
from pivy import coin

from . import view_utils

MODE_FULL = 'Keep effects'
MODE_NO_AO = 'Pause ambient occlusion'
MODE_NONE = 'Pause all effects'
MODES = [MODE_FULL, MODE_NO_AO, MODE_NONE]
DEFAULT_MODE = MODE_NONE
DEFAULT_DELAY_MS = 250

_states = {}        # address of a view's scene graph -> _ViewState
_hold = 0           # > 0: something (e.g. a turntable) wants the effects kept on


class _ViewState:
    def __init__(self, parent):
        from PySide import QtCore
        self.mode = DEFAULT_MODE
        self.delay = DEFAULT_DELAY_MS
        self.paused = False
        self.ao_switch = None
        self.shadow_group = None
        self.camera_address = 0
        self.triggers = 0       # camera movements seen (diagnostics)
        self.pose = None
        self.sensor = coin.SoNodeSensor(self._camera_changed, None)
        self.timer = QtCore.QTimer(parent)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._stopped)

    # ------------------------------------------------------------- sensing
    def watch(self, camera):
        address = view_utils.node_address(camera)
        if address == self.camera_address:
            return
        self.sensor.detach()
        self.camera_address = address
        self.pose = self._pose(camera)
        if camera is not None:
            self.sensor.attach(camera)

    @staticmethod
    def _pose(camera):
        """What navigation changes.  The clipping planes are left out: FreeCAD
        re-fits them whenever the model changes, which is not navigation."""
        if camera is None:
            return None
        pose = list(camera.position.getValue().getValue())
        pose += list(camera.orientation.getValue().getValue())
        for name in ('height', 'heightAngle'):
            field = camera.getField(name)
            if field is not None:
                pose.append(coin.cast(field, 'SoSFFloat').getValue())
        return tuple(round(value, 6) for value in pose)

    def _camera_changed(self, data, sensor):
        pose = self._pose(self.sensor.getAttachedNode())
        if pose == self.pose:
            return
        self.pose = pose
        self.triggers += 1
        if self.mode == MODE_FULL or _hold > 0:
            return
        if not self._has_effects():
            return
        self.timer.start(max(int(self.delay), 0))
        if not self.paused:
            self.paused = True
            self.apply()

    def _stopped(self):
        if self.paused:
            self.paused = False
            self.apply()

    # ------------------------------------------------------------ applying
    def _has_effects(self):
        return self.ao_switch is not None or self.shadow_group is not None

    def apply(self):
        """Put the effect nodes in the state ``paused`` and ``mode`` call for."""
        ao_on = not (self.paused and self.mode in (MODE_NO_AO, MODE_NONE))
        shadows_on = not (self.paused and self.mode == MODE_NONE)
        if self.ao_switch is not None:
            wanted = coin.SO_SWITCH_ALL if ao_on else coin.SO_SWITCH_NONE
            if self.ao_switch.whichChild.getValue() != wanted:
                self.ao_switch.whichChild.setValue(wanted)
        if self.shadow_group is not None:
            field = self.shadow_group.getField('isActive')
            if field is not None:
                field = coin.cast(field, 'SoSFBool')
                if bool(field.getValue()) != shadows_on:
                    field.setValue(shadows_on)

    def set_nodes(self, ao_switch, shadow_group):
        """Remember the effect nodes, keeping them alive for as long as we do.

        A Python wrapper is not always a reference to its Coin node (see
        view_utils.new_node): without the explicit ref a node taken out of the
        scene graph would be freed under our feet.
        """
        for name, node in (('ao_switch', ao_switch), ('shadow_group', shadow_group)):
            old = getattr(self, name)
            if view_utils.same_node(old, node):
                continue
            if node is not None:
                node.ref()
            setattr(self, name, node)
            if old is not None:
                old.unref()

    def release(self):
        """Forget everything; the view is gone, there is nothing to restore."""
        self.timer.stop()
        self.sensor.detach()
        self.camera_address = 0
        self.paused = False
        self.set_nodes(None, None)


def update(view, mode, delay, ao_switch, shadow_group, parent):
    """Tell the navigation watcher what a view contains now (called at every sync)."""
    key = view_utils.node_address(view.getSceneGraph())
    state = _states.get(key)
    if state is None:
        if ao_switch is None and shadow_group is None:
            return
        state = _states[key] = _ViewState(parent)
    state.mode = mode if mode in MODES else DEFAULT_MODE
    state.delay = delay
    state.set_nodes(ao_switch, shadow_group)
    state.watch(view.getCameraNode())
    if state.mode == MODE_FULL:
        state.paused = False
    state.apply()


def forget_except(views):
    """Drop the state of the views that no longer exist."""
    alive = set()
    for view in views:
        try:
            alive.add(view_utils.node_address(view.getSceneGraph()))
        except Exception:
            pass
    for key in list(_states):
        if key not in alive:
            _states.pop(key).release()


def hold(on):
    """Keep the effects on although the camera moves (used by the turntable)."""
    global _hold
    _hold = max(0, _hold + (1 if on else -1))
    if _hold:
        for state in _states.values():
            if state.paused:
                state.timer.stop()
                state.paused = False
                state.apply()


def is_paused(view):
    state = _states.get(view_utils.node_address(view.getSceneGraph()))
    return bool(state and state.paused)
