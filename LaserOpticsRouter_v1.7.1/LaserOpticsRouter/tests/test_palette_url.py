"""Exercise the real palette URL handoff without requiring Fusion or Windows."""
import ast
import pathlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class WindowsPathWithoutIO(pathlib.PureWindowsPath):
    def resolve(self):
        # These fixtures are absolute; skip OS access on non-Windows runners.
        if not self.is_absolute():
            raise AssertionError("The Windows fixture must be absolute")
        return self


class PosixPathWithoutIO(pathlib.PurePosixPath):
    def resolve(self):
        if not self.is_absolute():
            raise AssertionError("The macOS fixture must be absolute")
        return self


class PaletteURLTests(unittest.TestCase):
    def palette_url(self, entry_point, path_class):
        source_path = pathlib.Path(__file__).resolve().parents[1] / "LaserOpticsRouter.py"
        source = ast.parse(source_path.read_text(encoding="utf-8"))
        function = next(node for node in source.body
                        if isinstance(node, ast.FunctionDef) and node.name == "show_palette")
        # Compile the original function body, not a copied version of its logic.
        code = compile(ast.Module(body=[function], type_ignores=[]), str(source_path), "exec")
        add = Mock(return_value=SimpleNamespace(incomingFromHTML=object(), closed=object()))
        namespace = dict(
            __file__=entry_point, pathlib=SimpleNamespace(Path=path_class),
            design=lambda: None, palette=lambda: None, PALETTE_ID="LaserOpticsRouterPalette",
            _ui=SimpleNamespace(palettes=SimpleNamespace(add=add)),
            listen=lambda event, handler: None, HTMLHandler=object, PaletteClosed=object,
        )
        exec(code, namespace)
        namespace["show_palette"]()
        add.assert_called_once()
        return add.call_args.args[2]

    def test_reported_windows_installation_path(self):
        entry = (r"C:\Users\Admin\AppData\Roaming\Autodesk\Autodesk Fusion 360\API\Scripts"
                 r"\LaserOpticsRouter_v1.0.0\LaserOpticsRouter\LaserOpticsRouter.py")
        expected = ("file:///C:/Users/Admin/AppData/Roaming/Autodesk/Autodesk%20Fusion%20360"
                    "/API/Scripts/LaserOpticsRouter_v1.0.0/LaserOpticsRouter/palette.html")
        self.assertEqual(self.palette_url(entry, WindowsPathWithoutIO), expected)

    def test_windows_reserved_characters_and_unicode(self):
        entry = r"C:\Users\Jörg\Optics #1 100%\LaserOpticsRouter\LaserOpticsRouter.py"
        expected = ("file:///C:/Users/J%C3%B6rg/Optics%20%231%20100%25"
                    "/LaserOpticsRouter/palette.html")
        self.assertEqual(self.palette_url(entry, WindowsPathWithoutIO), expected)

    def test_macos_installation_path(self):
        entry = ("/Users/admin/Library/Application Support/Autodesk/"
                 "LaserOpticsRouter/LaserOpticsRouter.py")
        expected = ("file:///Users/admin/Library/Application%20Support/Autodesk/"
                    "LaserOpticsRouter/palette.html")
        self.assertEqual(self.palette_url(entry, PosixPathWithoutIO), expected)


if __name__ == "__main__":
    unittest.main()
