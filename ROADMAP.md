# OpenRegie – Roadmap

*Profi-Regie für alle. Einfach live.* Eigene Sendezentrale für CachyOS. OBS läuft unsichtbar als Motor
im Hintergrund und wird über den OBS-WebSocket gesteuert. Alle Grafiken im Stream kommen von Overlays.uno.

Grundregeln für alle Builds: große Knöpfe, einfacher Klick, kein Ziehen, kein Rechtsklick,
keine Tastenkombination als einziger Weg, wenig Tippen, alle Texte auf Deutsch.
**Ein Regiepult friert nie ein:** nichts, was warten kann, läuft im Haupt-Thread der Oberfläche.
OpenRegie wird Open Source: keine Geheimnisse im Code, Zugangsdaten nur im Passwortspeicher des Systems.

## Version 1

### Build 1.0 – Motortest (intern) · *fertig (10.11.2026)*
- [x] Eigenes Programmfenster im Regiepult-Look
- [x] Verbindung zu OBS über WebSocket mit gut sichtbarer Statusanzeige
- [x] Live-Vorschau des Sendebilds (Einzelbilder über den WebSocket statt virtueller Kamera)
- [x] Rotes „On Air“-Licht, wenn OBS live streamt
- [x] Countdown als eigene lokale Seite *(in Build 1.1 wieder entfernt – Countdown kommt jetzt von Uno)*
- [x] Build-Anzeige unten links (liest die Nummer automatisch aus der Datei `VERSION`)
- [x] Startmenü-Eintrag

### Build 1.1 – erste Version zum Streamen · *fertig (14.11.2026), Test-Streams stehen aus*
- [x] Umbenennung in **OpenRegie** mit Untertitel „Profi-Regie für alle. Einfach live.“
- [x] Ladebildschirm beim Start
- [x] Build-Anzeige als dezentes Wasserzeichen unten links („Vorabversion · Build 1.1“)
- [x] OBS startet unsichtbar mit (nur Symbol in der Taskleiste), verbindet sich von selbst,
      lädt die richtige Szenensammlung und wird beim Schließen mit beendet (Nachfrage, wenn live)
- [x] Klare Meldungen, wenn OBS nicht startet, abstürzt oder sich nicht meldet
- [x] Overlays.uno-Anbindung: Uno-Projekt per Zwischenablage einfügen (sicher gespeichert)
  - [x] Einfache Liste aller Uno-Overlays mit Tally-Licht
  - [x] Ein- und Ausblenden per Klick
  - [x] Texte direkt ändern (z. B. Bauchbinde, News-Ticker)
  - [x] Neue Uno-Overlays erscheinen mit „Liste neu laden“
- [x] Eigener Countdown entfernt – Uhr und Countdown sind normale Uno-Overlays
- [x] „Mit Twitch anmelden“ (offizielle Anmeldung ohne geheimen Schlüssel) und Streamtitel ändern
- [x] Rotes On-Air-Licht (aus Build 1.0)
- [ ] Ein bis zwei Test-Streams durch Kevin
- [x] Einzel-Unos (z. B. „Countdown | Circles“) einfügen – Korrektur nach erstem Test
- [ ] Prüfung mit einem echten Uno-Projekt mit mehreren Overlays (bisher nur Einzel-Uno echt geprüft)
- [x] Einzel-Uno: Steuerung mit echter Adresse geklärt und eingebaut (Ein/Aus, Tally, Countdown, Dauer, Texte)
- [x] Neues Aussehen nach dem Entwurf „Hauptfenster“ (Bibliothek mit Kacheln, Lampen, Live-Bild, Ausgewählt)
- [x] Neustart mit eingefügtem Einzel-Uno repariert, Meldungen sauber getrennt
- [x] Grundregel „Ein Regiepult friert nie ein“: Zeitlimit für Uno, Passwortspeicher im Hintergrund
- [x] Uno-Quellen automatisch in jeder OBS-Szene und immer ganz oben; alte Countdown-Quelle entfernt
- [x] Ausblenden über den Uno-Schalter „ShowOverlay“: Countdown verschwindet sanft in der Mitte
- [x] Countdown-Zeit direkt eintippen: Klick auf die große Zeit, z. B. „5:00“ tippen, Enter übernimmt,
      Esc bricht ab. Gesperrt, solange der Countdown im Stream ist (kurzer Hinweis, der von selbst
      verschwindet). Falsche Eingaben bekommen einen verständlichen Hinweis. Die Knöpfe „±1/±10 Min“
      bleiben und rechnen mit derselben Zeit weiter. *(16.11.2026)*
- [x] Countdown-Zeit eintippen mit dem echten Uno geprüft (13 von 13, 16.11.2026)
- [x] Countdown-Zeit ohne Enter/Esc: große Knöpfe ✓ „Übernehmen“ und ✕ „Abbrechen“ neben dem Feld.
      Ein Klick darauf bricht nicht ab, falsche Eingaben werden wie bei Enter abgefangen, Enter und Esc
      gehen weiter. Mit dem echten Uno geprüft (20 von 20). *(16.11.2026)*
- [ ] Twitch-App anlegen und Client-ID eintragen

### Build 1.2 – Shots & Wenn-dann · *fertig (22.11.2026)*
Vorbild für die Shots: Telestream Wirecast. Ab diesem Build streamt Kevin regulär.

**Teil A – Shots und Quellen**
- [x] Alle Szenen aus OBS als große Kacheln mit kleinem Vorschaubild unten unter dem Live-Bild (wie Wirecast)
- [x] Ein Klick auf einen Shot schaltet ihn sofort live (roter Rahmen = live)
- [x] „✎“ (Bearbeiten): Klick öffnet den Shot rechts zum Bearbeiten, ohne ihn live zu schalten
- [x] Quellen eines Shots als Kacheln mit Vorschaubild; Shots und Quellen umbenennen
- [x] „+ Shot hinzufügen“: Zweck wählen (Kamera, Spiel, Reactions, Bildschirm, Bild), passendes Layout
      kommt gleich mit (z. B. Reactions: Video groß, Kamera klein rechts unten) – Zweck und Layout sind Pflicht
- [x] „+ Quelle hinzufügen“ in einen Shot (Kamera, Spiel, Bildschirm, Bild) – OBS muss nie geöffnet werden
- [x] Es gibt nur eine Kamera-Quelle für alle Shots (eine Kamera lässt sich nur einmal öffnen)
- [x] Löschen gibt alles in OBS frei: Quellen, die in keinem Shot mehr vorkommen, werden ganz entfernt
- [x] Vorschaubilder nur, solange die Shot-Leiste (bzw. das Bearbeiten) zu sehen ist, alle 5 Sekunden,
      immer nur ein Bild gleichzeitig; zugeklappt (▾) oder Fenster minimiert: keine einzige Anfrage
- [x] Die Oberfläche spricht nur über die Motor-Schicht mit OBS (ein Test wacht darüber)

**Teil B – Wenn-dann-Fenster**
- [x] Knopf „⚡ Wenn-dann“ oben öffnet ein kleines Fenster: links „Wenn …“, rechts „… dann“
- [x] Große Auswahllisten mit Gruppen (Stream, Szenen, Overlays, Ton, Zeitplan), ganz ohne Tippen
- [x] Regeln anlegen, bearbeiten, an-/ausschalten, löschen; gespeichert in ~/.local/share/openregie/
- [x] Register für Auslöser und Aktionen – neue (Build 1.3) lassen sich einfach eintragen
- [x] Auslöser: Stream startet, Stream endet, Shot geht live, Startzeit laut Zeitplan
- [x] Aktionen: Shot live schalten, Overlay ein-/ausblenden, Ton stumm/an
- [x] Automatik läuft nur mit mindestens einer aktiven Regel – sonst keine Pegelmessung, kein Takt, keine Abfrage
- [x] Schutz vor Endlosschleifen (eine Regel löst höchstens alle 2 Sekunden aus)
- [x] Zeitplan: Tage und Uhrzeiten mit großen Knöpfen eintragen; „Nächster Stream: Fr 19:00“ oben im Regiepult
- [x] Test mit echtem OBS 33.0.3 (`werkzeuge/test_build_1_2_mit_echtem_obs.py`): 12 Läufe, je 37 von 37
- [x] Rechenlast gemessen: Leerlauf, Shot-Leiste offen, Regel aktiv – jeweils unter 1 % eines Kerns

### Build 1.2.1 – Korrektur: jede Kachel gehört fest zu ihrer Szene · *fertig (22.11.2026)*
Fehlerbericht: Klick auf „Bildschirmaufnahme“ zeigte nur den Countdown.
- [x] Ursache gefunden: Die Kachel schaltete die richtige Szene – aber die Bildschirmaufnahme lieferte
      kein Bild (Bildschirm im System-Fenster nicht freigegeben), und das Uno-Overlay „Countdown“ liegt
      in jeder Szene ganz oben. Zu sehen war darum nur der Countdown.
- [x] Jede Kachel ist fest mit der eindeutigen OBS-Kennung (UUID) ihrer Szene verknüpft – nie mit der
      Position in der Liste. Umschalten, Vorschaubilder und das große Live-Bild laufen über diese Kennung.
- [x] Stimmt auch nach Umbenennen (auch der Live-Szene – sofort), Neuanlegen, Umsortieren und wenn zwei
      Szenen die Namen tauschen. Wenn-dann-Regeln ziehen den neuen Namen eines Shots mit.
- [x] „⚠ Kein Bild“ auf der Kachel, wenn eine Aufnahme nichts liefert; beim Bearbeiten der Knopf
      „Bildschirm neu auswählen“ (öffnet das Auswahlfenster des Systems noch einmal)
- [x] Geprüft: Unit-Tests je 12×, echtes OBS 33.0.3 (`werkzeuge/test_zuordnung_mit_echtem_obs.py`,
      5 Szenen) 12 Läufe
- [x] ~~Frischen Screenshot fürs README machen~~ → verschoben nach Build 1.2.2

### Build 1.2.2 – Countdown-Korrektur & „Shot hinzufügen“ als eigenes Fenster · *fertig (23.11.2026)*
Fehlerbericht: Countdown steht auf 00:00 und lässt sich nicht bedienen.
- [x] Ursache gefunden: Der Uno-Countdown lief seit 16.11. durch und war abgelaufen; „Start“ war dann
      grau, nur „Zurück“ half – ohne Hinweis. (Nicht durch die Szenen-Korrektur aus 1.2.1.)
- [x] Abgelaufen: Knopf „▶ Neu starten“ beginnt mit einem Klick von vorn
- [x] Countdown-Befehle gehen nacheinander zu Uno – keiner überholt den anderen
- [x] Einblenden nimmt Inhalt und Zahlen wieder mit (Uno meldet im Bauplan jetzt alle Teile als „aus“)
- [x] „Shot hinzufügen“ / „Quelle hinzufügen“ als eigenes Fenster (wie „Add Input“ bei vMix), sperrt das
      Regiepult, solange es offen ist; Auswahl und Optionen unverändert; rechts bleibt der Countdown
- [x] Geprüft: Unit-Tests mehrfach, echtes Uno (28/28, Regiepult 48/48), echtes OBS 33.0.3 (127/127,
      Szenen-Zuordnung 20/20)
- [x] Frische Screenshots im README (Regiepult und Fenster „Shot hinzufügen“, als Pre-Alpha markiert)
- [ ] Ein Test-Stream mit Countdown durch Kevin

### Build 1.2.3 – Stream direkt aus OpenRegie starten · *fertig (27.11.2026)*
- [x] Großer Knopf oben neben ON AIR: „▶ Stream starten“ (ohne Nachfrage) / „■ Stream beenden“
      (mit Nachfrage „Stream wirklich beenden?“, vorgewählt ist „Weiter streamen“)
- [x] Zwischenzustand „Verbinde …“ / „Stoppe …“: Knopf gesperrt, kein Doppelklick
- [x] Knopf und ON AIR zeigen immer den echten Zustand von OBS – auch bei Start/Stopp in OBS selbst
- [x] ON AIR leuchtet nur rot, wenn OBS wirklich live ist; „VERBINDE …“ (orange) beim Verbinden und wenn
      die Verbindung zu Twitch mitten im Stream wegbricht
- [x] Vor dem Start prüft OpenRegie, ob in OBS ein Stream-Key eingetragen ist (sonst hängt das echte OBS
      und zeigt ein Fehlerfenster) – verständliche Meldung mit Knopf „Verstanden“
- [x] Verständliche Meldungen bei Fehlstart (Server nicht erreichbar), Zeitlimit (30 s) und Ablehnung
- [x] Neue Zwischenschicht `obs/stream.py` – die Oberfläche spricht weiter nie direkt mit OBS
- [x] Wenn-dann „Stream startet/endet“ nur bei echten Übergängen (nicht nach einem Wackler, nicht bei
      einem Fehlstart, nicht nur weil OBS kurz weg war)
- [x] Kopfleiste: Knopf, ON AIR und Uhr fest breit – nichts rutscht beim Umschalten unter dem Zeiger weg
- [x] Geprüft: Unit-Tests 3× je 315/315, echtes OBS 33.0.3 (`werkzeuge/test_stream_mit_echtem_obs.py`)
      3× je 73/73 ohne OBS-Fehlerfenster, echtes Uno 28/28
- [ ] Frischer Screenshot fürs README
- [ ] Ein echter Test-Stream zu Twitch mit dem neuen Knopf durch Kevin

### Build 1.3
- [ ] Lautstärke-Auslöser: Spricht Kevin (Pegel über Schwelle), schaltet OpenRegie auf die Kamera um;
      Schwellwert einstellbar. Pegelmessung nur, solange so eine Regel aktiv ist.
- [ ] Spiel-Erkennung: Bei aktivem Spiel-Shot die Kamera klein einblenden statt umzuschalten
- [ ] Performance-Test mit aktiver Lautstärke-Regel (Rechenlast vorher und nachher)
- [ ] Kamera auswählen, wenn mehrere angeschlossen sind (jetzt: die erste)
- [ ] Wählbar, in welchen Shots ein Uno-Overlay liegt (bisher automatisch in jedem – z. B. Countdown
      nur im Shot „Countdown“) *(aus dem Fehlerbericht zu 1.2.1)*
- [ ] Overlays direkt bearbeiten: über den Knopf „Bearbeiten“ (einfacher Klick) und zusätzlich per
      Doppelklick in der Vorschau *(war für 1.2 geplant, verschoben)*

### Build 1.7
- [ ] Ordner für Overlays (Bibliothek) und Suche
- [ ] Twitch-Kategorie ändern

## Später
- [ ] Studio-Modus: Vorschau-Bild neben dem Live-Bild mit Knopf „Los“ (wie Wirecast)
- [ ] Stream Dock

## Technik in Kürze
- `openregie/obs/` – die Motor-Schicht: Verbindung, Vorschau, OBS unsichtbar starten/beenden, Stream
  starten/beenden (`stream.py`),
  Shots und Quellen (`quellen.py`), Zwecke und Layouts (`vorlagen.py`)
- `openregie/automatik/` – Wenn-dann-Regeln, Register der Auslöser/Aktionen, Zeitplan
- `openregie/uno/` – Overlays.uno: Befehle an die API-Adresse eines Uno-Projekts
- `openregie/twitch/` – Twitch-Anmeldung (Device Code Flow, nur öffentliche Client-ID) und Titel
- `openregie/geheimspeicher.py` – Zugangsdaten im Passwortspeicher des Systems (`secret-tool`)
- `openregie/oberflaeche/` – das Regiepult
