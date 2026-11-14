"""Prüft einstellungen.toml und die Build-Anzeige."""

import unittest

from openregie import einstellungen


class EinstellungenTest(unittest.TestCase):
    def test_alles_vorhanden(self):
        E = einstellungen.lade()
        self.assertTrue(E.farben.hintergrund.startswith("#"))
        self.assertEqual(einstellungen.build_anzeige(E), "OpenRegie · Vorabversion · Build " + einstellungen.build_nummer())

    def test_fehlender_eintrag(self):
        E = einstellungen.lade()
        with self.assertRaises(einstellungen.EinstellungsFehler) as f:
            E.farben.gibtsnicht
        self.assertIn("[farben]", str(f.exception))

    def test_kaputte_datei(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as ordner:
            p = pathlib.Path(ordner) / "einstellungen.toml"
            p.write_text('[farben]\nhintergrund = "#123\n', encoding="utf-8")
            with self.assertRaises(einstellungen.EinstellungsFehler) as f:
                einstellungen.lade(p)
            self.assertIn("Zeile 2", str(f.exception))

    def test_alle_farben_gueltig(self):
        import re
        E = einstellungen.lade()
        for name, wert in E.farben.als_dict().items():
            self.assertRegex(wert, r"^#[0-9A-Fa-f]{6}$", name)


if __name__ == "__main__":
    unittest.main()
