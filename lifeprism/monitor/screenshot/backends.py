from pathlib import Path


class MSSCaptureBackend:
    """使用 mss 执行真实截图，延迟导入以避免测试环境硬依赖。"""

    def capture_to_file(self, target_path: Path) -> None:
        import mss
        import mss.tools

        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
            mss.tools.to_png(shot.rgb, shot.size, output=str(target_path))


class PynputInputListener:
    """使用 pynput 监听键盘鼠标事件，延迟导入以避免测试环境硬依赖。"""

    def __init__(self, tracker) -> None:
        self.tracker = tracker
        self._keyboard_listener = None
        self._mouse_listener = None

    def start(self) -> None:
        from pynput import keyboard, mouse

        def on_press(key) -> None:
            try:
                key_name = key.char or str(key).replace("Key.", "")
            except AttributeError:
                key_name = str(key).replace("Key.", "")
            self.tracker.record_keyboard_event(key_name)

        def on_move(x, y) -> None:
            self.tracker.record_mouse_event()

        def on_click(x, y, button, pressed) -> None:
            if pressed:
                self.tracker.record_mouse_event()

        self._keyboard_listener = keyboard.Listener(on_press=on_press)
        self._mouse_listener = mouse.Listener(
            on_move=on_move,
            on_click=on_click,
        )
        self._keyboard_listener.start()
        self._mouse_listener.start()

    def stop(self) -> None:
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
